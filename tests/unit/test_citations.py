"""build_citations 的单元测试：去重、编号、字段搬运。"""

from evidence_desk.rag.citations import build_citations
from evidence_desk.rag.models import RetrievalHit


def make_hit(
    *,
    rank: int,
    parent_doc_id: str,
    chunk_id: str,
    title: str = "示例标题",
    source_url: str = "https://docs.github.com/example",
) -> RetrievalHit:
    """构造一个最小可用的检索命中，供测试复用。"""

    return RetrievalHit(
        rank=rank,
        distance=0.1,
        score=0.9,
        chunk_id=chunk_id,
        parent_doc_id=parent_doc_id,
        title=title,
        section_path=["章节"],
        content="正文内容",
        source_url=source_url,
    )


def test_build_citations_numbers_from_one() -> None:
    hits = [
        make_hit(rank=1, parent_doc_id="doc_a", chunk_id="doc_a_0001"),
        make_hit(rank=2, parent_doc_id="doc_b", chunk_id="doc_b_0001"),
    ]

    citations = build_citations(hits)

    assert [c.index for c in citations] == [1, 2]
    assert [c.parent_doc_id for c in citations] == ["doc_a", "doc_b"]


def test_build_citations_dedupes_by_parent_document() -> None:
    # 同一篇父文档命中两个 Chunk，只应保留排名最靠前的那一条引用。
    hits = [
        make_hit(rank=1, parent_doc_id="doc_a", chunk_id="doc_a_0001"),
        make_hit(rank=2, parent_doc_id="doc_b", chunk_id="doc_b_0001"),
        make_hit(rank=3, parent_doc_id="doc_a", chunk_id="doc_a_0002"),
    ]

    citations = build_citations(hits)

    assert len(citations) == 2
    assert [c.index for c in citations] == [1, 2]
    assert [c.parent_doc_id for c in citations] == ["doc_a", "doc_b"]
    # 保留的是第一次出现（排名靠前）的 Chunk。
    assert citations[0].chunk_id == "doc_a_0001"


def test_build_citations_empty_input() -> None:
    assert build_citations([]) == []
