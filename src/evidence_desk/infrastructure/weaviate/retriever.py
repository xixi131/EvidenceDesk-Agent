"""基于 Weaviate near-vector 查询的 Dense Retriever。"""

from typing import cast

import weaviate
from weaviate.classes.query import MetadataQuery

from evidence_desk.rag.models import RetrievalHit


class WeaviateDenseRetriever:
    """接收查询向量，并返回带来源的 Top-K Chunk。"""

    def __init__(self, collection: weaviate.collections.Collection) -> None:
        self._collection = collection

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        query_text: str | None = None,
    ) -> list[RetrievalHit]:
        """使用 Weaviate 的向量索引搜索最相近的 Chunk。

        query_text 未使用：Dense 检索只看向量，这个参数是 ChunkRetriever
        端口为 BM25/Hybrid 检索器新增的（见 retrieval.py），Dense 实现按
        端口签名接住即可，不需要用它。
        """

        if top_k < 1:
            raise ValueError("top_k 必须大于等于1。")

        response = self._collection.query.near_vector(
            query_vector,
            limit=top_k,
            return_metadata=MetadataQuery(distance=True),
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
            distance = obj.metadata.distance
            if distance is None:
                raise RuntimeError("Weaviate 未返回向量距离。")

            properties = cast(dict[str, object], obj.properties)
            section_path = cast(list[object], properties["section_path"])
            hits.append(
                RetrievalHit(
                    rank=rank,
                    distance=distance,
                    score=1.0 - distance,
                    chunk_id=cast(str, properties["chunk_id"]),
                    parent_doc_id=cast(str, properties["parent_doc_id"]),
                    title=cast(str, properties["title"]),
                    section_path=[str(item) for item in section_path],
                    content=cast(str, properties["content"]),
                    source_url=cast(str, properties["source_url"]),
                )
            )

        return hits
