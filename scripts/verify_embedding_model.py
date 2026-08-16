"""验证冻结 Baseline 的 Chunk 能批量转换为 Embedding 向量。"""

from pathlib import Path

from evidence_desk.core.config import get_settings
from evidence_desk.infrastructure.embedding import (
    BgeEmbeddingAdapter,
    EmbeddingModelLoadError,
)
from evidence_desk.rag.chunking.chunk_quality_pipeline import (
    build_chunks_from_cleaned_corpus,
)
from evidence_desk.rag.embedding_text import build_embedding_text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = PROJECT_ROOT / "data/knowledge_base/github_actions_zh_v1"


def main() -> None:
    """读取293个 Chunk，拼接文本并批量生成向量。"""

    # 复用现有清洗和分块代码，得到带来源信息的 Chunk 列表。
    chunks, _ = build_chunks_from_cleaned_corpus(CORPUS_ROOT)

    # 每个 Chunk 都保留标题、章节路径和正文，再交给 Embedding 模型。
    texts = [build_embedding_text(chunk) for chunk in chunks]

    settings = get_settings()
    try:
        adapter = BgeEmbeddingAdapter(
            settings.embedding_model,
            settings.embedding_cache_dir,
        )
    except EmbeddingModelLoadError as error:
        raise SystemExit(f"模型准备失败：{error}") from error

    # texts 的第 N 项和 vectors 的第 N 项严格对应同一个 Chunk。
    vectors = adapter.embed_documents(texts)

    if len(chunks) != len(texts) or len(texts) != len(vectors):
        raise RuntimeError(
            "Chunk、Embedding 文本和向量数量不一致，不能继续写入向量库。"
        )

    dimensions = {len(vector) for vector in vectors}
    if len(dimensions) != 1:
        raise RuntimeError("向量维度不一致，不能继续写入向量库。")

    first_chunk = chunks[0]
    print(f"Chunk 数量：{len(chunks)}")
    print(f"文本数量：{len(texts)}")
    print(f"向量数量：{len(vectors)}")
    print(f"向量维度：{dimensions.pop()}")
    print()
    print(f"第一条 Chunk ID：{first_chunk.chunk_id}")
    print(f"第一条标题：{first_chunk.title}")
    print(f"第一条章节：{' > '.join(first_chunk.section_path)}")
    print("第一条模型输入文本：")
    print(texts[0])
    print()
    print(f"第一条向量前五个数值：{vectors[0][:5]}")


if __name__ == "__main__":
    main()