"""读取已经通过 Manifest 校验的 Raw Markdown 文档。"""

from collections.abc import Sequence
from pathlib import Path

from evidence_desk.rag.models import BaselineDocumentSelection, ParsedDocument


class MarkdownLoaderError(ValueError):
    """Raw Markdown 文档无法读取或无法转换。"""


def load_markdown_documents(
    corpus_root: Path,
    source_dataset_version: str,
    documents: Sequence[BaselineDocumentSelection],
) -> list[ParsedDocument]:
    """读取文档正文，并将每条 Manifest 记录转换成 ParsedDocument。"""

    parsed_documents: list[ParsedDocument] = []

    for document in documents:
        raw_path = corpus_root / document.source_relative_path

        try:
            content = raw_path.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise MarkdownLoaderError(
                f"Markdown 文档不存在：{document.source_relative_path}"
            ) from error
        except UnicodeDecodeError as error:
            raise MarkdownLoaderError(
                f"Markdown 文档不是有效的 UTF-8：{document.source_relative_path}"
            ) from error
        except OSError as error:
            raise MarkdownLoaderError(
                f"Markdown 文档读取失败：{document.source_relative_path}"
            ) from error

        parsed_documents.append(
            ParsedDocument(
                source_dataset_version=source_dataset_version,
                source_document_id=document.document_id,
                title=document.title,
                source_url=document.source_url,
                source_relative_path=document.source_relative_path,
                source_sha256=document.source_sha256,
                content=content,
                risk_flags=document.risk_flags,
            )
        )

    return parsed_documents
