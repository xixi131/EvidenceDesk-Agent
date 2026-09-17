"""P6-04：多语言文档 + Embedding 模型对比实验。

复核阶段 1 那个决定——当时把 4 篇「英文为主」的参考文档排除在中文 Baseline
之外，理由是"用中文 Embedding 模型，先把语言变量控制住"。现在问三个问题：

    A  29篇 + bge-small-zh-v1.5   现状基线
    B  33篇 + bge-small-zh-v1.5   英文文档塞进中文模型，会不会反而变差？
    C  33篇 + bge-m3              换多语言模型，能不能把这 4 篇变成净收益？

A→B 只变文档集，B→C 只变模型，每一步都只动一个变量。

一个必须先说清楚的事实：那 4 篇文档切出来 898 个 chunk，而原来 29 篇只有
293 个。也就是说"加 4 篇文档"实际上是"把索引的 75% 换成英文内容"，不是小
扰动。解读结果时要记住这点——B/C 变差的话，未必是"多语言"本身的错，很可能
是这批文档体量太大造成的稀释。

三组各自建独立的 Weaviate 集合：文档集不同必须分开，而且 bge-small-zh 是
512 维、bge-m3 是 1024 维，维度不同根本塞不进同一个集合。
"""

import json
import resource
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evidence_desk.core.config import get_settings
from evidence_desk.evaluation.dataset import load_eval_cases
from evidence_desk.evaluation.metrics import group_recall_by_tag
from evidence_desk.evaluation.runner import evaluate_retrieval
from evidence_desk.infrastructure.embedding import BgeEmbeddingAdapter
from evidence_desk.infrastructure.weaviate import (
    KnowledgeChunkIndexer,
    WeaviateDenseRetriever,
    connect_to_weaviate,
    ensure_knowledge_chunk_collection,
)
from evidence_desk.rag.chunking.chunk_quality_pipeline import (
    build_chunks_from_cleaned_corpus,
)
from evidence_desk.rag.corpus.manifest import (
    FROZEN_ZH_BASELINE,
    MULTILINGUAL_BASELINE,
    BaselineSpec,
)
from evidence_desk.rag.embedding_text import build_embedding_text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ZH_CORPUS = PROJECT_ROOT / "data/knowledge_base/github_actions_zh_v1"
MULTI_CORPUS = PROJECT_ROOT / "data/knowledge_base/github_actions_multilingual_v1"
DEV_SET_PATH = PROJECT_ROOT / "data/evaluation/dev_v1.jsonl"
JSON_REPORT_PATH = PROJECT_ROOT / "data/evaluation/multilingual_eval_v1.json"
MD_REPORT_PATH = PROJECT_ROOT / "data/evaluation/multilingual_eval_v1.md"
K = 5


@dataclass(frozen=True)
class Experiment:
    """一组实验配置。"""

    name: str
    corpus_root: Path
    spec: BaselineSpec
    embedding_model: str
    collection_name: str


EXPERIMENTS = (
    Experiment(
        name="A: 29篇 + bge-small-zh",
        corpus_root=ZH_CORPUS,
        spec=FROZEN_ZH_BASELINE,
        embedding_model="BAAI/bge-small-zh-v1.5",
        collection_name="P604ZhSmall",
    ),
    Experiment(
        name="B: 33篇 + bge-small-zh",
        corpus_root=MULTI_CORPUS,
        spec=MULTILINGUAL_BASELINE,
        embedding_model="BAAI/bge-small-zh-v1.5",
        collection_name="P604MultiSmall",
    ),
    Experiment(
        name="C: 33篇 + bge-m3",
        corpus_root=MULTI_CORPUS,
        spec=MULTILINGUAL_BASELINE,
        embedding_model="BAAI/bge-m3",
        collection_name="P604MultiM3",
    ),
)


def _peak_rss_mb() -> float:
    """当前进程的峰值常驻内存（MB）。

    ru_maxrss 在 macOS 上是字节、Linux 上是 KB，这里按 macOS 处理。
    注意这是**进程峰值**不是单步增量：三组顺序跑在同一个进程里，后面的组会
    继承前面的峰值，所以这个数只适合看"跑完这一组时内存到过多高"，不能拿来
    直接相减算某一组的开销。
    """

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)


