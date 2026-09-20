"""LLM Judge 的单元测试（P6-06，不调真实模型）。

只验证「外壳」：提示词有没有把资料和回答都带上、模型输出能不能正确解析、
格式不对时会不会优雅降级。judge 判得准不准是人工抽查的事，不在单测里测。
"""

from pathlib import Path

from evidence_desk.evaluation.answer_judge import (
    AnswerJudge,
    JudgeVerdict,
    build_judge_prompt,
    load_verdicts,
    save_verdicts,
)
from evidence_desk.rag.models import RetrievalHit


def _hit(title: str, content: str) -> RetrievalHit:
    return RetrievalHit(
        rank=1,
        distance=0.1,
        score=0.9,
        chunk_id="c1",
        parent_doc_id="doc_a",
        title=title,
        section_path=["章节"],
        content=content,
        source_url="https://docs.github.com/example",
    )


class FakeLLM:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.received_user: str | None = None
        self.received_temperature: float | None = None

    def complete(self, *, system: str, user: str, temperature: float) -> str:
        self.received_user = user
        self.received_temperature = temperature
        return self.reply


def test_prompt_contains_context_question_and_answer() -> None:
    """三样东西缺一不可：资料正文、问题、待评回答。"""

    prompt = build_judge_prompt(
        "保留多久？", "默认 90 天。", [_hit("构件", "构件默认保留 90 天。")]
    )

    assert "构件默认保留 90 天。" in prompt
    assert "保留多久？" in prompt
    assert "默认 90 天。" in prompt
    assert "[资料1]" in prompt


def test_parses_structured_verdict() -> None:
    reply = (
        '{"faithfulness": "supported", "unsupported_claims": [], '
        '"answer_quality": "correct", "citation_support": "supported", '
        '"reason": "资料里明确写了 90 天"}'
    )

    verdict = AnswerJudge(FakeLLM(reply)).judge("smoke-01", "q", "a", [])

    assert verdict.faithfulness == "supported"
    assert verdict.answer_quality == "correct"
    assert verdict.citation_support == "supported"
    assert verdict.unsupported_claims == []


def test_strips_markdown_code_fence() -> None:
    """模型爱把 JSON 包在 ```json 里，提示词禁了也不保证遵守。"""

    reply = (
        '```json\n{"faithfulness": "unsupported", "unsupported_claims": ["编的"], '
        '"answer_quality": "incorrect", "citation_support": "unsupported", '
        '"reason": "x"}\n```'
    )

    verdict = AnswerJudge(FakeLLM(reply)).judge("smoke-01", "q", "a", [])

    assert verdict.faithfulness == "unsupported"
    assert verdict.unsupported_claims == ["编的"]


def test_unparseable_output_degrades_instead_of_crashing() -> None:
    """格式不对不抛异常，记成 parse_error 继续跑。

    60 道题跑到第 50 道因为一条输出格式不对而整个崩掉，前面 50 次调用就白花了。
    原始输出要留着，不然只知道失败、不知道它吐了什么。
    """

    verdict = AnswerJudge(FakeLLM("我觉得这个回答还行吧")).judge("x", "q", "a", [])

    assert verdict.faithfulness == "parse_error"
    assert verdict.raw == "我觉得这个回答还行吧"


def test_temperature_is_zero_for_reproducibility() -> None:
    """判卷必须可复现：同一份答案跑两次给不同结论的话，指标就没意义了。"""

    llm = FakeLLM(
        '{"faithfulness": "supported", "unsupported_claims": [], "answer_quality": "correct", "reason": ""}'
    )
    AnswerJudge(llm).judge("x", "q", "a", [])

    assert llm.received_temperature == 0.0


def test_verdict_file_round_trip(tmp_path: Path) -> None:
    verdict = JudgeVerdict(
        case_id="smoke-01",
        faithfulness="partially_supported",
        unsupported_claims=["这句资料里没有"],
        answer_quality="partial",
        citation_support="partially_supported",
        reason="第二句缺依据",
        raw="{}",
    )
    path = tmp_path / "judge.jsonl"

    save_verdicts([verdict], path)

    assert load_verdicts(path) == [verdict]
