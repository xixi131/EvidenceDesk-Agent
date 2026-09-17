"""检索评测 Runner：对固定数据集『检索一次、算多个 K』。

只依赖应用层端口（QueryEmbedder / ChunkRetriever），不认识 Weaviate 细节，
因此可以用 Fake 检索器做单元测试，也可以接真实 Weaviate 跑实验。
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from evidence_desk.application.ports import ChunkRetriever, QueryEmbedder
from evidence_desk.evaluation.dataset import EvalCase
from evidence_desk.evaluation.metrics import (
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


@dataclass(frozen=True)
class CaseResult:
    """单题的评测结果。"""

    id: str
    question: str
    relevant_doc_ids: list[str]
    retrieved_doc_ids: list[str]
    recall: dict[int, float]
    precision: dict[int, float]
    reciprocal_rank: float
    tags: list[str]


@dataclass(frozen=True)
class EvalReport:
    """整个数据集的评测汇总。"""

    k_values: list[int]
    num_cases: int
    avg_recall: dict[int, float]
    avg_precision: dict[int, float]
    mrr: float
    cases: list[CaseResult]


def evaluate_retrieval(
    cases: Sequence[EvalCase],
    embedder: QueryEmbedder,
    retriever: ChunkRetriever,
    *,
    k_values: Sequence[int],
) -> EvalReport:
    """对每道有答案的题检索一次（Top-max_k），再切片算各 K 的指标。"""

    # 只评有答案且标注了相关文档的题；无答案题属于『拒答准确率』，不在检索指标内。
    answerable = [
        case for case in cases if case.should_answer and case.relevant_doc_ids
    ]
    ks = list(k_values)
    max_k = max(ks)

    results: list[CaseResult] = []
    for case in answerable:
        vector = embedder.embed_query(case.question)
        # query_text=case.question：P6-03 新增，Dense 检索器会忽略它，
        # BM25/Hybrid 检索器需要原始问题文本做关键词匹配（见 ChunkRetriever 端口）。
        hits = retriever.search(vector, top_k=max_k, query_text=case.question)
        ranked = [hit.parent_doc_id for hit in hits]  # 保留重复，供 MRR 用 chunk 排名
        relevant = set(case.relevant_doc_ids)
        results.append(
            CaseResult(
                id=case.id,
                question=case.question,
                relevant_doc_ids=case.relevant_doc_ids,
                retrieved_doc_ids=ranked,
                recall={k: recall_at_k(ranked, relevant, k) for k in ks},
                precision={k: precision_at_k(ranked, relevant, k) for k in ks},
                reciprocal_rank=reciprocal_rank(ranked, relevant),
                tags=case.tags,
            )
        )

    n = len(results)
    avg_recall = {k: _mean(r.recall[k] for r in results) for k in ks}
    avg_precision = {k: _mean(r.precision[k] for r in results) for k in ks}
    mrr = _mean(r.reciprocal_rank for r in results)

    return EvalReport(
        k_values=ks,
        num_cases=n,
        avg_recall=avg_recall,
        avg_precision=avg_precision,
        mrr=mrr,
        cases=results,
    )


def _mean(values: Iterable[float]) -> float:
    """对可迭代的浮点数求平均，空集合返回 0.0。"""
    nums = list(values)
    return sum(nums) / len(nums) if nums else 0.0
