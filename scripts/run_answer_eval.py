"""回答层评测（P6-06）：跑一遍全部题目，判分，出报告。

分两段，对应 answer_runner.py 里讲的那个拆分：

    阶段 A「跑」：60 道题各生成一次答案，结果存进 answer_run_v1.jsonl
    阶段 B「判」：读那个文件，算指标，写报告

默认两段都跑。加 --reuse-run 就跳过阶段 A，直接读上次的 run 文件重新判分——
改指标、加指标时用这个，一次 LLM 都不用重调。

四个指标都在这里：Refusal Accuracy 和 Citation 的结构性部分纯规则判，
Faithfulness / Answer Quality / Citation 的语义部分交给 LLM Judge。

前置：Weaviate 已导入 Baseline，.env 里配了 OPENAI_API_KEY。
"""

import argparse
import json
from pathlib import Path
from typing import Any

from evidence_desk.application.chat_service import ChatService
from evidence_desk.application.rag_answer_service import (
    ANSWER_PROMPT_VERSION,
    RagAnswerService,
)
from evidence_desk.core.config import get_settings
from evidence_desk.evaluation.answer_judge import (
    JUDGE_PROMPT_VERSION,
    AnswerJudge,
    JudgeVerdict,
    append_verdict,
    load_verdicts,
)
from evidence_desk.evaluation.answer_metrics import (
    detect_refusal,
    has_citation,
    missed_refusal,
    out_of_range_markers,
    over_refusal,
    refusal_correct,
    retrieval_hit,
)
from evidence_desk.evaluation.answer_runner import (
    AnswerRunRecord,
    append_run,
    iter_answers,
    load_run,
)
from evidence_desk.evaluation.dataset import load_eval_cases
from evidence_desk.infrastructure.embedding import BgeEmbeddingAdapter
from evidence_desk.infrastructure.llm import OpenAIChatClient
from evidence_desk.infrastructure.weaviate import (
    WeaviateDenseRetriever,
    connect_to_weaviate,
    ensure_knowledge_chunk_collection,
)
from evidence_desk.rag.citations import parse_citation_markers

DEV_SET_PATH = Path("data/evaluation/dev_v1.jsonl")
RUN_PATH = Path("data/evaluation/answer_run_v1.jsonl")
JUDGE_PATH = Path("data/evaluation/answer_judge_v1.jsonl")
JSON_REPORT_PATH = Path("data/evaluation/answer_eval_v1.json")
MD_REPORT_PATH = Path("data/evaluation/answer_eval_v1.md")


def _run_generation() -> list[AnswerRunRecord]:
    """阶段 A：装配生产同款链路，跑一遍全部题目，**边跑边写盘**。

    支持断点续传：run 文件里已经有结果的题直接跳过。
    这是被一次真实事故逼出来的——跑到一半 LLM 服务返回 503，脚本崩掉，
    前面几十次模型调用全白费。现在崩了再跑一次就从断点接上。

    想重新跑全部题目时，删掉 run 文件即可。
    """

    settings = get_settings()
    if not settings.openai_api_key:
        raise SystemExit("未配置 OPENAI_API_KEY，无法生成回答。")

    # 注意这里**不过滤** should_answer=False 的题。检索评测那边会把它们筛掉
    # （没有标注相关文档，算不了 Recall），但 Refusal Accuracy 要测的恰恰
    # 就是这批「跑题问题」，一道都不能少。
    cases = load_eval_cases(DEV_SET_PATH)

    # 断点续传：已经跑过的题跳过。注意要校验提示词版本——换了提示词之后
    # 旧结果就不能用了，混在一起等于把两个不同系统的输出算成一份报告。
    done: list[AnswerRunRecord] = []
    if RUN_PATH.exists():
        existing = load_run(RUN_PATH)
        stale = [r for r in existing if r.prompt_version != ANSWER_PROMPT_VERSION]
        if stale:
            raise SystemExit(
                f"{RUN_PATH} 里有 {len(stale)} 条是旧提示词版本"
                f"（{stale[0].prompt_version}，当前是 {ANSWER_PROMPT_VERSION}）。"
                "新旧结果不能混算，请先删除该文件再重跑。"
            )
        done = existing
        print(f"续跑：已有 {len(done)} 条结果，跳过这些题")

    done_ids = {r.id for r in done}
    todo = [c for c in cases if c.id not in done_ids]
    print(
        f"共 {len(cases)} 道题（含 {sum(1 for c in cases if not c.should_answer)} 道应拒答）"
        f"，本次要跑 {len(todo)} 道"
    )
    if not todo:
        return done

    embedder = BgeEmbeddingAdapter(
        settings.embedding_model, settings.embedding_cache_dir
    )
    llm = OpenAIChatClient(
        api_key=settings.openai_api_key,
        model=settings.answer_model,
        base_url=settings.openai_base_url,
    )
    answer_service = RagAnswerService(
        llm,
        temperature=settings.answer_temperature,
        # 拒答第 0 层闸门（见 refusal.py 的四层说明）：检索置信度不够就直接拒答。
        min_score=settings.answer_min_score,
    )

    client = connect_to_weaviate(settings)
    try:
        collection = ensure_knowledge_chunk_collection(client)
        # 跟 main.py 的装配保持一致：Dense 检索 + retrieval_top_k。
        # 评测必须测生产真正在跑的那套配置，换了就不是同一个系统了。
        chat_service = ChatService(
            embedder,
            WeaviateDenseRetriever(collection),
            answer_service,
            top_k=settings.retrieval_top_k,
        )
        records = list(done)
        # 每跑完一题就立刻追加写盘：中途崩了，已完成的部分留在文件里。
        for record in iter_answers(todo, chat_service):
            append_run(record, RUN_PATH)
            records.append(record)
        return records
    finally:
        client.close()


