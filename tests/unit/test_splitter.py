"""结构优先 + 递归分块测试。"""

from pathlib import Path

import pytest

from evidence_desk.rag.chunking.splitter import (
    ChunkingConfig,
    StructureThenRecursiveChunkingStrategy,
    split_section_content,
    split_sections_content,
)
from evidence_desk.rag.models import Section

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def build_section(content: str) -> Section:
    """构造测试用 Section。"""

    return Section(
        title="示例文档",
        section_path=["示例文档", "配置"],
        section_content=content,
        source_document_id="demo",
        source_url="https://example.com/demo",
    )


def test_short_section_stays_as_one_chunk() -> None:
    """不超过限制的 Section 不应被无意义拆分。"""

    section = build_section("ACTIONS_STEP_DEBUG 设置为 true。")

    chunks = split_section_content(
        section,
        StructureThenRecursiveChunkingStrategy(
            ChunkingConfig(chunk_size=600, chunk_overlap=80)
        ),
    )

    assert chunks == ["ACTIONS_STEP_DEBUG 设置为 true。"]


def test_long_section_prefers_paragraph_boundaries() -> None:
    """长 Section 应优先在段落边界切分。"""

    section = build_section(
        "第一段说明。" * 20
        + "\n\n"
        + "第二段说明。" * 20
        + "\n\n"
        + "第三段说明。" * 20
    )
    strategy = StructureThenRecursiveChunkingStrategy(
        ChunkingConfig(chunk_size=100, chunk_overlap=10)
    )

    chunks = split_section_content(section, strategy)

    assert len(chunks) >= 3
    assert all(len(chunk) <= 100 for chunk in chunks)
    assert "第一段说明。" in chunks[0]
    assert "第三段说明。" in chunks[-1]


def test_long_single_paragraph_falls_back_to_smaller_separators() -> None:
    """单段过长时应继续从句子边界递归切分。"""

    section = build_section("启用调试日志。" * 80)
    strategy = StructureThenRecursiveChunkingStrategy(
        ChunkingConfig(chunk_size=60, chunk_overlap=10)
    )

    chunks = split_section_content(section, strategy)

    assert len(chunks) > 1
    assert all(0 < len(chunk) <= 60 for chunk in chunks)


def test_overlap_preserves_previous_chunk_tail() -> None:
    """相邻 Chunk 应保留前一块尾部的有限上下文。"""

    section = build_section("甲" * 80 + "\n\n" + "乙" * 80)
    strategy = StructureThenRecursiveChunkingStrategy(
        ChunkingConfig(chunk_size=100, chunk_overlap=20)
    )

    chunks = split_section_content(section, strategy)

    assert len(chunks) == 2
    # 换行本身也占1个字符，因此在100字符上限内保留19个正文字符。
    assert chunks[1].startswith("甲" * 19 + "\n")
    assert len(chunks[1]) <= 100


def test_multiple_sections_are_never_joined() -> None:
    """不同 Section 之间不能为了凑长度而拼接。"""

    sections = [build_section("第一节内容"), build_section("第二节内容")]
    strategy = StructureThenRecursiveChunkingStrategy(
        ChunkingConfig(chunk_size=100, chunk_overlap=20)
    )

    chunks = split_sections_content(sections, strategy)

    assert chunks == ["第一节内容", "第二节内容"]


def test_invalid_chunking_config_is_rejected() -> None:
    """切块参数必须满足基本边界。"""

    with pytest.raises(ValueError, match="chunk_overlap 必须小于 chunk_size"):
        ChunkingConfig(chunk_size=80, chunk_overlap=80)


def test_splitter_accepts_a_fake_strategy() -> None:
    """调用方可以注入 Fake 策略，而不依赖递归实现。"""

    class FakeStrategy:
        strategy_name = "fake"
        strategy_version = "fake-v1"

        def split_section_content(self, section: Section) -> list[str]:
            return [f"FAKE::{section.section_content}"]

    sections = [build_section("需要验证的正文")]

    chunks = split_sections_content(sections, FakeStrategy())

    assert chunks == ["FAKE::需要验证的正文"]


