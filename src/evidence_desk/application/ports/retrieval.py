"""检索链路的端口：查询向量化与向量检索。"""

from typing import Protocol

from evidence_desk.rag.models import RetrievalHit


class QueryEmbedder(Protocol):
    """把用户问题转换成查询向量的能力。"""

    def embed_query(self, query: str) -> list[float]:
        """返回与文档向量可比较的查询向量。"""
        ...


class ChunkRetriever(Protocol):
    """按查询向量取回 Top-K Chunk 的能力。"""

    def search(self, query_vector: list[float], *, top_k: int) -> list[RetrievalHit]:
        """返回按相关度排序的命中列表。"""
        ...
