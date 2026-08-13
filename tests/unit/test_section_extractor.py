"""Section 提取器测试。"""

from pathlib import Path

import pytest

from evidence_desk.rag.chunking.section_extractor import (
    SectionExtractionError,
    extract_sections,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLEANED_DOCUMENT = (
    PROJECT_ROOT
    / "data"
    / "knowledge_base"
    / "github_actions_zh_v1"
    / "cleaned"
    / "actions"
    / "how-tos"
    / "monitor-workflows"
    / "enable-debug-logging.md"
)


def test_extract_sections_from_real_cleaned_document() -> None:
    """真实 Cleaned 文档应按标题层级提取 Section。"""

    sections = extract_sections(
        content=CLEANED_DOCUMENT.read_text(encoding="utf-8"),
        title="启用调试日志记录",
        source_document_id="actions-how-tos-monitor-workflows-enable-debug-logging",
        source_url="https://docs.github.com/zh/actions/how-tos/monitor-workflows/enable-debug-logging",
    )

    assert [section.section_path for section in sections] == [
        ["启用调试日志记录"],
        ["启用调试日志记录", "启用运行程序诊断日志"],
        ["启用调试日志记录", "启用步骤调试日志"],
    ]
    assert "ACTIONS_RUNNER_DEBUG" in sections[1].section_content
    assert "ACTIONS_STEP_DEBUG" in sections[2].section_content
    assert all(section.source_document_id for section in sections)
    assert all(section.source_url.startswith("https://") for section in sections)


def test_heading_like_text_inside_fenced_code_is_not_a_section() -> None:
    """代码围栏中的井号只能作为代码内容，不能改变标题路径。"""

    sections = extract_sections(
        content=(
            "# 示例文档\n\n"
            "## 配置\n\n"
            "```yaml\n"
            "# 这是 YAML 注释，不是 Markdown 标题\n"
            "name: demo\n"
            "```\n\n"
            "配置结束。\n"
        ),
        title="示例文档",
        source_document_id="demo",
        source_url="https://example.com/demo",
    )

    assert len(sections) == 1
    assert sections[0].section_path == ["示例文档", "配置"]
    assert "# 这是 YAML 注释，不是 Markdown 标题" in sections[0].section_content


def test_same_level_heading_replaces_previous_section_path_tail() -> None:
    """同级 Heading 应结束上一节，并替换路径中的同级标题。"""

    sections = extract_sections(
        content=(
            "# 根标题\n\n"
            "## 第一节\n\n"
            "### 子节\n\n"
            "子节正文。\n\n"
            "## 第二节\n\n"
            "第二节正文。\n"
        ),
        title="根标题",
        source_document_id="demo",
        source_url="https://example.com/demo",
    )

    assert [section.section_path for section in sections] == [
        ["根标题", "第一节", "子节"],
        ["根标题", "第二节"],
    ]


def test_document_without_non_empty_section_is_rejected() -> None:
    """没有标题正文的 Markdown 不应静默产生空 Section。"""

    with pytest.raises(SectionExtractionError, match="没有可提取的非空 Section"):
        extract_sections(
            content="# 只有标题\n",
            title="只有标题",
            source_document_id="demo",
            source_url="https://example.com/demo",
        )


def test_extract_all_real_cleaned_baseline_documents() -> None:
    """29篇真实 Cleaned Baseline 文档都应至少产生一个 Section。"""

    import json

    baseline = json.loads(
        (
            PROJECT_ROOT
            / "data"
            / "knowledge_base"
            / "github_actions_zh_v1"
            / "baseline_manifest.json"
        ).read_text(encoding="utf-8")
    )
    included_documents = [
        document for document in baseline["documents"] if document["baseline_included"]
    ]
    corpus_root = PROJECT_ROOT / "data" / "knowledge_base" / "github_actions_zh_v1"

    assert len(included_documents) == 29

    for document in included_documents:
        raw_relative_path = Path(document["source_relative_path"])
        cleaned_relative_path = Path("cleaned") / raw_relative_path.relative_to(
            "documents"
        )
        sections = extract_sections(
            content=(corpus_root / cleaned_relative_path).read_text(encoding="utf-8"),
            title=document["title"],
            source_document_id=document["document_id"],
            source_url=document["source_url"],
        )

        assert sections
        assert all(section.section_content.strip() for section in sections)
        assert all(
            section.source_document_id == document["document_id"]
            for section in sections
        )
        assert all(section.source_url == document["source_url"] for section in sections)
