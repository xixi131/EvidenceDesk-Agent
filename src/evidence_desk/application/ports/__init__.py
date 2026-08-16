"""应用层依赖的对外端口（Port）。

端口是应用层「需要什么能力」的抽象接口；具体怎么实现（OpenAI、假模型……）
由 infrastructure 层或测试提供。应用层只依赖端口，不依赖具体实现。
"""

from evidence_desk.application.ports.llm import LLMClient

__all__ = ["LLMClient"]