def test_build_chunks_adds_traceable_metadata_and_stable_id() -> None:
    """Chunk Builder 应保留 Section 追溯信息并生成稳定身份。"""

    from evidence_desk.rag.chunking.chunk_builder import build_chunks

    sections = [build_section("第一节内容。"), build_section("第二节内容。")]
    kwargs = {
        "dataset_version": "dataset-v1",
        "cleaning_rules_version": "cleaning-v1",
        "chunk_config_version": "recursive-600-80-v1",
    }

    first_run = build_chunks(sections, **kwargs)
    second_run = build_chunks(sections, **kwargs)

    assert [chunk.chunk_id for chunk in first_run] == [
        chunk.chunk_id for chunk in second_run
    ]
    assert [chunk.chunk_index for chunk in first_run] == [1, 2]
    assert first_run[0].parent_doc_id == "demo"
    assert first_run[0].section_path == ["示例文档", "配置"]
    assert first_run[0].content_hash == calculate_content_hash_for_test(
        first_run[0].content
    )


def calculate_content_hash_for_test(content: str) -> str:
    """测试中调用公共哈希函数，避免重复实现哈希算法。"""

    from evidence_desk.rag.models.chunk import calculate_content_hash

    return calculate_content_hash(content)


def test_chunk_config_version_changes_chunk_id() -> None:
    """切块配置版本变化时不能复用旧 Chunk ID。"""

    from evidence_desk.rag.chunking.chunk_builder import build_chunks

    sections = [build_section("同一段正文。")]
    common = {
        "dataset_version": "dataset-v1",
        "cleaning_rules_version": "cleaning-v1",
    }

    baseline_chunks = build_chunks(
        sections,
        **common,
        chunk_config_version="recursive-600-80-v1",
    )
    experiment_chunks = build_chunks(
        sections,
        **common,
        chunk_config_version="recursive-800-100-v1",
    )

    assert baseline_chunks[0].content == experiment_chunks[0].content
    assert baseline_chunks[0].chunk_id != experiment_chunks[0].chunk_id


def test_chunk_index_restarts_for_each_parent_document() -> None:
    """Chunk 顺序应在每个父文档内独立编号。"""

    from evidence_desk.rag.chunking.chunk_builder import build_chunks

    first_document = build_section("第一篇正文。")
    second_document = first_document.model_copy(
        update={
            "source_document_id": "another-document",
            "source_url": "https://example.com/another-document",
        }
    )

    chunks = build_chunks(
        [first_document, second_document],
        dataset_version="dataset-v1",
        cleaning_rules_version="cleaning-v1",
        chunk_config_version="recursive-600-80-v1",
    )

    assert [chunk.chunk_index for chunk in chunks] == [1, 1]
    assert chunks[0].chunk_id != chunks[1].chunk_id


def test_fenced_code_block_is_kept_whole_and_not_overlapped() -> None:
    """代码围栏应作为完整单元，且不复制半截代码作为 overlap。"""

    code_block = (
        "```yaml\nenv:\n  ACTIONS_STEP_DEBUG: true\n  GITHUB_TOKEN: secret\n```"
    )
    section = build_section(f"说明文字。\n\n{code_block}\n\n结论文字。")
    strategy = StructureThenRecursiveChunkingStrategy(
        ChunkingConfig(chunk_size=30, chunk_overlap=10)
    )

    chunks = split_section_content(section, strategy)

    assert code_block in chunks
    assert chunks.count(code_block) == 1
    assert chunks[0] == "说明文字。"
    assert chunks[-1] == "结论文字。"


def test_long_code_block_is_not_silently_cut() -> None:
    """超过 Chunk 长度的代码块也不能被普通字符切分。"""

    code_block = "```yaml\n" + "ACTIONS_STEP_DEBUG: true\n" * 20 + "```"
    section = build_section(code_block)
    strategy = StructureThenRecursiveChunkingStrategy(
        ChunkingConfig(chunk_size=60, chunk_overlap=10)
    )

    chunks = split_section_content(section, strategy)

    assert chunks == [code_block]
    assert len(chunks[0]) > 60


def test_protected_identifiers_are_not_split_by_character_fallback() -> None:
    """字符兜底切分不能拆开关键技术标识符。"""

    identifiers = ["ACTIONS_STEP_DEBUG", "GITHUB_TOKEN", "owner/repo/run_id"]
    content = "x" * 35 + " ".join(identifiers) + "y" * 35
    section = build_section(content)
    strategy = StructureThenRecursiveChunkingStrategy(
        ChunkingConfig(chunk_size=40, chunk_overlap=0)
    )

    chunks = split_section_content(section, strategy)

    assert all(identifier in "\n".join(chunks) for identifier in identifiers)
    assert all(
        any(identifier in chunk for chunk in chunks) for identifier in identifiers
    )
