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

    # 会话 id = 记忆的 key：客户端首轮不传 → 这里新建一个（并在响应里返回）；
    # 后续轮客户端带回同一个 id → 下面用它当 thread_id，就能取到这段对话的历史。
    conversation_id = payload.conversation_id or f"conv_{uuid.uuid4().hex}"

    # 一次 invoke 跑完整个 ReAct 循环（调模型→执行工具→再调模型→…→收尾）。
    # 参数1：这一轮的新输入（只放 user 消息）；
    # 参数2 config.thread_id：告诉 checkpointer「这属于哪段会话」，它自动把历史消息拼进去。
    result = cast(
        dict[str, Any],
        agent.invoke(
            {"messages": [{"role": "user", "content": payload.question}]},
            {"configurable": {"thread_id": conversation_id}},
        ),
    )

    # result["messages"] 是整段对话序列；最后一条 AI 消息就是最终答案。
    messages = result["messages"]
    answer = str(messages[-1].content) if messages else ""
    # 顺带收集这轮里模型调用过哪些工具（AIMessage.tool_calls），返回给前端做透明展示。
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
