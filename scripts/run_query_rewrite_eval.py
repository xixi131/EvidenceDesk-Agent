"""Query Rewrite 对比实验（P6-02）。

三组对比，一次只变"要不要改写、什么时候改写"这一个变量：

    Original           直接拿用户原问题检索（当前生产行为，基准组）
    RewriteAlways      每道题都先让 LLM 改写，再拿改写后的问题检索
    RewriteOnFailure   先用原问题检索；Top-1 分数低于阈值才改写并重查一次

为什么要有 RewriteOnFailure 这一组：路线图 P6-02 写的是"比较 original_query
与**失败后** rewrite"。无条件改写会让每道题都吃一次 LLM 延迟，而且给了模型
51 次机会去破坏那些本来就检索得好好的问题；只在没把握时才改写，是生产里更
现实的用法。

失败信号怎么定：生产环境拿不到标准答案，不能用 Recall 判失败（那是作弊——
用答案去决定要不要重查，线上根本做不到）。这里用检索器自己给的 Top-1 score
低于阈值作为"没把握"的代理信号，这是线上真能算出来的东西。阈值默认值见
config.py，脚本会打印真实的分数分布供你回头调。

底层检索固定用 Dense（main.py 当前的生产配置），不开重排——一次只动一个变量。
Hybrid / Rerank 的取舍是 P6-03/P6-05 的事，混在一起就说不清是谁的功劳。

运行前置：Weaviate 已导入 Baseline，且 .env 里配了 OPENAI_API_KEY。
"""

import argparse
import json
import statistics
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from evidence_desk.application.ports import ChunkRetriever, QueryEmbedder
from evidence_desk.application.query_rewriter import LlmQueryRewriter
from evidence_desk.core.config import get_settings
from evidence_desk.evaluation.dataset import EvalCase, load_eval_cases
from evidence_desk.evaluation.metrics import group_recall_by_tag
from evidence_desk.evaluation.query_rewrite_metrics import (
    diff_identifiers,
    summarize_identifiers,
)
from evidence_desk.evaluation.runner import EvalReport, evaluate_retrieval
from evidence_desk.infrastructure.embedding import BgeEmbeddingAdapter
from evidence_desk.infrastructure.llm import OpenAIChatClient
from evidence_desk.infrastructure.weaviate import (
    WeaviateDenseRetriever,
    connect_to_weaviate,
    ensure_knowledge_chunk_collection,
)

DEV_SET_PATH = Path("data/evaluation/dev_v1.jsonl")
JSON_REPORT_PATH = Path("data/evaluation/query_rewrite_eval_v1.json")
MD_REPORT_PATH = Path("data/evaluation/query_rewrite_eval_v1.md")
K = 5

ORIGINAL = "Original"
REWRITE_ALWAYS = "RewriteAlways"
REWRITE_ON_FAILURE = "RewriteOnFailure"


@dataclass(frozen=True, slots=True)
class PreparedQuery:
    """一道题最终送进检索的问题，以及它是怎么来的。"""

    case_id: str
    original: str
    final: str
    # 真的用上了改写结果才是 True。没触发改写、或改写被兜底退回原问题，都是 False。
    rewritten: bool
    fallback_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ArmTiming:
    """一组实验的耗时拆解（秒）。三段分开记，才能说清延迟加在哪。"""

    # 失败探测：只有 RewriteOnFailure 有，用原问题先检索一遍看分数。
    probe_seconds: float
    # LLM 改写调用的总耗时。
    rewrite_seconds: float
    # 正式评测检索的总耗时。
    retrieval_seconds: float


def _prepare_original(cases: list[EvalCase]) -> list[PreparedQuery]:
    """基准组：原问题原样送进检索。"""
    return [PreparedQuery(c.id, c.question, c.question, False) for c in cases]


def _prepare_rewrite_always(
    cases: list[EvalCase], rewriter: LlmQueryRewriter
) -> tuple[list[PreparedQuery], float]:
    """无条件改写组。返回准备好的问题和改写总耗时（秒）。"""

    prepared: list[PreparedQuery] = []
    started = time.perf_counter()
    for case in cases:
        result = rewriter.rewrite(case.question)
        prepared.append(
            PreparedQuery(
                case.id,
                case.question,
                result.rewritten,
                result.changed,
                result.fallback_reason,
            )
        )
    return prepared, time.perf_counter() - started


