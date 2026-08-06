"""HTTP API 的通用响应 Schema。"""

from datetime import UTC, datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")


class APIModel(BaseModel):
    """启用严格字段校验的 API 模型基类。"""

    model_config = ConfigDict(extra="forbid")


class ApiError(APIModel):
    """返回给 API 客户端的安全错误信息。"""

    code: str
    message: str
    details: dict[str, object] | None = None
    retryable: bool = False


class ResponseMeta(APIModel):
    """成功响应和失败响应共用的元数据。"""

    request_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SuccessResponse(APIModel, Generic[DataT]):
    """包含明确业务数据类型的成功响应。"""

    ok: Literal[True] = True
    data: DataT
    error: None = None
    meta: ResponseMeta


class ErrorResponse(APIModel):
    """包含安全错误信息的失败响应。"""

    ok: Literal[False] = False
    data: None = None
    error: ApiError
    meta: ResponseMeta


class HealthResponse(APIModel):
    """进程存活检查接口返回的数据。"""

    status: str


class VersionResponse(APIModel):
    """服务版本接口返回的数据。"""

    service: str
    version: str


class ReadyResponse(APIModel):
    """依赖就绪检查接口返回的数据。"""

    status: Literal["ready"] = "ready"
    dependencies: dict[str, str]
