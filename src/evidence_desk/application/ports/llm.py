"""大模型（LLM）端口。"""

from typing import Protocol


class LLMClient(Protocol):
    """生成式大模型的最小接口。

    应用层只依赖这个协议，不关心背后是真实的 OpenAI，还是测试用的假模型。
    只要某个类拥有同样签名的 ``complete`` 方法，就可以当作 ``LLMClient`` 使用。
    """

    def complete(self, *, system: str, user: str, temperature: float) -> str:
        """根据系统指令和用户消息生成一段纯文本回答。

        参数:
            system: 系统指令，用来约束模型的角色和行为（例如「只准用给定资料」）。
            user: 用户消息，通常是「参考资料 + 问题」拼成的正文。
            temperature: 采样温度，0 表示尽量确定、不发挥。

        返回:
            模型生成的纯文本。
        """
        ...
