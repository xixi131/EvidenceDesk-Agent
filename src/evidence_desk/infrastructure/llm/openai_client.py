"""基于 OpenAI Chat Completions 的 ``LLMClient`` 适配器。"""

from openai import OpenAI, OpenAIError
from openai.types.chat import ChatCompletionMessageParam

from evidence_desk.core.errors import AppError


class OpenAIChatClient:
    """用 OpenAI 官方 SDK 实现应用层的 ``LLMClient`` 端口。"""

    def __init__(
        self, *, api_key: str, model: str, base_url: str | None = None
    ) -> None:
        # base_url 为 None 时，SDK 使用 OpenAI 官方地址；
        # 传入中转站地址即可把请求发到代理服务。
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def complete(self, *, system: str, user: str, temperature: float) -> str:
        """调用 Chat Completions，返回模型生成的纯文本。"""

        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=temperature,
                messages=messages,
            )
        except OpenAIError as exc:
            # 把 SDK 的各种网络/额度/超时错误收敛成一个稳定的应用错误码，
            # 让上层只需处理 LLM_UNAVAILABLE，而不用认识 OpenAI 的内部异常。
            raise AppError(
                code="LLM_UNAVAILABLE",
                message="回答生成服务暂时不可用",
                status_code=503,
                retryable=True,
            ) from exc

        content = response.choices[0].message.content
        return content or ""
