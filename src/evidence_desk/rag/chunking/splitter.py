"""Chunking 门面：调度可替换的 Section 切分策略。"""

from collections.abc import Sequence

from evidence_desk.rag.models import Section

from .contracts import ChunkingStrategy
from .strategies import (
    ChunkingConfig,
    StructureThenRecursiveChunkingStrategy,
)

DEFAULT_CHUNKING_STRATEGY: ChunkingStrategy = StructureThenRecursiveChunkingStrategy()


def split_section_content(
    section: Section,
    strategy: ChunkingStrategy = DEFAULT_CHUNKING_STRATEGY,
) -> list[str]:
    """使用注入的策略切分一个 Section，不让调用方依赖具体算法。"""

    return strategy.split_section_content(section)


def split_sections_content(
    sections: Sequence[Section],
    strategy: ChunkingStrategy = DEFAULT_CHUNKING_STRATEGY,
) -> list[str]:
    """使用同一个策略切分多个 Section，且不跨 Section 拼接。"""

    chunks: list[str] = []
    for section in sections:
        chunks.extend(strategy.split_section_content(section))
    return chunks


__all__ = [
    "ChunkingConfig",
    "ChunkingStrategy",
    "DEFAULT_CHUNKING_STRATEGY",
    "StructureThenRecursiveChunkingStrategy",
    "split_section_content",
    "split_sections_content",
]
