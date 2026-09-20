"""基于 LangGraph ReAct Agent 的问答路由。"""

import uuid
from typing import Any, cast

from fastapi import APIRouter, Request
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command

from evidence_desk.api.dependencies import AgentDependency
from evidence_desk.api.schemas.chat import (
    AgentChatRequest,
    AgentChatResponseData,
    AgentDecisionRequest,
    PendingApprovalView,
)
from evidence_desk.api.schemas.common import ResponseMeta, SuccessResponse

router = APIRouter(tags=["agent"])


def _build_response_data(
    result: dict[str, Any], *, conversation_id: str, user_id: str
) -> AgentChatResponseData:
    """把 agent.invoke(...) 的原始返回，翻译成对外的响应数据。

    两种结局：
    - 正常收尾：result 里没有 __interrupt__，messages 最后一条就是最终答案。
    - 卡在审批点：result 里有 __interrupt__（阶段 5 HITL），这次请求还没有
      「最终答案」，只有一个待审批的操作描述，要单独识别、单独包装返回。
    """

    # __interrupt__ 只有触发了 HumanInTheLoopMiddleware 才会出现；正常收尾的
    # result 里根本没有这个 key，所以先用 .get(...) 取，取不到就是 None。
    interrupts = result.get("__interrupt__")
    if interrupts:
        # HumanInTheLoopMiddleware 把「本轮所有待审批的工具调用」打包成一个
        # HITLRequest 塞进同一个 interrupt 里（见 human_in_the_loop.py 的
        # after_model），所以这里只有一个 Interrupt 对象，取第一个即可。
        hitl_request = interrupts[0].value
        # 目前只有一个写工具（create_support_ticket），所以 action_requests
        # 只会有一条；真出现多条也只展示第一条给客户端（先满足当前场景，
        # 多个写工具同轮触发审批的场景以后再扩展这里）。
        action = hitl_request["action_requests"][0]
        return AgentChatResponseData(
            status="pending_approval",
            answer=f"这个操作需要人工审批后才会执行：{action['description']}",
            conversation_id=conversation_id,
            user_id=user_id,
            tools_used=[],
            pending_approval=PendingApprovalView(
                tool_name=action["name"],
                arguments=action["args"],
                description=action["description"],
            ),
        )

    # 正常收尾：result["messages"] 是整段对话序列；最后一条 AI 消息就是最终答案。
    messages = result["messages"]
    answer = str(messages[-1].content) if messages else ""
    # 顺带收集这轮里模型调用过哪些工具（AIMessage.tool_calls），返回给前端做透明展示。
    #
    # 有个坑：HumanInTheLoopMiddleware 处理「拒绝」决定时，并不会把这条
    # tool_calls 从 AIMessage 里删掉（它只是额外塞了一条 status="error" 的
    # ToolMessage，工具函数本身根本没被真正调用——探针脚本验证过这一点）。
    # 如果只看 AIMessage.tool_calls，会把「被拒绝、没真正执行」的工具也算进
    # tools_used，对前端是误导。所以这里先把「有对应 error ToolMessage」的
    # tool_call_id 收集出来，生成 tools_used 时排除掉它们。
    rejected_call_ids = {
        message.tool_call_id
        for message in messages
        if isinstance(message, ToolMessage) and message.status == "error"
    }
    tools_used = [
        tool_call["name"]
        for message in messages
        if isinstance(message, AIMessage)
        for tool_call in message.tool_calls
        if tool_call["id"] not in rejected_call_ids
    ]
    return AgentChatResponseData(
        status="completed",
        answer=answer,
        conversation_id=conversation_id,
        user_id=user_id,
        tools_used=tools_used,
    )


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
    """由 LLM 自主决定调用 search_docs / GitHub 工具，支持多轮对话记忆。

    如果模型这一轮触发了需要审批的写操作（阶段 5 HITL），这次请求会提前收尾，
    响应里 status="pending_approval"；客户端要调用下面的 decisions 接口提交
    审批结果，才能真正让这次对话继续跑完。
    """

    # 会话 id = 短期记忆(M-1/M-2)的 key：客户端首轮不传 → 这里新建一个（并在响应里返回）；
    # 后续轮客户端带回同一个 id → 下面用它当 thread_id，就能取到这段对话的历史。
    conversation_id = payload.conversation_id or f"conv_{uuid.uuid4().hex}"
    # 用户 id = 长期记忆(M-3)的 key：不传就退化用 conversation_id（等于长期记忆只在
    # 这一段会话内有效）；客户端如果对同一个人的多段会话都传同一个 user_id，
    # save_user_memory / recall_user_memory 这两个工具就能跨 conversation_id 共享记忆。
    user_id = payload.user_id or conversation_id

    # 一次 invoke 跑完整个 ReAct 循环（调模型→执行工具→再调模型→…→收尾，
    # 或者中途因为触发审批而提前返回）。
    # 参数1：这一轮的新输入（只放 user 消息）；
    # 参数2 configurable：thread_id 给 checkpointer 用来拼历史消息（M-1/M-2），
    #        也是阶段 5 HITL 恢复执行时用来找到「暂停在哪」的 key；
    #        user_id 给 save_user_memory/recall_user_memory 这两个工具用来确定
    #        「记的是谁」——工具内部通过 get_config() 读回这个值（见 tools.py）。
    result = cast(
        dict[str, Any],
        agent.invoke(
            {"messages": [{"role": "user", "content": payload.question}]},
            {"configurable": {"thread_id": conversation_id, "user_id": user_id}},
        ),
    )

    data = _build_response_data(
        result, conversation_id=conversation_id, user_id=user_id
    )
    return SuccessResponse(
        data=data,
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/api/v1/agent/chat/{conversation_id}/decisions",
    response_model=SuccessResponse[AgentChatResponseData],
    summary="对一次待审批的写操作提交审批结果（阶段 5 HITL）",
)
def agent_decision(
    request: Request,
    conversation_id: str,
    payload: AgentDecisionRequest,
    agent: AgentDependency,
) -> SuccessResponse[AgentChatResponseData]:
    """审批通过 → 真正执行那个被拦下的写工具；拒绝 → 工具不执行，模型据此继续。

    必须是此前 /agent/chat 响应里 status="pending_approval" 的那个 conversation_id，
    否则这段对话根本没有卡在等审批的地方，LangGraph 会因为找不到匹配的暂停点报错。
    """

    user_id = payload.user_id or conversation_id

    # approve：{"type": "approve"}——工具照原样放行。
    # reject：{"type": "reject", "message": ...}——工具不执行，改成一条「已拒绝」
    #   的伪造结果回喂给模型；不传 reason 时用一句默认话术。
    if payload.decision == "approve":
        decision: dict[str, Any] = {"type": "approve"}
    else:
        decision = {"type": "reject"}
        if payload.reason:
            decision["message"] = payload.reason

    # Command(resume=...)：不是发新消息，是「续上」某个之前被 interrupt() 暂停的
    # thread_id。resume 的值会被 HumanInTheLoopMiddleware 里那句
    # `interrupt(hitl_request)["decisions"]` 原样接收——所以这里必须传成
    # {"decisions": [...]} 这个形状，跟 action_requests 一一对应
    # （目前只有一个写工具，所以 decisions 列表里也只放一条）。
    result = cast(
        dict[str, Any],
        agent.invoke(
            Command(resume={"decisions": [decision]}),
            {"configurable": {"thread_id": conversation_id, "user_id": user_id}},
        ),
    )

    data = _build_response_data(
        result, conversation_id=conversation_id, user_id=user_id
    )
    return SuccessResponse(
        data=data,
        meta=ResponseMeta(request_id=request.state.request_id),
    )
