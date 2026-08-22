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


class AgentChatResponseData(APIModel):
    """Agent 一次问答返回的数据（比无 Agent 版多一个 intent，暴露路由决策）。"""

    answer: str
    answered: bool
    intent: str
    citations: list[CitationView]