def _answered(record: AnswerRunRecord) -> bool:
    """判分时重新判定「这题到底答了没」，不直接用 run 文件里存的 answered。

    为什么要重判：run 文件是**历史产物**，里面的 answered 用的是当时那版判定
    逻辑。生产侧现在已经换成 detect_refusal 了，但老的 run 文件还留着旧结果。
    在这里统一重判，保证「同一批数据，换了判定逻辑就能重新算」——这正是
    跑判分离的意义：判定逻辑可以演进，历史数据不用重跑。
    """

    return not detect_refusal(record.answer)


def _score_refusal(records: list[AnswerRunRecord]) -> dict[str, Any]:
    """阶段 B：算 Refusal Accuracy，两类错误分开，误拒再按检索有没有命中归因。"""

    correct = sum(1 for r in records if refusal_correct(r.should_answer, _answered(r)))
    over = [r for r in records if over_refusal(r.should_answer, _answered(r))]
    missed = [r for r in records if missed_refusal(r.should_answer, _answered(r))]

    # 误拒归因：检索没捞到正确文档时，模型说「答不了」是**正确行为**，
    # 该修的是检索不是提示词。两种误拒混在一个数字里，会把两条相反的
    # 修复方向糊住。
    over_no_retrieval = [
        r
        for r in over
        if not retrieval_hit(r.relevant_doc_ids, [h.parent_doc_id for h in r.hits])
    ]
    over_with_retrieval = [r for r in over if r not in over_no_retrieval]

    # 分母分开算：误拒率的分母是「该答的题」，漏拒率的分母是「该拒的题」。
    # 用总题数当分母会把两个率都稀释得看不出来——9 道应拒答的题里漏了 3 道
    # （漏拒率 33%，很严重），除以 60 会变成 5%，看着像没事。
    num_should_answer = sum(1 for r in records if r.should_answer)
    num_should_refuse = len(records) - num_should_answer

    return {
        "num_cases": len(records),
        "accuracy": round(correct / len(records), 4) if records else 0.0,
        "num_should_answer": num_should_answer,
        "num_should_refuse": num_should_refuse,
        "over_refusal_count": len(over),
        "over_refusal_rate": round(len(over) / num_should_answer, 4)
        if num_should_answer
        else 0.0,
        "missed_refusal_count": len(missed),
        "missed_refusal_rate": round(len(missed) / num_should_refuse, 4)
        if num_should_refuse
        else 0.0,
        "over_refusal_no_retrieval": len(over_no_retrieval),
        "over_refusal_with_retrieval": len(over_with_retrieval),
        # 逐条列出错的题，供人工核对。指标只给一个数，看不出「为什么错」；
        # 阶段 6 门禁要求「有失败案例」，靠的就是这份清单。
        "over_refusal_cases": [
            {
                "id": r.id,
                "tags": r.tags,
                "question": r.question,
                "retrieval_hit": retrieval_hit(
                    r.relevant_doc_ids, [h.parent_doc_id for h in r.hits]
                ),
                # 捞回来的章节路径——dev-060 那种「文档对了但章节答非所问」
                # 一眼就能看出来。
                "retrieved_sections": [" > ".join(h.section_path) for h in r.hits[:3]],
            }
            for r in over
        ],
        "missed_refusal_cases": [
            {"id": r.id, "tags": r.tags, "question": r.question, "answer": r.answer}
            for r in missed
        ],
    }


