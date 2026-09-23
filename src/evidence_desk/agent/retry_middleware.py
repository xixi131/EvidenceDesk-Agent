import time
from collections.abc import Callable

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from openai import APIConnectionError, InternalServerError, RateLimitError

RETRYABLE_EXCEPTIONS = (APIConnectionError, InternalServerError, RateLimitError)


class RetryMiddleware(AgentMiddleware):
    """网络问题/对方临时故障时，原地重试几次，不直接把异常甩给用户。"""

    def __init__(
        self, *, max_attempts: int = 3, base_delay_seconds: float = 1.0
    ) -> None:
        self._max_attempts = max_attempts
        self._base_delay_seconds = base_delay_seconds

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        for attempt in range(self._max_attempts):
            try:
                return handler(request)
            except RETRYABLE_EXCEPTIONS:
                if attempt == self._max_attempts - 1:
                    raise
                delay = self._base_delay_seconds * (2**attempt)
                time.sleep(delay)
        raise AssertionError("unreachable: max_attempts 必须 >= 1")
