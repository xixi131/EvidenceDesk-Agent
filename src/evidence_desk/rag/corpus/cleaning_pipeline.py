"""生成 Cleaned 文档和 Cleaning Report。"""

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from evidence_desk.rag.corpus.cleaner import (
    CLEANING_RULES_VERSION,
    clean_documents,
)
from evidence_desk.rag.corpus.manifest import (
    load_and_validate_manifests,
)
from evidence_desk.rag.corpus.markdown_loader import (
    load_markdown_documents,
)
from evidence_desk.rag.models import (
    CleaningDocumentReport,
    CleaningReport,
)

CLEANING_REPORT_VERSION = "github-actions-cleaning-report-v1"
CLEANED_DIRECTORY_NAME = "cleaned"
CLEANING_REPORT_RELATIVE_PATH = Path("reports/cleaning_report.json")


class CleaningPipelineError(ValueError):
    """Cleaned 文档或 Cleaning Report 生成失败。"""


def generate_cleaned_corpus(
    corpus_root: Path,
) -> CleaningReport:
    """读取、清洗并保存第一次中文 Baseline 的29篇文档。"""

    manifests = load_and_validate_manifests(corpus_root)

    parsed_documents = load_markdown_documents(
        corpus_root=corpus_root,
        source_dataset_version=(manifests.source_manifest.dataset_version),
        documents=manifests.included_documents,
    )

    cleaning_results = clean_documents(parsed_documents)

    if len(parsed_documents) != len(cleaning_results):
        raise CleaningPipelineError("Cleaner 输入数量与输出数量不一致")

    cleaned_root = corpus_root / CLEANED_DIRECTORY_NAME

    # cleaned/ 是根据 Raw 重新生成的派生目录。
    # 每次运行前删除旧目录，避免残留过期文件。
    if cleaned_root.exists():
        shutil.rmtree(cleaned_root)

    cleaned_root.mkdir(parents=True)

    document_reports: list[CleaningDocumentReport] = []

    for result in cleaning_results:
        source_relative_path = Path(result.source_relative_path)

        try:
            document_relative_path = source_relative_path.relative_to("documents")
        except ValueError as error:
            raise CleaningPipelineError(
                f"Raw 文档路径不在 documents/ 目录中：{result.source_relative_path}"
            ) from error

        cleaned_relative_path = Path(CLEANED_DIRECTORY_NAME) / document_relative_path

        cleaned_path = corpus_root / cleaned_relative_path
        cleaned_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        resolved_cleaned_root = cleaned_root.resolve()
        resolved_cleaned_path = cleaned_path.resolve()

        try:
            resolved_cleaned_path.relative_to(resolved_cleaned_root)
        except ValueError as error:
            raise CleaningPipelineError(
                f"Cleaned 文档路径越出 cleaned/ 目录：{cleaned_relative_path}"
            ) from error

        cleaned_path.write_text(
            result.cleaned_content,
            encoding="utf-8",
        )

        document_reports.append(
            CleaningDocumentReport(
                source_document_id=(result.source_document_id),
                source_relative_path=(result.source_relative_path),
                cleaned_relative_path=(cleaned_relative_path.as_posix()),
                source_sha256=result.source_sha256,
                cleaned_sha256=result.cleaned_sha256,
                removed_svg_count=(result.removed_svg_count),
                replaced_svg_label_count=(result.replaced_svg_label_count),
                removed_html_tag_count=(result.removed_html_tag_count),
                converted_link_count=(result.converted_link_count),
                converted_callout_count=(result.converted_callout_count),
                warnings=result.warnings,
            )
        )

    written_files = list(cleaned_root.rglob("*.md"))

    if len(written_files) != len(cleaning_results):
        raise CleaningPipelineError("Cleaned 文件数量与 Cleaner 结果数量不一致")

    report = CleaningReport(
        report_version=CLEANING_REPORT_VERSION,
        source_dataset_version=(manifests.source_manifest.dataset_version),
        baseline_version=(manifests.baseline_manifest.baseline_version),
        cleaning_rules_version=CLEANING_RULES_VERSION,
        generated_at=datetime.now(UTC),
        cleaned_output_directory=(f"{CLEANED_DIRECTORY_NAME}/"),
        input_document_count=len(parsed_documents),
        output_document_count=len(cleaning_results),
        removed_svg_count=sum(result.removed_svg_count for result in cleaning_results),
        replaced_svg_label_count=sum(
            result.replaced_svg_label_count for result in cleaning_results
        ),
        removed_html_tag_count=sum(
            result.removed_html_tag_count for result in cleaning_results
        ),
        converted_link_count=sum(
            result.converted_link_count for result in cleaning_results
        ),
        converted_callout_count=sum(
            result.converted_callout_count for result in cleaning_results
        ),
        warning_document_count=sum(
            bool(result.warnings) for result in cleaning_results
        ),
        documents=document_reports,
    )

    report_path = corpus_root / CLEANING_REPORT_RELATIVE_PATH
    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_json = json.dumps(
        report.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
    )

    report_path.write_text(
        report_json + "\n",
        encoding="utf-8",
    )

    return report
