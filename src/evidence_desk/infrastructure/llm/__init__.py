"""大模型适配器：把外部 LLM 服务实现成应用层的 ``LLMClient`` 端口。"""

from evidence_desk.infrastructure.llm.openai_client import OpenAIChatClient

__all__ = ["OpenAIChatClient"]
