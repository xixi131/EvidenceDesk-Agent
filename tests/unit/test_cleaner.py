"""Cleaner 测试。"""

from hashlib import sha256
from pathlib import Path

from evidence_desk.rag.corpus.cleaner import clean_document, clean_documents
from evidence_desk.rag.corpus.manifest import load_and_validate_manifests
from evidence_desk.rag.corpus.markdown_loader import load_markdown_documents
from evidence_desk.rag.models import ParsedDocument

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = PROJECT_ROOT / "data" / "knowledge_base" / "github_actions_zh_v1"


def build_document(content: str) -> ParsedDocument:
    """创建一篇用于测试的 ParsedDocument。"""

    return ParsedDocument(
        source_dataset_version="github-actions-zh-2026-08-05-v1",
        source_document_id="doc_test",
        title="测试文档",
        source_url="https://docs.github.com/zh/actions/test",
        source_relative_path="documents/test.md",
        source_sha256="a" * 64,
        content=content,
        risk_flags=[],
    )


def test_clean_document_transforms_text_outside_code() -> None:
    """代码块外应清洗，代码块内应原样保留。"""

    raw_content = (
        "# 测试文档\r\n"
        "\r\n"
        "> \\[!NOTE] 这是一条说明\r\n"
        "\r\n"
        "<span>普通正文</span>\r\n"
        "\r\n"
        '<svg aria-label="菜单图标"><path></path></svg>\r\n'
        "\r\n"
        "<svg><path></path></svg>\r\n"
        "\r\n"
        "[官方文档](/zh/actions/test#debug)\r\n"
        "\r\n"
        "```html\r\n"
        "<svg><path></path></svg>\r\n"
        "<span>代码示例</span>\r\n"
        "```\r\n"
    )

    document = build_document(raw_content)

    result = clean_document(document)
    outside_code_content = result.cleaned_content.split("```html", maxsplit=1)[0]

    assert "注意：" in result.cleaned_content
    assert "普通正文" in result.cleaned_content
    assert "<span>" not in outside_code_content
    assert "菜单图标" in result.cleaned_content
    assert "<svg><path></path></svg>" not in outside_code_content
    assert "https://docs.github.com/zh/actions/test#debug" in (result.cleaned_content)

    # 代码块中的 HTML 和 SVG 必须保留。
    assert "<svg><path></path></svg>" in result.cleaned_content
    assert "<span>代码示例</span>" in result.cleaned_content

    assert result.replaced_svg_label_count == 1
    assert result.removed_svg_count == 1
    assert result.removed_html_tag_count == 2
    assert result.converted_link_count == 1
    assert result.converted_callout_count == 1
    assert len(result.cleaned_sha256) == 64


def test_clean_document_keeps_source_traceability() -> None:
    """清洗结果应保留来源信息。"""

    document = build_document("# 原始标题\n\n原始正文\n")

    result = clean_document(document)

    assert result.source_dataset_version == document.source_dataset_version
    assert result.source_document_id == document.source_document_id
    assert result.source_relative_path == document.source_relative_path
    assert result.source_sha256 == document.source_sha256
    assert result.cleaning_rules_version == "github-actions-cleaning-v1"
    assert result.cleaned_content.startswith("# 原始标题")
    assert (
        result.cleaned_sha256
        == sha256(result.cleaned_content.encode("utf-8")).hexdigest()
    )


def test_clean_document_preserves_fenced_code_inside_list() -> None:
    """列表项中的围栏代码也应原样保留。"""

    document = build_document(
        "* ```\n  <span>列表中的代码示例</span>\n  ```\n\n<span>代码块外正文</span>\n"
    )

    result = clean_document(document)

    assert "<span>列表中的代码示例</span>" in result.cleaned_content
    assert "<span>代码块外正文</span>" not in result.cleaned_content
    assert "代码块外正文" in result.cleaned_content
    assert result.warnings == []


def test_clean_real_baseline_documents() -> None:
    """真实29篇 Baseline 文档应全部完成内存清洗。"""

    manifests = load_and_validate_manifests(CORPUS_ROOT)
    parsed_documents = load_markdown_documents(
        corpus_root=CORPUS_ROOT,
        source_dataset_version=manifests.source_manifest.dataset_version,
        documents=manifests.included_documents,
    )

    results = clean_documents(parsed_documents)

    assert len(results) == 29
    assert all(result.cleaned_content.strip() for result in results)
    assert all(len(result.cleaned_sha256) == 64 for result in results)
    assert all(result.warnings == [] for result in results)
