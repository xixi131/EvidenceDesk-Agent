"""读取并校验冻结的 Source/Baseline Manifest。"""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from pydantic import ValidationError

from evidence_desk.rag.models import (
    BaselineDocumentSelection,
    BaselineManifest,
    SourceDocument,
    SourceManifest,
)

EXPECTED_DATASET_VERSION = "github-actions-zh-2026-08-05-v1"
EXPECTED_BASELINE_VERSION = "github-actions-zh-baseline-v1"
EXPECTED_CLEANING_RULES_VERSION = "github-actions-cleaning-v1"
EXPECTED_SOURCE_COUNT = 33
EXPECTED_INCLUDED_COUNT = 29
EXPECTED_EXCLUDED_COUNT = 4


class ManifestValidationError(ValueError):
    """Manifest 缺失、格式错误或与冻结数据不一致。"""


@dataclass(frozen=True, slots=True)
class ManifestReadResult:
    """校验通过后交给后续 Loader 使用的 Manifest 结果。"""

    source_manifest: SourceManifest
    baseline_manifest: BaselineManifest
    included_documents: tuple[BaselineDocumentSelection, ...]
    excluded_documents: tuple[BaselineDocumentSelection, ...]

    @property
    def document_count(self) -> int:
        """返回 Source Dataset 文档总数。"""

        return len(self.baseline_manifest.documents)

    @property
    def included_document_count(self) -> int:
        """返回第一次中文 Baseline 纳入文档数。"""

        return len(self.included_documents)

    @property
    def excluded_document_count(self) -> int:
        """返回第一次中文 Baseline 排除文档数。"""

        return len(self.excluded_documents)


def read_source_manifest(path: Path) -> SourceManifest:
    """读取 Source Manifest，并执行 Pydantic 结构校验。"""

    try:
        json_text = path.read_text(encoding="utf-8")
        return SourceManifest.model_validate_json(json_text, strict=True)
    except OSError as error:
        raise ManifestValidationError(f"无法读取 Source Manifest：{path}") from error
    except ValidationError as error:
        raise ManifestValidationError("Source Manifest 数据结构校验失败") from error


def read_baseline_manifest(path: Path) -> BaselineManifest:
    """读取 Baseline Manifest，并执行 Pydantic 结构校验。"""

    try:
        json_text = path.read_text(encoding="utf-8")
        return BaselineManifest.model_validate_json(json_text, strict=True)
    except OSError as error:
        raise ManifestValidationError(f"无法读取 Baseline Manifest：{path}") from error
    except ValidationError as error:
        raise ManifestValidationError("Baseline Manifest 数据结构校验失败") from error


def load_and_validate_manifests(corpus_root: Path) -> ManifestReadResult:
    """读取两个 Manifest，校验冻结规则，并返回29篇 Baseline 文档。"""

    source_manifest = read_source_manifest(corpus_root / "manifest.json")
    baseline_manifest = read_baseline_manifest(corpus_root / "baseline_manifest.json")

    _validate_versions(source_manifest, baseline_manifest)
    _validate_source_counts(source_manifest)
    included_documents, excluded_documents = _validate_baseline_counts(
        baseline_manifest
    )
    source_documents_by_id = _validate_unique_source_ids(source_manifest)
    baseline_documents_by_id = _validate_unique_baseline_ids(baseline_manifest)
    _validate_document_sets(source_documents_by_id, baseline_documents_by_id)
    _validate_selection_policy(baseline_manifest, excluded_documents)
    _validate_source_metadata(source_documents_by_id, baseline_documents_by_id)
    _validate_raw_files(corpus_root, source_documents_by_id)

    return ManifestReadResult(
        source_manifest=source_manifest,
        baseline_manifest=baseline_manifest,
        included_documents=included_documents,
        excluded_documents=excluded_documents,
    )


def _validate_versions(
    source_manifest: SourceManifest,
    baseline_manifest: BaselineManifest,
) -> None:
    if source_manifest.dataset_version != EXPECTED_DATASET_VERSION:
        raise ManifestValidationError("Source Dataset 版本与冻结版本不一致")
    if baseline_manifest.baseline_version != EXPECTED_BASELINE_VERSION:
        raise ManifestValidationError("Baseline 版本与冻结版本不一致")
    if baseline_manifest.source_dataset_version != source_manifest.dataset_version:
        raise ManifestValidationError("Baseline 引用的 Source Dataset 版本不一致")
    if baseline_manifest.cleaning_rules_version != EXPECTED_CLEANING_RULES_VERSION:
        raise ManifestValidationError("Baseline 清洗规则版本与冻结版本不一致")
    if (
        baseline_manifest.source_repository_commit
        != source_manifest.source_repository_commit
    ):
        raise ManifestValidationError("两个 Manifest 的来源仓库 Commit 不一致")


def _validate_source_counts(manifest: SourceManifest) -> None:
    actual_count = len(manifest.documents)
    if manifest.document_count != actual_count:
        raise ManifestValidationError("Source 声明的文档数与实际记录数不一致")
    if actual_count != EXPECTED_SOURCE_COUNT:
        raise ManifestValidationError(
            f"Source 文档总数必须是 {EXPECTED_SOURCE_COUNT}，实际是 {actual_count}"
        )


