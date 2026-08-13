"""Markdown Loader 和 Cleaner 之间传递的数据模型。"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

SHA256_PATTERN = r"^[0-9a-f]{64}$"
NonEmptyString = Annotated[str, Field(min_length=1)]


class CleaningModel(BaseModel):
    """文档清洗数据模型的公共基类。"""

    model_config = ConfigDict(extra="forbid")


class ParsedDocument(CleaningModel):
    """Markdown Loader 读取 Raw 文档后交给 Cleaner 的结构。"""

    source_dataset_version: NonEmptyString = Field(description="Source Dataset 版本")
    source_document_id: NonEmptyString = Field(description="来源文档编号")
    title: NonEmptyString = Field(description="来源文档标题")
    source_url: NonEmptyString = Field(description="GitHub Docs 官方页面地址")
    source_relative_path: NonEmptyString = Field(description="Raw 文档相对路径")
    source_sha256: str = Field(
        pattern=SHA256_PATTERN,
        description="Raw 文档的 SHA-256 哈希",
    )
    content: NonEmptyString = Field(description="Loader 读取的原始 Markdown 正文")
    risk_flags: list[NonEmptyString] = Field(description="清洗时需要关注的风险标记")


class CleaningWarning(CleaningModel):
    """Cleaner 未阻断处理但需要记录的一条警告。"""

    code: NonEmptyString = Field(description="稳定的警告代码")
    message: NonEmptyString = Field(description="可读的警告说明")
    line_number: int | None = Field(
        default=None,
        ge=1,
        description="能够定位时记录的 Raw 文档行号",
    )


class CleaningResult(CleaningModel):
    """Cleaner 处理一篇文档后输出的正文、追溯信息和变更统计。"""

    source_dataset_version: NonEmptyString = Field(description="Source Dataset 版本")
    source_document_id: NonEmptyString = Field(description="来源文档编号")
    source_relative_path: NonEmptyString = Field(description="Raw 文档相对路径")
    source_sha256: str = Field(
        pattern=SHA256_PATTERN,
        description="Raw 文档的 SHA-256 哈希",
    )
    cleaning_rules_version: NonEmptyString = Field(description="本次使用的清洗规则版本")
    cleaned_content: NonEmptyString = Field(description="清洗后的 Markdown 正文")
    cleaned_sha256: str = Field(
        pattern=SHA256_PATTERN,
        description="清洗后正文的 SHA-256 哈希",
    )
    removed_svg_count: int = Field(ge=0, description="删除的 SVG 数量")
    replaced_svg_label_count: int = Field(ge=0, description="替换为可读标签的 SVG 数量")
    removed_html_tag_count: int = Field(ge=0, description="删除的 HTML 标签数量")
    converted_link_count: int = Field(ge=0, description="转换为绝对地址的链接数量")
    converted_callout_count: int = Field(ge=0, description="转换的 Callout 数量")
    warnings: list[CleaningWarning] = Field(description="不阻断处理的清洗警告")


class CleaningDocumentReport(CleaningModel):
    """Cleaning Report 中一篇文档的清洗记录。"""

    source_document_id: NonEmptyString = Field(description="来源文档编号")
    source_relative_path: NonEmptyString = Field(description="Raw 文档相对路径")
    cleaned_relative_path: NonEmptyString = Field(description="Cleaned 文档相对路径")
    source_sha256: str = Field(
        pattern=SHA256_PATTERN,
        description="Raw 文档 SHA-256",
    )
    cleaned_sha256: str = Field(
        pattern=SHA256_PATTERN,
        description="Cleaned 文档 SHA-256",
    )
    removed_svg_count: int = Field(
        ge=0,
        description="直接删除的 SVG 数量",
    )
    replaced_svg_label_count: int = Field(
        ge=0,
        description="替换为可读标签的 SVG 数量",
    )
    removed_html_tag_count: int = Field(
        ge=0,
        description="删除的普通 HTML 标签数量",
    )
    converted_link_count: int = Field(
        ge=0,
        description="转换的相对链接数量",
    )
    converted_callout_count: int = Field(
        ge=0,
        description="转换的 Callout 数量",
    )
    warnings: list[CleaningWarning] = Field(description="当前文档的清洗警告")


class CleaningReport(CleaningModel):
    """一次完整 Baseline 清洗运行的报告。"""

    report_version: NonEmptyString = Field(description="清洗报告版本")
    source_dataset_version: NonEmptyString = Field(description="Source Dataset 版本")
    baseline_version: NonEmptyString = Field(description="Baseline 版本")
    cleaning_rules_version: NonEmptyString = Field(description="清洗规则版本")
    generated_at: datetime = Field(description="报告生成时间")
    cleaned_output_directory: NonEmptyString = Field(description="Cleaned 文档输出目录")
    input_document_count: int = Field(gt=0, description="输入文档数量")
    output_document_count: int = Field(gt=0, description="输出文档数量")
    removed_svg_count: int = Field(ge=0, description="直接删除的 SVG 总数")
    replaced_svg_label_count: int = Field(ge=0, description="替换为可读标签的 SVG 总数")
    removed_html_tag_count: int = Field(ge=0, description="删除的普通 HTML 标签总数")
    converted_link_count: int = Field(ge=0, description="转换的相对链接总数")
    converted_callout_count: int = Field(ge=0, description="转换的 Callout 总数")
    warning_document_count: int = Field(ge=0, description="产生警告的文档数量")
    documents: list[CleaningDocumentReport] = Field(
        min_length=1,
        description="每篇文档的清洗记录",
    )
