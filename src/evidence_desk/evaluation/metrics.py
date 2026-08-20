"""检索评测指标：Recall@K、Precision@K、MRR（文档级）。

约定（与路线图 P2-02 一致）：
- 检索返回 Top-K 个 chunk，映射成父文档 ID 的有序列表 ``ranked_doc_ids``（保留重复）；
- 命中按『唯一相关父文档』计数；
- Recall@K 分母是相关文档总数，Precision@K 分母固定是 K；
- MRR 使用第一个命中相关文档的 chunk 排名。
"""

from collections.abc import Sequence


def _relevant_hits(
    ranked_doc_ids: Sequence[str], relevant: set[str], k: int
) -> set[str]:
    """Top-K chunk 里命中的『唯一相关父文档』集合。"""
    return {doc_id for doc_id in ranked_doc_ids[:k] if doc_id in relevant}


def recall_at_k(ranked_doc_ids: Sequence[str], relevant: set[str], k: int) -> float:
    """该找到的相关文档，进了 Top-K 的比例。分母 = 相关文档总数。"""
    if not relevant:
        raise ValueError("relevant 不能为空：Recall 需要至少一个相关文档")
    return len(_relevant_hits(ranked_doc_ids, relevant, k)) / len(relevant)


def precision_at_k(ranked_doc_ids: Sequence[str], relevant: set[str], k: int) -> float:
    """返回的 K 个里有几个相关。分母固定 = K。"""
    if k <= 0:
        raise ValueError("k 必须为正整数")
    return len(_relevant_hits(ranked_doc_ids, relevant, k)) / k


def reciprocal_rank(ranked_doc_ids: Sequence[str], relevant: set[str]) -> float:
    """第一个命中相关文档的排名的倒数；一个都没命中则为 0。"""
    for rank, doc_id in enumerate(ranked_doc_ids, start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0
