"""从 Cleaned Markdown 文档中提取带标题路径的 Section。"""

import re
from collections.abc import Iterator

from evidence_desk.rag.models import Section

_HEADING_PATTERN = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
_FENCE_PATTERN = re.compile(r"^\s*(`{3,}|~{3,})")


class SectionExtractionError(ValueError):
    """Cleaned Markdown 无法提取 Section。"""


def _iter_lines(content: str) -> Iterator[str]:
    """逐行读取正文，同时保留换行前的文本。"""

    yield from content.splitlines()


def extract_sections(
    *,
    content: str,
    title: str,
    source_document_id: str,
    source_url: str,
) -> list[Section]:
    """从一篇 Cleaned Markdown 文档中提取 Section。

    标题只在代码围栏外识别。遇到新的 Heading 时，先保存之前积累的正文，
    再根据 Heading 层级更新标题路径。
    """

    sections: list[Section] = []
    current_path: list[str] = []
    current_level = 0
    current_content: list[str] = []
    fence_marker: str | None = None

    def flush_current_section() -> None:
        section_content = "\n".join(current_content).strip()
        if not current_path or not section_content:
            return

        sections.append(
            Section(
                title=title,
                section_path=current_path.copy(),
                section_content=section_content,
                source_document_id=source_document_id,
                source_url=source_url,
            )
        )

    for line in _iter_lines(content):
        fence_match = _FENCE_PATTERN.match(line)

        if fence_marker is not None:
            current_content.append(line)
            if fence_match and fence_match.group(1)[0] == fence_marker[0]:
                if len(fence_match.group(1)) >= len(fence_marker):
                    fence_marker = None
            continue

        if fence_match:
            fence_marker = fence_match.group(1)
            current_content.append(line)
            continue

        heading_match = _HEADING_PATTERN.match(line)
        if heading_match:
            flush_current_section()

            heading_level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()
            if not heading_text:
                raise SectionExtractionError("Heading 不能没有标题文字")

            if heading_level <= current_level:
                current_path = current_path[: heading_level - 1]

            current_path.append(heading_text)
            current_level = heading_level
            current_content = []
            continue

        current_content.append(line)

    flush_current_section()

    if not sections:
        raise SectionExtractionError(
            f"文档没有可提取的非空 Section：{source_document_id}"
        )

    return sections
