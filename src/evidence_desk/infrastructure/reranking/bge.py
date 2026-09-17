"""基于 sentence-transformers CrossEncoder 的本地 BGE Reranker 实现（P6-05）。

跟 BgeEmbeddingAdapter 是同一个模式（本地模型 + 项目内缓存目录 + 加载失败给出
可操作的报错），区别是模型类型不同：

- Embedding 用的是 SentenceTransformer（双塔）：问题和文档**分别**编码成两个
  向量，比较的是两个向量的距离。好处是文档向量可以预先算好存进库里，查询时只
  编码问题，所以能在几百上千个 chunk 里快速筛选。
- Reranker 用的是 CrossEncoder（交叉编码）：把「问题 + 文档」拼成一对**一起**
  喂进模型，直接输出一个相关度分数。模型能看到问题和文档的逐词交互，判断更准，
  但没法预计算——每个候选都要实时跑一次模型，所以只能用在小批量候选上。

两者是配合关系不是替代关系：检索器负责"从全库快速捞出可能相关的 20 条"，
重排器负责"把这 20 条排准，选出最好的 5 条"。
"""

from collections.abc import Sequence
from pathlib import Path

from sentence_transformers import CrossEncoder

from evidence_desk.rag.models import RetrievalHit


class RerankerModelLoadError(RuntimeError):
    """Reranker 模型无法下载或从本地缓存加载。"""


class BgeRerankerAdapter:
    """用交叉编码模型给「问题-文档」对打分，重新排序候选。"""

    def __init__(self, model_name: str, cache_dir: Path) -> None:
        """从项目缓存加载模型；本机缺失时下载到该目录。"""

        self.model_name = model_name
        self.cache_dir = cache_dir.resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._model = CrossEncoder(model_name, cache_folder=str(self.cache_dir))
        except OSError as error:
            raise RerankerModelLoadError(
                "Reranker 模型无法下载或加载。"
                f"模型：{model_name}；缓存目录：{self.cache_dir}。"
                "请检查网络/Hugging Face 访问、磁盘空间和目录写权限，"
                "再重新运行该命令。"
            ) from error

    def rerank(
        self,
        query_text: str,
        # 收 Sequence 而不是 list：端口声明的是 Sequence，实现**不能收得比端口更窄**
        # （端口答应调用方可以传任何序列，实现只认 list 就食言了）。mypy 会直接
        # 报出来。反过来收得更宽是允许的。
        hits: Sequence[RetrievalHit],
        *,
        top_k: int,
    ) -> list[RetrievalHit]:
        """给每个候选算一个相关度分数，按分数取前 top_k。"""

        if top_k < 1:
            raise ValueError("top_k 必须大于等于1。")
        if not hits:
            return []

        # 把候选组装成「(问题, 文档正文)」的配对列表，一次性交给模型批量打分。
        # 这里只用 content 不拼 title/section_path，是为了和 Dense 检索保持
        # 同一个变量：Dense 那边用的是 build_embedding_text（带标题和章节），
        # 要不要给重排也拼上属于另一个实验，不在这一轮里混着改。
        pairs = [(query_text, hit.content) for hit in hits]
        scores = [float(score) for score in self._model.predict(pairs)]

        # zip 出「(分数, 命中)」再按分数从高到低排序。
        # key=lambda pair: pair[0] 指定只按分数排，不去比第二个元素——
        # RetrievalHit 之间没法比大小，分数打平时若去比它会直接抛异常。
        ranked = sorted(zip(scores, hits, strict=True), key=lambda p: p[0], reverse=True)

        # 重新编号：rank 要反映**重排后**的名次，而不是检索时的原始名次，
        # 否则下游看到的 rank 会是乱序的。score 也换成重排分数，distance
        # 保留检索阶段的原值（它描述的是向量距离，跟重排无关）。
        return [
            hit.model_copy(update={"rank": rank, "score": score})
            for rank, (score, hit) in enumerate(ranked[:top_k], start=1)
        ]
