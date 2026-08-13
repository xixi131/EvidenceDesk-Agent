"""Section 提取阶段使用的数据模型。"""

from evidence_desk.rag.models.cleaning import CleaningModel, NonEmptyString


class Section(CleaningModel):
    """一篇 Cleaned Markdown 文档中、由同一标题管理的一段正文。"""

    title: NonEmptyString
    section_path: list[NonEmptyString]
    section_content: NonEmptyString
    source_document_id: NonEmptyString
    source_url: NonEmptyString