def _score_citations(records: list[AnswerRunRecord]) -> dict[str, Any]:
    """Citation Correctness 的**结构性**部分——纯规则，不用 Judge。

    两种失败纯靠规则就能百分百查准，没道理为它多花模型调用：
    1. 越界引用：只有 5 条资料却标了 [7]，用户点进去什么都没有；
    2. 该引不引：一句结论光秃秃摆着，用户没有任何核实途径。

    语义那一半（「[2] 指向的资料真的支撑这句话吗」）才交给 Judge。
    """

    answered = [r for r in records if _answered(r)]
    total = len(answered)

    no_citation = []
    out_of_range = []
    for record in answered:
        markers = parse_citation_markers(record.answer)
        if not has_citation(markers):
            no_citation.append(record)
            continue
        bad = out_of_range_markers(markers, len(record.hits))
        if bad:
            out_of_range.append((record, bad))

    return {
        "num_answered": total,
        "no_citation_count": len(no_citation),
        "no_citation_rate": round(len(no_citation) / total, 4) if total else 0.0,
        "out_of_range_count": len(out_of_range),
        "out_of_range_rate": round(len(out_of_range) / total, 4) if total else 0.0,
        "no_citation_cases": [
            {"id": r.id, "question": r.question} for r in no_citation[:10]
        ],
        "out_of_range_cases": [
            {
                "id": r.id,
                "question": r.question,
                "bad_markers": bad,
                "num_hits": len(r.hits),
            }
            for r, bad in out_of_range[:10]
        ],
    }


def _run_judge(records: list[AnswerRunRecord]) -> list[JudgeVerdict]:
    """对「真的答了」的题逐条判分。拒答的题没内容可判，跳过。"""

    settings = get_settings()
    if not settings.openai_api_key:
        raise SystemExit("未配置 OPENAI_API_KEY，无法运行 judge。")

    judge = AnswerJudge(
        OpenAIChatClient(
            api_key=settings.openai_api_key,
            model=settings.answer_model,
            base_url=settings.openai_base_url,
        )
    )

    # 同样支持断点续传（judge 要调几十次模型，崩一次代价不小）。
    done: list[JudgeVerdict] = load_verdicts(JUDGE_PATH) if JUDGE_PATH.exists() else []
    done_ids = {v.case_id for v in done}
    targets = [r for r in records if _answered(r) and r.id not in done_ids]
    print(f"judge 开始：{len(targets)} 道待判（已有 {len(done)} 条，拒答题跳过）")

    verdicts = list(done)
    for index, record in enumerate(targets, start=1):
        verdict = judge.judge(record.id, record.question, record.answer, record.hits)
        append_verdict(verdict, JUDGE_PATH)
        verdicts.append(verdict)
        print(f"  [{index}/{len(targets)}] {record.id} 判完")
    return verdicts


