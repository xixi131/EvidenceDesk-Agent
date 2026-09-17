"""检索链路的端口：查询向量化、向量检索与重排。"""

from collections.abc import Sequence
from typing import Protocol

from evidence_desk.rag.models import RetrievalHit


class QueryEmbedder(Protocol):
    """把用户问题转换成查询向量的能力。"""

    def embed_query(self, query: str) -> list[float]:
        """返回与文档向量可比较的查询向量。"""
        ...


class ChunkRetriever(Protocol):
    """按查询向量取回 Top-K Chunk 的能力。"""

    def search(
        self, query_vector: list[float], *, top_k: int, query_text: str | None = None
    ) -> list[RetrievalHit]:
        """返回按相关度排序的命中列表。

        query_text（P6-03 新增，可选）：原始问题文本，只有 BM25/Hybrid 检索
        才用得上（关键词匹配需要原文，不是向量）；Dense 检索直接忽略这个参数，
        不影响原有行为，不用改任何已有调用方。
        """
        ...


class Reranker(Protocol):
    """把一批候选 Chunk 按与问题的相关度重新排序的能力（P6-05）。

    跟 ChunkRetriever 的区别在于"看多少": 检索器要从几百上千个 chunk 里
    捞出候选，为了快，它只能把问题和文档各自压成一个向量再比距离——问题和
    文档从头到尾没有"见过面"。重排器只处理已经捞出来的二三十个候选，所以
    负担得起把「问题 + 这篇文档」拼成一对一起喂给模型，让模型直接判断这一对
    配不配。看得细，自然排得准，代价是慢得多，只能用在小批量候选上。

    典型用法是两段式：先用检索器取 candidate_top_n=20 个候选（保证答案在
    里面），再用重排器精排出 context_top_k=5 个给模型看。
    """

    def rerank(
        self,
        query_text: str,
        hits: Sequence[RetrievalHit],
        *,
        top_k: int,
    ) -> list[RetrievalHit]:
        """返回重排后的前 top_k 个命中，rank 从 1 重新编号。"""
        ...