def _validate_baseline_counts(
    manifest: BaselineManifest,
) -> tuple[
    tuple[BaselineDocumentSelection, ...],
    tuple[BaselineDocumentSelection, ...],
]:
    included_documents = tuple(
        document for document in manifest.documents if document.baseline_included
    )
    excluded_documents = tuple(
        document for document in manifest.documents if not document.baseline_included
    )
    actual_count = len(manifest.documents)

    if manifest.document_count != actual_count:
        raise ManifestValidationError("Baseline 声明的文档数与实际记录数不一致")
    if actual_count != EXPECTED_SOURCE_COUNT:
        raise ManifestValidationError(
            f"Baseline 文档总数必须是 {EXPECTED_SOURCE_COUNT}，实际是 {actual_count}"
        )
    if manifest.included_document_count != len(included_documents):
        raise ManifestValidationError("Baseline 声明的纳入数与实际统计不一致")
    if manifest.excluded_document_count != len(excluded_documents):
        raise ManifestValidationError("Baseline 声明的排除数与实际统计不一致")
    if len(included_documents) != EXPECTED_INCLUDED_COUNT:
        raise ManifestValidationError(
            "Baseline 实际纳入文档数必须是 "
            f"{EXPECTED_INCLUDED_COUNT}，实际是 {len(included_documents)}"
        )
    if len(excluded_documents) != EXPECTED_EXCLUDED_COUNT:
        raise ManifestValidationError(
            "Baseline 实际排除文档数必须是 "
            f"{EXPECTED_EXCLUDED_COUNT}，实际是 {len(excluded_documents)}"
        )

    return included_documents, excluded_documents


def _validate_unique_source_ids(
    manifest: SourceManifest,
) -> dict[str, SourceDocument]:
    documents_by_id = {
        document.document_id: document for document in manifest.documents
    }
    if len(documents_by_id) != len(manifest.documents):
        raise ManifestValidationError("Source Manifest 存在重复的 document_id")
    return documents_by_id


def _validate_unique_baseline_ids(
    manifest: BaselineManifest,
) -> dict[str, BaselineDocumentSelection]:
    documents_by_id = {
        document.document_id: document for document in manifest.documents
    }
    if len(documents_by_id) != len(manifest.documents):
        raise ManifestValidationError("Baseline Manifest 存在重复的 document_id")
    return documents_by_id


def _validate_document_sets(
    source_documents_by_id: dict[str, SourceDocument],
    baseline_documents_by_id: dict[str, BaselineDocumentSelection],
) -> None:
    source_ids = set(source_documents_by_id)
    baseline_ids = set(baseline_documents_by_id)
    if source_ids != baseline_ids:
        missing_ids = sorted(source_ids - baseline_ids)
        unexpected_ids = sorted(baseline_ids - source_ids)
        raise ManifestValidationError(
            "Source 和 Baseline 文档集合不一致："
            f"missing={missing_ids}, unexpected={unexpected_ids}"
        )


def _validate_selection_policy(
    manifest: BaselineManifest,
    excluded_documents: tuple[BaselineDocumentSelection, ...],
) -> None:
    actual_excluded_ids = {document.document_id for document in excluded_documents}
    policy_excluded_ids = set(manifest.selection_policy.excluded_document_ids)
    if len(policy_excluded_ids) != len(manifest.selection_policy.excluded_document_ids):
        raise ManifestValidationError("Selection Policy 存在重复的排除文档编号")
    if policy_excluded_ids != actual_excluded_ids:
        raise ManifestValidationError("Selection Policy 与实际排除文档不一致")

    for document in manifest.documents:
        if document.baseline_included:
            if (
                document.exclusion_reason is not None
                or document.future_experiment is not None
            ):
                raise ManifestValidationError(
                    f"纳入文档不应有排除原因或后续实验：{document.document_id}"
                )
        elif document.exclusion_reason is None or document.future_experiment is None:
            raise ManifestValidationError(
                f"排除文档缺少原因或后续实验：{document.document_id}"
            )


def _validate_source_metadata(
    source_documents_by_id: dict[str, SourceDocument],
    baseline_documents_by_id: dict[str, BaselineDocumentSelection],
) -> None:
    for document_id, source_document in source_documents_by_id.items():
        baseline_document = baseline_documents_by_id[document_id]
        if source_document.title != baseline_document.title:
            raise ManifestValidationError(f"文档标题不一致：{document_id}")
        if source_document.relative_path != baseline_document.source_relative_path:
            raise ManifestValidationError(f"文档相对路径不一致：{document_id}")
        if source_document.public_url != baseline_document.source_url:
            raise ManifestValidationError(f"文档来源地址不一致：{document_id}")
        if source_document.sha256 != baseline_document.source_sha256:
            raise ManifestValidationError(f"文档哈希登记不一致：{document_id}")


def _validate_raw_files(
    corpus_root: Path,
    source_documents_by_id: dict[str, SourceDocument],
) -> None:
    resolved_corpus_root = corpus_root.resolve()
    for document in source_documents_by_id.values():
        raw_path = (resolved_corpus_root / document.relative_path).resolve()
        try:
            raw_path.relative_to(resolved_corpus_root)
        except ValueError as error:
            raise ManifestValidationError(
                f"Raw 文档路径越出语料目录：{document.document_id}"
            ) from error

        if not raw_path.is_file():
            raise ManifestValidationError(f"Raw 文档不存在：{document.relative_path}")

        actual_sha256 = sha256(raw_path.read_bytes()).hexdigest()
        if actual_sha256 != document.sha256:
            raise ManifestValidationError(f"Raw 文档哈希不一致：{document.document_id}")
