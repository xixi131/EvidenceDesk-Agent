"""从 Cleaned 文档生成第一次 Baseline 的 Chunk Quality Report。"""

import json
from pathlib import Path

from evidence_desk.rag.chunking.chunk_builder import build_chunks
from evidence_desk.rag.chunking.quality_report import build_chunk_quality_report
from evidence_desk.rag.chunking.section_extractor import extract_sections
from evidence_desk.rag.chunking.strategies import (
    ChunkingConfig,
    StructureThenRecursiveChunkingStrategy,
)
from evidence_desk.rag.corpus.manifest import (
    ManifestReadResult,
    load_and_validate_manifests,
)
from evidence_desk.rag.models import Chunk, ChunkQualityReport

CHUNK_CONFIG_VERSION = "structure-then-recursive-600-80-v1"
CHUNK_QUALITY_REPORT_RELATIVE_PATH = Path("reports/chunk_report_600_80.json")


class ChunkQualityPipelineError(ValueError):
    """读取 Cleaned 文档或生成 Chunk Quality Report 失败。"""


def generate_chunk_quality_report(corpus_root: Path) -> ChunkQualityReport:
    """将29篇 Cleaned 文档切块，并保存600/80配置的质量报告。"""

    chunks, manifests = build_chunks_from_cleaned_corpus(corpus_root)
    config = ChunkingConfig()

    report = build_chunk_quality_report(
        chunks,
        baseline_version=manifests.baseline_manifest.baseline_version,
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        source_relative_path_by_document={
            document.document_id: _cleaned_path(
                corpus_root,
                document.source_relative_path,
            )
            .relative_to(corpus_root)
            .as_posix()
            for document in manifests.included_documents
        },
    )
    report_path = corpus_root / CHUNK_QUALITY_REPORT_RELATIVE_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def build_chunks_from_cleaned_corpus(
    corpus_root: Path,
) -> tuple[list[Chunk], ManifestReadResult]:
    """使用固定 Baseline 配置，从 Cleaned 语料重新生成 Chunk。"""

    manifests = load_and_validate_manifests(corpus_root)
    config = ChunkingConfig()
    strategy = StructureThenRecursiveChunkingStrategy(config)
    chunks: list[Chunk] = []

    for document in manifests.included_documents:
        cleaned_path = _cleaned_path(corpus_root, document.source_relative_path)
        try:
            cleaned_content = cleaned_path.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise ChunkQualityPipelineError(
                f"Cleaned 文档不存在：{cleaned_path.relative_to(corpus_root)}"
            ) from error
        except UnicodeDecodeError as error:
            raise ChunkQualityPipelineError(
                f"Cleaned 文档不是有效的 UTF-8：{cleaned_path.relative_to(corpus_root)}"
            ) from error
        except OSError as error:
            raise ChunkQualityPipelineError(
                f"Cleaned 文档读取失败：{cleaned_path.relative_to(corpus_root)}"
            ) from error

        sections = extract_sections(
            content=cleaned_content,
            title=document.title,
            source_document_id=document.document_id,
            source_url=document.source_url,
        )
        chunks.extend(
            build_chunks(
                sections,
                dataset_version=manifests.source_manifest.dataset_version,
                cleaning_rules_version=manifests.baseline_manifest.cleaning_rules_version,
                chunk_config_version=CHUNK_CONFIG_VERSION,
                strategy=strategy,
            )
        )

    return chunks, manifests


def _cleaned_path(corpus_root: Path, source_relative_path: str) -> Path:
    """将 documents/ 下的 Raw 相对路径映射到 cleaned/ 下的派生文档。"""

    try:
        document_relative_path = Path(source_relative_path).relative_to("documents")
    except ValueError as error:
        raise ChunkQualityPipelineError(
            f"Raw 文档路径不在 documents/ 目录中：{source_relative_path}"
        ) from error

    cleaned_path = corpus_root / "cleaned" / document_relative_path
    try:
        cleaned_path.resolve().relative_to((corpus_root / "cleaned").resolve())
    except ValueError as error:
        raise ChunkQualityPipelineError(
            f"Cleaned 文档路径越出 cleaned/ 目录：{source_relative_path}"
        ) from error

    return cleaned_path