def _prepare_rewrite_on_failure(
    cases: list[EvalCase],
    embedder: QueryEmbedder,
    retriever: ChunkRetriever,
    rewriter: LlmQueryRewriter,
    *,
    threshold: float,
) -> tuple[list[PreparedQuery], float, float, list[float]]:
    """失败后改写组。

    返回 (准备好的问题, 探测耗时, 改写耗时, 每题的 Top-1 分数)。
    Top-1 分数全量返回，是为了让报告能打印分布——阈值定得合不合理，
    只有看着真实分布才判断得了，不能凭感觉拍一个数。
    """

    prepared: list[PreparedQuery] = []
    top1_scores: list[float] = []
    probe_seconds = 0.0
    rewrite_seconds = 0.0

    for case in cases:
        probe_started = time.perf_counter()
        vector = embedder.embed_query(case.question)
        hits = retriever.search(vector, top_k=1, query_text=case.question)
        probe_seconds += time.perf_counter() - probe_started

        # 一条都没捞到也算失败（score 记 0，会落在任何阈值之下）。
        top1 = hits[0].score if hits else 0.0
        top1_scores.append(top1)

        if top1 >= threshold:
            prepared.append(PreparedQuery(case.id, case.question, case.question, False))
            continue

        rewrite_started = time.perf_counter()
        result = rewriter.rewrite(case.question)
        rewrite_seconds += time.perf_counter() - rewrite_started
        prepared.append(
            PreparedQuery(
                case.id,
                case.question,
                result.rewritten,
                result.changed,
                result.fallback_reason,
            )
        )

    return prepared, probe_seconds, rewrite_seconds, top1_scores


def _apply(cases: list[EvalCase], prepared: list[PreparedQuery]) -> list[EvalCase]:
    """把准备好的问题装回 EvalCase，供 evaluate_retrieval 直接跑。

    这是整个脚本能省掉一整套评测代码的关键：evaluate_retrieval 是拿
    case.question 去检索的，那我只要造一批"问题被换成改写后文本"的 EvalCase，
    就能原样复用 P6-03/P6-05 用的同一条评测路径——指标口径完全一致，
    跨实验的数字才能横向比。

    EvalCase 是 frozen dataclass（不可改），dataclasses.replace 会照着原对象
    复制一个、只把指定字段换掉，跟 RetrievalHit 用 model_copy 是同一个套路。
    """

    by_id = {p.case_id: p for p in prepared}
    return [replace(case, question=by_id[case.id].final) for case in cases]


def _summarize(
    report: EvalReport,
    prepared: list[PreparedQuery],
    timing: ArmTiming,
    num_cases: int,
) -> dict[str, Any]:
    """把一组实验的质量、改写行为、延迟汇总成一个字典。"""

    tag_recall = group_recall_by_tag([(c.tags, c.recall[K]) for c in report.cases])
    rewritten = [p for p in prepared if p.rewritten]
    fallbacks = [p for p in prepared if p.fallback_reason]

    # 生产环境下的真实每题延迟。三组的构成不一样，不能一刀切：
    #   Original          只有一次检索
    #   RewriteAlways     每题一次 LLM 改写 + 一次检索
    #   RewriteOnFailure  每题一次探测检索 + （仅失败题）一次改写 + 一次重查
    # 最后这一项要特别小心：evaluate_retrieval 是对**所有**题都检索了一遍，
    # 但线上只有触发改写的那几题才需要重查，没触发的直接复用探测结果。
    # 直接拿 retrieval_seconds 当重查耗时会系统性高估这一组的延迟，
    # 所以这里按"单题检索均价 × 实际触发数"折算。
    retrieval_per_case = timing.retrieval_seconds / num_cases if num_cases else 0.0
    if timing.probe_seconds > 0:
        triggered = sum(1 for p in prepared if p.final != p.original or p.rewritten)
        total_seconds = (
            timing.probe_seconds
            + timing.rewrite_seconds
            + retrieval_per_case * triggered
        )
    else:
        total_seconds = timing.rewrite_seconds + timing.retrieval_seconds

    return {
        "num_cases": report.num_cases,
        f"recall@{K}": round(report.avg_recall[K], 4),
        f"precision@{K}": round(report.avg_precision[K], 4),
        "mrr": round(report.mrr, 4),
        "num_rewritten": len(rewritten),
        "rewrite_rate": round(len(rewritten) / num_cases, 4) if num_cases else 0.0,
        "num_fallback": len(fallbacks),
        "ms_per_query": round(total_seconds * 1000 / num_cases, 1)
        if num_cases
        else 0.0,
        "ms_breakdown": {
            "probe": round(timing.probe_seconds * 1000 / num_cases, 1)
            if num_cases
            else 0.0,
            "rewrite": round(timing.rewrite_seconds * 1000 / num_cases, 1)
            if num_cases
            else 0.0,
            "retrieval": round(retrieval_per_case * 1000, 1),
        },
        f"tag_recall@{K}": {tag: round(v, 4) for tag, v in sorted(tag_recall.items())},
    }


