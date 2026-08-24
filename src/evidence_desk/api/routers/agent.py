"""基于 LangGraph ReAct Agent 的问答路由。"""

import uuid
from typing import Any, cast

from fastapi import APIRouter, Request
from langchain_core.messages import AIMessage

from evidence_desk.api.dependencies import AgentDependency
from evidence_desk.api.schemas.chat import AgentChatRequest, AgentChatResponseData
from evidence_desk.api.schemas.common import ResponseMeta, SuccessResponse

router = APIRouter(tags=["agent"])


@router.post(
    "/api/v1/agent/chat",
    response_model=SuccessResponse[AgentChatResponseData],
    summary="基于 LangGraph ReAct Agent 的多轮问答",
)
def agent_chat(
    request: Request,
    payload: AgentChatRequest,
    agent: AgentDependency,
) -> SuccessResponse[AgentChatResponseData]:
    """由 LLM 自主决定调用 search_docs / GitHub 工具，支持多轮对话记忆。"""

    conversation_id = payload.conversation_id or f"conv_{uuid.uuid4().hex}"
    # 同一 conversation_id 作为 thread_id，checkpointer 自动带上该会话的历史消息。
    result = cast(
        dict[str, Any],
        agent.invoke(
            {"messages": [{"role": "user", "content": payload.question}]},
            {"configurable": {"thread_id": conversation_id}},
        ),
    )

    messages = result["messages"]
    answer = str(messages[-1].content) if messages else ""
    tools_used = [
        tool_call["name"]
        for message in messages
        if isinstance(message, AIMessage)
        for tool_call in message.tool_calls
    ]
    data = AgentChatResponseData(
        answer=answer,
        conversation_id=conversation_id,
        tools_used=tools_used,
    )
    return SuccessResponse(
        data=data,
        meta=ResponseMeta(request_id=request.state.request_id),
    )
