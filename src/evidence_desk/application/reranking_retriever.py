"""把「粗筛 + 精排」两段组合成一个检索器（P6-05）。

设计要点：它自己也满足 ChunkRetriever 端口。也就是说对调用方（评测 Runner、
ChatService、Agent 工具）来说，它跟 WeaviateDenseRetriever 长得一模一样，
换成它不用改任何调用代码——这正是当初把检索抽象成端口的收益兑现的地方。

两段式的分工：
    第一段（粗筛）：底层检索器取 candidate_top_n=20 条。目标是**别漏**，
                    宁可多带回一些不相关的，也不能把正确答案漏在外面——
                    漏掉的东西，后面再准的重排也救不回来。
    第二段（精排）：Reranker 把这 20 条重新排序，只留 top_k=5 条。目标是**排准**。

所以做这个实验之前要先确认粗筛的 Recall 够高。本项目 Dense 检索的
Recall@20 = 1.0000（见 data/evaluation/retrieval_eval_v1.md），候选集是满的，
重排的上限就是 100%，掉下来的分只可能是重排自己排错，实验变量很干净。
"""

from evidence_desk.application.ports.retrieval import ChunkRetriever, Reranker
from evidence_desk.rag.models import RetrievalHit


class RerankingRetriever:
    """先用底层检索器粗筛候选，再用 Reranker 精排出 Top-K。"""

    def __init__(
        self,
        base_retriever: ChunkRetriever,
        reranker: Reranker,
        *,
        candidate_top_n: int = 20,
    ) -> None:
        if candidate_top_n < 1:
            raise ValueError("candidate_top_n 必须大于等于1。")

        self._base_retriever = base_retriever
        self._reranker = reranker
        self._candidate_top_n = candidate_top_n

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        query_text: str | None = None,
    ) -> list[RetrievalHit]:
        """粗筛 candidate_top_n 条，重排后返回 top_k 条。"""

        if top_k < 1:
            raise ValueError("top_k 必须大于等于1。")
        # 重排器要把「问题 + 文档」拼成一对喂给模型，没有原始问题文本就没法工作。
        # 这跟 BM25 需要 query_text 是同一个道理，但这里是硬性要求不是可选项，
        # 所以缺了直接报错，而不是悄悄退化成"不重排"——静默降级会让评测结果
        # 看起来正常、实际却没测到重排，比报错难查得多。
        if not query_text:
            raise ValueError("重排需要 query_text（原始问题文本）。")

        # 粗筛数量取 max(candidate_top_n, top_k)：正常情况下候选数远大于最终
        # 要的条数；但万一调用方传了个比候选数还大的 top_k（比如 top_k=50 而
        # candidate_top_n=20），只捞 20 条就永远凑不出 50 条，这里兜一下底。
        candidates = self._base_retriever.search(
            query_vector,
            top_k=max(self._candidate_top_n, top_k),
            query_text=query_text,
        )

        return self._reranker.rerank(query_text, candidates, top_k=top_k)
