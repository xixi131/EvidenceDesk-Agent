"""/api/v1/chat 的请求与响应 Schema。"""

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


class AgentChatResponseData(APIModel):
    """ReAct Agent 一次问答返回的数据。"""

    answer: str
    conversation_id: str
    tools_used: list[str]
