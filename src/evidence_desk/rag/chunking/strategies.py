"""Chunking 策略的具体实现。"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar

from evidence_desk.rag.models import Section

DEFAULT_SEPARATORS: tuple[str, ...] = (
    "\n\n",
    "\n",
    "。",
    "！",
    "？",
    "；",
    "，",
    " ",
    "",
)
_FENCE_PATTERN = re.compile(r"^\s*(`{3,}|~{3,})")
_PROTECTED_IDENTIFIER_PATTERN = re.compile(
    r"[A-Z][A-Z0-9_]{2,}"
    r"|[A-Za-z_][A-Za-z0-9_-]*(?:/[A-Za-z_][A-Za-z0-9_-]*)+"
)


@dataclass(frozen=True)
class _MarkdownBlock:
    """Markdown 中的普通文本块或完整代码块。"""

    content: str
    is_code_block: bool


@dataclass(frozen=True)
class ChunkingConfig:
    """第一次 Chunk Baseline 使用的切分配置。"""

    chunk_size: int = 600
    chunk_overlap: int = 80
    separators: tuple[str, ...] = DEFAULT_SEPARATORS

    def __post_init__(self) -> None:
        if self.chunk_size <= 0:
            raise ValueError("chunk_size 必须大于0")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap 不能小于0")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap 必须小于 chunk_size")
        if not self.separators:
            raise ValueError("separators 不能为空")
        if self.separators[-1] != "":
            raise ValueError("最后一个 separator 必须是空字符串")


class StructureThenRecursiveChunkingStrategy:
    """先尊重 Section，再按分隔符递归切分超长正文。"""

    _STRATEGY_NAME: ClassVar[str] = "structure_then_recursive"
    _STRATEGY_VERSION: ClassVar[str] = "structure-then-recursive-v1"

    @property
    def strategy_name(self) -> str:
        return self._STRATEGY_NAME

    @property
    def strategy_version(self) -> str:
        return self._STRATEGY_VERSION

    def __init__(self, config: ChunkingConfig | None = None) -> None:
        self.config = config or ChunkingConfig()

    def split_section_content(self, section: Section) -> list[str]:
        """使用当前配置切分一个 Section，并保护完整代码块。"""

        units: list[_MarkdownBlock] = []
        for block in _extract_markdown_blocks(section.section_content):
            if block.is_code_block:
                units.append(block)
                continue

            units.extend(
                _MarkdownBlock(content=unit, is_code_block=False)
                for unit in _recursive_units(
                    block.content,
                    chunk_size=self.config.chunk_size,
                    separators=self.config.separators,
                )
            )

        return _apply_overlap(
            units,
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
        )


def _extract_markdown_blocks(text: str) -> list[_MarkdownBlock]:
    """将 Markdown 分为普通文本块和完整代码围栏块。"""

    blocks: list[_MarkdownBlock] = []
    text_lines: list[str] = []
    code_lines: list[str] = []
    fence_marker: str | None = None

    def flush_text() -> None:
        text_content = "".join(text_lines).strip()
        if text_content:
            blocks.append(_MarkdownBlock(text_content, is_code_block=False))
        text_lines.clear()

    for line in text.splitlines(keepends=True):
        fence_match = _FENCE_PATTERN.match(line)

        if fence_marker is not None:
            code_lines.append(line)
            if fence_match and fence_match.group(1)[0] == fence_marker[0]:
                if len(fence_match.group(1)) >= len(fence_marker):
                    blocks.append(
                        _MarkdownBlock(
                            "".join(code_lines).strip(),
                            is_code_block=True,
                        )
                    )
                    code_lines.clear()
                    fence_marker = None
            continue

        if fence_match:
            flush_text()
            fence_marker = fence_match.group(1)
            code_lines.append(line)
            continue

        text_lines.append(line)

    if fence_marker is not None:
        blocks.append(
            _MarkdownBlock(
                "".join(code_lines).strip(),
                is_code_block=True,
            )
        )
    flush_text()
    return blocks


def _find_separator(text: str, separators: Sequence[str]) -> tuple[int, str] | None:
    """找到当前文本中最优先、且实际出现的分隔符。"""

    for index, separator in enumerate(separators):
        if separator == "" or separator in text:
            return index, separator
    return None


def _recursive_units(
    text: str,
    *,
    chunk_size: int,
    separators: Sequence[str],
) -> list[str]:
    """递归寻找不超过 chunk_size 的自然文本单元。"""

    normalized_text = text.strip()
    if not normalized_text:
        return []
    if len(normalized_text) <= chunk_size:
        return [normalized_text]

    separator_info = _find_separator(normalized_text, separators)
    if separator_info is None:
        return _safe_character_units(normalized_text, chunk_size)

    separator_index, separator = separator_info
    if separator == "":
        return _safe_character_units(normalized_text, chunk_size)

    parts = normalized_text.split(separator)
    units: list[str] = []
    buffer: list[str] = []

    for raw_part in parts:
        part = raw_part.strip()
        if not part:
            continue

        if len(part) > chunk_size:
            if buffer:
                units.append(separator.join(buffer))
                buffer = []
            units.extend(
                _recursive_units(
                    part,
                    chunk_size=chunk_size,
                    separators=separators[separator_index + 1 :],
                )
            )
            continue

        candidate = separator.join([*buffer, part])
        if len(candidate) <= chunk_size:
            buffer.append(part)
        else:
            if buffer:
                units.append(separator.join(buffer))
            buffer = [part]

    if buffer:
        units.append(separator.join(buffer))

    return units


def _safe_character_units(text: str, chunk_size: int) -> list[str]:
    """按字符兜底切分，但尽量不切断关键技术标识符。"""

    protected_ranges = [
        match.span() for match in _PROTECTED_IDENTIFIER_PATTERN.finditer(text)
    ]
    units: list[str] = []
    start = 0

    while start < len(text):
        ideal_end = min(start + chunk_size, len(text))
        end = ideal_end

        for protected_start, protected_end in protected_ranges:
            if protected_start < ideal_end < protected_end:
                if protected_start > start:
                    end = protected_start
                else:
                    end = protected_end
                break

        if end <= start:
            end = ideal_end

        units.append(text[start:end].strip())
        start = end

    return [unit for unit in units if unit]


def _apply_overlap(
    units: Sequence[_MarkdownBlock],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """给普通文本块增加上下文重叠，但不切开或复制半截代码块。"""

    if not units:
        return []

    chunks: list[str] = []
    previous_text_chunk: str | None = None

    for unit in units:
        if unit.is_code_block:
            chunks.append(unit.content)
            previous_text_chunk = None
            continue

        if previous_text_chunk is None:
            current_chunk = unit.content
        else:
            available_overlap = min(
                chunk_overlap,
                max(0, chunk_size - len(unit.content) - 1),
            )
            overlap_text = (
                previous_text_chunk[-available_overlap:] if available_overlap else ""
            )
            current_chunk = (
                f"{overlap_text}\n{unit.content}" if overlap_text else unit.content
            )

        chunks.append(current_chunk)
        previous_text_chunk = current_chunk

    return chunks
