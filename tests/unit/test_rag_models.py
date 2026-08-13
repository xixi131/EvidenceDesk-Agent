"""RAG 数据模型测试。"""

from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from evidence_desk.rag.models import (
    BaselineDocumentSelection,
    BaselineManifest,
    CleaningResult,
    CleaningWarning,
    ParsedDocument,
    SourceDocument,
    SourceManifest,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = PROJECT_ROOT / "data" / "knowledge_base" / "github_actions_zh_v1"
SOURCE_MANIFEST_PATH = CORPUS_ROOT / "manifest.json"
BASELINE_MANIFEST_PATH = CORPUS_ROOT / "baseline_manifest.json"


def load_source_manifest() -> SourceManifest:
    """读取真实 Source Manifest 并转换成 Pydantic 对象。"""

    manifest_json = SOURCE_MANIFEST_PATH.read_text(encoding="utf-8")
    return SourceManifest.model_validate_json(manifest_json)


def load_baseline_manifest() -> BaselineManifest:
    """读取真实 Baseline Manifest 并转换成 Pydantic 对象。"""

    manifest_json = BASELINE_MANIFEST_PATH.read_text(encoding="utf-8")
    return BaselineManifest.model_validate_json(manifest_json)


def test_source_manifest_can_load_real_data() -> None:
    """真实 manifest.json 可以转换成 SourceManifest。"""

    manifest = load_source_manifest()

    assert manifest.dataset_version == "github-actions-zh-2026-08-05-v1"
    assert manifest.document_count == 33
    assert len(manifest.documents) == 33

    first_document = manifest.documents[0]

    assert first_document.title == "故障排除工作流"
    assert first_document.byte_size == 16068


def test_baseline_manifest_can_load_real_data() -> None:
    """真实 baseline_manifest.json 可以转换成 BaselineManifest。"""

    manifest = load_baseline_manifest()

    assert manifest.baseline_version == "github-actions-zh-baseline-v1"
    assert manifest.source_dataset_version == "github-actions-zh-2026-08-05-v1"
    assert manifest.embedding_baseline.model == "BAAI/bge-small-zh-v1.5"
    assert manifest.document_count == 33
    assert manifest.included_document_count == 29
    assert manifest.excluded_document_count == 4
    assert len(manifest.documents) == 33
    assert sum(document.baseline_included for document in manifest.documents) == 29

    excluded_document = next(
        document for document in manifest.documents if not document.baseline_included
    )
    assert excluded_document.language_profile == "english_dominant"
    assert excluded_document.future_experiment == (
        "github-actions-multilingual-reference-v1"
    )


def test_source_document_rejects_invalid_sha256() -> None:
    """SourceDocument 应拒绝格式错误的 SHA-256。"""

    manifest = load_source_manifest()
    document_data = manifest.documents[0].model_dump()
    document_data["sha256"] = "错误的哈希"

    with pytest.raises(ValidationError):
        SourceDocument.model_validate(document_data)


def test_baseline_document_rejects_invalid_source_sha256() -> None:
    """BaselineDocumentSelection 应拒绝格式错误的 Raw 哈希。"""

    manifest = load_baseline_manifest()
    document_data = manifest.documents[0].model_dump()
    document_data["source_sha256"] = "invalid"

    with pytest.raises(ValidationError):
        BaselineDocumentSelection.model_validate(document_data)


def test_source_document_rejects_unknown_field() -> None:
    """SourceDocument 应拒绝未定义字段。"""

    manifest = load_source_manifest()
    document_data = manifest.documents[0].model_dump()
    document_data["unknown_field"] = "不应该出现的字段"

    with pytest.raises(ValidationError):
        SourceDocument.model_validate(document_data)


def test_parsed_document_and_cleaning_result_preserve_traceability() -> None:
    """Loader 输出和 Cleaner 结果应保留同一篇 Raw 文档的追溯信息。"""

    baseline = load_baseline_manifest()
    selection = baseline.documents[0]
    raw_content = (CORPUS_ROOT / selection.source_relative_path).read_text(
        encoding="utf-8"
    )
    parsed_document = ParsedDocument(
        source_dataset_version=baseline.source_dataset_version,
        source_document_id=selection.document_id,
        title=selection.title,
        source_url=selection.source_url,
        source_relative_path=selection.source_relative_path,
        source_sha256=selection.source_sha256,
        content=raw_content,
        risk_flags=selection.risk_flags,
    )
    cleaned_content = parsed_document.content.rstrip() + "\n"
    warning = CleaningWarning(
        code="HTML_VISIBLE_TEXT_REVIEW",
        message="删除标签后保留了可见文本，需要人工抽查。",
        line_number=12,
    )
    result = CleaningResult(
        source_dataset_version=parsed_document.source_dataset_version,
        source_document_id=parsed_document.source_document_id,
        source_relative_path=parsed_document.source_relative_path,
        source_sha256=parsed_document.source_sha256,
        cleaning_rules_version=baseline.cleaning_rules_version,
        cleaned_content=cleaned_content,
        cleaned_sha256=sha256(cleaned_content.encode("utf-8")).hexdigest(),
        removed_svg_count=0,
        replaced_svg_label_count=0,
        removed_html_tag_count=1,
        converted_link_count=0,
        converted_callout_count=0,
        warnings=[warning],
    )

    assert parsed_document.source_document_id == selection.document_id
    assert result.source_document_id == parsed_document.source_document_id
    assert result.source_sha256 == parsed_document.source_sha256
    assert result.cleaning_rules_version == "github-actions-cleaning-v1"
    assert result.warnings[0].line_number == 12


def test_cleaning_models_reject_empty_content_and_invalid_count() -> None:
    """清洗模型应拒绝空正文和负数变更统计。"""

    baseline = load_baseline_manifest()
    selection = baseline.documents[0]

    with pytest.raises(ValidationError):
        ParsedDocument(
            source_dataset_version=baseline.source_dataset_version,
            source_document_id=selection.document_id,
            title=selection.title,
            source_url=selection.source_url,
            source_relative_path=selection.source_relative_path,
            source_sha256=selection.source_sha256,
            content="",
            risk_flags=selection.risk_flags,
        )

    with pytest.raises(ValidationError):
        CleaningResult(
            source_dataset_version=baseline.source_dataset_version,
            source_document_id=selection.document_id,
            source_relative_path=selection.source_relative_path,
            source_sha256=selection.source_sha256,
            cleaning_rules_version=baseline.cleaning_rules_version,
            cleaned_content="正文",
            cleaned_sha256=sha256("正文".encode()).hexdigest(),
            removed_svg_count=-1,
            replaced_svg_label_count=0,
            removed_html_tag_count=0,
            converted_link_count=0,
            converted_callout_count=0,
            warnings=[],
        )
