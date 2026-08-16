"""把检索结果组装成去重、编号后的引用列表。

这一步是纯确定性的数据整理：不调用大模型，只从 ``RetrievalHit`` 里取字段。
同一篇父文档命中多个 Chunk 时只保留一条引用（保留排名最靠前的那个），
避免「来源」区块把同一个官方页面列很多遍。
"""

from evidence_desk.rag.models import Citation, RetrievalHit


def build_citations(hits: list[RetrievalHit]) -> list[Citation]:
    """按父文档去重后，把检索命中转换为有序引用列表。"""

    citations: list[Citation] = []
    seen_doc_ids: set[str] = set()

    for hit in hits:
        if hit.parent_doc_id in seen_doc_ids:
            continue
        seen_doc_ids.add(hit.parent_doc_id)
        citations.append(
            Citation(
                index=len(citations) + 1,
                chunk_id=hit.chunk_id,
                parent_doc_id=hit.parent_doc_id,
                title=hit.title,
                section_path=hit.section_path,
                source_url=hit.source_url,
            )
        )

    return citations