def _identifier_section(prepared: list[PreparedQuery]) -> dict[str, Any]:
    """标识符保留 / 新增的汇总 + 逐条明细（供人工抽查）。"""

    pairs = [(p.original, p.final) for p in prepared if p.rewritten]
    summary = summarize_identifiers(pairs)

    details = []
    for p in prepared:
        if not p.rewritten:
            continue
        diff = diff_identifiers(p.original, p.final)
        if diff.lost or diff.introduced:
            details.append(
                {
                    "case_id": p.case_id,
                    "original": p.original,
                    "rewritten": p.final,
                    "lost": diff.lost,
                    "introduced": diff.introduced,
                }
            )

    return {
        "num_cases_with_identifier": summary.num_cases_with_identifier,
        "num_identifiers": summary.num_identifiers,
        "num_lost": summary.num_lost,
        "retention": round(summary.retention, 4),
        "num_cases_with_loss": summary.num_cases_with_loss,
        "num_cases_with_introduced": summary.num_cases_with_introduced,
        "details": details,
    }


def _regressions(
    baseline: EvalReport, arm: EvalReport, prepared: list[PreparedQuery]
) -> list[dict[str, Any]]:
    """找出相对基准组 Recall 掉下来的题（阶段 6 门禁要求"有退化案例"）。

    平均分涨了不代表没伤到人——可能是一批题涨、另一批题崩，平均看起来还行。
    逐题比对才能把被牺牲掉的那些揪出来。
    """

    base_by_id = {c.id: c for c in baseline.cases}
    by_id = {p.case_id: p for p in prepared}

    rows = []
    for case in arm.cases:
        before = base_by_id[case.id].recall[K]
        after = case.recall[K]
        if after < before:
            p = by_id[case.id]
            rows.append(
                {
                    "case_id": case.id,
                    "tags": case.tags,
                    "recall_before": round(before, 4),
                    "recall_after": round(after, 4),
                    "original": p.original,
                    "rewritten": p.final,
                }
            )
    return rows


