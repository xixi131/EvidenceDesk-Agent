"""将可追溯 Chunk 组装成用于向量检索的文本。"""

from evidence_desk.rag.models.chunk import Chunk


def build_embedding_text(chunk: Chunk) -> str:
    """保留标题、章节路径和正文，避免只对孤立正文生成向量。"""

    section_path = " > ".join(chunk.section_path)

    return "\n".join(
        [
            f"标题：{chunk.title}",
            f"章节：{section_path}",
            f"正文：{chunk.content}",
        ]
    )
