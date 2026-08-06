"""健康检查、就绪检查和服务元数据路由。"""

from fastapi import APIRouter, Request

from evidence_desk.api.schemas.common import (
    ErrorResponse,
    HealthResponse,
    ReadyResponse,
    ResponseMeta,
    SuccessResponse,
    VersionResponse,
)
from evidence_desk.core.config import get_settings
from evidence_desk.core.dependency_checks import check_dependencies
from evidence_desk.core.errors import AppError

router = APIRouter(tags=["system"])


def _success_meta(request: Request) -> ResponseMeta:
    return ResponseMeta(request_id=request.state.request_id)


@router.get(
    "/health",
    response_model=SuccessResponse[HealthResponse],
    summary="检查服务进程是否存活",
)
def health(request: Request) -> SuccessResponse[HealthResponse]:
    """应用进程存活时返回稳定响应。"""

    return SuccessResponse(
        data=HealthResponse(status="ok"),
        meta=_success_meta(request),
    )


@router.get(
    "/ready",
    response_model=SuccessResponse[ReadyResponse],
    responses={503: {"model": ErrorResponse}},
    summary="检查外部依赖是否就绪",
)
async def ready(request: Request) -> SuccessResponse[ReadyResponse]:
    """检查必要的外部依赖是否可用。"""

    settings = get_settings()
    dependencies = await check_dependencies(settings)
    unavailable = [name for name, status in dependencies.items() if status != "ok"]
    if unavailable:
        raise AppError(
            code="DEPENDENCIES_UNAVAILABLE",
            message="必要外部依赖不可用",
            status_code=503,
            details={"dependencies": dependencies, "unavailable": unavailable},
            retryable=True,
        )

    return SuccessResponse(
        data=ReadyResponse(dependencies=dependencies),
        meta=_success_meta(request),
    )


@router.get(
    "/api/v1/version",
    response_model=SuccessResponse[VersionResponse],
    summary="获取服务版本",
)
def version(request: Request) -> SuccessResponse[VersionResponse]:
    """返回服务名称和配置的版本号。"""

    settings = get_settings()
    return SuccessResponse(
        data=VersionResponse(service="evidence-desk", version=settings.app_version),
        meta=_success_meta(request),
    )
