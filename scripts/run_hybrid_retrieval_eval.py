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
from evidence_desk.rag.tokenization import TOKENIZER_VERSION

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
        "## 中文分词方案",
        "",
        f"分词版本：`{TOKENIZER_VERSION}`（应用侧 jieba + 领域词典，"
        "见 `src/evidence_desk/rag/tokenization.py`）",
        "",
        "上一轮用 Weaviate 内置的 GSE_CH 分词器时，BM25 在中文上几乎完全失效"
        "（Recall@5=0.1176，「标签」「构件」「取消」等词确认存在于原文却"
        "返回 0 条）。根因是索引端和查询端切词不一致——BM25 靠 token 精确"
        "相等匹配，两端切法不同就永远匹配不上。排查过程见"
        "`/Users/tangxitao/学习/My-Notes/Agent开发/错误记录/"
        "Weaviate中文BM25分词失效排查.md`。",
        "",
        "现在改为：索引和查询都调用同一个 `segment()` 切词，Weaviate 侧的"
        "`content_tokens`/`title_tokens` 字段只用 WHITESPACE 分词（按空格切，"
        "不做任何推断）。分词的确定性由应用代码保证，失配这类问题从结构上消除。",
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
            {
                "k": K,
                "hybrid_alpha": HYBRID_ALPHA,
                "tokenizer_version": TOKENIZER_VERSION,
                "methods": summaries,
            },
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
