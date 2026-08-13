"""Source/Baseline Manifest Reader 测试。"""

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from evidence_desk.rag.corpus.manifest import (
    ManifestValidationError,
    load_and_validate_manifests,
    read_source_manifest,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = PROJECT_ROOT / "data" / "knowledge_base" / "github_actions_zh_v1"


def copy_corpus_fixture(tmp_path: Path) -> Path:
    """复制测试需要的两个 Manifest 和33篇 Raw 文档。"""

    target = tmp_path / "github_actions_zh_v1"
    target.mkdir()
    shutil.copy2(CORPUS_ROOT / "manifest.json", target / "manifest.json")
    shutil.copy2(
        CORPUS_ROOT / "baseline_manifest.json",
        target / "baseline_manifest.json",
    )
    shutil.copytree(CORPUS_ROOT / "documents", target / "documents")
    return target


def update_json(path: Path, update: dict[str, Any]) -> None:
    """修改临时 JSON 顶层字段并保持 UTF-8 格式。"""

    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(update)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_load_and_validate_manifests_returns_real_baseline_documents() -> None:
    """真实语料应返回29篇纳入文档和4篇排除文档。"""

    result = load_and_validate_manifests(CORPUS_ROOT)

    assert result.document_count == 33
    assert result.included_document_count == 29
    assert result.excluded_document_count == 4
    assert all(document.baseline_included for document in result.included_documents)
    assert all(not document.baseline_included for document in result.excluded_documents)
    assert result.included_documents[0].title == "故障排除工作流"


def test_read_source_manifest_rejects_missing_manifest(tmp_path: Path) -> None:
    """Source Manifest 文件不存在时应给出明确错误。"""

    with pytest.raises(ManifestValidationError, match="无法读取 Source Manifest"):
        read_source_manifest(tmp_path / "manifest.json")


def test_read_source_manifest_uses_strict_field_types(tmp_path: Path) -> None:
    """冻结 Manifest 不应把字符串数量自动转换成整数。"""

    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads((CORPUS_ROOT / "manifest.json").read_text(encoding="utf-8"))
    manifest["document_count"] = "33"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ManifestValidationError, match="数据结构校验失败"):
        read_source_manifest(manifest_path)


def test_manifest_reader_rejects_declared_count_mismatch(tmp_path: Path) -> None:
    """JSON 声明的纳入数量与实际统计不一致时应失败。"""

    corpus_root = copy_corpus_fixture(tmp_path)
    update_json(
        corpus_root / "baseline_manifest.json",
        {"included_document_count": 28},
    )

    with pytest.raises(ManifestValidationError, match="声明的纳入数"):
        load_and_validate_manifests(corpus_root)


def test_manifest_reader_rejects_duplicate_document_id(tmp_path: Path) -> None:
    """Baseline 中出现重复 document_id 时应失败。"""

    corpus_root = copy_corpus_fixture(tmp_path)
    baseline_path = corpus_root / "baseline_manifest.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline["documents"][1]["document_id"] = baseline["documents"][0]["document_id"]
    baseline_path.write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ManifestValidationError, match="重复的 document_id"):
        load_and_validate_manifests(corpus_root)


def test_manifest_reader_rejects_missing_raw_document(tmp_path: Path) -> None:
    """Manifest 登记的 Raw 文档不存在时应失败。"""

    corpus_root = copy_corpus_fixture(tmp_path)
    source = read_source_manifest(corpus_root / "manifest.json")
    missing_path = corpus_root / source.documents[0].relative_path
    missing_path.unlink()

    with pytest.raises(ManifestValidationError, match="Raw 文档不存在"):
        load_and_validate_manifests(corpus_root)


def test_manifest_reader_rejects_changed_raw_hash(tmp_path: Path) -> None:
    """Raw 文档内容变化导致 SHA-256 不一致时应失败。"""

    corpus_root = copy_corpus_fixture(tmp_path)
    source = read_source_manifest(corpus_root / "manifest.json")
    changed_path = corpus_root / source.documents[0].relative_path
    changed_path.write_text(
        changed_path.read_text(encoding="utf-8") + "\n被测试修改的内容\n",
        encoding="utf-8",
    )

    with pytest.raises(ManifestValidationError, match="Raw 文档哈希不一致"):
        load_and_validate_manifests(corpus_root)
