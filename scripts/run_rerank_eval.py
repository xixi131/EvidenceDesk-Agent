"""对比重排前后的检索质量和延迟（P6-05）。

四组对比，一次只变"要不要重排"这一个变量：

    Dense            粗筛 top_k=5，不重排
    Hybrid           粗筛 top_k=5，不重排（P6-03 的最优方案）
    Dense+Rerank     粗筛 top_n=20 → 重排 → top_k=5
    Hybrid+Rerank    粗筛 top_n=20 → 重排 → top_k=5

前提：Dense 的 Recall@20 = 1.0000（见 retrieval_eval_v1.md），候选集是满的，
所以重排的上限是 100%，掉下来的分只可能是重排自己排错。

除了质量还记了延迟——重排要给 20 个候选逐个跑一次交叉编码模型，必然比不重排
慢。质量涨多少、延迟涨多少，两个数字放一起才能判断这笔买卖划不划算。
"""

import json
import time
from pathlib import Path
from typing import Any

from evidence_desk.application.ports import ChunkRetriever
from evidence_desk.application.reranking_retriever import RerankingRetriever
from evidence_desk.core.config import get_settings
from evidence_desk.evaluation.dataset import load_eval_cases
from evidence_desk.evaluation.metrics import group_recall_by_tag
from evidence_desk.evaluation.runner import EvalReport, evaluate_retrieval
from evidence_desk.infrastructure.embedding import BgeEmbeddingAdapter
from evidence_desk.infrastructure.reranking import BgeRerankerAdapter
from evidence_desk.infrastructure.weaviate import (
    WeaviateDenseRetriever,
    WeaviateHybridRetriever,
    connect_to_weaviate,
    ensure_knowledge_chunk_collection,
)

DEV_SET_PATH = Path("data/evaluation/dev_v1.jsonl")
JSON_REPORT_PATH = Path("data/evaluation/rerank_eval_v1.json")
MD_REPORT_PATH = Path("data/evaluation/rerank_eval_v1.md")
K = 5
HYBRID_ALPHA = 0.5


def _summarize(report: EvalReport, elapsed_seconds: float) -> dict[str, Any]:
    tag_recall = group_recall_by_tag([(c.tags, c.recall[K]) for c in report.cases])
    return {
        "num_cases": report.num_cases,
        f"recall@{K}": round(report.avg_recall[K], 4),
        f"precision@{K}": round(report.avg_precision[K], 4),
        "mrr": round(report.mrr, 4),
        # 每题平均耗时（毫秒）。含查询向量化，因为那是任何一次真实检索都跑不掉的，
        # 只掐重排那一段会低估用户实际感受到的延迟。
        "ms_per_query": round(elapsed_seconds * 1000 / report.num_cases, 1),
        f"tag_recall@{K}": {tag: round(v, 4) for tag, v in sorted(tag_recall.items())},
    }


def _to_markdown(
    summaries: dict[str, dict[str, Any]], reranker_model: str, top_n: int
) -> str:
    methods = list(summaries.keys())
    lines = [
        "# 重排（Reranker）对比报告（P6-05）",
        "",
        f"- 最终返回条数 context_top_k：{K}",
        f"- 重排候选数 candidate_top_n：{top_n}",
        f"- Reranker：`{reranker_model}`",
        f"- Hybrid alpha：{HYBRID_ALPHA}",
        f"- 题目数：{summaries[methods[0]]['num_cases']}",
        "",
        "粗筛的 Recall@20 = 1.0000，候选集里必定含正确答案，所以重排的上限是"
        "100%——这里掉下来的每一分都只能归因于重排本身排错，不是候选没捞到。",
        "",
        "## 总体指标",
        "",
        "| 方法 | Recall@K | Precision@K | MRR | 每题耗时(ms) |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name in methods:
        s = summaries[name]
        lines.append(
            f"| {name} | {s[f'recall@{K}']:.4f} | {s[f'precision@{K}']:.4f} "
            f"| {s['mrr']:.4f} | {s['ms_per_query']:.1f} |"
        )

    lines += ["", "## 按标签细分的 Recall@K", ""]
    all_tags = sorted({tag for s in summaries.values() for tag in s[f"tag_recall@{K}"]})
    lines += [
        "| 标签 | " + " | ".join(methods) + " |",
        "| --- | " + " | ".join(["---"] * len(methods)) + " |",
    ]
    for tag in all_tags:
        row = [
            f"{summaries[name][f'tag_recall@{K}'].get(tag, float('nan')):.4f}"
            for name in methods
        ]
        lines.append(f"| {tag} | " + " | ".join(row) + " |")

    return "\n".join(lines) + "\n"


def main() -> None:
    settings = get_settings()
    cases = load_eval_cases(DEV_SET_PATH)

    embedder = BgeEmbeddingAdapter(
        settings.embedding_model,
        settings.embedding_cache_dir,
    )
    reranker = BgeRerankerAdapter(
        settings.reranker_model,
        settings.embedding_cache_dir,
    )

    client = connect_to_weaviate(settings)
    try:
        collection = ensure_knowledge_chunk_collection(client)
        dense = WeaviateDenseRetriever(collection)
        hybrid = WeaviateHybridRetriever(collection, alpha=HYBRID_ALPHA)
        top_n = settings.rerank_candidate_top_n

        retrievers: dict[str, ChunkRetriever] = {
            "Dense": dense,
            "Hybrid": hybrid,
            "Dense+Rerank": RerankingRetriever(
                dense, reranker, candidate_top_n=top_n
            ),
            "Hybrid+Rerank": RerankingRetriever(
                hybrid, reranker, candidate_top_n=top_n
            ),
        }

        summaries = {}
        for name, retriever in retrievers.items():
            started = time.perf_counter()
            report = evaluate_retrieval(cases, embedder, retriever, k_values=[K])
            elapsed = time.perf_counter() - started
            summaries[name] = _summarize(report, elapsed)
            print(
                f"{name}: Recall@{K}={summaries[name][f'recall@{K}']:.4f}  "
                f"MRR={summaries[name]['mrr']:.4f}  "
                f"{summaries[name]['ms_per_query']:.1f}ms/题"
            )
    finally:
        client.close()

    JSON_REPORT_PATH.write_text(
        json.dumps(
            {
                "k": K,
                "candidate_top_n": top_n,
                "reranker_model": settings.reranker_model,
                "hybrid_alpha": HYBRID_ALPHA,
                "methods": summaries,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    MD_REPORT_PATH.write_text(
        _to_markdown(summaries, settings.reranker_model, top_n),
        encoding="utf-8",
    )
    print(f"报告已保存：{JSON_REPORT_PATH} 和 {MD_REPORT_PATH}")


if __name__ == "__main__":
    main()
