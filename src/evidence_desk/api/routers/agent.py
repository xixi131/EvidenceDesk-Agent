"""基于 LangGraph Agent 的问答路由。"""

from typing import Any, cast

from fastapi import APIRouter, Request

from evidence_desk.agent.graph import MAX_GRAPH_STEPS
from evidence_desk.api.dependencies import AgentGraphDependency
from evidence_desk.api.schemas.chat import (
    AgentChatResponseData,
    ChatRequest,
    CitationView,
)
from evidence_desk.api.schemas.common import ResponseMeta, SuccessResponse
from evidence_desk.rag.models import Citation

router = APIRouter(tags=["agent"])


@router.post(
    "/api/v1/agent/chat",
    response_model=SuccessResponse[AgentChatResponseData],
    summary="基于 LangGraph Agent 的证据约束问答",
)
def agent_chat(
    request: Request,
    payload: ChatRequest,
    graph: AgentGraphDependency,
) -> SuccessResponse[AgentChatResponseData]:
    """经意图路由 → 检索 → 评估 →（必要时改写重试）→ 生成的 Agent 问答。"""

    # invoke：给初始白板（只有 question），LangGraph 跑到 END，返回最终白板。
    final_state = cast(
        dict[str, Any],
        graph.invoke(
            {"question": payload.question},
            {"recursion_limit": MAX_GRAPH_STEPS},
        ),
    )

    citations = cast(list[Citation], final_state.get("citations", []))
    data = AgentChatResponseData(
        answer=cast(str, final_state.get("answer", "")),
        answered=cast(bool, final_state.get("answered", False)),
        intent=cast(str, final_state.get("intent", "")),
        citations=[
            CitationView(
                index=citation.index,
                title=citation.title,
                section_path=citation.section_path,
                source_url=citation.source_url,
            )
            for citation in citations
        ],
    )
    return SuccessResponse(
        data=data,
        meta=ResponseMeta(request_id=request.state.request_id),
    )
