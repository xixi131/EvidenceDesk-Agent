"""Source Manifest 和 Baseline Manifest 使用的数据模型。"""

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

SHA256_PATTERN = r"^[0-9a-f]{64}$"
GIT_COMMIT_PATTERN = r"^[0-9a-f]{40}$"
NonEmptyString = Annotated[str, Field(min_length=1)]


class RagModel(BaseModel):
    """RAG 数据模型的公共基类。"""

    model_config = ConfigDict(extra="forbid")


class SourceDocument(RagModel):
    """Source Manifest 中登记的一篇原始文档。"""

    document_id: str = Field(
        min_length=1,
        description="文档在整个数据集中的唯一编号",
    )
    title: str = Field(
        min_length=1,
        description="文档标题",
    )
    locale: str = Field(
        min_length=1,
        description="文档语言，例如 zh",
    )
    pathname: str = Field(
        min_length=1,
        description="文档在 GitHub Docs 中的页面路径",
    )
    public_url: str = Field(
        min_length=1,
        description="用户可以访问的 GitHub Docs 官方页面地址",
    )
    download_url: str = Field(
        min_length=1,
        description="下载文档正文时使用的地址",
    )
    relative_path: str = Field(
        min_length=1,
        description="文档在本地数据目录中的相对路径",
    )
    sha256: str = Field(
        pattern=SHA256_PATTERN,
        description="原始 Markdown 文件的 SHA-256 哈希",
    )
    byte_size: int = Field(
        gt=0,
        description="原始 Markdown 文件的字节大小",
    )
    status: str = Field(
        min_length=1,
        description="文档状态，例如 active",
    )


class SourceManifest(RagModel):
    """整个 Source Manifest 文件。"""

    dataset_version: str = Field(
        min_length=1,
        description="当前 Source Dataset 的版本号",
    )
    status: str = Field(
        min_length=1,
        description="当前数据集状态，例如 frozen",
    )
    product_context: str = Field(
        min_length=1,
        description="数据集对应的产品和业务场景",
    )
    source_name: str = Field(
        min_length=1,
        description="数据来源名称",
    )
    source_repository: str = Field(
        min_length=1,
        description="数据来源仓库地址",
    )
    source_repository_commit: str = Field(
        pattern=GIT_COMMIT_PATTERN,
        description="下载数据时固定的来源仓库 Commit",
    )
    source_repository_commit_date: datetime = Field(
        description="来源仓库 Commit 的时间",
    )
    retrieved_at: datetime = Field(
        description="本地下载数据的时间",
    )
    locale: str = Field(
        min_length=1,
        description="数据集主要语言",
    )
    license: str = Field(
        min_length=1,
        description="数据集使用的许可证",
    )
    license_file: str = Field(
        min_length=1,
        description="本地许可证文件路径",
    )
    document_count: int = Field(
        gt=0,
        description="Manifest 声明的文档数量",
    )
    documents: list[SourceDocument] = Field(
        min_length=1,
        description="Source Dataset 中的全部文档记录",
    )


class DocumentMetrics(RagModel):
    """Baseline 选择时记录的一篇文档画像指标。"""

    character_count: int = Field(ge=0, description="文档字符数")
    line_count: int = Field(gt=0, description="文档行数")
    heading_count: int = Field(ge=0, description="Markdown 标题总数")
    h2_count: int = Field(ge=0, description="二级标题数量")
    code_block_count: int = Field(ge=0, description="代码块数量")
    cjk_character_count: int = Field(ge=0, description="中日韩统一表意字符数量")
    latin_character_count: int = Field(ge=0, description="拉丁字母数量")
    cjk_ratio: float = Field(ge=0, le=1, description="中文字符占语言字符的比例")
    svg_count: int = Field(ge=0, description="内联 SVG 数量")
    html_tag_count: int = Field(ge=0, description="HTML 标签数量")
    relative_link_count: int = Field(ge=0, description="相对链接数量")
    english_relative_link_count: int = Field(
        ge=0,
        description="指向英文页面的相对链接数量",
    )
    escaped_callout_count: int = Field(ge=0, description="转义 Callout 数量")


class EmbeddingBaseline(RagModel):
    """第一次检索实验冻结的 Embedding 和召回配置。"""

    model: NonEmptyString = Field(description="Embedding 模型名称")
    retrieval_mode: NonEmptyString = Field(description="检索方式")
    top_k: int = Field(gt=0, description="最终返回的候选数量")
    query_rewrite: bool = Field(description="是否启用 Query Rewrite")
    reranker: NonEmptyString | None = Field(description="Reranker 名称，未启用时为空")


class SelectionPolicy(RagModel):
    """Chinese Baseline 文档选择策略。"""

    description: NonEmptyString = Field(description="文档选择规则说明")
    english_dominant_threshold: float = Field(
        ge=0,
        le=1,
        description="判定英文占主导的中文字符比例阈值",
    )
    excluded_document_ids: list[NonEmptyString] = Field(
        min_length=1,
        description="第一次中文 Baseline 排除的文档编号",
    )
    future_experiment: NonEmptyString = Field(description="排除文档预留的后续实验")


class BaselineDocumentSelection(RagModel):
    """一篇 Source 文档在第一次中文 Baseline 中的选择记录。"""

    document_id: NonEmptyString = Field(description="Source Dataset 中的文档编号")
    title: NonEmptyString = Field(description="文档标题")
    category: NonEmptyString = Field(description="文档业务分类")
    source_relative_path: NonEmptyString = Field(description="Raw 文档相对路径")
    source_url: NonEmptyString = Field(description="GitHub Docs 官方页面地址")
    source_sha256: str = Field(
        pattern=SHA256_PATTERN,
        description="对应 Raw 文档的 SHA-256 哈希",
    )
    language_profile: NonEmptyString = Field(description="文档语言画像")
    baseline_included: bool = Field(description="是否进入第一次中文 Baseline")
    exclusion_reason: NonEmptyString | None = Field(description="暂时排除的原因")
    future_experiment: NonEmptyString | None = Field(description="后续重新加入的实验")
    cleaning_status: NonEmptyString = Field(description="文档清洗状态")
    risk_flags: list[NonEmptyString] = Field(description="清洗和分块风险标记")
    metrics: DocumentMetrics = Field(description="文档画像指标")


class BaselineManifest(RagModel):
    """第一次中文 RAG Baseline 使用的文档选择清单。"""

    baseline_version: NonEmptyString = Field(description="Baseline 版本号")
    status: NonEmptyString = Field(description="Baseline 状态")
    decision_date: date = Field(description="Baseline 决策日期")
    source_dataset_version: NonEmptyString = Field(description="来源数据集版本")
    source_manifest: NonEmptyString = Field(description="Source Manifest 相对路径")
    source_repository_commit: str = Field(
        pattern=GIT_COMMIT_PATTERN,
        description="来源仓库固定 Commit",
    )
    cleaning_rules_version: NonEmptyString = Field(description="清洗规则版本")
    cleaned_output_directory: NonEmptyString = Field(description="Cleaned 输出目录")
    embedding_baseline: EmbeddingBaseline = Field(description="第一次检索配置")
    selection_policy: SelectionPolicy = Field(description="文档选择策略")
    document_count: int = Field(gt=0, description="Source 文档总数")
    included_document_count: int = Field(ge=0, description="Baseline 纳入文档数")
    excluded_document_count: int = Field(ge=0, description="Baseline 排除文档数")
    documents: list[BaselineDocumentSelection] = Field(
        min_length=1,
        description="每篇 Source 文档的 Baseline 选择记录",
    )