def _to_markdown(payload: dict[str, Any]) -> str:
    summaries: dict[str, dict[str, Any]] = payload["methods"]
    methods = list(summaries.keys())

    lines = [
        "# Query Rewrite 对比报告（P6-02）",
        "",
        "- 检索方式：Dense（不开重排，一次只动一个变量）",
        f"- Top-K：{K}",
        f"- 改写模型：`{payload['rewrite_model']}`",
        f"- 改写提示词版本：`{payload['prompt_version']}`",
        f"- 失败阈值（Top-1 score）：{payload['failure_threshold']}",
        f"- 题目数：{payload['num_cases']}",
        "",
        "## 总体指标",
        "",
        "| 方法 | Recall@K | Precision@K | MRR | 改写率 | 每题耗时(ms) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for name in methods:
        s = summaries[name]
        lines.append(
            f"| {name} | {s[f'recall@{K}']:.4f} | {s[f'precision@{K}']:.4f} "
            f"| {s['mrr']:.4f} | {s['rewrite_rate']:.2%} | {s['ms_per_query']:.1f} |"
        )

    lines += [
        "",
        "## 延迟拆解（ms/题）",
        "",
        "| 方法 | 失败探测 | LLM 改写 | 检索 | 合计 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name in methods:
        s = summaries[name]
        b = s["ms_breakdown"]
        lines.append(
            f"| {name} | {b['probe']:.1f} | {b['rewrite']:.1f} "
            f"| {b['retrieval']:.1f} | {s['ms_per_query']:.1f} |"
        )

    lines += [
        "",
        "## 精确标识符保留情况",
        "",
        "只统计**真的被改写过**的题。保留率的分母是原问题里的标识符总数；"
        "大小写变化不算丢失（索引和查询都会归一化），标识符整个消失或被翻译成"
        "中文才算。",
        "",
        "| 方法 | 含标识符题数 | 标识符总数 | 丢失个数 | 保留率 | 丢失题数 | 新增标识符题数 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name in methods:
        ident = payload["identifiers"].get(name)
        if not ident:
            continue
        lines.append(
            f"| {name} | {ident['num_cases_with_identifier']} "
            f"| {ident['num_identifiers']} | {ident['num_lost']} "
            f"| {ident['retention']:.4f} | {ident['num_cases_with_loss']} "
            f"| {ident['num_cases_with_introduced']} |"
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

    lines += [
        "",
        "## 退化案例（相对 Original 掉分的题）",
        "",
    ]
    any_regression = False
    for name in methods:
        rows = payload["regressions"].get(name, [])
        if not rows:
            continue
        any_regression = True
        lines += [f"### {name}", ""]
        for r in rows:
            lines += [
                f"- **{r['case_id']}**（{', '.join(r['tags'])}）"
                f"Recall {r['recall_before']:.2f} → {r['recall_after']:.2f}",
                f"  - 原问题：{r['original']}",
                f"  - 改写后：{r['rewritten']}",
            ]
        lines.append("")
    if not any_regression:
        lines += ["无。", ""]

    lines += [
        "## 标识符异常明细（人工抽查用）",
        "",
        "`lost` 是真问题；`introduced` 只是**可疑**——模型把「手动触发」归一化成 "
        "`workflow_dispatch` 反而可能帮到检索，必须逐条看原文判断，不能自动判错。",
        "",
    ]
    any_detail = False
    for name in methods:
        details = payload["identifiers"].get(name, {}).get("details", [])
        if not details:
            continue
        any_detail = True
        lines += [f"### {name}", ""]
        for d in details:
            lines += [
                f"- **{d['case_id']}**",
                f"  - 原问题：{d['original']}",
                f"  - 改写后：{d['rewritten']}",
                f"  - 丢失：{d['lost'] or '无'}；新增：{d['introduced'] or '无'}",
            ]
        lines.append("")
    if not any_detail:
        lines += ["无。", ""]

    dist = payload["top1_score_distribution"]
    lines += [
        "## Top-1 分数分布（用于校准失败阈值）",
        "",
        "RewriteOnFailure 用「Top-1 score 低于阈值」当失败信号。阈值定得对不对，"
        "要看这份真实分布——阈值太低则永远不触发（等于 Original），"
        "太高则每题都触发（等于 RewriteAlways）。",
        "",
        f"- 最小值：{dist['min']:.4f}",
        f"- 25 分位：{dist['p25']:.4f}",
        f"- 中位数：{dist['median']:.4f}",
        f"- 75 分位：{dist['p75']:.4f}",
        f"- 最大值：{dist['max']:.4f}",
        f"- 当前阈值 {payload['failure_threshold']} 下触发改写：{dist['triggered']} 题",
        "",
    ]

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Query Rewrite 对比实验（P6-02）")
    parser.add_argument(
        "--failure-threshold",
        type=float,
        default=None,
        help="RewriteOnFailure 的 Top-1 分数阈值；不传则用 config 里的默认值",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.openai_api_key:
        raise SystemExit("未配置 OPENAI_API_KEY，无法运行改写实验。")

    threshold = (
        args.failure_threshold
        if args.failure_threshold is not None
        else settings.query_rewrite_score_threshold
    )

    # 只评有答案且标注了相关文档的题：跟 evaluate_retrieval 内部的筛选口径
    # 保持一致，这样"题目数"在改写阶段和评测阶段是同一批，统计才对得上。
    cases = [
        c
        for c in load_eval_cases(DEV_SET_PATH)
        if c.should_answer and c.relevant_doc_ids
    ]
    num_cases = len(cases)

    embedder = BgeEmbeddingAdapter(
        settings.embedding_model, settings.embedding_cache_dir
    )
    rewriter = LlmQueryRewriter(
        OpenAIChatClient(
            api_key=settings.openai_api_key,
            model=settings.answer_model,
            base_url=settings.openai_base_url,
        ),
        # 温度 0：改写必须可复现，否则重跑一次数字就变，实验没法复核。
        temperature=0.0,
    )

    client = connect_to_weaviate(settings)
    try:
        collection = ensure_knowledge_chunk_collection(client)
        retriever = WeaviateDenseRetriever(collection)

        print(f"共 {num_cases} 道有答案的题，失败阈值 {threshold}")

        prepared_by_arm: dict[str, list[PreparedQuery]] = {}
        timing_by_arm: dict[str, ArmTiming] = {}

        prepared_by_arm[ORIGINAL] = _prepare_original(cases)
        timing_by_arm[ORIGINAL] = ArmTiming(0.0, 0.0, 0.0)

        print("改写全部问题中（每题一次 LLM 调用）……")
        always, always_rewrite_s = _prepare_rewrite_always(cases, rewriter)
        prepared_by_arm[REWRITE_ALWAYS] = always
        timing_by_arm[REWRITE_ALWAYS] = ArmTiming(0.0, always_rewrite_s, 0.0)

        print("探测失败题并改写中……")
        on_failure, probe_s, failure_rewrite_s, top1_scores = (
            _prepare_rewrite_on_failure(
                cases, embedder, retriever, rewriter, threshold=threshold
            )
        )
        prepared_by_arm[REWRITE_ON_FAILURE] = on_failure
        timing_by_arm[REWRITE_ON_FAILURE] = ArmTiming(probe_s, failure_rewrite_s, 0.0)

        reports: dict[str, EvalReport] = {}
        for name, prepared in prepared_by_arm.items():
            started = time.perf_counter()
            reports[name] = evaluate_retrieval(
                _apply(cases, prepared), embedder, retriever, k_values=[K]
            )
            elapsed = time.perf_counter() - started
            timing_by_arm[name] = replace(
                timing_by_arm[name], retrieval_seconds=elapsed
            )
    finally:
        client.close()

    summaries = {
        name: _summarize(
            reports[name], prepared_by_arm[name], timing_by_arm[name], num_cases
        )
        for name in prepared_by_arm
    }
    for name, s in summaries.items():
        print(
            f"{name}: Recall@{K}={s[f'recall@{K}']:.4f}  MRR={s['mrr']:.4f}  "
            f"改写率={s['rewrite_rate']:.2%}  {s['ms_per_query']:.1f}ms/题"
        )

    sorted_scores = sorted(top1_scores)
    payload: dict[str, Any] = {
        "k": K,
        "num_cases": num_cases,
        "retriever": "Dense",
        "rewrite_model": settings.answer_model,
        "prompt_version": rewriter.prompt_version,
        "failure_threshold": threshold,
        "methods": summaries,
        "identifiers": {
            name: _identifier_section(prepared)
            for name, prepared in prepared_by_arm.items()
            if name != ORIGINAL
        },
        "regressions": {
            name: _regressions(reports[ORIGINAL], reports[name], prepared_by_arm[name])
            for name in prepared_by_arm
            if name != ORIGINAL
        },
        "top1_score_distribution": {
            "min": min(sorted_scores),
            "p25": sorted_scores[len(sorted_scores) // 4],
            "median": statistics.median(sorted_scores),
            "p75": sorted_scores[len(sorted_scores) * 3 // 4],
            "max": max(sorted_scores),
            "triggered": sum(1 for s in sorted_scores if s < threshold),
        },
    }

    JSON_REPORT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    MD_REPORT_PATH.write_text(_to_markdown(payload), encoding="utf-8")
    print(f"报告已保存：{JSON_REPORT_PATH} 和 {MD_REPORT_PATH}")


if __name__ == "__main__":
    main()
