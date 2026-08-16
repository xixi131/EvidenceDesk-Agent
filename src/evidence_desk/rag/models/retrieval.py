"""Dense Retrieval 的稳定结果模型。"""

from evidence_desk.rag.models.source import NonEmptyString, RagModel


class RetrievalHit(RagModel):
    """一次检索中命中的一个 Chunk。"""

    rank: int
    distance: float
    score: float
    chunk_id: NonEmptyString
    parent_doc_id: NonEmptyString
    title: NonEmptyString
    section_path: list[NonEmptyString]
    content: NonEmptyString
    source_url: NonEmptyString
