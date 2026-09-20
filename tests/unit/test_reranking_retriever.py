"""两段式检索（粗筛+精排）的单元测试（不依赖 Weaviate 和重排模型）。

用假的检索器和假的重排器，只验证"组装逻辑"对不对：捞多少条、传不传原始
问题、最后截到几条。真模型的效果好不好是评测脚本的事，不在单测里测。
"""

from collections.abc import Sequence

import pytest

from evidence_desk.application.reranking_retriever import RerankingRetriever
from evidence_desk.rag.models import RetrievalHit


def _hit(rank: int, doc: str) -> RetrievalHit:
    return RetrievalHit(
        rank=rank,
        distance=0.1 * rank,
        score=1.0 / rank,
        chunk_id=f"chunk_{rank}",
        parent_doc_id=doc,
        title="标题",
        section_path=["章节"],
        content=f"正文{rank}",
        source_url="https://example.com",
    )


class FakeRetriever:
    """记下别人问它要了几条、带没带原始问题。"""

    def __init__(self) -> None:
        self.requested_top_k: int | None = None
        self.requested_query_text: str | None = None

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        query_text: str | None = None,
    ) -> list[RetrievalHit]:
        self.requested_top_k = top_k
        self.requested_query_text = query_text
        return [_hit(i, f"doc_{i}") for i in range(1, top_k + 1)]


class ReverseReranker:
    """把候选顺序整个倒过来——好验证"重排确实生效了"。"""

    def rerank(
        self,
        query_text: str,
        hits: Sequence[RetrievalHit],
        *,
        top_k: int,
    ) -> list[RetrievalHit]:
        reversed_hits = list(reversed(hits))[:top_k]
        return [
            hit.model_copy(update={"rank": rank})
            for rank, hit in enumerate(reversed_hits, start=1)
        ]


def test_fetches_candidates_then_truncates_to_top_k() -> None:
    """粗筛要按 candidate_top_n 捞，最终只返回 top_k 条。"""

    base = FakeRetriever()
    retriever = RerankingRetriever(base, ReverseReranker(), candidate_top_n=20)

    hits = retriever.search([0.1], top_k=5, query_text="怎么取消工作流")

    assert base.requested_top_k == 20, "粗筛应该捞 20 条候选，不是 5 条"
    assert len(hits) == 5, "最终只返回 top_k 条"


def test_rerank_actually_changes_order() -> None:
    """重排结果要真的按重排器的顺序来，不能还是原来的检索顺序。"""

    retriever = RerankingRetriever(
        FakeRetriever(), ReverseReranker(), candidate_top_n=20
    )

    hits = retriever.search([0.1], top_k=3, query_text="怎么取消工作流")

    # 假重排器把 20 条倒序，所以第 20 条变第 1
    assert [hit.parent_doc_id for hit in hits] == ["doc_20", "doc_19", "doc_18"]
    # rank 必须重新编号成 1/2/3，反映重排后的名次而不是检索时的原始名次
    assert [hit.rank for hit in hits] == [1, 2, 3]


def test_query_text_is_passed_down_to_base_retriever() -> None:
    """原始问题要往下传：底层可能是 BM25/Hybrid，它们需要原文。"""

    base = FakeRetriever()
    retriever = RerankingRetriever(base, ReverseReranker())

    retriever.search([0.1], top_k=5, query_text="怎么取消工作流")

    assert base.requested_query_text == "怎么取消工作流"


def test_missing_query_text_raises_instead_of_silently_skipping_rerank() -> None:
    """没有原始问题就报错，不能悄悄退化成"不重排"。

    静默降级最危险：评测会跑完、数字看着正常，实际根本没测到重排。
    """

    retriever = RerankingRetriever(FakeRetriever(), ReverseReranker())

    with pytest.raises(ValueError, match="query_text"):
        retriever.search([0.1], top_k=5)


def test_candidate_count_never_below_top_k() -> None:
    """top_k 比 candidate_top_n 还大时，粗筛要按 top_k 捞，否则永远凑不够。"""

    base = FakeRetriever()
    retriever = RerankingRetriever(base, ReverseReranker(), candidate_top_n=20)

    hits = retriever.search([0.1], top_k=50, query_text="问题")

    assert base.requested_top_k == 50
    assert len(hits) == 50
