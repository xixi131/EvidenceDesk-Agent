"""基于 Weaviate Hybrid 查询的 Dense+BM25 融合 Retriever（P6-03）。

融合算法（Dense 分数和 BM25 分数怎么合并排序）不是我们自己写的，直接用
Weaviate 数据库自带的 hybrid() 能力——跟这个项目一路的工程选型一致（复用
SummarizationMiddleware/HumanInTheLoopMiddleware/ConnectionPool 这些现成
能力，而不是自己重新发明）。
"""

from typing import cast

import weaviate
from weaviate.classes.query import HybridFusion, MetadataQuery

from evidence_desk.rag.models import RetrievalHit


class WeaviateHybridRetriever:
    """接收查询向量 + 原始问题文本，返回 Dense/BM25 融合排序的 Top-K Chunk。"""

    def __init__(
        self,
        collection: weaviate.collections.Collection,
        *,
        alpha: float = 0.5,
    ) -> None:
        # alpha：0 = 纯 BM25，1 = 纯 Dense，0.5 = 各占一半。做成构造参数是为了
        # 以后方便做参数扫描实验（比如对比 alpha=0.25/0.5/0.75），不用改代码。
        self._collection = collection
        self._alpha = alpha

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        query_text: str | None = None,
    ) -> list[RetrievalHit]:
        """使用 Weaviate 的 Hybrid 检索（Dense 向量 + BM25 关键词融合排序）。"""

        if top_k < 1:
            raise ValueError("top_k 必须大于等于1。")
        if not query_text:
            raise ValueError("Hybrid 检索需要 query_text（原始问题文本）。")

        response = self._collection.query.hybrid(
            query=query_text,
            vector=query_vector,
            alpha=self._alpha,
            # RELATIVE_SCORE：把 Dense/BM25 各自的分数归一化到同一个区间再按
            # alpha 加权求和，比默认的排名融合（RANKED）更细腻，是 Weaviate
            # 官方推荐的融合方式。
            fusion_type=HybridFusion.RELATIVE_SCORE,
            limit=top_k,
            return_metadata=MetadataQuery(score=True),
            return_properties=[
                "chunk_id",
                "parent_doc_id",
                "title",
                "section_path",
                "content",
                "source_url",
            ],
        )

        hits: list[RetrievalHit] = []
        for rank, obj in enumerate(response.objects, start=1):
            score = obj.metadata.score
            if score is None:
                raise RuntimeError("Weaviate 未返回 Hybrid 分数。")

            properties = cast(dict[str, object], obj.properties)
            section_path = cast(list[object], properties["section_path"])
            hits.append(
                RetrievalHit(
                    rank=rank,
                    # 跟 BM25Retriever 一样：Hybrid 分数不是向量距离，distance
                    # 占位不影响评测指标（只看 parent_doc_id）。
                    distance=0.0,
                    score=score,
                    chunk_id=cast(str, properties["chunk_id"]),
                    parent_doc_id=cast(str, properties["parent_doc_id"]),
                    title=cast(str, properties["title"]),
                    section_path=[str(item) for item in section_path],
                    content=cast(str, properties["content"]),
                    source_url=cast(str, properties["source_url"]),
                )
            )

        return hits
