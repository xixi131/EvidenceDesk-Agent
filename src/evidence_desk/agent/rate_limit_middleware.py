import threading
import time
from collections.abc import Callable

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse


class RateLimitMiddleware(AgentMiddleware):
    """保证两次真正调用模型之间至少间隔 min_interval_seconds 秒。"""

    def __init__(self, *, min_interval_seconds: float) -> None:
        self._min_interval = min_interval_seconds
        self._next_call_at: float | None = None
        self._lock = threading.Lock()

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        wait_seconds = 0.0

        with self._lock:
            now = time.monotonic()
            if self._next_call_at is not None and self._next_call_at > now:
                wait_seconds = self._next_call_at - now
            self._next_call_at = now + wait_seconds + self._min_interval

        if wait_seconds > 0:
            time.sleep(wait_seconds)

        return handler(request)
