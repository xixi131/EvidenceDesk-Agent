"""对比 Dense / BM25 / Hybrid 三种检索方式，输出总体指标 + 按标签细分（P6-03）。

固定 K=5（跟 Baseline 的 context_top_k 一致），一次只改变"检索方式"这一个
变量，遵守 docs/06 §11"一次只改一个变量"的实验原则——K 的扫描已经在
run_retrieval_eval.py 里做过了，这里不重复扫。
"""

import json
from pathlib import Path

from evidence_desk.core.config import get_settings
from evidence_desk.evaluation.dataset import load_eval_cases
from evidence_desk.evaluation.metrics import group_recall_by_tag
from evidence_desk.evaluation.runner import EvalReport, evaluate_retrieval
from evidence_desk.infrastructure.embedding import BgeEmbeddingAdapter
from evidence_desk.infrastructure.weaviate import (
    WeaviateBM25Retriever,
    WeaviateDenseRetriever,
    WeaviateHybridRetriever,
    connect_to_weaviate,
    ensure_knowledge_chunk_collection,
)

DEV_SET_PATH = Path("data/evaluation/dev_v1.jsonl")
JSON_REPORT_PATH = Path("data/evaluation/hybrid_retrieval_eval_v1.json")
MD_REPORT_PATH = Path("data/evaluation/hybrid_retrieval_eval_v1.md")
K = 5
HYBRID_ALPHA = 0.5


def _report_to_summary(report: EvalReport) -> dict:
    """一个方法的整体指标 + 按标签细分的 Recall@K。"""
    tag_recall = group_recall_by_tag([(c.tags, c.recall[K]) for c in report.cases])
    return {
        "num_cases": report.num_cases,
        f"recall@{K}": round(report.avg_recall[K], 4),
        f"precision@{K}": round(report.avg_precision[K], 4),
        "mrr": round(report.mrr, 4),
        f"tag_recall@{K}": {tag: round(v, 4) for tag, v in sorted(tag_recall.items())},
    }


def _to_markdown(summaries: dict[str, dict]) -> str:
    methods = list(summaries.keys())
    lines = [
        "# Dense / BM25 / Hybrid 检索对比报告（P6-03）",
        "",
        f"- K：{K}",
        f"- Hybrid alpha：{HYBRID_ALPHA}（0=纯BM25，1=纯Dense）",
        f"- 题目数：{summaries[methods[0]]['num_cases']}",
        "",
        "## ⚠️ 已知限制：BM25/Hybrid 数字不代表检索方式本身的能力",
        "",
        "排查结论：Weaviate 内置的 GSE_CH 中文分词器在这份语料上不可靠——"
        "同样是常见双字词，「机密」能正确索引匹配，「标签」「构件」「取消」"
        "等词确认存在于原文中却查不到（BM25 直接返回 0 条结果，不是排序"
        "靠后）。已排除 AND/OR 查询逻辑、搜索字段范围、分词配置未生效这几个"
        "假设，定位到是分词器本身对特定词的处理问题，不是本项目的检索/融合"
        "代码逻辑问题。详细排查过程见"
        "`/Users/tangxitao/学习/My-Notes/Agent开发/错误记录/"
        "Weaviate中文BM25分词失效排查.md`。",
        "",
        "**结论**：本轮 BM25/Hybrid 的数字不采纳为结论依据；Dense 检索"
        "（阶段 2 已验证的 Baseline）继续作为生产使用的检索方式。",
        "",
        "## 总体指标",
        "",
        "| 方法 | Recall@K | Precision@K | MRR |",
        "| --- | --- | --- | --- |",
    ]
    for name in methods:
        s = summaries[name]
        lines.append(f"| {name} | {s[f'recall@{K}']:.4f} | {s[f'precision@{K}']:.4f} | {s['mrr']:.4f} |")

    lines += ["", "## 按标签细分的 Recall@K", ""]
    all_tags = sorted({tag for s in summaries.values() for tag in s[f"tag_recall@{K}"]})
    header = "| 标签 | " + " | ".join(methods) + " |"
    lines += [header, "| --- | " + " | ".join(["---"] * len(methods)) + " |"]
    for tag in all_tags:
        row = [f"{summaries[name][f'tag_recall@{K}'].get(tag, float('nan')):.4f}" for name in methods]
        lines.append(f"| {tag} | " + " | ".join(row) + " |")

    return "\n".join(lines) + "\n"


def main() -> None:
    settings = get_settings()
    cases = load_eval_cases(DEV_SET_PATH)

    embedder = BgeEmbeddingAdapter(settings.embedding_model, settings.embedding_cache_dir)
    client = connect_to_weaviate(settings)
    try:
        collection = ensure_knowledge_chunk_collection(client)
        retrievers = {
            "Dense": WeaviateDenseRetriever(collection),
            "BM25": WeaviateBM25Retriever(collection),
            "Hybrid": WeaviateHybridRetriever(collection, alpha=HYBRID_ALPHA),
        }
        summaries = {}
        for name, retriever in retrievers.items():
            report = evaluate_retrieval(cases, embedder, retriever, k_values=[K])
            summaries[name] = _report_to_summary(report)
    finally:
        client.close()

    JSON_REPORT_PATH.write_text(
        json.dumps(
            {"k": K, "hybrid_alpha": HYBRID_ALPHA, "methods": summaries},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    MD_REPORT_PATH.write_text(_to_markdown(summaries), encoding="utf-8")

    for name, s in summaries.items():
        print(f"{name}: Recall@{K}={s[f'recall@{K}']:.4f}  Precision@{K}={s[f'precision@{K}']:.4f}  MRR={s['mrr']:.4f}")
    print(f"报告已保存：{JSON_REPORT_PATH} 和 {MD_REPORT_PATH}")


if __name__ == "__main__":
    main()
