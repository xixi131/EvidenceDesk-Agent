"""请求 ID 传递与 HTTP 访问日志。"""

import logging
from collections.abc import Awaitable, Callable
from time import perf_counter

from fastapi import Request
from starlette.responses import Response

from evidence_desk.core.ids import new_request_id

logger = logging.getLogger("evidence_desk.http")


async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """复用或生成请求 ID，并记录处理完成的 HTTP 请求。"""

    request_id = request.headers.get("X-Request-ID") or new_request_id()
    request.state.request_id = request_id
    started_at = perf_counter()

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    logger.info(
        "HTTP 请求处理完成",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "latency_ms": round((perf_counter() - started_at) * 1000, 2),
            "error_code": getattr(request.state, "error_code", None),
        },
    )
    return response
