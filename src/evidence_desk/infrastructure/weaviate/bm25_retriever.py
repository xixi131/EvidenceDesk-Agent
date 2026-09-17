"""基于 Weaviate BM25 查询的关键词 Retriever（P6-03）。

跟 WeaviateDenseRetriever 是同一个模式：接收查询、调 Weaviate、把结果映射成
统一的 RetrievalHit。区别是不算向量距离，靠 Weaviate 自带的 BM25 公式算分。

分词不交给 Weaviate 做：查询文本先过 segment() 切成空格分隔的词串，再去搜
同样切好的 content_tokens/title_tokens 字段（原因见 rag/tokenization.py）。
BM25 的打分公式仍然是数据库实现的，我们只接管"怎么切词"这一步。
"""

from typing import cast

import weaviate
from weaviate.classes.query import MetadataQuery

from evidence_desk.infrastructure.weaviate.schema import BM25_QUERY_PROPERTIES
from evidence_desk.rag.models import RetrievalHit
from evidence_desk.rag.tokenization import segment


class WeaviateBM25Retriever:
    """接收原始问题文本，返回 BM25 关键词匹配的 Top-K Chunk。"""

    def __init__(self, collection: weaviate.collections.Collection) -> None:
        self._collection = collection

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        query_text: str | None = None,
    ) -> list[RetrievalHit]:
        """使用 Weaviate 的 BM25 关键词检索。

        query_vector 未使用（BM25 是关键词匹配，不需要向量）——保留这个参数
        只是为了满足 ChunkRetriever 端口的签名，跟 evaluate_retrieval 统一
        调用方式（它固定会传 embedder 算出来的向量）。
        """

        if top_k < 1:
            raise ValueError("top_k 必须大于等于1。")
        if not query_text:
            raise ValueError("BM25 检索需要 query_text（原始问题文本）。")

        response = self._collection.query.bm25(
            # 查询端分词：跟索引端（KnowledgeChunkIndexer）调的是同一个
            # segment()，这是 BM25 能在中文上工作的前提。
            query=segment(query_text),
            # 必须显式限定搜 *_tokens 字段：不传的话 Weaviate 会搜遍所有可搜索
            # 的 text 字段，包括没分过词的原始 content/title——那些字段上中文是
            # 匹配不上的，白白拉低结果。
            query_properties=BM25_QUERY_PROPERTIES,
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
                raise RuntimeError("Weaviate 未返回 BM25 分数。")

            properties = cast(dict[str, object], obj.properties)
            section_path = cast(list[object], properties["section_path"])
            hits.append(
                RetrievalHit(
                    rank=rank,
                    # BM25 没有『向量距离』这个概念，这里用 0.0 占位——
                    # 评测指标（Recall/Precision/MRR）只看 parent_doc_id，
                    # 不消费 distance/score，占位不影响任何计算结果。
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
