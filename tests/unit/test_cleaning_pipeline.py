"""Cleaning Pipeline 测试。"""

import json
import shutil
from pathlib import Path

from evidence_desk.rag.corpus.cleaning_pipeline import (
    generate_cleaned_corpus,
)
from evidence_desk.rag.corpus.manifest import read_source_manifest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_CORPUS_ROOT = PROJECT_ROOT / "data" / "knowledge_base" / "github_actions_zh_v1"


def copy_corpus_fixture(tmp_path: Path) -> Path:
    """复制生成 Cleaned 文档所需的冻结语料。"""

    corpus_root = tmp_path / "github_actions_zh_v1"
    corpus_root.mkdir()

    shutil.copy2(
        SOURCE_CORPUS_ROOT / "manifest.json",
        corpus_root / "manifest.json",
    )
    shutil.copy2(
        SOURCE_CORPUS_ROOT / "baseline_manifest.json",
        corpus_root / "baseline_manifest.json",
    )
    shutil.copytree(
        SOURCE_CORPUS_ROOT / "documents",
        corpus_root / "documents",
    )

    return corpus_root


def test_generate_cleaned_corpus_writes_documents_and_report(
    tmp_path: Path,
) -> None:
    """Pipeline 应生成29篇 Cleaned 文档和一份报告。"""

    corpus_root = copy_corpus_fixture(tmp_path)
    source_manifest = read_source_manifest(corpus_root / "manifest.json")
    first_source_path = corpus_root / source_manifest.documents[0].relative_path
    original_raw_content = first_source_path.read_bytes()

    report = generate_cleaned_corpus(corpus_root)

    cleaned_files = list((corpus_root / "cleaned").rglob("*.md"))
    report_path = corpus_root / "reports" / "cleaning_report.json"

    assert report.input_document_count == 29
    assert report.output_document_count == 29
    assert report.warning_document_count == 0
    assert len(report.documents) == 29
    assert len(cleaned_files) == 29
    assert report_path.is_file()

    report_json = json.loads(report_path.read_text(encoding="utf-8"))

    assert report_json["input_document_count"] == 29
    assert report_json["output_document_count"] == 29
    assert len(report_json["documents"]) == 29

    # Pipeline 不能修改 Raw 文件。
    assert first_source_path.read_bytes() == (original_raw_content)

    first_cleaned_path = corpus_root / report.documents[0].cleaned_relative_path

    assert first_cleaned_path.is_file()
    assert first_cleaned_path.read_text(encoding="utf-8").startswith("# 故障排除工作流")
