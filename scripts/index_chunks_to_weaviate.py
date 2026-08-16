"""将 293 个 Baseline Chunk 向量写入 Docker 中的 Weaviate。"""

from pathlib import Path

from evidence_desk.core.config import get_settings
from evidence_desk.infrastructure.embedding import BgeEmbeddingAdapter
from evidence_desk.infrastructure.weaviate import (
    KnowledgeChunkIndexer,
    connect_to_weaviate,
    ensure_knowledge_chunk_collection,
)
from evidence_desk.rag.chunking.chunk_quality_pipeline import (
    build_chunks_from_cleaned_corpus,
)
from evidence_desk.rag.embedding_text import build_embedding_text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = PROJECT_ROOT / "data/knowledge_base/github_actions_zh_v1"


def main() -> None:
    """重建测试 Collection，生成向量并批量写入。"""

    settings = get_settings()
    chunks, _ = build_chunks_from_cleaned_corpus(CORPUS_ROOT)
    texts = [build_embedding_text(chunk) for chunk in chunks]

    embedder = BgeEmbeddingAdapter(
        settings.embedding_model,
        settings.embedding_cache_dir,
    )
    vectors = embedder.embed_documents(texts)

    client = connect_to_weaviate(settings)
    try:
        collection = ensure_knowledge_chunk_collection(client, recreate=True)
        indexer = KnowledgeChunkIndexer(collection)
        inserted_count = indexer.insert_many(
            chunks,
            vectors,
            embedding_model=embedder.model_name,
        )
        stored_count = collection.aggregate.over_all(total_count=True).total_count
        print(f"写入对象数：{inserted_count}")
        print(f"Weaviate 对象数：{stored_count}")
        if stored_count != inserted_count:
            raise RuntimeError("写入数量和 Weaviate 实际对象数量不一致。")
    finally:
        client.close()


if __name__ == "__main__":
    main()
