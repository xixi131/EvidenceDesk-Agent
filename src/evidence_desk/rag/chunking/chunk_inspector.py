"""按 Chunk ID 查看可追溯 Chunk 正文。"""

from pathlib import Path

from evidence_desk.rag.chunking.chunk_quality_pipeline import (
    build_chunks_from_cleaned_corpus,
)
from evidence_desk.rag.models import Chunk


def find_chunk(corpus_root: Path, chunk_id: str) -> tuple[Chunk, str]:
    """按确定性 Chunk ID 找到 Chunk，并返回 Cleaned 文件相对路径。"""

    chunks, manifests = build_chunks_from_cleaned_corpus(corpus_root)
    chunk = next((item for item in chunks if item.chunk_id == chunk_id), None)
    if chunk is None:
        raise ValueError(f"找不到 Chunk：{chunk_id}")

    document = next(
        (
            item
            for item in manifests.included_documents
            if item.document_id == chunk.parent_doc_id
        ),
        None,
    )
    if document is None:
        raise ValueError(f"Chunk 找不到父文档：{chunk.parent_doc_id}")

    source_relative_path = (
        Path("cleaned") / Path(document.source_relative_path).relative_to("documents")
    ).as_posix()
    return chunk, source_relative_path


def format_chunk_for_review(chunk: Chunk, source_relative_path: str) -> str:
    """将 Chunk 格式化成适合终端和人工阅读的文本。"""

    section_path = " > ".join(chunk.section_path)
    return "\n".join(
        [
            f"chunk_id: {chunk.chunk_id}",
            f"source_relative_path: {source_relative_path}",
            f"section_path: {section_path}",
            f"source_url: {chunk.source_url}",
            f"content_length: {len(chunk.content)}",
            "",
            "----- Chunk 正文 -----",
            chunk.content,
            "----- 正文结束 -----",
        ]
    )
