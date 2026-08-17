"""FastAPI 应用入口（组合根）。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from evidence_desk.api.exception_handlers import register_exception_handlers
from evidence_desk.api.middleware.request_context import request_context_middleware
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

    from evidence_desk.infrastructure.embedding import BgeEmbeddingAdapter
    from evidence_desk.infrastructure.llm import OpenAIChatClient
    from evidence_desk.infrastructure.weaviate import (
        WeaviateDenseRetriever,
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
    answer_service = RagAnswerService(llm, temperature=settings.answer_temperature)

    client = connect_to_weaviate(settings)
    try:
        collection = ensure_knowledge_chunk_collection(client)
        retriever = WeaviateDenseRetriever(collection)
        app.state.chat_service = ChatService(
            embedder,
            retriever,
            answer_service,
            top_k=settings.retrieval_top_k,
        )
        yield
    finally:
        client.close()


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
