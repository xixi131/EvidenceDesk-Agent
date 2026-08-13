"""Chunk Quality Report 使用的数据模型。"""

from datetime import datetime

from pydantic import Field

from evidence_desk.rag.models.source import NonEmptyString, RagModel


class ChunkQualityWarning(RagModel):
    """一条需要人工查看但不阻断本次切块的质量警告。"""

    code: NonEmptyString = Field(description="稳定的警告代码")
    message: NonEmptyString = Field(description="可读的警告说明")
    chunk_id: NonEmptyString = Field(description="需要查看的 Chunk 编号")
    parent_doc_id: NonEmptyString = Field(description="Chunk 所属文档编号")
    source_relative_path: NonEmptyString | None = Field(
        default=None,
        description="Cleaned 文档相对路径",
    )
    section_path: list[NonEmptyString] = Field(
        min_length=1,
        description="Chunk 所在的标题路径",
    )
    source_url: NonEmptyString = Field(description="官方来源地址")
    content_length: int = Field(gt=0, description="Chunk 正文字符数")


class ChunkQualityReport(RagModel):
    """一次固定配置下生成 Chunk 后的质量统计。"""

    report_version: NonEmptyString = Field(description="报告格式版本")
    source_dataset_version: NonEmptyString = Field(description="Source Dataset 版本")
    baseline_version: NonEmptyString = Field(description="Baseline 版本")
    cleaning_rules_version: NonEmptyString = Field(description="清洗规则版本")
    chunk_config_version: NonEmptyString = Field(description="Chunk 配置版本")
    generated_at: datetime = Field(description="报告生成时间")
    document_count: int = Field(gt=0, description="参与切块的文档数量")
    chunk_count: int = Field(gt=0, description="最终 Chunk 总数")
    chunk_size: int = Field(gt=0, description="本次 Chunk 字符上限")
    chunk_overlap: int = Field(ge=0, description="相邻普通文本 Chunk 的重叠字符数")
    min_chunk_length: int = Field(gt=0, description="最短 Chunk 字符数")
    max_chunk_length: int = Field(gt=0, description="最长 Chunk 字符数")
    average_chunk_length: float = Field(gt=0, description="平均 Chunk 字符数")
    p50_chunk_length: int = Field(gt=0, description="Chunk 长度 P50")
    p95_chunk_length: int = Field(gt=0, description="Chunk 长度 P95")
    short_chunk_threshold: int = Field(gt=0, description="过短 Chunk 的字符阈值")
    short_chunk_count: int = Field(ge=0, description="小于过短阈值的 Chunk 数")
    long_chunk_count: int = Field(ge=0, description="超过 chunk_size 的 Chunk 数")
    duplicate_content_hash_count: int = Field(
        ge=0,
        description="重复正文哈希对应的额外 Chunk 数",
    )
    duplicate_chunk_id_count: int = Field(
        ge=0,
        description="重复 Chunk ID 对应的额外 Chunk 数",
    )
    chunk_count_by_document: dict[NonEmptyString, int] = Field(
        min_length=1,
        description="每篇文档产生的 Chunk 数",
    )
    code_block_warnings: list[ChunkQualityWarning] = Field(
        description="完整代码块超长或疑似未闭合的警告",
    )
