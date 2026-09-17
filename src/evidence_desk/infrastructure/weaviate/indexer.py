"""将 Chunk 和应用生成的向量批量写入 Weaviate。"""

from collections.abc import Sequence

import weaviate

from evidence_desk.rag.models.chunk import Chunk
from evidence_desk.rag.tokenization import TOKENIZER_VERSION, segment


class KnowledgeChunkIndexer:
    """负责保持 Chunk 元数据和向量的一一对应。"""

    def __init__(self, collection: weaviate.collections.Collection) -> None:
        self._collection = collection

    def insert_many(
        self,
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
        *,
        embedding_model: str,
    ) -> int:
        """批量写入 Chunk；写入前验证数量，避免元数据与向量错位。"""

        if len(chunks) != len(vectors):
            raise ValueError(
                f"Chunk 数量({len(chunks)})与向量数量({len(vectors)})不一致。"
            )

        with self._collection.batch.fixed_size(batch_size=100) as batch:
            for chunk, vector in zip(chunks, vectors, strict=True):
                batch.add_object(
                    properties={
                        "chunk_id": chunk.chunk_id,
                        "parent_doc_id": chunk.parent_doc_id,
                        "title": chunk.title,
                        "section_path": chunk.section_path,
                        "content": chunk.content,
                        # 索引端分词（P6-03）。查询端用的是同一个 segment()
                        # （见 WeaviateBM25Retriever/WeaviateHybridRetriever）——
                        # 两端共用一个函数是整个方案成立的前提，不能在这里图省事
                        # 换成别的切法。
                        "title_tokens": segment(chunk.title),
                        "content_tokens": segment(chunk.content),
                        "source_url": chunk.source_url,
                        "dataset_version": chunk.dataset_version,
                        "embedding_model": embedding_model,
                        "tokenizer_version": TOKENIZER_VERSION,
                    },
                    vector=list(vector),
                )

        failed_objects = self._collection.batch.failed_objects
        if failed_objects:
            raise RuntimeError(f"Weaviate 批量写入失败：{len(failed_objects)} 个对象。")

        return len(chunks)
