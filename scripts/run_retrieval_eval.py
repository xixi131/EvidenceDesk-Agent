"""对固定评测集跑 Dense 检索评测，输出 Recall@K / Precision@K / MRR 报告。

一次检索取 Top-max(K)，从同一份结果里算出各 K 的指标（top_k 实验免重复检索）。
报告写入 data/evaluation/：JSON（逐题明细）+ Markdown（汇总表）。
"""

import json
from pathlib import Path

from evidence_desk.core.config import get_settings
from evidence_desk.evaluation.dataset import load_eval_cases
from evidence_desk.evaluation.runner import EvalReport, evaluate_retrieval
from evidence_desk.infrastructure.embedding import BgeEmbeddingAdapter
from evidence_desk.infrastructure.weaviate import (
    WeaviateDenseRetriever,
    connect_to_weaviate,
    ensure_knowledge_chunk_collection,
)

DEV_SET_PATH = Path("data/evaluation/dev_v1.jsonl")
JSON_REPORT_PATH = Path("data/evaluation/retrieval_eval_v1.json")
MD_REPORT_PATH = Path("data/evaluation/retrieval_eval_v1.md")
K_VALUES = [2, 5, 10, 20]


def _report_to_dict(report: EvalReport, model: str) -> dict:
    """把 EvalReport 摊平成可 JSON 序列化的字典（int 的 K 转成字符串键）。"""
    return {
        "embedding_model": model,
        "k_values": report.k_values,
        "num_cases": report.num_cases,
        "avg_recall": {str(k): round(v, 4) for k, v in report.avg_recall.items()},
        "avg_precision": {str(k): round(v, 4) for k, v in report.avg_precision.items()},
        "mrr": round(report.mrr, 4),
        "cases": [
            {
                "id": case.id,
                "question": case.question,
                "relevant_doc_ids": case.relevant_doc_ids,
                "retrieved_doc_ids": case.retrieved_doc_ids,
                "recall": {str(k): round(v, 4) for k, v in case.recall.items()},
                "precision": {str(k): round(v, 4) for k, v in case.precision.items()},
                "reciprocal_rank": round(case.reciprocal_rank, 4),
            }
            for case in report.cases
        ],
    }


def _report_to_markdown(report: EvalReport, model: str) -> str:
    """生成一张 K × 指标的 Markdown 汇总表。"""
    lines = [
        "# 检索评测报告（Dense Baseline）",
        "",
        f"- Embedding：`{model}`",
        f"- 有答案题数：{report.num_cases}",
        f"- MRR：{report.mrr:.4f}",
        "",
        "| K | Recall@K | Precision@K |",
        "| --- | --- | --- |",
    ]
    for k in report.k_values:
        lines.append(
            f"| {k} | {report.avg_recall[k]:.4f} | {report.avg_precision[k]:.4f} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    settings = get_settings()
    cases = load_eval_cases(DEV_SET_PATH)

    embedder = BgeEmbeddingAdapter(
        settings.embedding_model, settings.embedding_cache_dir
    )
    client = connect_to_weaviate(settings)
    try:
        collection = ensure_knowledge_chunk_collection(client)
        retriever = WeaviateDenseRetriever(collection)
        report = evaluate_retrieval(cases, embedder, retriever, k_values=K_VALUES)
    finally:
        client.close()

    JSON_REPORT_PATH.write_text(
        json.dumps(
            _report_to_dict(report, settings.embedding_model),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    MD_REPORT_PATH.write_text(
        _report_to_markdown(report, settings.embedding_model), encoding="utf-8"
    )

    print(f"有答案题数：{report.num_cases}")
    print(f"MRR：{report.mrr:.4f}")
    print(f"{'K':>4} | {'Recall@K':>9} | {'Precision@K':>11}")
    for k in report.k_values:
        print(
            f"{k:>4} | {report.avg_recall[k]:>9.4f} | {report.avg_precision[k]:>11.4f}"
        )
    print(f"报告已保存：{JSON_REPORT_PATH} 和 {MD_REPORT_PATH}")


if __name__ == "__main__":
    main()
