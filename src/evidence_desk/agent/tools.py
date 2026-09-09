"""ReAct Agent 可调用的工具集合。

每个工具用 ``@tool`` 封装：函数的 **docstring 和参数类型** 会被序列化成
「工具说明 + 参数 schema」塞给 LLM，LLM 据此自己决定调不调、填什么参数。
工具通过工厂闭包注入依赖（检索器 / GitHub 网关），并返回给 LLM 阅读的纯文本。
"""

import uuid

from langchain_core.tools import BaseTool, tool
from langgraph.config import get_config, get_store
from langgraph.store.base import BaseStore

from evidence_desk.application.ports import (
    ChunkRetriever,
    GitHubGateway,
    QueryEmbedder,
)
from evidence_desk.application.ticket_service import TicketService
from evidence_desk.core.errors import AppError


def build_agent_tools(
    embedder: QueryEmbedder,
    retriever: ChunkRetriever,
    gateway: GitHubGateway,
    *,
    top_k: int,
    store: BaseStore | None = None,
    memory_top_k: int = 5,
    ticket_service: TicketService | None = None,
) -> list[BaseTool]:
    """注入依赖，返回 ReAct Agent 使用的工具列表。

    store 不传（None）时不注册 save_user_memory/recall_user_memory 这两个
    长期记忆工具（M-3），行为跟之前一样；main.py 会传 InMemoryStore 正式启用。
    ticket_service 不传（None）时不注册 create_support_ticket 这个写工具（P4-05），
    main.py 会传具体实现正式启用。
    """

    @tool
    def search_docs(query: str) -> str:
        """检索 GitHub Actions 官方文档，返回最相关的片段与来源链接。

        当用户询问 GitHub Actions 的用法、概念、配置或故障排查等知识性问题时使用。
        query 请用简洁的检索关键词（可对用户口语做提炼）。回答时应引用返回的来源链接。
        """
        hits = retriever.search(embedder.embed_query(query), top_k=top_k)
        if not hits:
            return "未检索到相关文档。"
        blocks = [
            f"[资料{i}] {hit.title}\n来源：{hit.source_url}\n内容：{hit.content}"
            for i, hit in enumerate(hits, start=1)
        ]
        return "\n\n".join(blocks)

    @tool
    def get_workflow_run(owner: str, repo: str, run_id: int) -> str:
        """查询某次 GitHub Actions workflow 运行的真实状态与结论。

        当用户询问某次具体运行（需给出 owner、repo 和 run_id）是否成功、为何失败等
        实时事实时使用。不要用文档去猜运行结果——运行状态必须来自本工具。
        """
        try:
            run = gateway.get_workflow_run(owner, repo, run_id)
        except AppError as exc:
            return f"查询失败：{exc.message}"
        conclusion = run.conclusion or "尚无结论（可能仍在运行）"
        return (
            f"工作流「{run.name}」运行 #{run.run_id}"
            f"（{owner}/{repo}，分支 {run.head_branch or '未知'}，事件 {run.event}）："
            f"状态 {run.status}，结论 {conclusion}。详情：{run.html_url}"
        )

    @tool
    def list_workflow_jobs(owner: str, repo: str, run_id: int) -> str:
        """列出某次 workflow 运行下所有作业(job)的状态与结论。

        当需要进一步定位是哪一个作业/步骤失败时使用。
        """
        try:
            jobs = gateway.list_workflow_jobs(owner, repo, run_id)
        except AppError as exc:
            return f"查询失败：{exc.message}"
        if not jobs:
            return "该运行没有作业记录。"
        lines = [
            f"- {job.name}：状态 {job.status}，结论 {job.conclusion or '尚无'}"
            for job in jobs
        ]
        return "作业列表：\n" + "\n".join(lines)

    tools: list[BaseTool] = [search_docs, get_workflow_run, list_workflow_jobs]

    if store is not None:
        # ③（M-3）长期用户画像记忆：这两个工具由 LLM 自主决定「什么时候调」——
        # 不是每轮自动触发，是照着 docstring 里写的场景描述，模型自己判断。
        #
        # user_id 从哪来：不是通过 build_agent_tools 的参数传进来的（因为这个函数
        # 只在服务启动时调用一次，所有请求共用同一份工具；而 user_id 是「每次请求」
        # 才知道的）。而是靠 get_config()——LangGraph 在真正执行这次 invoke() 时，
        # 会把 agent.py 路由层传的 {"configurable": {"user_id": ...}} 挂在一个
        # 「当前调用上下文」里，工具函数运行时随时能读出来，等价于函数参数之外
        # 又多了一条隐式的「这次调用属于谁」的通道。
        #
        # store 同理：不是闭包捕获参数 store，而是用 get_store() 现取——它读取的
        # 是 create_agent(store=store) 编译时挂在图上的那同一个 store 实例。
        # （这里其实闭包捕获 store 变量也能工作，用 get_store() 是为了跟官方
        # LangGraph 长期记忆的标准写法保持一致，工具函数本身不用关心 store 从哪来。）
        @tool
        def save_user_memory(memory: str) -> str:
            """记住一条关于当前用户的长期信息（身份、偏好、习惯等），跨会话保留。

            仅在用户明确提供了值得长期记住的个人信息时调用，例如自我介绍、明确的
            偏好设置。不要为只在本轮对话内有意义的临时内容调用这个工具。
            """
            user_id = get_config()["configurable"]["user_id"]
            memory_store = get_store()
            # namespace 用 (user_id, "memories") 这个二元组，把不同用户的记忆
            # 隔在不同「文件夹」里；key 用随机 uuid，每条记忆各占一条，不覆盖。
            memory_store.put((user_id, "memories"), uuid.uuid4().hex, {"content": memory})
            return "已记住这条信息。"

        @tool
        def recall_user_memory(query: str) -> str:
            """检索关于当前用户的长期记忆（身份、偏好、习惯等）。

            当需要了解这个用户的背景信息才能更好地回答时调用，比如用户提到
            "之前说过""你还记得吗"，或者你判断结合用户已知的偏好能让回答更贴切。
            """
            user_id = get_config()["configurable"]["user_id"]
            memory_store = get_store()
            hits = memory_store.search(
                (user_id, "memories"), query=query, limit=memory_top_k
            )
            if not hits:
                return "没有找到这个用户相关的长期记忆。"
            lines = [f"- {item.value['content']}" for item in hits]
            return "关于该用户的长期记忆：\n" + "\n".join(lines)

        tools.extend([save_user_memory, recall_user_memory])

    if ticket_service is not None:
        # ④（P4-05）创建支持工单：这是目前唯一一个「写」工具——会在 Postgres
        # 真的插入一行数据，所以 docstring 里明确要求模型必须先在对话里问过
        # 用户、拿到同意才调用（阶段 4 范围内是「提示词引导」，不是技术强制拦截；
        # 阶段 5 会补 interrupt 硬审批）。
        @tool
        def create_support_ticket(title: str, description: str, context_summary: str) -> str:
            """在知识文档和已有工具都无法解决用户问题时，创建一张支持工单。

            仅在已经用过 search_docs / get_workflow_run / list_workflow_jobs 仍
            解决不了问题，并且已经在对话中明确询问用户、得到用户同意创建工单后，
            才调用这个工具。不要在未获得用户同意的情况下调用。
            title：简短的问题标题。
            description：问题的详细描述。
            context_summary：简要复述本次对话里已经了解到的背景和已尝试过的排查步骤，
            方便人工客服接手时不用从头再问一遍。
            """
            # thread_id 就是这段对话的 conversation_id，直接拿来当幂等键：
            # 语义是「同一段对话最多升级成一张工单」，模型不小心调用两次也不会
            # 重复建单——见 ticket_repository.py 的 create_or_get 实现。
            thread_id = get_config()["configurable"]["thread_id"]
            try:
                ticket, is_new = ticket_service.create_ticket(
                    idempotency_key=thread_id,
                    title=title,
                    description=description,
                    context_summary=context_summary,
                )
            except AppError as exc:
                return f"创建工单失败：{exc.message}"
            if is_new:
                return f"已创建支持工单 #{ticket.id}（{ticket.title}）。"
            return f"这段对话此前已经创建过支持工单 #{ticket.id}（{ticket.title}），不会重复创建。"

        tools.append(create_support_ticket)

    return tools
