"""Refusal Accuracy 相关指标的单元测试（P6-06）。

四种组合全部钉死。指标函数看着简单（就是两个布尔值比来比去），但它是
安全门禁的依据——判反了会让「漏拒」被统计成「正确」，报告一片祥和，
实际系统在编造内容。所以每一格都要有测试守着。
"""

from evidence_desk.evaluation.answer_metrics import (
    detect_refusal,
    has_citation,
    missed_refusal,
    out_of_range_markers,
    over_refusal,
    refusal_correct,
    retrieval_hit,
)


def test_detects_the_exact_canonical_refusal() -> None:
    assert detect_refusal("知识库中没有找到相关信息，无法回答该问题。") is True


def test_detects_refusal_without_trailing_punctuation() -> None:
    """少个句号也要认出来——精确匹配就是栽在这种地方。"""

    assert detect_refusal("知识库中没有找到相关信息，无法回答该问题") is True


def test_detects_paraphrased_refusal() -> None:
    """模型换个说法照样是拒答。

    第三条是实现时踩的坑：第一版模式要求出现「相关」「对应」这类修饰词，
    这句「没有这方面的资料」就漏了。写测试时被抓出来，模式已放宽。
    """

    assert detect_refusal("抱歉，我无法回答这个问题。") is True
    assert detect_refusal("参考资料不足，没有相关内容。") is True
    assert detect_refusal("抱歉，知识库里没有这方面的资料。") is True
    assert detect_refusal("文档中未包含相关内容。") is True


def test_normal_answer_is_not_a_refusal() -> None:
    assert detect_refusal("把 ACTIONS_STEP_DEBUG 设为 true 即可开启调试日志。") is False


def test_long_answer_mentioning_refusal_words_is_not_a_refusal() -> None:
    """一大段正经回答里恰好出现「无法回答」，不能算拒答。

    长度兜底就是防这个误伤的。
    """

    long_answer = (
        "可以通过多种方式排查工作流失败。" * 10 + "某些情况下系统会提示无法回答。"
    )

    assert detect_refusal(long_answer) is False


def test_out_of_range_markers_are_detected() -> None:
    """只有 5 条资料却标了 [7]：用户点进去什么都没有，纯规则就能查准。"""

    assert out_of_range_markers([1, 3, 7], num_hits=5) == [7]
    assert out_of_range_markers([1, 3], num_hits=5) == []
    assert out_of_range_markers([0], num_hits=5) == [0]


def test_has_citation() -> None:
    """该引不引：一句结论光秃秃摆着，用户没有任何核实途径。"""

    assert has_citation([1]) is True
    assert has_citation([]) is False


def test_retrieval_hit_attribution() -> None:
    """误拒归因：检索有没有捞到标注的相关文档。"""

    assert retrieval_hit(["doc_a"], ["doc_b", "doc_a"]) is True
    assert retrieval_hit(["doc_a"], ["doc_b", "doc_c"]) is False
    assert retrieval_hit([], ["doc_b"]) is False


def test_answered_when_should_answer_is_correct() -> None:
    """该答，也答了 —— 正确。"""

    assert refusal_correct(should_answer=True, answered=True) is True
    assert over_refusal(should_answer=True, answered=True) is False
    assert missed_refusal(should_answer=True, answered=True) is False


def test_refused_when_should_refuse_is_correct() -> None:
    """该拒，也拒了 —— 正确。"""

    assert refusal_correct(should_answer=False, answered=False) is True
    assert over_refusal(should_answer=False, answered=False) is False
    assert missed_refusal(should_answer=False, answered=False) is False


def test_refused_when_should_answer_is_over_refusal() -> None:
    """该答却拒了 —— 误拒（体验问题）。"""

    assert refusal_correct(should_answer=True, answered=False) is False
    assert over_refusal(should_answer=True, answered=False) is True
    assert missed_refusal(should_answer=True, answered=False) is False


def test_answered_when_should_refuse_is_missed_refusal() -> None:
    """不该答却答了 —— 漏拒（安全事故）。

    这是四格里最严重的一格：知识库没有答案，系统却编了一段，
    底下还挂着官方链接。必须能被单独识别出来，不能混进笼统的准确率里。
    """

    assert refusal_correct(should_answer=False, answered=True) is False
    assert over_refusal(should_answer=False, answered=True) is False
    assert missed_refusal(should_answer=False, answered=True) is True


def test_two_error_types_are_mutually_exclusive() -> None:
    """两类错误不可能同时发生——同一题只会落进其中一格。"""

    for should_answer in (True, False):
        for answered in (True, False):
            both = over_refusal(should_answer, answered) and missed_refusal(
                should_answer, answered
            )
            assert both is False
