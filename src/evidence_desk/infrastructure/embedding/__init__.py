"""本地与外部 Embedding 实现。"""

from evidence_desk.infrastructure.embedding.bge import (
    BgeEmbeddingAdapter,
    EmbeddingModelLoadError,
)

__all__ = ["BgeEmbeddingAdapter", "EmbeddingModelLoadError"]
