"""记录一次 Agent 调用花了多少：几次模型调用、多少 token、多少钱、调了哪些工具。

为什么需要这个：现在的日志只有「这个 HTTP 请求花了多少毫秒」
（api/middleware/request_context.py），但一次 Agent 调用背后是「调模型→执行
工具→再调模型→…」的循环，慢在哪、贵在哪，外面完全看不见。

为什么用回调（callback）而不是直接数 result["messages"]：
接了 checkpointer 之后，result["messages"] 里是**整段会话的历史**，不只是这一轮。
直接遍历它算 token，第二轮会把第一轮的又算一遍，越聊越离谱。回调只在**本次
invoke 真正发生的模型调用**上触发，天然只统计这一轮。

用法（一次请求一个实例，不要复用）：
    collector = UsageCollector()
    agent.invoke(payload, {"configurable": {...}, "callbacks": [collector]})
    snapshot = collector.snapshot()
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


@dataclass(frozen=True)
class UsageSnapshot:
    """一次 Agent 调用的开销快照。"""

    llm_calls: int
    input_tokens: int
    output_tokens: int
    tool_calls: list[str]
    # 这一轮用的模型名。理论上一轮里可能换模型，这里只记最后一次报上来的。
    model: str | None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def estimate_cost_usd(
    snapshot: UsageSnapshot,
    *,
    input_price_per_1m: float,
    output_price_per_1m: float,
) -> float:
    """按「每百万 token 多少美元」折算这一轮的花费。

    输入和输出必须分开算：几乎所有厂商的输出价都比输入价贵好几倍，
    用同一个单价会把成本估偏。

    两个单价都从配置读（core/config.py），默认 0.0——因为价格取决于你用的是
    官方还是中转站，代码里写死任何数字都是瞎编。没配就是 0，日志里照样有
    token 数，只是没有金额。
    """
    return (
        snapshot.input_tokens * input_price_per_1m
        + snapshot.output_tokens * output_price_per_1m
    ) / 1_000_000


@dataclass
class _Accumulator:
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: list[str] = field(default_factory=list)
    model: str | None = None


class UsageCollector(BaseCallbackHandler):
    """挂在一次 invoke 上，收集这一轮的模型调用和工具调用。"""

    def __init__(self) -> None:
        self._acc = _Accumulator()

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """每次模型返回时触发一次。"""
        self._acc.llm_calls += 1

        if response.llm_output:
            model = response.llm_output.get("model_name")
            if isinstance(model, str):
                self._acc.model = model

        for generation_list in response.generations:
            for generation in generation_list:
                # 只有聊天模型的 generation 才有 .message；补一层 getattr，
                # 换成非聊天模型也不会在这里炸。
                message = getattr(generation, "message", None)
                usage = getattr(message, "usage_metadata", None)
                if not usage:
                    continue
                self._acc.input_tokens += int(usage.get("input_tokens", 0))
                self._acc.output_tokens += int(usage.get("output_tokens", 0))

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """每次工具开始执行时触发一次。

        记的是「真的跑起来了」的工具。被 HITL 拦下等审批、最后被拒绝的那次，
        工具函数根本没执行，所以不会出现在这里——这正是我们想要的口径
        （跟 api/routers/agent.py 里 tools_used 排除 rejected 的口径一致）。
        """
        name = serialized.get("name")
        self._acc.tool_calls.append(name if isinstance(name, str) else "unknown")

    def snapshot(self) -> UsageSnapshot:
        """取走当前统计结果。"""
        return UsageSnapshot(
            llm_calls=self._acc.llm_calls,
            input_tokens=self._acc.input_tokens,
            output_tokens=self._acc.output_tokens,
            tool_calls=list(self._acc.tool_calls),
            model=self._acc.model,
        )
