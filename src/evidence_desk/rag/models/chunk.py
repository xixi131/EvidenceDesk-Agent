"""最终可追踪 Chunk 的数据模型和确定性身份函数。"""

from hashlib import sha256

from pydantic import Field

from evidence_desk.rag.models.source import (
    SHA256_PATTERN,
    NonEmptyString,
    RagModel,
)


def calculate_content_hash(content: str) -> str:
    """计算 Chunk 正文的 SHA-256 哈希。"""

    return sha256(content.encode("utf-8")).hexdigest()


def build_chunk_id(
    *,
    parent_doc_id: str,
    chunk_config_version: str,
    chunk_index: int,
    content_hash: str,
) -> str:
    """根据输入文档、配置、顺序和正文生成确定性 Chunk ID。"""

    identity = "\x1f".join(
        [
            parent_doc_id,
            chunk_config_version,
            str(chunk_index),
            content_hash,
        ]
    )
    identity_hash = sha256(identity.encode("utf-8")).hexdigest()[:16]
    return (
        f"{parent_doc_id}__{chunk_config_version}__{chunk_index:04d}__{identity_hash}"
    )


class Chunk(RagModel):
    """一条可以被检索、引用、评测和重新索引的 Chunk。"""

    chunk_id: NonEmptyString = Field(description="Chunk 的确定性唯一编号")
    parent_doc_id: NonEmptyString = Field(description="所属父文档编号")
    title: NonEmptyString = Field(description="父文档标题")
    section_path: list[NonEmptyString] = Field(
        min_length=1,
        description="Chunk 所在的标题路径",
    )
    content: NonEmptyString = Field(description="Chunk 正文")
    chunk_index: int = Field(ge=1, description="父文档内从1开始的 Chunk 顺序")
    content_hash: str = Field(
        pattern=SHA256_PATTERN,
        description="Chunk 正文的 SHA-256 哈希",
    )
    source_url: NonEmptyString = Field(description="官方来源地址")
    dataset_version: NonEmptyString = Field(description="Source Dataset 版本")
    cleaning_rules_version: NonEmptyString = Field(
        description="生成 Cleaned 正文时使用的规则版本",
    )
    chunk_config_version: NonEmptyString = Field(
        description="生成当前 Chunk 时使用的切块配置版本",
    )