def _score_judge(
    verdicts: list[JudgeVerdict], records: list[AnswerRunRecord]
) -> dict[str, Any]:
    """把 judge 的逐题判定汇总成两个指标 + 人工抽查样本。"""

    by_id = {r.id: r for r in records}
    total = len(verdicts)

    def _rate(field: str, value: str) -> float:
        hits = sum(1 for v in verdicts if getattr(v, field) == value)
        return round(hits / total, 4) if total else 0.0

    # 解析失败率单独报：它不是模型答得差，是 judge 的输出格式没兜住，
    # 属于评测工具自身的问题，混进指标里会把结论带偏。
    parse_errors = [v for v in verdicts if v.faithfulness == "parse_error"]

    unfaithful = [
        v for v in verdicts if v.faithfulness in ("partially_supported", "unsupported")
    ]
    low_quality = [v for v in verdicts if v.answer_quality in ("partial", "incorrect")]

    def _detail(v: JudgeVerdict) -> dict[str, Any]:
        record = by_id.get(v.case_id)
        return {
            "case_id": v.case_id,
            "question": record.question if record else "",
            "answer": record.answer if record else "",
            "faithfulness": v.faithfulness,
            "answer_quality": v.answer_quality,
            "citation_support": v.citation_support,
            "unsupported_claims": v.unsupported_claims,
            "reason": v.reason,
        }

    return {
        "num_judged": total,
        "parse_error_count": len(parse_errors),
        "faithfulness": {
            "supported": _rate("faithfulness", "supported"),
            "partially_supported": _rate("faithfulness", "partially_supported"),
            "unsupported": _rate("faithfulness", "unsupported"),
        },
        "answer_quality": {
            "correct": _rate("answer_quality", "correct"),
            "partial": _rate("answer_quality", "partial"),
            "incorrect": _rate("answer_quality", "incorrect"),
        },
        "citation_support": {
            "supported": _rate("citation_support", "supported"),
            "partially_supported": _rate("citation_support", "partially_supported"),
            "unsupported": _rate("citation_support", "unsupported"),
            "no_citation": _rate("citation_support", "no_citation"),
        },
        "unfaithful_cases": [_detail(v) for v in unfaithful],
        "low_quality_cases": [_detail(v) for v in low_quality],
        # 人工抽查样本：judge 判「全对」的题里随便取几条。抽查要抽**它说对的**，
        # 因为 judge 最常见的毛病是过于宽松、无脑给高分。只看它报的问题，
        # 等于只检查它已经承认的错误，抓不到它放过去的。
        "manual_review_sample": [
            _detail(v)
            for v in verdicts
            if v.faithfulness == "supported" and v.answer_quality == "correct"
        ][:5],
    }


