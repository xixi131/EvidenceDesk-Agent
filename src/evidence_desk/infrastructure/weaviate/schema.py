"""定义第一版 KnowledgeChunk Collection。"""

import weaviate
from weaviate.classes.config import Configure, DataType, Property, Tokenization

KNOWLEDGE_CHUNK_COLLECTION = "KnowledgeChunk"


def ensure_knowledge_chunk_collection(
    client: weaviate.WeaviateClient,
    *,
    recreate: bool = False,
) -> weaviate.collections.Collection:
    """创建自带向量的 KnowledgeChunk Collection。"""

    if recreate and client.collections.exists(KNOWLEDGE_CHUNK_COLLECTION):
        client.collections.delete(KNOWLEDGE_CHUNK_COLLECTION)

    if not client.collections.exists(KNOWLEDGE_CHUNK_COLLECTION):
        client.collections.create(
            name=KNOWLEDGE_CHUNK_COLLECTION,
            vector_config=Configure.Vectors.self_provided(),
            properties=[
                Property(
                    name="chunk_id",
                    data_type=DataType.TEXT,
                    skip_vectorization=True,
                ),
                Property(
                    name="parent_doc_id",
                    data_type=DataType.TEXT,
                    skip_vectorization=True,
                ),
                # title/content 显式设成 GSE_CH（Weaviate 核心自带的中文分词器，
                # >=1.20 版本不需要额外装模块）——P6-03 要用 BM25/Hybrid 关键词
                # 检索，默认的 word 分词器不认中文词语边界，会导致 BM25 在中文
                # 语料上基本失效。改分词属于 Schema 变更，Property 一旦建好不能
                # 原地改分词方式，只能删了重建（下面 ensure_knowledge_chunk_
                # collection 的 recreate=True 分支负责这件事）。
                Property(
                    name="title",
                    data_type=DataType.TEXT,
                    skip_vectorization=True,
                    tokenization=Tokenization.GSE_CH,
                ),
                Property(
                    name="section_path",
                    data_type=DataType.TEXT_ARRAY,
                    skip_vectorization=True,
                ),
                Property(
                    name="content",
                    data_type=DataType.TEXT,
                    skip_vectorization=True,
                    tokenization=Tokenization.GSE_CH,
                ),
                Property(
                    name="source_url",
                    data_type=DataType.TEXT,
                    skip_vectorization=True,
                ),
                Property(
                    name="dataset_version",
                    data_type=DataType.TEXT,
                    skip_vectorization=True,
                ),
                Property(
                    name="embedding_model",
                    data_type=DataType.TEXT,
                    skip_vectorization=True,
                ),
            ],
        )

    return client.collections.get(KNOWLEDGE_CHUNK_COLLECTION)
