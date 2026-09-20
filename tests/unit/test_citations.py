"""引用标号解析与引用组装的单元测试（P6-06 改造后）。

改造前 build_citations(hits) 把检索结果全列出来当"来源"，不看回答文本；
改造后只为**答案真正引用到的**资料生成引用，编号沿用资料编号。
这些测试把新契约钉死，尤其是「不重排、不去重」——那两条看起来像可以
顺手优化掉的东西，一旦被优化掉，答案里的 [3] 和来源列表里的 [3] 就会
指向不同文档，而且不报错、渲染正常。
"""

from evidence_desk.rag.citations import build_citations, parse_citation_markers
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


def _hits(n: int) -> list[RetrievalHit]:
    return [
        make_hit(rank=i, parent_doc_id=f"doc_{i}", chunk_id=f"doc_{i}_0001")
        for i in range(1, n + 1)
    ]


# --- parse_citation_markers ---------------------------------------------


def test_parses_single_marker() -> None:
    assert parse_citation_markers("设为 true [1]。") == [1]


def test_parses_adjacent_markers() -> None:
    """[1][3] 连着写要能分别抽出来。"""

    assert parse_citation_markers("属于日志开关 [1][3]。") == [1, 3]


def test_deduplicates_and_sorts() -> None:
    assert parse_citation_markers("先 [3] 再 [1]，又一次 [1]") == [1, 3]


def test_no_markers_returns_empty() -> None:
    assert parse_citation_markers("就是一段没有标号的普通回答。") == []


def test_multi_digit_marker() -> None:
    """\\d+ 的 + 要真的生效，两位数也得认。"""

    assert parse_citation_markers("见 [12]") == [12]


def test_out_of_range_marker_is_still_returned() -> None:
    """越界标号照样返回——这里只负责"文本里写了什么"。

    如果在解析阶段顺手过滤掉 [7]，上层指标就永远看不到"引用了不存在的资料"
    这个错误，报告会显示一片完美。判断合法是调用方的事。
    """

    assert parse_citation_markers("见 [7]") == [7]


# --- build_citations -----------------------------------------------------


def test_only_cited_hits_become_citations() -> None:
    """没被引用的资料不该出现在来源列表里。"""

    citations = build_citations(_hits(5), [1, 3])

    assert [c.parent_doc_id for c in citations] == ["doc_1", "doc_3"]


def test_index_follows_material_number_and_may_be_non_contiguous() -> None:
    """index 沿用资料编号，不重新编号——编号不连续是对的。

    重排会让答案里的 [3] 和来源列表里的 [3] 指向不同文档：不报错、
    页面渲染正常，用户点进去是另一篇文章。连续好看 vs 指向正确，后者压倒性重要。
    """

    citations = build_citations(_hits(5), [1, 3, 4])

    assert [c.index for c in citations] == [1, 3, 4]


def test_same_parent_document_is_not_deduplicated() -> None:
    """同一父文档的两条资料都被引用时，两条都要保留。

    去重一旦丢掉资料2，模型写的 [2] 就成了悬空标号。
    去重和标号可解析二者不可兼得，必须保后者。
    """

    hits = [
        make_hit(rank=1, parent_doc_id="doc_a", chunk_id="doc_a_0001"),
        make_hit(rank=2, parent_doc_id="doc_a", chunk_id="doc_a_0002"),
    ]

    citations = build_citations(hits, [1, 2])

    assert len(citations) == 2
    assert [c.chunk_id for c in citations] == ["doc_a_0001", "doc_a_0002"]


def test_out_of_range_marker_is_skipped() -> None:
    """越界标号造不出引用，跳过即可——但指标那边照样统计得到。"""

    citations = build_citations(_hits(3), [1, 7])

    assert [c.index for c in citations] == [1]


def test_no_markers_yields_no_citations() -> None:
    """模型一个标号都没写是合法输入，返回空列表，交给指标去判该不该扣分。"""

    assert build_citations(_hits(3), []) == []


def test_markers_are_deduplicated_and_sorted() -> None:
    citations = build_citations(_hits(3), [3, 1, 1])

    assert [c.index for c in citations] == [1, 3]
