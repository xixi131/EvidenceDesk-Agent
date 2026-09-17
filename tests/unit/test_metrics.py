"""检索评测指标的单元测试（不依赖 Weaviate）。"""

import pytest

from evidence_desk.evaluation.metrics import (
    group_recall_by_tag,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)

# 排名列表保留重复：同一父文档可能有多个 chunk 进入 Top-K。
RANKED = ["doc_a", "doc_b", "doc_a", "doc_c"]


def test_recall_hits_and_misses() -> None:
    # doc_a 在第 1 名 → Top-1 就命中，Recall@1 = 1/1
    assert recall_at_k(RANKED, {"doc_a"}, 1) == pytest.approx(1.0)
    # doc_c 在第 4 名 → Top-2 里没有，Recall@2 = 0；Top-4 里有，Recall@4 = 1
    assert recall_at_k(RANKED, {"doc_c"}, 2) == pytest.approx(0.0)
    assert recall_at_k(RANKED, {"doc_c"}, 4) == pytest.approx(1.0)


def test_recall_multi_relevant_counts_unique_docs() -> None:
    # 相关 = {a, c}，Top-4 命中 a 和 c 两篇 → Recall@4 = 2/2 = 1.0
    assert recall_at_k(RANKED, {"doc_a", "doc_c"}, 4) == pytest.approx(1.0)


def test_precision_denominator_is_k() -> None:
    # Top-2 = [a, b]，唯一相关命中 {a} = 1 篇，分母固定 K=2 → 0.5
    assert precision_at_k(RANKED, {"doc_a"}, 2) == pytest.approx(0.5)
    # Top-4 命中 {a, c} = 2 篇，分母 K=4 → 0.5
    assert precision_at_k(RANKED, {"doc_a", "doc_c"}, 4) == pytest.approx(0.5)


def test_reciprocal_rank_uses_first_hit() -> None:
    # doc_a 首次出现在第 1 名 → RR = 1/1
    assert reciprocal_rank(RANKED, {"doc_a"}) == pytest.approx(1.0)
    # doc_c 首次出现在第 4 名 → RR = 1/4
    assert reciprocal_rank(RANKED, {"doc_c"}) == pytest.approx(0.25)
    # 全没命中 → 0
    assert reciprocal_rank(RANKED, {"doc_zzz"}) == pytest.approx(0.0)


def test_recall_requires_relevant() -> None:
    with pytest.raises(ValueError):
        recall_at_k(RANKED, set(), 5)


def test_precision_rejects_non_positive_k() -> None:
    with pytest.raises(ValueError):
        precision_at_k(RANKED, {"doc_a"}, 0)


def test_group_recall_by_tag_averages_within_each_tag() -> None:
    tagged = [
        (["knowledge"], 1.0),
        (["knowledge"], 0.5),
        (["security"], 0.0),
    ]
    result = group_recall_by_tag(tagged)
    assert result == pytest.approx({"knowledge": 0.75, "security": 0.0})


def test_group_recall_by_tag_counts_multi_tag_case_in_every_tag() -> None:
    tagged = [
        (["multi_document", "security"], 1.0),
        (["security"], 0.0),
    ]
    result = group_recall_by_tag(tagged)
    assert result == pytest.approx({"multi_document": 1.0, "security": 0.5})


def test_group_recall_by_tag_empty_input_returns_empty_dict() -> None:
    assert group_recall_by_tag([]) == {}
