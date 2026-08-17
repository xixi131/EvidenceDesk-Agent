"""无 Agent 知识问答路由。"""

from fastapi import APIRouter, Request

from evidence_desk.api.dependencies import ChatServiceDependency
from evidence_desk.api.schemas.chat import (
    ChatRequest,
    ChatResponseData,
    CitationView,
)
from evidence_desk.api.schemas.common import ResponseMeta, SuccessResponse

router = APIRouter(tags=["chat"])


@router.post(
    "/api/v1/chat",
    response_model=SuccessResponse[ChatResponseData],
    summary="基于官方文档的证据约束问答",
)
def chat(
    request: Request,
    payload: ChatRequest,
    chat_service: ChatServiceDependency,
) -> SuccessResponse[ChatResponseData]:
    """检索官方文档并生成带引用、受证据约束的回答。"""

    result = chat_service.answer_question(payload.question)
    data = ChatResponseData(
        answer=result.answer,
        answered=result.answered,
        citations=[
            CitationView(
                index=citation.index,
                title=citation.title,
                section_path=citation.section_path,
                source_url=citation.source_url,
            )
            for citation in result.citations
        ],
    )
    return SuccessResponse(
        data=data,
        meta=ResponseMeta(request_id=request.state.request_id),
    )
