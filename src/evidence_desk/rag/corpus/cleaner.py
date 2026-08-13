"""对 Raw Markdown 执行确定性的文本清洗。"""

import re
from collections.abc import Sequence
from hashlib import sha256
from re import Match

from evidence_desk.rag.models import (
    CleaningResult,
    CleaningWarning,
    ParsedDocument,
)

CLEANING_RULES_VERSION = "github-actions-cleaning-v1"
DOCS_BASE_URL = "https://docs.github.com"

CALLOUT_LABELS = {
    "NOTE": "注意：",
    "WARNING": "警告：",
    "CAUTION": "谨慎：",
    "IMPORTANT": "重要：",
}

CALLOUT_PATTERN = re.compile(
    r"\\\[!(NOTE|WARNING|CAUTION|IMPORTANT)\]",
    re.IGNORECASE,
)

RELATIVE_LINK_PATTERN = re.compile(
    r"\]\((?P<path>/(?:zh|en)/[^)\s]*)\)",
)

SVG_PATTERN = re.compile(
    r"<svg\b(?P<attributes>[^>]*)>.*?</svg\s*>",
    re.IGNORECASE | re.DOTALL,
)

SVG_LABEL_PATTERN = re.compile(
    r"""(?:aria-label|title)\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE,
)

# 这里只处理常见的普通 HTML 标签。
# <owner>、<repo> 这类文档占位符不能被当成 HTML 删除。
HTML_TAG_PATTERN = re.compile(
    r"""</?(?:a|abbr|b|br|button|code|div|em|figcaption|figure|
    i|img|kbd|label|li|mark|ol|p|pre|small|span|strong|sub|sup|
    table|tbody|td|th|thead|tr|u|ul)
    (?:\s[^<>]*)?\s*/?>""",
    re.IGNORECASE | re.VERBOSE,
)

# GitHub Docs 的围栏代码块既可能直接以 ``` 开头，
# 也可能位于列表项中，例如：* ```。
CODE_FENCE_PATTERN = re.compile(
    r"^[ \t]*(?:(?:[-+*]|\d+[.)])[ \t]+)?(?:`{3,}|~{3,})",
)


class CleanerError(ValueError):
    """Cleaner 无法生成有效清洗结果。"""


def _clean_outside_code(
    text: str,
    stats: dict[str, int],
    warnings: list[CleaningWarning],
) -> str:
    """只清洗代码围栏外的普通 Markdown 文本。"""

    def replace_callout(match: Match[str]) -> str:
        callout_name = match.group(1).upper()
        return f"{CALLOUT_LABELS[callout_name]} "

    text, callout_count = CALLOUT_PATTERN.subn(
        replace_callout,
        text,
    )
    stats["converted_callout_count"] += callout_count

    def replace_link(match: Match[str]) -> str:
        relative_path = match.group("path")
        return f"]({DOCS_BASE_URL}{relative_path})"

    text, link_count = RELATIVE_LINK_PATTERN.subn(
        replace_link,
        text,
    )
    stats["converted_link_count"] += link_count

    def replace_svg(match: Match[str]) -> str:
        attributes = match.group("attributes")
        label_match = SVG_LABEL_PATTERN.search(attributes)

        if label_match is not None:
            stats["replaced_svg_label_count"] += 1
            return label_match.group(1).strip()

        stats["removed_svg_count"] += 1
        return ""

    text = SVG_PATTERN.sub(replace_svg, text)

    if re.search(r"<svg\b", text, re.IGNORECASE):
        warnings.append(
            CleaningWarning(
                code="UNMATCHED_SVG",
                message="发现没有完整闭合的 SVG，保留原文供人工抽查。",
            )
        )

    text, html_tag_count = HTML_TAG_PATTERN.subn(
        "",
        text,
    )
    stats["removed_html_tag_count"] += html_tag_count

    # 删除每一行末尾的空格和制表符。
    lines = text.split("\n")
    lines = [line.rstrip(" \t") for line in lines]
    text = "\n".join(lines)

    # 连续三个以上换行压缩成两个换行。
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text


def clean_document(
    document: ParsedDocument,
    cleaning_rules_version: str = CLEANING_RULES_VERSION,
) -> CleaningResult:
    """清洗一篇 ParsedDocument，并返回带追溯信息的结果。"""

    stats = {
        "removed_svg_count": 0,
        "replaced_svg_label_count": 0,
        "removed_html_tag_count": 0,
        "converted_link_count": 0,
        "converted_callout_count": 0,
    }
    warnings: list[CleaningWarning] = []

    # 第一步：统一换行。
    normalized_content = document.content.replace("\r\n", "\n")
    normalized_content = normalized_content.replace("\r", "\n")

    cleaned_parts: list[str] = []
    outside_code_lines: list[str] = []
    in_code_block = False
    lines = normalized_content.splitlines(keepends=True)

    for line in lines:
        is_code_fence = CODE_FENCE_PATTERN.match(line) is not None

        if is_code_fence:
            if not in_code_block:
                # 即将进入代码块，先处理之前积累的普通文本。
                if outside_code_lines:
                    outside_text = "".join(outside_code_lines)
                    cleaned_parts.append(
                        _clean_outside_code(
                            outside_text,
                            stats,
                            warnings,
                        )
                    )
                    outside_code_lines = []

                # 代码围栏本身保留。
                cleaned_parts.append(line)
                in_code_block = True
            else:
                # 代码围栏结束，结束标记也原样保留。
                cleaned_parts.append(line)
                in_code_block = False

        elif in_code_block:
            # 代码围栏内部完全保留，不清洗 HTML、SVG 或空格。
            cleaned_parts.append(line)

        else:
            # 暂时收集普通文本，遇到代码块边界时统一处理。
            outside_code_lines.append(line)

    # 处理文件末尾最后一段普通文本。
    if outside_code_lines:
        outside_text = "".join(outside_code_lines)
        cleaned_parts.append(
            _clean_outside_code(
                outside_text,
                stats,
                warnings,
            )
        )

    if in_code_block:
        warnings.append(
            CleaningWarning(
                code="UNCLOSED_CODE_FENCE",
                message="文档中存在没有闭合的代码围栏，代码内容已保留。",
                line_number=len(lines),
            )
        )

    cleaned_content = "".join(cleaned_parts).rstrip() + "\n"

    if not cleaned_content.strip():
        raise CleanerError(f"清洗后正文为空：{document.source_document_id}")

    cleaned_sha256 = sha256(cleaned_content.encode("utf-8")).hexdigest()

    return CleaningResult(
        source_dataset_version=document.source_dataset_version,
        source_document_id=document.source_document_id,
        source_relative_path=document.source_relative_path,
        source_sha256=document.source_sha256,
        cleaning_rules_version=cleaning_rules_version,
        cleaned_content=cleaned_content,
        cleaned_sha256=cleaned_sha256,
        removed_svg_count=stats["removed_svg_count"],
        replaced_svg_label_count=stats["replaced_svg_label_count"],
        removed_html_tag_count=stats["removed_html_tag_count"],
        converted_link_count=stats["converted_link_count"],
        converted_callout_count=stats["converted_callout_count"],
        warnings=warnings,
    )


def clean_documents(
    documents: Sequence[ParsedDocument],
    cleaning_rules_version: str = CLEANING_RULES_VERSION,
) -> list[CleaningResult]:
    """清洗多篇 ParsedDocument。"""

    return [
        clean_document(
            document,
            cleaning_rules_version=cleaning_rules_version,
        )
        for document in documents
    ]
