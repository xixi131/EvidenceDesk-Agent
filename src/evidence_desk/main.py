"""FastAPI 应用入口（组合根）。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import SecretStr

from evidence_desk.api.exception_handlers import register_exception_handlers
from evidence_desk.api.middleware.request_context import request_context_middleware
from evidence_desk.api.routers.agent import router as agent_router
from evidence_desk.api.routers.chat import router as chat_router
from evidence_desk.api.routers.health import router as health_router
from evidence_desk.application.chat_service import ChatService
from evidence_desk.application.rag_answer_service import RagAnswerService
from evidence_desk.application.readiness import ReadinessService
from evidence_desk.core.config import get_settings
from evidence_desk.core.logging import configure_logging
from evidence_desk.infrastructure.readiness import check_dependencies

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """在服务启动时装配一次重量级依赖，关闭时释放连接。

    Embedding 模型加载和 Weaviate 连接都很昂贵，只在真正启动服务时做一次，
    并把成品放进 app.state 供各请求复用。这些 import 放在函数内部，
    避免仅仅「导入本模块」（例如跑测试）就触发加载 torch/weaviate/openai。
    """

    from langchain_openai import ChatOpenAI
    from langgraph.checkpoint.postgres import PostgresSaver
    from langgraph.store.postgres import PostgresStore
    from psycopg import Connection
    from psycopg.rows import DictRow, dict_row
    from psycopg_pool import ConnectionPool

    from evidence_desk.agent.react import build_react_agent
    from evidence_desk.application.ticket_service import TicketService
    from evidence_desk.infrastructure.embedding import BgeEmbeddingAdapter
    from evidence_desk.infrastructure.github import GitHubRestClient
    from evidence_desk.infrastructure.llm import OpenAIChatClient
    from evidence_desk.infrastructure.postgres.schema import ensure_ticket_table
    from evidence_desk.infrastructure.postgres.ticket_repository import (
        PostgresTicketRepository,
    )
    from evidence_desk.infrastructure.weaviate import (
        WeaviateHybridRetriever,
        connect_to_weaviate,
        ensure_knowledge_chunk_collection,
    )

    if not settings.openai_api_key:
        raise RuntimeError("未配置 OPENAI_API_KEY，无法启动问答服务。")

    embedder = BgeEmbeddingAdapter(
        settings.embedding_model, settings.embedding_cache_dir
    )
    llm = OpenAIChatClient(
        api_key=settings.openai_api_key,
        model=settings.answer_model,
        base_url=settings.openai_base_url,
    )
    answer_service = RagAnswerService(
        llm,
        temperature=settings.answer_temperature,
        # 拒答第 0 层闸门（见 refusal.py 的四层说明）：检索置信度不够就直接拒答。
        min_score=settings.answer_min_score,
    )
    # ReAct Agent 的「大脑」：支持 function calling 的聊天模型（可配中转站 base_url）。
    chat_model = ChatOpenAI(
        model=settings.answer_model,
        api_key=SecretStr(settings.openai_api_key),
        base_url=settings.openai_base_url,
        temperature=settings.answer_temperature,
    )
    gateway = GitHubRestClient(
        base_url=settings.github_api_base_url,
        api_version=settings.github_api_version,
        token=settings.github_token,
    )

    # 阶段 5：短期记忆持久化。PostgresSaver 要求连接返回字典格式的行（dict_row），
    # 但这只是运行时传给 kwargs 的参数，mypy 静态检查阶段看不出来，所以显式标注
    # ConnectionPool[Connection[DictRow]]，把「这个连接池里的连接是字典格式」这件事
    # 在类型层面也声明清楚，跟 PostgresSaver 要求的类型对上。
    checkpoint_pool: ConnectionPool[Connection[DictRow]] = ConnectionPool(
        conninfo=settings.database_url,
        max_size=20,
        kwargs={"autocommit": True, "row_factory": dict_row, "prepare_threshold": 0},
        open=True,
    )
    checkpointer = PostgresSaver(checkpoint_pool)
    # setup()：第一次用之前必须手动调用，跟 ensure_ticket_table 是同一件事——
    # 在 Postgres 里建好它自己需要的表（checkpoints、checkpoint_writes 等）。
    # 内部逻辑「没有就建、有就跳过」，每次启动都调用没问题，天然幂等。
    checkpointer.setup()

    # 阶段 5：长期记忆持久化。PostgresStore 跟上面的 PostgresSaver 是同一族——
    # 一个管跨会话的长期记忆（M-3），一个管单会话内的历史（M-1/M-2）。两者共用
    # 同一个 checkpoint_pool：它们只是各自向池子借连接去执行自己的 SQL，互不
    # 干扰，没必要为长期记忆再单独开一个连接池。
    # index 配置语义跟之前的 InMemoryStore 完全一样（这就是「端口」抽象的好处：
    # 换成 Postgres 实现，调用方看到的配置接口没变）：
    #   dims  = 向量维度，直接用真实 embedder 探测一次，不写死数字，换模型也不用改配置；
    #   embed = 一个「文本列表 -> 向量列表」的函数，这里包一层薄适配器，
    #           复用已有的 embedder.embed_query（跟 RAG 检索用的是同一个模型/同一份权重）。
    # PostgresStore 做语义检索靠 pgvector 扩展存向量，compose.yml 里的 Postgres
    # 镜像已经换成 pgvector/pgvector:pg17（普通 postgres 镜像没有这个扩展）。
    memory_dims = len(embedder.embed_query("_dims_probe"))
    memory_store = PostgresStore(
        checkpoint_pool,
        index={
            "dims": memory_dims,
            "embed": lambda texts: [embedder.embed_query(t) for t in texts],
        },
    )
    # 跟 checkpointer.setup() 同理：第一次用之前必须手动调用，建好它自己需要的
    # 表（store、store_vectors 等）和 pgvector 索引，内部「没有就建、有就跳过」。
    memory_store.setup()

    # P4-04/05：工单表 + 仓储。ensure_ticket_table 是「没有就建」，可以每次启动
    # 都调用，天然幂等。PostgresTicketRepository 不常驻连接（见该文件内的注释），
    # 所以这里不需要 client/gateway 那种「finally 里关闭」的收尾。
    ensure_ticket_table(settings.database_url)
    ticket_service = TicketService(PostgresTicketRepository(settings.database_url))

    client = connect_to_weaviate(settings)
    try:
        collection = ensure_knowledge_chunk_collection(client)
        # P6-09 冻结：生产检索用 Hybrid（向量 + BM25 关键词融合），不开重排。
        #
        # 为什么是 Hybrid 而不是 Dense：Recall@5 0.9608 vs 0.9314，高 3 个点，
        # 而延迟只多 3 毫秒（13ms vs 10ms）——几乎是白拿的。
        #
        # 为什么不开重排：Dense+Rerank 能把 Recall@5 拉到 1.0000（全标签满分），
        # 但延迟要 1390ms，是 110 倍。技术支持问答是交互场景，让用户每次多等
        # 1.4 秒只为了那 4 个点，不划算。重排代码保留（RerankingRetriever +
        # smoke_retrieval.py --rerank），离线批处理或延迟不敏感的场景可开启。
        #
        # alpha=0.5：向量和关键词各占一半。P6-03 实验用的就是这个值。
        retriever = WeaviateHybridRetriever(collection, alpha=settings.hybrid_alpha)
        app.state.chat_service = ChatService(
            embedder,
            retriever,
            answer_service,
            top_k=settings.retrieval_top_k,
        )
        # 装配 ReAct Agent 存进 app.state 供各请求复用（复用同一 embedder/retriever/gateway）。
        # checkpointer=PostgresSaver（阶段 5）：短期多轮记忆(M-1/M-2)落盘持久化，
        # 服务重启后能从 Postgres 里恢复历史对话，不再是进程内存里的字典。
        # summary_trigger_tokens/summary_keep_messages：M-2 上下文超限策略——
        # 会话（近似）token 数超过阈值时，自动把旧消息摘要压缩，只留最近 N 条原始消息。
        # store/memory_top_k：M-3 长期用户画像记忆——挂上 store 后，Agent 会多出
        # save_user_memory/recall_user_memory 两个工具（见 tools.py），由模型自主
        # 判断何时记、何时查。
        # ticket_service：P4-05 写工具——挂上后 Agent 会多出 create_support_ticket，
        # 由模型在拿到用户明确同意后调用，创建/复用支持工单。
        app.state.agent = build_react_agent(
            chat_model,
            embedder,
            retriever,
            gateway,
            top_k=settings.retrieval_top_k,
            checkpointer=checkpointer,
            summary_trigger_tokens=settings.context_summary_trigger_tokens,
            summary_keep_messages=settings.context_keep_messages,
            store=memory_store,
            memory_top_k=settings.long_term_memory_top_k,
            ticket_service=ticket_service,
            rate_limit_min_interval_seconds=settings.agent_rate_limit_min_interval_seconds,
            response_cache_max_entries=settings.agent_response_cache_max_entries,
            retry_max_attempts=settings.agent_retry_max_attempts,
            retry_base_delay_seconds=settings.agent_retry_base_delay_seconds,
        )
        yield
    finally:
        gateway.close()
        client.close()
        checkpoint_pool.close()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="可评测的企业技术支持与工单协同 Agent",
    lifespan=lifespan,
)
app.state.readiness_service = ReadinessService(check_dependencies)
app.middleware("http")(request_context_middleware)
register_exception_handlers(app)
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(agent_router)
