"""基于 LangGraph Agent 的问答路由。"""

from typing import cast

from fastapi import APIRouter, Request

from evidence_desk.agent.graph import MAX_GRAPH_STEPS
from evidence_desk.agent.state import AgentState
from evidence_desk.api.dependencies import AgentGraphDependency
from evidence_desk.api.schemas.chat import (
    AgentChatResponseData,
    ChatRequest,
    CitationView,
)
from evidence_desk.api.schemas.common import ResponseMeta, SuccessResponse

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

    # 只 cast 一次成 AgentState（TypedDict 自带各字段类型），后面取值就无需再 cast。
    final_state = cast(
        AgentState,
        graph.invoke(
            {"question": payload.question},
            {"recursion_limit": MAX_GRAPH_STEPS},
        ),
    )

    citations = final_state.get("citations", [])
    data = AgentChatResponseData(
        answer=final_state.get("answer", ""),
        answered=final_state.get("answered", False),
        intent=final_state.get("intent", ""),
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
