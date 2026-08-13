"""将 Section 和切块策略结果组装为最终 Chunk。"""

from collections.abc import Sequence

from evidence_desk.rag.models import Chunk, Section
from evidence_desk.rag.models.chunk import (
    build_chunk_id,
    calculate_content_hash,
)

from .contracts import ChunkingStrategy
from .splitter import DEFAULT_CHUNKING_STRATEGY


def build_chunks(
    sections: Sequence[Section],
    *,
    dataset_version: str,
    cleaning_rules_version: str,
    chunk_config_version: str,
    strategy: ChunkingStrategy = DEFAULT_CHUNKING_STRATEGY,
) -> list[Chunk]:
    """将多个 Section 切分并补齐最终 Chunk 的身份和追溯 Metadata。"""

    chunks: list[Chunk] = []
    next_index_by_document: dict[str, int] = {}

    for section in sections:
        section_contents = strategy.split_section_content(section)
        for content in section_contents:
            chunk_index = next_index_by_document.get(section.source_document_id, 0) + 1
            next_index_by_document[section.source_document_id] = chunk_index
            content_hash = calculate_content_hash(content)
            chunks.append(
                Chunk(
                    chunk_id=build_chunk_id(
                        parent_doc_id=section.source_document_id,
                        chunk_config_version=chunk_config_version,
                        chunk_index=chunk_index,
                        content_hash=content_hash,
                    ),
                    parent_doc_id=section.source_document_id,
                    title=section.title,
                    section_path=section.section_path,
                    content=content,
                    chunk_index=chunk_index,
                    content_hash=content_hash,
                    source_url=section.source_url,
                    dataset_version=dataset_version,
                    cleaning_rules_version=cleaning_rules_version,
                    chunk_config_version=chunk_config_version,
                )
            )

    return chunks
