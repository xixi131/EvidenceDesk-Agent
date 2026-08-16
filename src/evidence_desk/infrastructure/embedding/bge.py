"""基于 sentence-transformers 的本地 BGE Embedding 实现。"""

from pathlib import Path
from typing import cast

from sentence_transformers import SentenceTransformer


class EmbeddingModelLoadError(RuntimeError):
    """Embedding 模型无法下载或从本地缓存加载。"""


class BgeEmbeddingAdapter:
    """将文本批量转换为可写入向量库的浮点向量。"""

    def __init__(self, model_name: str, cache_dir: Path) -> None:
        """从项目缓存加载模型；本机缺失时下载到该目录。"""

        self.model_name = model_name
        self.cache_dir = cache_dir.resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._model = SentenceTransformer(
                model_name,
                cache_folder=str(self.cache_dir),
            )
        except OSError as error:
            raise EmbeddingModelLoadError(
                "Embedding 模型无法下载或加载。"
                f"模型：{model_name}；缓存目录：{self.cache_dir}。"
                "请检查网络/Hugging Face 访问、磁盘空间和目录写权限，"
                "再重新运行该命令。"
            ) from error

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """将待入库的 Chunk 文本批量转换成归一化向量。"""

        if not texts:
            return []

        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=True,
        )
        return cast(list[list[float]], vectors.tolist())

    def embed_query(self, query: str) -> list[float]:
        """将用户问题转换成一个与文档向量可比较的向量。"""

        vector = self._model.encode(
            query,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return cast(list[float], vector.tolist())
