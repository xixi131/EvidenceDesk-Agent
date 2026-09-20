"""Query Rewriter 的单元测试（P6-02，不调真实 LLM）。

用假模型只验证"外壳逻辑"：输出清洗、兜底条件、changed 标志对不对。
改写质量好不好是评测脚本的事，那要真模型跑真数据，不在单测里测。
"""

import pytest

from evidence_desk.application.query_rewriter import LlmQueryRewriter


class FakeLLM:
    """按预设内容回答，并记下收到的参数。"""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.received_user: str | None = None
        self.received_temperature: float | None = None

    def complete(self, *, system: str, user: str, temperature: float) -> str:
        self.received_user = user
        self.received_temperature = temperature
        return self.reply


def test_returns_rewritten_text_and_marks_changed() -> None:
    """正常改写：返回模型文本，changed 为 True。"""

    rewriter = LlmQueryRewriter(FakeLLM("如何在 GitHub Actions 中配置依赖缓存"))

    result = rewriter.rewrite("那个缓存的东西咋配")

    assert result.rewritten == "如何在 GitHub Actions 中配置依赖缓存"
    assert result.changed is True
    assert result.fallback_reason is None


def test_identical_output_is_not_marked_changed() -> None:
    """模型原样返回时 changed 要是 False。

    否则报告里的"改写率"会把没改的题也算进去，看起来像改写覆盖了全部题目。
    """

    question = "如何启用 ACTIONS_STEP_DEBUG？"
    result = LlmQueryRewriter(FakeLLM(question)).rewrite(question)

    assert result.changed is False


def test_strips_quotes_and_extra_lines() -> None:
    """模型爱加的引号和多余解释要洗掉，不能带进检索。"""

    rewriter = LlmQueryRewriter(FakeLLM('  "如何配置依赖缓存"\n解释：我换了说法  '))

    assert rewriter.rewrite("那个缓存咋配").rewritten == "如何配置依赖缓存"


def test_empty_model_output_falls_back_to_original_with_reason() -> None:
    """模型返回空时退回原问题，并写明原因。

    退回本身是对的（检索不能拿空串去跑），但必须留痕——静默降级会让
    报告里"改写组"的成绩其实混着一批根本没改写的题。
    """

    result = LlmQueryRewriter(FakeLLM("   ")).rewrite("怎么管理缓存？")

    assert result.rewritten == "怎么管理缓存？"
    assert result.changed is False
    assert result.fallback_reason == "模型返回空"


def test_overlong_output_falls_back_to_original() -> None:
    """输出异常长基本等于模型在补原问题没有的内容，退回原问题。"""

    question = "怎么管理缓存？"
    rewriter = LlmQueryRewriter(FakeLLM("如何" + "很长的补充说明" * 20))

    result = rewriter.rewrite(question)

    assert result.rewritten == question
    assert result.fallback_reason == "改写结果过长"


def test_temperature_defaults_to_zero_for_reproducibility() -> None:
    """默认温度必须是 0：同一个问题每次改写都不一样的话，实验就没法复核。"""

    llm = FakeLLM("改写结果")
    LlmQueryRewriter(llm).rewrite("问题")

    assert llm.received_temperature == 0.0


def test_blank_question_raises() -> None:
    """空问题直接报错，不要浪费一次 LLM 调用。"""

    with pytest.raises(ValueError, match="question"):
        LlmQueryRewriter(FakeLLM("x")).rewrite("   ")
