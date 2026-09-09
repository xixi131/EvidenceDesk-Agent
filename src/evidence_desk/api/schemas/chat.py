"""/api/v1/chat 的请求与响应 Schema。"""

from typing import Any, Literal

from pydantic import Field

from evidence_desk.api.schemas.common import APIModel


class ChatRequest(APIModel):
    """用户提问请求体。"""

    question: str = Field(min_length=1, max_length=2000, description="用户问题")


class CitationView(APIModel):
    """返回给客户端的一条引用（面向展示的精简字段）。"""

    index: int
    title: str
    section_path: list[str]
    source_url: str


class ChatResponseData(APIModel):
    """一次问答返回的业务数据。"""

    answer: str
    answered: bool
    citations: list[CitationView]


class AgentChatRequest(APIModel):
    """ReAct Agent 问答请求体（可带多轮对话 id）。"""

    question: str = Field(min_length=1, max_length=2000, description="用户问题")
    conversation_id: str | None = Field(
        default=None, description="多轮对话 id（thread_id）；不传则新建一段会话"
    )
    # M-3：长期记忆要「跨会话」才有意义，所以需要一个比 conversation_id 更稳定的
    # 身份标识。不传就退化成用 conversation_id 当 user_id——此时长期记忆实际上只在
    # 这一段会话里有效，不会真正跨会话；传了固定值才能让多个 conversation_id
    # 共享同一份长期记忆。
    user_id: str | None = Field(
        default=None, description="用户身份 id；不传则退化为用 conversation_id"
    )


class PendingApprovalView(APIModel):
    """一个正在等待人工审批的操作（阶段 5 HITL）。"""

    tool_name: str
    arguments: dict[str, Any]
    description: str


class AgentChatResponseData(APIModel):
    """ReAct Agent 一次问答返回的数据。

    status="pending_approval" 时，answer 是一句给人看的提示文本，
    真正结构化的审批信息在 pending_approval 字段里；此时 tools_used
    不包含那个被拦下、还没真正执行的工具。
    """

    status: Literal["completed", "pending_approval"] = "completed"
    answer: str
    conversation_id: str
    user_id: str
    tools_used: list[str]
    pending_approval: PendingApprovalView | None = None


class AgentDecisionRequest(APIModel):
    """对一个待审批操作提交审批结果（阶段 5 HITL）。"""

    decision: Literal["approve", "reject"]
    reason: str | None = Field(
        default=None, description="拒绝时给模型看的理由；同意时忽略"
    )
    user_id: str | None = Field(
        default=None, description="同首轮请求的 user_id；不传则退化为用 conversation_id"
    )