def run_experiment(experiment: Experiment) -> dict[str, Any]:
    """建索引 + 跑评测，返回质量和性能指标。"""

    settings = get_settings()
    chunks, _ = build_chunks_from_cleaned_corpus(
        experiment.corpus_root, spec=experiment.spec
    )
    texts = [build_embedding_text(chunk) for chunk in chunks]

    load_started = time.perf_counter()
    embedder = BgeEmbeddingAdapter(
        experiment.embedding_model, settings.embedding_cache_dir
    )
    model_load_seconds = time.perf_counter() - load_started

    embed_started = time.perf_counter()
    vectors = embedder.embed_documents(texts)
    embed_seconds = time.perf_counter() - embed_started

    client = connect_to_weaviate(settings)
    try:
        collection = ensure_knowledge_chunk_collection(
            client, recreate=True, collection_name=experiment.collection_name
        )
        write_started = time.perf_counter()
        KnowledgeChunkIndexer(collection).insert_many(
            chunks, vectors, embedding_model=embedder.model_name
        )
        write_seconds = time.perf_counter() - write_started

        cases = load_eval_cases(DEV_SET_PATH)
        query_started = time.perf_counter()
        report = evaluate_retrieval(
            cases, embedder, WeaviateDenseRetriever(collection), k_values=[K]
        )
        query_seconds = time.perf_counter() - query_started
    finally:
        client.close()

    tag_recall = group_recall_by_tag([(c.tags, c.recall[K]) for c in report.cases])
    return {
        "chunk_count": len(chunks),
        "vector_dim": len(vectors[0]),
        f"recall@{K}": round(report.avg_recall[K], 4),
        f"precision@{K}": round(report.avg_precision[K], 4),
        "mrr": round(report.mrr, 4),
        "model_load_seconds": round(model_load_seconds, 1),
        "embed_seconds": round(embed_seconds, 1),
        "write_seconds": round(write_seconds, 1),
        "ms_per_query": round(query_seconds * 1000 / report.num_cases, 1),
        "peak_rss_mb": round(_peak_rss_mb(), 1),
        f"tag_recall@{K}": {tag: round(v, 4) for tag, v in sorted(tag_recall.items())},
    }


def _to_markdown(results: dict[str, dict[str, Any]]) -> str:
    names = list(results.keys())
    lines = [
        "# 多语言文档 + Embedding 模型对比（P6-04）",
        "",
        f"- 评测集：dev_v1.jsonl，K={K}，Dense 检索，固定 Chunk 配置 600/80",
        "- A→B 只变文档集，B→C 只变 Embedding 模型",
        "",
        "## 背景",
        "",
        "阶段 1 建中文 Baseline 时排除了 4 篇「英文为主」的参考文档"
        "（workflow-syntax 的中文字符占比只有 0.04%，另外 3 篇是 REST API "
        "文档），理由记在 baseline_manifest 里：用中文 Embedding 模型，"
        "先把语言变量控制住。那 4 条记录上预留了 "
        "`future_experiment: github-actions-multilingual-reference-v1`，"
        "就是这个实验。",
        "",
        "**解读结果前必须知道的一点**：那 4 篇切出 898 个 chunk，原来 29 篇"
        "只有 293 个。「加 4 篇文档」实际是「把索引的 75% 换成英文内容」，"
        "不是小扰动。B/C 若变差，未必是多语言本身的问题，更可能是这批文档"
        "体量太大造成的稀释。",
        "",
        "## 质量",
        "",
        "| 配置 | Chunk 数 | 向量维度 | Recall@K | Precision@K | MRR |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for name in names:
        r = results[name]
        lines.append(
            f"| {name} | {r['chunk_count']} | {r['vector_dim']} "
            f"| {r[f'recall@{K}']:.4f} | {r[f'precision@{K}']:.4f} | {r['mrr']:.4f} |"
        )

    lines += [
        "",
        "## 成本（索引时间 / 延迟 / 内存）",
        "",
        "| 配置 | 模型加载(s) | 向量化(s) | 写库(s) | 每题查询(ms) | 峰值内存(MB) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for name in names:
        r = results[name]
        lines.append(
            f"| {name} | {r['model_load_seconds']:.1f} | {r['embed_seconds']:.1f} "
            f"| {r['write_seconds']:.1f} | {r['ms_per_query']:.1f} "
            f"| {r['peak_rss_mb']:.1f} |"
        )
    lines += [
        "",
        "峰值内存是**进程累计峰值**（三组顺序跑在同一进程里），只能看"
        "「跑到这一组时内存到过多高」，不能相减算单组开销。",
        "",
        "## 按标签细分的 Recall@K",
        "",
    ]
    all_tags = sorted({t for r in results.values() for t in r[f"tag_recall@{K}"]})
    lines += [
        "| 标签 | " + " | ".join(names) + " |",
        "| --- | " + " | ".join(["---"] * len(names)) + " |",
    ]
    for tag in all_tags:
        row = [
            f"{results[name][f'tag_recall@{K}'].get(tag, float('nan')):.4f}"
            for name in names
        ]
        lines.append(f"| {tag} | " + " | ".join(row) + " |")

    return "\n".join(lines) + "\n"


def main() -> None:
    results: dict[str, dict[str, Any]] = {}
    for experiment in EXPERIMENTS:
        print(f"\n===== {experiment.name} =====")
        results[experiment.name] = run_experiment(experiment)
        r = results[experiment.name]
        print(
            f"chunk={r['chunk_count']} dim={r['vector_dim']} "
            f"Recall@{K}={r[f'recall@{K}']:.4f} MRR={r['mrr']:.4f} "
            f"向量化={r['embed_seconds']:.1f}s 查询={r['ms_per_query']:.1f}ms/题"
        )

    JSON_REPORT_PATH.write_text(
        json.dumps({"k": K, "experiments": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    MD_REPORT_PATH.write_text(_to_markdown(results), encoding="utf-8")
    print(f"\n报告已保存：{JSON_REPORT_PATH} 和 {MD_REPORT_PATH}")


if __name__ == "__main__":
    main()
