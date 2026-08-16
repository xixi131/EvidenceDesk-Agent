"""定义第一版 KnowledgeChunk Collection。"""

import weaviate
from weaviate.classes.config import Configure, DataType, Property

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
                Property(
                    name="title",
                    data_type=DataType.TEXT,
                    skip_vectorization=True,
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
