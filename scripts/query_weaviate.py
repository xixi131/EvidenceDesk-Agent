"""使用真实问题查询 KnowledgeChunk 的 Dense Retrieval 结果。"""

from evidence_desk.core.config import get_settings
from evidence_desk.infrastructure.embedding import BgeEmbeddingAdapter
from evidence_desk.infrastructure.weaviate import (
    WeaviateDenseRetriever,
    connect_to_weaviate,
    ensure_knowledge_chunk_collection,
)


def main() -> None:
    """将问题向量化并打印 Weaviate 返回的 Top-K Chunk。"""

    settings = get_settings()
    question = "如何启用 ACTIONS_STEP_DEBUG 调试日志？"
    embedder = BgeEmbeddingAdapter(
        settings.embedding_model,
        settings.embedding_cache_dir,
    )
    query_vector = embedder.embed_query(question)

    client = connect_to_weaviate(settings)
    try:
        collection = ensure_knowledge_chunk_collection(client)
        retriever = WeaviateDenseRetriever(collection)
        hits = retriever.search(query_vector, top_k=settings.retrieval_top_k)
    finally:
        client.close()

    print(f"问题：{question}")
    print(f"命中数量：{len(hits)}")
    for hit in hits:
        print()
        print(f"排名：{hit.rank}，距离：{hit.distance:.6f}，相似度：{hit.score:.6f}")
        print(f"Chunk ID：{hit.chunk_id}")
        print(f"标题：{hit.title}")
        print(f"章节：{' > '.join(hit.section_path)}")
        print(f"来源：{hit.source_url}")
        print(f"正文：{hit.content[:180]}")


if __name__ == "__main__":
    main()
