"""FastAPI 依赖注入入口。"""

from typing import Annotated, cast

from fastapi import Depends, Request

from evidence_desk.application.chat_service import ChatService
from evidence_desk.application.readiness import ReadinessService


def get_readiness_service(request: Request) -> ReadinessService:
    """从应用状态中取得就绪检查服务。"""

    return cast(ReadinessService, request.app.state.readiness_service)


ReadinessServiceDependency = Annotated[
    ReadinessService,
    Depends(get_readiness_service),
]


def get_chat_service(request: Request) -> ChatService:
    """从应用状态中取得在启动阶段装配好的问答服务。"""

    return cast(ChatService, request.app.state.chat_service)


ChatServiceDependency = Annotated[
    ChatService,
    Depends(get_chat_service),
]
