"""回答引用（Citation）数据模型。"""

from pydantic import Field

from evidence_desk.rag.models.source import NonEmptyString, RagModel


class Citation(RagModel):
    """答案里一条指向官方来源的引用。

    每条引用都来自一个真实检索到的 Chunk，字段全部取自 ``RetrievalHit``，
    不允许模型自己编造来源。``source_url`` 一定是当初冻结语料时保存的官方页面地址。
    """

    index: int = Field(ge=1, description="引用序号，从 1 开始，对应答案中的 [1][2]")
    chunk_id: NonEmptyString = Field(description="命中的具体 Chunk 编号")
    parent_doc_id: NonEmptyString = Field(description="Chunk 所属的父文档编号")
    title: NonEmptyString = Field(description="来源文档标题")
    section_path: list[NonEmptyString] = Field(description="命中章节的标题路径")
    source_url: NonEmptyString = Field(description="官方页面 URL，可点击核实")
