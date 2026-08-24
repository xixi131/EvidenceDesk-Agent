from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from evidence_desk.agent.tools import build_agent_tools
from evidence_desk.application.ports import ChunkRetriever, GitHubGateway, QueryEmbedder

SYSTEM_PROMPT = """\
<角色>
你是 GitHub Actions 技术支持助手，尽力准确、可靠地帮助用户。
</角色>

<工具使用策略>
- 知识性问题（用法、概念、配置、故障排查）：调用 search_docs 检索官方文档，并在回答中引用返回的来源链接。
- 询问某次具体运行的状态或结论（会给出 owner、repo、run_id）：调用 get_workflow_run；需要定位是哪一步失败时再调 list_workflow_jobs。
- 运行结果必须来自工具，严禁用文档猜测运行状态。
- 问候或闲聊：直接、友好、简短地回应，不要调用任何工具。
</工具使用策略>

<回答准则>
- 只依据工具返回的内容作答，不编造。
- 工具与文档都无法提供依据时，如实说明你不知道。
- 使用简体中文，简洁、准确。
</回答准则>
"""


def build_react_agent(
    model: BaseChatModel,
    embedder: QueryEmbedder,
    retriever: ChunkRetriever,
    gateway: GitHubGateway,
    *,
    top_k: int,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """装配并编译一个绑定工具的 ReAct Agent（checkpointer 提供多轮记忆）。"""
    tools = build_agent_tools(embedder, retriever, gateway, top_k=top_k)
    return create_agent(
        model, tools, system_prompt=SYSTEM_PROMPT, checkpointer=checkpointer
    )
