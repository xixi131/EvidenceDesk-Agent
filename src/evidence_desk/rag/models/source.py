"""Source Manifest 和 Baseline Manifest 使用的数据模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

SHA256_PATTERN = r"^[0-9a-f]{64}$"
GIT_COMMIT_PATTERN = r"^[0-9a-f]{40}$"


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
