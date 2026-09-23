import hashlib
import json
from collections import OrderedDict
from collections.abc import Callable

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import BaseMessage


def _message_signature(message: BaseMessage) -> dict[str, object]:
    """把一条消息提炼成"参与判断是否相同"的最小信息。"""

    return {
        "type": message.type,
        "content": message.content,
        "tool_calls": getattr(message, "tool_calls", None),
    }


class LLMResponseCacheMiddleware(AgentMiddleware):
    """完全相同的请求直接返回缓存结果，不再真的调用模型。"""

    def __init__(self, *, max_entries: int = 256) -> None:
        self._max_entries = max_entries
        self._cache: OrderedDict[str, ModelResponse] = OrderedDict()

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        key = self._build_key(request)

        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]

        response = handler(request)

        self._cache[key] = response
        self._cache.move_to_end(key)
        if len(self._cache) > self._max_entries:
            self._cache.popitem(last=False)

        return response

    @staticmethod
    def _build_key(request: ModelRequest) -> str:
        fingerprint = {
            "model": getattr(request.model, "model_name", str(request.model)),
            "temperature": getattr(request.model, "temperature", None),
            "messages": [_message_signature(m) for m in request.messages],
        }
        raw = json.dumps(fingerprint, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
