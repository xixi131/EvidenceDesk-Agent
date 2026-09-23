"""Agent 开销统计的单元测试（不连模型，直接喂造好的回调事件）。"""

from uuid import uuid4

from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from evidence_desk.agent.usage import UsageCollector, estimate_cost_usd


def _llm_result(
    *, input_tokens: int, output_tokens: int, model: str = "gpt-5.5"
) -> LLMResult:
    message = AIMessage(
        content="答案",
        usage_metadata={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
    )
    return LLMResult(
        generations=[[ChatGeneration(message=message)]],
        llm_output={"model_name": model},
    )


def _end(collector: UsageCollector, result: LLMResult) -> None:
    collector.on_llm_end(result, run_id=uuid4())


def test_collects_nothing_before_any_call() -> None:
    snapshot = UsageCollector().snapshot()
    assert snapshot.llm_calls == 0
    assert snapshot.total_tokens == 0
    assert snapshot.tool_calls == []
    assert snapshot.model is None


def test_accumulates_tokens_across_the_react_loop() -> None:
    # 一轮 ReAct 会调好几次模型（想→调工具→看结果→再想），token 要累加。
    collector = UsageCollector()
    _end(collector, _llm_result(input_tokens=100, output_tokens=20))
    _end(collector, _llm_result(input_tokens=350, output_tokens=60))

    snapshot = collector.snapshot()
    assert snapshot.llm_calls == 2
    assert snapshot.input_tokens == 450
    assert snapshot.output_tokens == 80
    assert snapshot.total_tokens == 530
    assert snapshot.model == "gpt-5.5"


def test_records_tool_calls_in_order() -> None:
    collector = UsageCollector()
    collector.on_tool_start({"name": "search_docs"}, "怎么开调试日志", run_id=uuid4())
    collector.on_tool_start({"name": "get_workflow_run"}, "{}", run_id=uuid4())

    assert collector.snapshot().tool_calls == ["search_docs", "get_workflow_run"]


def test_tool_without_a_name_does_not_crash() -> None:
    collector = UsageCollector()
    collector.on_tool_start({}, "x", run_id=uuid4())
    assert collector.snapshot().tool_calls == ["unknown"]


def test_missing_usage_metadata_is_skipped_not_fatal() -> None:
    # 有些模型/代理不回 usage，这时 token 记 0，但「调了几次」照样要记下来。
    collector = UsageCollector()
    result = LLMResult(
        generations=[[ChatGeneration(message=AIMessage(content="无用量信息"))]],
        llm_output=None,
    )
    _end(collector, result)

    snapshot = collector.snapshot()
    assert snapshot.llm_calls == 1
    assert snapshot.total_tokens == 0


def test_snapshot_is_a_copy_not_a_live_view() -> None:
    collector = UsageCollector()
    collector.on_tool_start({"name": "search_docs"}, "x", run_id=uuid4())
    snapshot = collector.snapshot()
    collector.on_tool_start({"name": "create_support_ticket"}, "x", run_id=uuid4())

    # 取过的快照不该被后续调用改写，否则日志里记的数会跟实际对不上。
    assert snapshot.tool_calls == ["search_docs"]


def test_cost_prices_input_and_output_separately() -> None:
    collector = UsageCollector()
    _end(collector, _llm_result(input_tokens=1_000_000, output_tokens=1_000_000))

    cost = estimate_cost_usd(
        collector.snapshot(), input_price_per_1m=0.5, output_price_per_1m=2.0
    )
    # 输入 1M×0.5 + 输出 1M×2.0 = 2.5，不是 1M×(0.5+2.0)/2 那种合并单价。
    assert cost == 2.5


def test_cost_is_zero_when_prices_are_not_configured() -> None:
    collector = UsageCollector()
    _end(collector, _llm_result(input_tokens=500, output_tokens=100))

    cost = estimate_cost_usd(
        collector.snapshot(), input_price_per_1m=0.0, output_price_per_1m=0.0
    )
    assert cost == 0.0
