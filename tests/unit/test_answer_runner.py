"""跑批与 run 文件读写的单元测试（P6-06，不碰 Weaviate 和 OpenAI）。

用假的 ChatService 只验证「搬运」对不对：题目字段有没有抄全、生成结果有没有
接住、存成 JSONL 再读回来是不是原样。

为什么专门测「存了再读回来」（业内叫 round-trip 测试）：run 文件是后面三个
指标唯一的输入。它要是在序列化时悄悄丢了字段——比如 hits 的 content 没存
下来——Faithfulness 判分会拿着空正文去比对，跑出来的数字看着正常，实际全错，
而且极难排查。
"""

from pathlib import Path

from evidence_desk.evaluation.answer_runner import (
    AnswerRunRecord,
    generate_answers,
    load_run,
    save_run,
)
from evidence_desk.evaluation.dataset import EvalCase
from evidence_desk.rag.models import Citation, RetrievalHit


def _hit(chunk_id: str = "chunk_1") -> RetrievalHit:
    return RetrievalHit(
        rank=1,
        distance=0.1,
        score=0.9,
        chunk_id=chunk_id,
        parent_doc_id="doc_a",
        title="启用调试日志",
        section_path=["启用调试日志", "运行程序日志"],
        content="把 ACTIONS_STEP_DEBUG 设为 true。",
        source_url="https://docs.github.com/example",
    )


def _citation() -> Citation:
    return Citation(
        index=1,
        chunk_id="chunk_1",
        parent_doc_id="doc_a",
        title="启用调试日志",
        section_path=["启用调试日志"],
        source_url="https://docs.github.com/example",
    )


class FakeChatService:
    """按预设内容回答，并记下被问过哪些问题。"""

    def __init__(self, answer: str, answered: bool) -> None:
        self.answer = answer
        self.answered = answered
        self.asked: list[str] = []

    def answer_question(self, question: str) -> object:
        self.asked.append(question)

        class _Result:
            answer = self.answer
            answered = self.answered
            citations = [_citation()]
            hits = [_hit()]

        return _Result()


def test_generate_answers_copies_case_fields_and_result() -> None:
    """题目字段和生成结果都要进记录，一个都不能少。"""

    cases = [
        EvalCase(
            id="smoke-01",
            question="如何启用 ACTIONS_STEP_DEBUG？",
            relevant_doc_ids=["doc_a"],
            should_answer=True,
            tags=["exact_identifier", "debug"],
        )
    ]
    service = FakeChatService("把它设为 true。", True)

    records = generate_answers(cases, service)  # type: ignore[arg-type]

    assert len(records) == 1
    record = records[0]
    assert record.id == "smoke-01"
    assert record.should_answer is True
    assert record.tags == ["exact_identifier", "debug"]
    assert record.relevant_doc_ids == ["doc_a"]
    assert record.answer == "把它设为 true。"
    assert record.answered is True
    assert service.asked == ["如何启用 ACTIONS_STEP_DEBUG？"]


def test_run_file_round_trip_preserves_everything(tmp_path: Path) -> None:
    """存成 JSONL 再读回来，每个字段都要原样还原。

    重点盯 hits 里的 content：Faithfulness 判分全靠它，丢了就等于白跑。
    """

    record = AnswerRunRecord(
        id="smoke-01",
        question="如何启用 ACTIONS_STEP_DEBUG？",
        tags=["debug"],
        should_answer=True,
        relevant_doc_ids=["doc_a"],
        answer="把 ACTIONS_STEP_DEBUG 设为 true [1]。",
        answered=True,
        citations=[_citation()],
        hits=[_hit()],
        prompt_version="answer-v1",
    )
    path = tmp_path / "run.jsonl"

    save_run([record], path)
    restored = load_run(path)

    assert restored == [record]
    assert restored[0].hits[0].content == "把 ACTIONS_STEP_DEBUG 设为 true。"
    assert restored[0].citations[0].source_url == "https://docs.github.com/example"


def test_load_run_skips_blank_lines(tmp_path: Path) -> None:
    """文件里的空行要跳过，不能炸。"""

    record = AnswerRunRecord(
        id="x",
        question="q",
        tags=[],
        should_answer=False,
        relevant_doc_ids=[],
        answer="知识库中没有找到相关信息，无法回答该问题。",
        answered=False,
        citations=[],
        hits=[],
        prompt_version="answer-v1",
    )
    path = tmp_path / "run.jsonl"
    path.write_text(record.to_json_line() + "\n\n\n", encoding="utf-8")

    assert load_run(path) == [record]
