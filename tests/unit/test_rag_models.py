"""RAG 数据模型测试。"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from evidence_desk.rag.models import SourceDocument, SourceManifest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_MANIFEST_PATH = (
    PROJECT_ROOT / "data" / "knowledge_base" / "github_actions_zh_v1" / "manifest.json"
)


def load_source_manifest() -> SourceManifest:
    """读取真实 Source Manifest 并转换成 Pydantic 对象。"""

    manifest_json = SOURCE_MANIFEST_PATH.read_text(encoding="utf-8")
    return SourceManifest.model_validate_json(manifest_json)


def test_source_manifest_can_load_real_data() -> None:
    """真实 manifest.json 可以转换成 SourceManifest。"""

    manifest = load_source_manifest()

    assert manifest.dataset_version == "github-actions-zh-2026-08-05-v1"
    assert manifest.document_count == 33
    assert len(manifest.documents) == 33

    first_document = manifest.documents[0]

    assert first_document.title == "故障排除工作流"
    assert first_document.byte_size == 16068


def test_source_document_rejects_invalid_sha256() -> None:
    """SourceDocument 应拒绝格式错误的 SHA-256。"""

    manifest = load_source_manifest()
    document_data = manifest.documents[0].model_dump()
    document_data["sha256"] = "错误的哈希"

    with pytest.raises(ValidationError):
        SourceDocument.model_validate(document_data)


def test_source_document_rejects_unknown_field() -> None:
    """SourceDocument 应拒绝未定义字段。"""

    manifest = load_source_manifest()
    document_data = manifest.documents[0].model_dump()
    document_data["unknown_field"] = "不应该出现的字段"

    with pytest.raises(ValidationError):
        SourceDocument.model_validate(document_data)
