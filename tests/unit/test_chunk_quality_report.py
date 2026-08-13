"""Chunk Quality Report 测试。"""

import json
from pathlib import Path

import pytest

from evidence_desk.rag.chunking.chunk_inspector import (
    find_chunk,
    format_chunk_for_review,
)
from evidence_desk.rag.chunking.chunk_quality_pipeline import (
    CHUNK_CONFIG_VERSION,
    generate_chunk_quality_report,
)
from evidence_desk.rag.chunking.quality_report import build_chunk_quality_report
from evidence_desk.rag.models import Chunk
from evidence_desk.rag.models.chunk import build_chunk_id, calculate_content_hash

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = PROJECT_ROOT / "data" / "knowledge_base" / "github_actions_zh_v1"


def build_chunk(
    content: str,
    *,
    parent_doc_id: str = "demo-document",
    chunk_index: int = 1,
) -> Chunk:
    """构造带完整追溯信息的测试 Chunk。"""

    content_hash = calculate_content_hash(content)
    return Chunk(
        chunk_id=build_chunk_id(
            parent_doc_id=parent_doc_id,
            chunk_config_version="test-600-80-v1",
            chunk_index=chunk_index,
            content_hash=content_hash,
        ),
        parent_doc_id=parent_doc_id,
        title="测试文档",
        section_path=["测试文档", "测试章节"],
        content=content,
        chunk_index=chunk_index,
        content_hash=content_hash,
        source_url="https://example.com/demo",
        dataset_version="dataset-v1",
        cleaning_rules_version="cleaning-v1",
        chunk_config_version="test-600-80-v1",
    )


def test_report_calculates_lengths_duplicates_and_document_counts() -> None:
    """报告应汇总长度、重复正文和每篇文档的 Chunk 数。"""

    chunks = [
        build_chunk("甲" * 20, chunk_index=1),
        build_chunk("乙" * 100, chunk_index=2),
        build_chunk("丙" * 200, parent_doc_id="second-document", chunk_index=1),
        build_chunk("乙" * 100, parent_doc_id="second-document", chunk_index=2),
    ]

    report = build_chunk_quality_report(
        chunks,
        baseline_version="baseline-v1",
        chunk_size=600,
        chunk_overlap=80,
    )

    assert report.document_count == 2
    assert report.chunk_count == 4
    assert report.min_chunk_length == 20
    assert report.max_chunk_length == 200
    assert report.average_chunk_length == 105
    assert report.p50_chunk_length == 100
    assert report.p95_chunk_length == 200
    assert report.short_chunk_count == 1
    assert report.long_chunk_count == 0
    assert report.duplicate_content_hash_count == 1
    assert report.duplicate_chunk_id_count == 0
    assert report.chunk_count_by_document == {
        "demo-document": 2,
        "second-document": 2,
    }


def test_report_warns_about_oversized_or_unclosed_code_blocks() -> None:
    """完整但超长的代码块与未闭合代码围栏都需要留警告。"""

    oversized_code = "```yaml\n" + "ACTIONS_STEP_DEBUG: true\n" * 30 + "```"
    unclosed_code = "```bash\necho hello"

    report = build_chunk_quality_report(
        [
            build_chunk(oversized_code, chunk_index=1),
            build_chunk(unclosed_code, chunk_index=2),
        ],
        baseline_version="baseline-v1",
        chunk_size=100,
        chunk_overlap=0,
    )

    assert report.long_chunk_count == 1
    assert [warning.code for warning in report.code_block_warnings] == [
        "OVERSIZED_CODE_BLOCK",
        "UNCLOSED_CODE_FENCE",
    ]


def test_report_rejects_mixed_chunk_configurations() -> None:
    """不同配置生成的 Chunk 不能混入同一报告。"""

    first = build_chunk("第一段", chunk_index=1)
    second = first.model_copy(update={"chunk_config_version": "another-config-v1"})

    with pytest.raises(ValueError, match="不能混合"):
        build_chunk_quality_report(
            [first, second],
            baseline_version="baseline-v1",
            chunk_size=600,
            chunk_overlap=80,
        )


def test_pipeline_generates_report_from_real_cleaned_corpus() -> None:
    """29篇真实 Cleaned 文档应生成可读取的600/80质量报告。"""

    report = generate_chunk_quality_report(CORPUS_ROOT)
    report_path = CORPUS_ROOT / "reports" / "chunk_report_600_80.json"
    report_json = json.loads(report_path.read_text(encoding="utf-8"))

    assert report.document_count == 29
    assert report.chunk_count == sum(report.chunk_count_by_document.values())
    assert report.chunk_config_version == CHUNK_CONFIG_VERSION
    assert report.long_chunk_count >= len(
        [
            warning
            for warning in report.code_block_warnings
            if warning.code == "OVERSIZED_CODE_BLOCK"
        ]
    )
    assert all(
        warning.source_relative_path is not None
        and warning.section_path
        and warning.source_url.startswith("https://")
        for warning in report.code_block_warnings
    )
    assert report_json["chunk_count"] == report.chunk_count
    assert report_json["chunk_count_by_document"] == report.chunk_count_by_document


def test_inspector_finds_a_real_warning_chunk() -> None:
    """查看工具应能按报告中的真实 ID 找回正文和路径。"""

    report = generate_chunk_quality_report(CORPUS_ROOT)
    warning = report.code_block_warnings[0]
    chunk, source_relative_path = find_chunk(CORPUS_ROOT, warning.chunk_id)
    formatted = format_chunk_for_review(chunk, source_relative_path)

    assert chunk.chunk_id == warning.chunk_id
    assert source_relative_path == warning.source_relative_path
    assert chunk.content in formatted