def _to_markdown(payload: dict[str, Any]) -> str:
    refusal = payload["refusal"]
    lines = [
        "# 回答层评测报告（P6-06）",
        "",
        f"- 检索方式：Dense，top_k={payload['top_k']}",
        f"- 回答模型：`{payload['answer_model']}`",
        f"- 提示词版本：`{payload['prompt_version']}`",
        f"- 题目数：{refusal['num_cases']}"
        f"（应答 {refusal['num_should_answer']} / 应拒答 {refusal['num_should_refuse']}）",
        "",
        "## Refusal Accuracy（拒答准确率）",
        "",
        f"**{refusal['accuracy']:.4f}**",
        "",
        "两类错误分开看——它们的严重程度差着量级：",
        "",
        "| 错误类型 | 含义 | 次数 | 比率 | 分母 |",
        "| --- | --- | --- | --- | --- |",
        f"| 误拒 over_refusal | 该答却说没找到 | {refusal['over_refusal_count']} "
        f"| {refusal['over_refusal_rate']:.4f} | 应答题数 |",
        f"| 漏拒 missed_refusal | 不该答却编了一段 | {refusal['missed_refusal_count']} "
        f"| {refusal['missed_refusal_rate']:.4f} | 应拒答题数 |",
        "",
        "误拒是体验问题（用户知道自己没拿到答案）；漏拒是安全事故"
        "（用户拿到一段编造内容，底下还挂着官方链接当证据，毫无察觉）。",
        "",
    ]

    if refusal["missed_refusal_cases"]:
        lines += ["### 漏拒案例（优先排查）", ""]
        for case in refusal["missed_refusal_cases"]:
            lines += [
                f"- **{case['id']}**（{', '.join(case['tags'])}）{case['question']}",
                f"  - 系统回答：{case['answer']}",
            ]
        lines.append("")
    else:
        lines += ["### 漏拒案例", "", "无。", ""]

    lines += [
        "### 误拒归因",
        "",
        f"- 检索**没捞到**正确文档（模型拒答是正确行为，该修检索）："
        f"{refusal['over_refusal_no_retrieval']} 题",
        f"- 检索**捞到了**仍拒答（该修提示词或分块）："
        f"{refusal['over_refusal_with_retrieval']} 题",
        "",
    ]
    if refusal["over_refusal_cases"]:
        for case in refusal["over_refusal_cases"]:
            flag = "检索命中" if case["retrieval_hit"] else "**检索未命中**"
            lines += [
                f"- **{case['id']}**（{', '.join(case['tags'])}）{case['question']} — {flag}",
                f"  - 捞回的章节：{' ／ '.join(case['retrieved_sections'])}",
            ]
        lines.append("")
    else:
        lines += ["无。", ""]

    cite = payload["citation_structure"]
    lines += [
        "## Citation Correctness — 结构性（纯规则）",
        "",
        f"统计范围：{cite['num_answered']} 道已回答的题。",
        "",
        "| 失败类型 | 含义 | 次数 | 比率 |",
        "| --- | --- | --- | --- |",
        f"| 该引不引 | 一个 [n] 标号都没有，用户无从核实 "
        f"| {cite['no_citation_count']} | {cite['no_citation_rate']:.4f} |",
        f"| 越界引用 | 标了参考资料里不存在的编号 "
        f"| {cite['out_of_range_count']} | {cite['out_of_range_rate']:.4f} |",
        "",
        "> 这两种纯规则就能百分百查准，不花一次模型调用。"
        "语义那一半（「[2] 指向的资料真支撑这句话吗」）见下面 Judge 的 citation_support。",
        "",
    ]
    if cite["out_of_range_cases"]:
        lines += ["### 越界引用案例", ""]
        for case in cite["out_of_range_cases"]:
            lines.append(
                f"- **{case['id']}** 标了 {case['bad_markers']}，"
                f"但只有 {case['num_hits']} 条资料 — {case['question']}"
            )
        lines.append("")
    if cite["no_citation_cases"]:
        lines += ["### 该引不引案例", ""]
        for case in cite["no_citation_cases"]:
            lines.append(f"- **{case['id']}** {case['question']}")
        lines.append("")

    judge = payload.get("judge")
    if judge:
        lines += [
            "## Faithfulness（忠实度，LLM Judge）",
            "",
            f"判定题数：{judge['num_judged']}（拒答题不参与）"
            f"；解析失败：{judge['parse_error_count']}",
            "",
            "| 判定 | 含义 | 占比 |",
            "| --- | --- | --- |",
            f"| supported | 全部说法都能在资料里找到依据 "
            f"| {judge['faithfulness']['supported']:.4f} |",
            f"| partially_supported | 有个别说法找不到依据 "
            f"| {judge['faithfulness']['partially_supported']:.4f} |",
            f"| unsupported | 主要内容都找不到依据 "
            f"| {judge['faithfulness']['unsupported']:.4f} |",
            "",
            "## Answer Quality（回答质量，LLM Judge，无参考）",
            "",
            "| 判定 | 占比 |",
            "| --- | --- |",
            f"| correct | {judge['answer_quality']['correct']:.4f} |",
            f"| partial | {judge['answer_quality']['partial']:.4f} |",
            f"| incorrect | {judge['answer_quality']['incorrect']:.4f} |",
            "",
            "## Citation Support（引用语义正确性，LLM Judge）",
            "",
            "| 判定 | 含义 | 占比 |",
            "| --- | --- | --- |",
            f"| supported | 标号都指向真正支撑该句的资料 "
            f"| {judge['citation_support']['supported']:.4f} |",
            f"| partially_supported | 个别标号指错了资料 "
            f"| {judge['citation_support']['partially_supported']:.4f} |",
            f"| unsupported | 标号基本都对不上 "
            f"| {judge['citation_support']['unsupported']:.4f} |",
            f"| no_citation | 回答里一个标号都没有 "
            f"| {judge['citation_support']['no_citation']:.4f} |",
            "",
            "> 这是**无参考**判法：judge 只能看到检索到的资料，看不到客观真理。"
            "所以它衡量的是「在给定资料下答得好不好」，不是严格意义的 Answer "
            "Correctness——那需要人工写的标准答案，列为已知限制。",
            "",
        ]

        if judge["unfaithful_cases"]:
            lines += ["### 忠实度问题（可能编造）", ""]
            for case in judge["unfaithful_cases"]:
                lines += [
                    f"- **{case['case_id']}** [{case['faithfulness']}] {case['question']}",
                    f"  - 找不到依据的说法：{case['unsupported_claims'] or '（judge 未列出）'}",
                    f"  - 理由：{case['reason']}",
                ]
            lines.append("")

        if judge["low_quality_cases"]:
            lines += ["### 回答质量问题", ""]
            for case in judge["low_quality_cases"]:
                lines += [
                    f"- **{case['case_id']}** [{case['answer_quality']}] {case['question']}",
                    f"  - 理由：{case['reason']}",
                ]
            lines.append("")

        lines += [
            "### 人工抽查样本（judge 判为全对的题）",
            "",
            "抽查要抽 judge **说对的**题。LLM Judge 最常见的毛病是过于宽松、"
            "无脑给高分；只看它报出来的问题，等于只检查它已经承认的错误，"
            "抓不到它放过去的。**这一节没人看过，上面的数字就不算数。**",
            "",
        ]
        for case in judge["manual_review_sample"]:
            lines += [
                f"- **{case['case_id']}** {case['question']}",
                f"  - 回答：{case['answer'][:200]}",
            ]
        lines.append("")

        lines += [
            "### Judge 已知风险",
            "",
            f"- **自我偏好**：judge 和被评模型都是 `{payload['answer_model']}`，"
            "模型倾向于给自己生成的内容打高分，这里的分数偏乐观。",
            "- **judge 未经验证**：没有人工金标准集，也没算一致率。"
            "本轮结论必须配合上面的人工抽查一起看。",
            "- **温度已设 0**，但不能完全消除判定漂移。",
            "",
        ]

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="回答层评测（P6-06）")
    parser.add_argument(
        "--reuse-run",
        action="store_true",
        help="跳过生成，直接读上次的 run 文件重新判分（改指标时用）",
    )
    parser.add_argument(
        "--reuse-judge",
        action="store_true",
        help="跳过 judge 调用，直接读上次的判定文件（改报告格式时用）",
    )
    parser.add_argument(
        "--skip-judge",
        action="store_true",
        help="完全不跑 judge，只出拒答指标",
    )
    args = parser.parse_args()

    if args.reuse_run:
        if not RUN_PATH.exists():
            raise SystemExit(
                f"没有找到 run 文件：{RUN_PATH}，请先不带 --reuse-run 跑一次。"
            )
        records = load_run(RUN_PATH)
        print(f"复用已有 run 文件：{RUN_PATH}（{len(records)} 条）")
    else:
        records = _run_generation()
        print(f"跑批结果已保存：{RUN_PATH}（{len(records)} 条）")

    settings = get_settings()
    payload: dict[str, Any] = {
        "top_k": settings.retrieval_top_k,
        "answer_model": settings.answer_model,
        # 从 run 文件里取，而不是从当前配置取——判分判的是「那一批答案」，
        # 提示词版本必须跟着那批答案走，不能跟着当前代码走。
        "prompt_version": records[0].prompt_version if records else "unknown",
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "refusal": _score_refusal(records),
        "citation_structure": _score_citations(records),
    }

    if not args.skip_judge:
        if args.reuse_judge:
            if not JUDGE_PATH.exists():
                raise SystemExit(f"没有找到判定文件：{JUDGE_PATH}，请先跑一次 judge。")
            verdicts = load_verdicts(JUDGE_PATH)
            print(f"复用已有判定文件：{JUDGE_PATH}（{len(verdicts)} 条）")
        else:
            verdicts = _run_judge(records)
            print(f"judge 判定已保存：{JUDGE_PATH}")
        payload["judge"] = _score_judge(verdicts, records)

    JSON_REPORT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    MD_REPORT_PATH.write_text(_to_markdown(payload), encoding="utf-8")

    refusal = payload["refusal"]
    print(f"Refusal Accuracy：{refusal['accuracy']:.4f}")
    print(
        f"  误拒 {refusal['over_refusal_count']} 题"
        f"（检索未命中 {refusal['over_refusal_no_retrieval']} / "
        f"检索命中仍拒答 {refusal['over_refusal_with_retrieval']}）"
        f" / 漏拒 {refusal['missed_refusal_count']} 题"
    )
    if "judge" in payload:
        judge = payload["judge"]
        print(
            f"Faithfulness supported：{judge['faithfulness']['supported']:.4f}"
            f"  Answer Quality correct：{judge['answer_quality']['correct']:.4f}"
            f"  Citation supported：{judge['citation_support']['supported']:.4f}"
        )
    print(f"报告已保存：{JSON_REPORT_PATH} 和 {MD_REPORT_PATH}")


if __name__ == "__main__":
    main()
