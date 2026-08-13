"""Markdown Loader 测试。"""

import shutil
from pathlib import Path

import pytest

from evidence_desk.rag.corpus.manifest import load_and_validate_manifests
from evidence_desk.rag.corpus.markdown_loader import (
    MarkdownLoaderError,
    load_markdown_documents,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = PROJECT_ROOT / "data" / "knowledge_base" / "github_actions_zh_v1"


def test_loader_converts_real_baseline_documents() -> None:
    """Loader 应把真实29篇 Baseline 文档转换成 ParsedDocument。"""

    manifests = load_and_validate_manifests(CORPUS_ROOT)
    parsed_documents = load_markdown_documents(
        corpus_root=CORPUS_ROOT,
        source_dataset_version=manifests.source_manifest.dataset_version,
        documents=manifests.included_documents,
    )

    assert len(parsed_documents) == 29
    assert parsed_documents[0].source_document_id == (
        "github_actions_zh_actions__how-tos__troubleshoot-workflows"
    )
    assert parsed_documents[0].title == "故障排除工作流"
    assert parsed_documents[0].content.startswith("# 故障排除工作流")
    assert parsed_documents[0].source_sha256 == (
        manifests.included_documents[0].source_sha256
    )


def test_loader_does_not_modify_raw_document(tmp_path: Path) -> None:
    """Loader 只读取 Raw 文档，不应修改文件内容。"""

    corpus_root = tmp_path / "corpus"
    shutil.copytree(CORPUS_ROOT, corpus_root)
    manifests = load_and_validate_manifests(corpus_root)
    raw_path = corpus_root / manifests.included_documents[0].source_relative_path
    original_content = raw_path.read_bytes()

    load_markdown_documents(
        corpus_root=corpus_root,
        source_dataset_version=manifests.source_manifest.dataset_version,
        documents=manifests.included_documents[:1],
    )

    assert raw_path.read_bytes() == original_content


def test_loader_rejects_missing_markdown_file(tmp_path: Path) -> None:
    """Markdown 文件不存在时应返回 Loader 专用错误。"""

    manifests = load_and_validate_manifests(CORPUS_ROOT)
    missing_document = manifests.included_documents[0].model_copy(
        update={"source_relative_path": "documents/not-found.md"}
    )

    with pytest.raises(MarkdownLoaderError, match="Markdown 文档不存在"):
        load_markdown_documents(
            corpus_root=CORPUS_ROOT,
            source_dataset_version=manifests.source_manifest.dataset_version,
            documents=[missing_document],
        )


def test_loader_rejects_invalid_utf8_file(tmp_path: Path) -> None:
    """Markdown 文件不是 UTF-8 时应返回 Loader 专用错误。"""

    raw_path = tmp_path / "invalid.md"
    raw_path.write_bytes(b"# invalid\xff")
    manifests = load_and_validate_manifests(CORPUS_ROOT)
    invalid_document = manifests.included_documents[0].model_copy(
        update={"source_relative_path": "invalid.md"}
    )

    with pytest.raises(MarkdownLoaderError, match="不是有效的 UTF-8"):
        load_markdown_documents(
            corpus_root=tmp_path,
            source_dataset_version=manifests.source_manifest.dataset_version,
            documents=[invalid_document],
        )
