"""Chunking 领域的可替换协议。"""

from typing import Protocol

from evidence_desk.rag.models import Section


class ChunkingStrategy(Protocol):
    """一个可以把 Section 正文切成 Chunk 正文的策略。"""

    @property
    def strategy_name(self) -> str:
        """可记录的策略名称。"""
        ...

    @property
    def strategy_version(self) -> str:
        """可记录的策略实现版本。"""
        ...

    def split_section_content(self, section: Section) -> list[str]:
        """将一个 Section 切成不跨章节的 Chunk 正文。"""
        ...
