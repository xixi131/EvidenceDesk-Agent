"""生成 Chunk Quality Report。"""

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from evidence_desk.rag.models import Chunk, ChunkQualityReport, ChunkQualityWarning

DEFAULT_SHORT_CHUNK_THRESHOLD = 100
CHUNK_QUALITY_REPORT_VERSION = "github-actions-chunk-quality-report-v1"
_FENCE_PATTERN = re.compile(r"^\s*(`{3,}|~{3,})")


def build_chunk_quality_report(
    chunks: Sequence[Chunk],
    *,
    baseline_version: str,
    chunk_size: int,
    chunk_overlap: int,
    short_chunk_threshold: int = DEFAULT_SHORT_CHUNK_THRESHOLD,
    source_relative_path_by_document: Mapping[str, str] | None = None,
) -> ChunkQualityReport:
    """把最终 Chunk 汇总为可检查的质量报告。"""

    if not chunks:
        raise ValueError("无法为零个 Chunk 生成质量报告")
    if short_chunk_threshold <= 0:
        raise ValueError("short_chunk_threshold 必须大于0")

    _validate_shared_metadata(chunks)

    lengths = [len(chunk.content) for chunk in chunks]
    content_hash_counts = Counter(chunk.content_hash for chunk in chunks)
    chunk_id_counts = Counter(chunk.chunk_id for chunk in chunks)
    chunk_count_by_document = Counter(chunk.parent_doc_id for chunk in chunks)

    first_chunk = chunks[0]
    return ChunkQualityReport(
        report_version=CHUNK_QUALITY_REPORT_VERSION,
        source_dataset_version=first_chunk.dataset_version,
        baseline_version=baseline_version,
        cleaning_rules_version=first_chunk.cleaning_rules_version,
        chunk_config_version=first_chunk.chunk_config_version,
        generated_at=datetime.now(UTC),
        document_count=len(chunk_count_by_document),
        chunk_count=len(chunks),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        min_chunk_length=min(lengths),
        max_chunk_length=max(lengths),
        average_chunk_length=sum(lengths) / len(lengths),
        p50_chunk_length=_nearest_rank(lengths, 0.50),
        p95_chunk_length=_nearest_rank(lengths, 0.95),
        short_chunk_threshold=short_chunk_threshold,
        short_chunk_count=sum(length < short_chunk_threshold for length in lengths),
        long_chunk_count=sum(length > chunk_size for length in lengths),
        duplicate_content_hash_count=_extra_duplicate_count(content_hash_counts),
        duplicate_chunk_id_count=_extra_duplicate_count(chunk_id_counts),
        chunk_count_by_document=dict(sorted(chunk_count_by_document.items())),
        code_block_warnings=_find_code_block_warnings(
            chunks,
            chunk_size,
            source_relative_path_by_document=source_relative_path_by_document,
        ),
    )


def _validate_shared_metadata(chunks: Sequence[Chunk]) -> None:
    """同一份报告不能混合不同数据或配置生成的 Chunk。"""

    first_chunk = chunks[0]
    expected_metadata = (
        first_chunk.dataset_version,
        first_chunk.cleaning_rules_version,
        first_chunk.chunk_config_version,
    )

    for chunk in chunks[1:]:
        metadata = (
            chunk.dataset_version,
            chunk.cleaning_rules_version,
            chunk.chunk_config_version,
        )
        if metadata != expected_metadata:
            raise ValueError("一份质量报告不能混合不同数据或切块配置的 Chunk")


def _nearest_rank(values: Sequence[int], percentile: float) -> int:
    """使用项目已有的最近位置规则计算长度分位数。"""

    ordered_values = sorted(values)
    index = round((len(ordered_values) - 1) * percentile)
    return ordered_values[index]


def _extra_duplicate_count(counts: Counter[str]) -> int:
    """统计重复项中除首次出现外的额外数量。"""

    return sum(count - 1 for count in counts.values() if count > 1)


def _find_code_block_warnings(
    chunks: Sequence[Chunk],
    chunk_size: int,
    *,
    source_relative_path_by_document: Mapping[str, str] | None,
) -> list[ChunkQualityWarning]:
    """找出完整代码块超长或代码围栏未闭合的 Chunk。"""

    warnings: list[ChunkQualityWarning] = []

    for chunk in chunks:
        fence_marker = _code_fence_marker(chunk.content)
        if fence_marker is None:
            continue

        if not _has_closing_fence(chunk.content, fence_marker):
            warnings.append(
                ChunkQualityWarning(
                    code="UNCLOSED_CODE_FENCE",
                    message="代码围栏没有闭合，无法确认代码块是否完整。",
                    chunk_id=chunk.chunk_id,
                    parent_doc_id=chunk.parent_doc_id,
                    source_relative_path=(
                        source_relative_path_by_document.get(chunk.parent_doc_id)
                        if source_relative_path_by_document is not None
                        else None
                    ),
                    section_path=chunk.section_path,
                    source_url=chunk.source_url,
                    content_length=len(chunk.content),
                )
            )
        elif len(chunk.content) > chunk_size:
            warnings.append(
                ChunkQualityWarning(
                    code="OVERSIZED_CODE_BLOCK",
                    message="完整代码块超过字符上限，已保留原样等待人工查看。",
                    chunk_id=chunk.chunk_id,
                    parent_doc_id=chunk.parent_doc_id,
                    source_relative_path=(
                        source_relative_path_by_document.get(chunk.parent_doc_id)
                        if source_relative_path_by_document is not None
                        else None
                    ),
                    section_path=chunk.section_path,
                    source_url=chunk.source_url,
                    content_length=len(chunk.content),
                )
            )

    return warnings


def _code_fence_marker(content: str) -> str | None:
    """仅识别以代码围栏开头的完整代码块 Chunk。"""

    first_line = content.splitlines()[0]
    match = _FENCE_PATTERN.match(first_line)
    return match.group(1) if match else None


def _has_closing_fence(content: str, opening_marker: str) -> bool:
    """确认同类且长度足够的代码围栏是否在后续行闭合。"""

    for line in content.splitlines()[1:]:
        match = _FENCE_PATTERN.match(line)
        if match and match.group(1)[0] == opening_marker[0]:
            if len(match.group(1)) >= len(opening_marker):
                return True
    return False
