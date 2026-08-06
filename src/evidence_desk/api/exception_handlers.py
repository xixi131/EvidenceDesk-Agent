"""将预期异常和未预期异常转换为安全的 API 响应。"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from evidence_desk.api.schemas.common import ApiError, ErrorResponse, ResponseMeta
from evidence_desk.core.errors import AppError

logger = logging.getLogger("evidence_desk.api")


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "req_unknown")


def _error_response(
    request: Request,
    *,
    code: str,
    message: str,
    status_code: int,
    details: dict[str, object] | None = None,
    retryable: bool = False,
) -> JSONResponse:
    request.state.error_code = code
    payload = ErrorResponse(
        error=ApiError(
            code=code,
            message=message,
            details=details,
            retryable=retryable,
        ),
        meta=ResponseMeta(request_id=_request_id(request)),
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
        headers={"X-Request-ID": _request_id(request)},
    )


async def handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return _error_response(
        request,
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
        retryable=exc.retryable,
    )


async def handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    return _error_response(
        request,
        code="HTTP_ERROR",
        message=str(exc.detail),
        status_code=exc.status_code,
        retryable=exc.status_code >= 500,
    )


async def handle_validation_error(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return _error_response(
        request,
        code="VALIDATION_ERROR",
        message="请求参数校验失败",
        status_code=422,
        details={"errors": exc.errors()},
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("未处理的应用异常")
    return _error_response(
        request,
        code="INTERNAL_SERVER_ERROR",
        message="服务内部错误",
        status_code=500,
        retryable=True,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """在应用中注册安全的异常映射。"""

    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(HTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
