"""RagAnswerService 的单元测试。

关键点：全部用「假模型」验证编排逻辑，不依赖真实 OpenAI，
所以 CI 里既不需要 API Key，也不会烧钱，且结果完全确定。
"""

from evidence_desk.application.rag_answer_service import (
    NO_EVIDENCE_REPLY,
    RagAnswerService,
)
from evidence_desk.rag.models import RetrievalHit


class FakeLLM:
    """记录收到的 Prompt、返回预设文本的假大模型。"""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[tuple[str, str, float]] = []

    def complete(self, *, system: str, user: str, temperature: float) -> str:
        self.calls.append((system, user, temperature))
        return self.reply


def make_hit(parent_doc_id: str = "doc_a") -> RetrievalHit:
    return RetrievalHit(
        rank=1,
        distance=0.1,
        score=0.9,
        chunk_id=f"{parent_doc_id}_0001",
        parent_doc_id=parent_doc_id,
        title="启用调试日志记录",
        section_path=["启用调试日志记录", "启用步骤调试日志"],
        content="把 ACTIONS_STEP_DEBUG 设为 true 即可开启步骤调试日志。",
        source_url="https://docs.github.com/enable-debug-logging",
    )


def test_answer_with_evidence_returns_text_and_citations() -> None:
    fake = FakeLLM("将 ACTIONS_STEP_DEBUG 设为 true [1]。")
    service = RagAnswerService(fake, temperature=0.0)

    result = service.answer("如何开启调试日志？", [make_hit()])

    assert result.answered is True
    assert result.answer == "将 ACTIONS_STEP_DEBUG 设为 true [1]。"
    assert len(result.citations) == 1
    assert (
        result.citations[0].source_url == "https://docs.github.com/enable-debug-logging"
    )
    assert result.prompt_version == "answer-v2"


def test_answer_without_markers_yields_no_citations() -> None:
    """模型没标任何 [n] 时来源列表就是空的。

    这**不是** bug，是一个真实的失败模式（该引不引）——留给
    Citation Correctness 指标去测，不能在生产侧悄悄补上。
    """

    fake = FakeLLM("将 ACTIONS_STEP_DEBUG 设为 true。")
    service = RagAnswerService(fake, temperature=0.0)

    result = service.answer("如何开启调试日志？", [make_hit()])

    assert result.answered is True
    assert result.citations == []


def test_only_cited_hits_appear_in_citations() -> None:
    """来源列表由回答决定，不是检索到什么就列什么。"""

    fake = FakeLLM("第一句 [2]。")
    service = RagAnswerService(fake, temperature=0.0)

    result = service.answer("问题", [make_hit("doc_a"), make_hit("doc_b")])

    assert [c.index for c in result.citations] == [2]
    assert result.citations[0].parent_doc_id == "doc_b"


def test_system_prompt_requires_inline_markers() -> None:
    """引用规则必须在系统指令里，否则模型根本不会标。"""

    fake = FakeLLM("回答 [1]")
    RagAnswerService(fake, temperature=0.0).answer("问题", [make_hit()])

    system, _, _ = fake.calls[0]
    assert "[1]" in system and "引用规则" in system


def test_prompt_contains_context_question_and_temperature() -> None:
    fake = FakeLLM("回答")
    service = RagAnswerService(fake, temperature=0.0)

    service.answer("如何开启调试日志？", [make_hit()])

    system, user, temperature = fake.calls[0]
    assert temperature == 0.0
    assert "只能依据" in system  # 系统指令锁定证据范围
    assert "ACTIONS_STEP_DEBUG" in user  # 检索到的资料确实进了 Prompt
    assert "如何开启调试日志？" in user  # 用户问题也在 Prompt 里


def test_low_score_refuses_without_calling_model() -> None:
    """第 0 层闸门：检索置信度不够就直接拒答，连模型都不调。

    这一层最可靠——分数是检索器算的客观数字，模型再不听话也影响不了它。
    """

    fake = FakeLLM("不该被调用")
    service = RagAnswerService(fake, temperature=0.0, min_score=0.62)

    # make_hit 造的 hit score=0.9，这里手工压到 0.3 模拟"捞到了但都不相关"
    weak_hit = make_hit().model_copy(update={"score": 0.3})
    result = service.answer("一个跑题的问题", [weak_hit])

    assert result.answered is False
    assert result.answer == NO_EVIDENCE_REPLY
    assert fake.calls == []  # 完全没有调用大模型


def test_score_above_threshold_still_calls_model() -> None:
    """分数够就正常往下走——闸门不能把正常问题也挡住。"""

    fake = FakeLLM("回答 [1]")
    service = RagAnswerService(fake, temperature=0.0, min_score=0.62)

    result = service.answer("正常问题", [make_hit()])  # score=0.9

    assert result.answered is True
    assert len(fake.calls) == 1


def test_min_score_defaults_to_disabled() -> None:
    """不传 min_score 时闸门不生效，老调用方行为完全不变。

    这是让改动能安全上线的关键：默认值必须等价于"改动之前"。
    """

    fake = FakeLLM("回答 [1]")
    service = RagAnswerService(fake, temperature=0.0)  # 没传 min_score

    weak_hit = make_hit().model_copy(update={"score": 0.01})
    result = service.answer("问题", [weak_hit])

    assert result.answered is True
    assert len(fake.calls) == 1


def test_paraphrased_refusal_is_recognized() -> None:
    """第 2 层兜底：模型换个说法拒答也要认得出。

    老写法 `NO_EVIDENCE_REPLY not in text` 是一字不差的匹配，这条会判错。
    """

    fake = FakeLLM("抱歉，知识库里没有这方面的资料。")
    service = RagAnswerService(fake, temperature=0.0)

    result = service.answer("问题", [make_hit()])

    assert result.answered is False
    assert result.citations == []


def test_no_hits_refuses_without_calling_model() -> None:
    fake = FakeLLM("不该被调用")
    service = RagAnswerService(fake, temperature=0.0)

    result = service.answer("一个知识库里没有的问题", [])

    assert result.answered is False
    assert result.answer == NO_EVIDENCE_REPLY
    assert result.citations == []
    assert fake.calls == []  # 完全没有调用大模型


def test_model_refusal_drops_citations() -> None:
    # 即使有检索结果，但模型判断资料不足给出兜底拒答时，不应附带引用。
    fake = FakeLLM(NO_EVIDENCE_REPLY)
    service = RagAnswerService(fake, temperature=0.0)

    result = service.answer("资料覆盖不到的问题", [make_hit()])

    assert result.answered is False
    assert result.citations == []
