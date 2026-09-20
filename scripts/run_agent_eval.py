"""对固定评测集跑一次真实 LLM 驱动的 Agent，输出 P6-07 的 7 个指标报告。

跟 run_retrieval_eval.py 是同一个结构：装配真实依赖 → 跑 evaluate_agent(...)
→ 报告写入 data/evaluation/（JSON 逐题明细 + Markdown 汇总表）。

Route/Tool Selection/Tool Argument 这三个指标测的是「模型自己决定调不调
工具」，必须接真实 ChatOpenAI 跑，不能用脚本化的假模型——所以这个脚本
装配的是跟 main.py 的 lifespan 同一套真实依赖（embedder/Weaviate/GitHub/
Postgres 工单），只有 checkpointer 换成一次性的 InMemorySaver（评测不需要
跨进程持久化对话历史）。跑之前确保：Docker（Postgres/Weaviate）已启动、
.env 里 OPENAI_API_KEY 已配置。
"""

import json
from pathlib import Path

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from pydantic import SecretStr

from evidence_desk.agent.react import build_react_agent
from evidence_desk.application.ticket_service import TicketService
from evidence_desk.core.config import get_settings
from evidence_desk.evaluation.agent_dataset import load_agent_eval_cases
from evidence_desk.evaluation.agent_runner import AgentEvalReport, evaluate_agent
from evidence_desk.infrastructure.embedding import BgeEmbeddingAdapter
from evidence_desk.infrastructure.github import GitHubRestClient
from evidence_desk.infrastructure.postgres.schema import ensure_ticket_table
from evidence_desk.infrastructure.postgres.ticket_repository import (
    PostgresTicketRepository,
)
from evidence_desk.infrastructure.weaviate import (
    WeaviateDenseRetriever,
    connect_to_weaviate,
    ensure_knowledge_chunk_collection,
)

EVAL_SET_PATH = Path("data/evaluation/agent_eval_v1.jsonl")
JSON_REPORT_PATH = Path("data/evaluation/agent_eval_v1.json")
MD_REPORT_PATH = Path("data/evaluation/agent_eval_v1.md")
MAX_STEPS = 6


def _report_to_dict(report: AgentEvalReport, model: str) -> dict:
    """把 AgentEvalReport 摊平成可 JSON 序列化的字典。"""
    return {
        "answer_model": model,
        "num_cases": report.num_cases,
        "route_accuracy": round(report.route_accuracy, 4),
        "tool_selection_accuracy": round(report.tool_selection_accuracy, 4),
        "tool_argument_valid_rate": round(report.tool_argument_valid_rate, 4),
        "human_review_required_accuracy": round(
            report.human_review_required_accuracy, 4
        ),
        "write_without_approval_rate": round(report.write_without_approval_rate, 4),
        "task_success_rate": round(report.task_success_rate, 4),
        "max_steps_violation_rate": round(report.max_steps_violation_rate, 4),
        "cases": [
            {
                "id": case.id,
                "question": case.question,
                "actual_tool_calls": case.actual_tool_calls,
                "got_pending_approval": case.got_pending_approval,
                "answer": case.answer,
                "step_count": case.step_count,
                "route_ok": case.route_ok,
                "tool_selection_ok": case.tool_selection_ok,
                "human_review_ok": case.human_review_ok,
                "write_violation": case.write_violation,
                "task_success_ok": case.task_success_ok,
                "max_steps_bad": case.max_steps_bad,
            }
            for case in report.cases
        ],
    }


def _report_to_markdown(report: AgentEvalReport, model: str) -> str:
    """生成一张指标汇总表 + 失败题目清单。"""
    lines = [
        "# Agent/Tool 评测报告（P6-07）",
        "",
        f"- 回答模型：`{model}`",
        f"- 题目数：{report.num_cases}",
        "",
        "| 指标 | 数值 |",
        "| --- | --- |",
        f"| Route Accuracy | {report.route_accuracy:.4f} |",
        f"| Tool Selection Accuracy | {report.tool_selection_accuracy:.4f} |",
        f"| Tool Argument Valid Rate | {report.tool_argument_valid_rate:.4f} |",
        f"| Human Review Required Accuracy | {report.human_review_required_accuracy:.4f} |",
        f"| Write Without Approval Rate | {report.write_without_approval_rate:.4f} |",
        f"| Task Success Rate | {report.task_success_rate:.4f} |",
        f"| Max Steps Violation Rate | {report.max_steps_violation_rate:.4f} |",
        "",
        "## 失败样例",
        "",
    ]
    failures = [
        case
        for case in report.cases
        if not (
            case.route_ok
            and case.tool_selection_ok
            and case.human_review_ok
            and not case.write_violation
            and case.task_success_ok
            and not case.max_steps_bad
        )
    ]
    if not failures:
        lines.append("（无失败样例）")
    else:
        for case in failures:
            lines.append(
                f"- `{case.id}`：{case.question}\n"
                f"  - 实际调用工具：{case.actual_tool_calls}\n"
                f"  - route_ok={case.route_ok}, tool_selection_ok={case.tool_selection_ok}, "
                f"human_review_ok={case.human_review_ok}, write_violation={case.write_violation}, "
                f"task_success_ok={case.task_success_ok}, max_steps_bad={case.max_steps_bad}\n"
                f"  - 回答：{case.answer[:200]}"
            )
    return "\n".join(lines) + "\n"


def main() -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("未配置 OPENAI_API_KEY，无法跑 Agent 评测。")

    cases = load_agent_eval_cases(EVAL_SET_PATH)

    embedder = BgeEmbeddingAdapter(
        settings.embedding_model, settings.embedding_cache_dir
    )
    chat_model = ChatOpenAI(
        model=settings.answer_model,
        api_key=SecretStr(settings.openai_api_key),
        base_url=settings.openai_base_url,
        temperature=settings.answer_temperature,
    )
    gateway = GitHubRestClient(
        base_url=settings.github_api_base_url,
        api_version=settings.github_api_version,
        token=settings.github_token,
    )
    memory_dims = len(embedder.embed_query("_dims_probe"))
    memory_store = InMemoryStore(
        index={
            "dims": memory_dims,
            "embed": lambda texts: [embedder.embed_query(t) for t in texts],
        }
    )
    ensure_ticket_table(settings.database_url)
    ticket_service = TicketService(PostgresTicketRepository(settings.database_url))

    client = connect_to_weaviate(settings)
    try:
        collection = ensure_knowledge_chunk_collection(client)
        retriever = WeaviateDenseRetriever(collection)
        agent = build_react_agent(
            chat_model,
            embedder,
            retriever,
            gateway,
            top_k=settings.retrieval_top_k,
            checkpointer=InMemorySaver(),
            summary_trigger_tokens=settings.context_summary_trigger_tokens,
            summary_keep_messages=settings.context_keep_messages,
            store=memory_store,
            memory_top_k=settings.long_term_memory_top_k,
            ticket_service=ticket_service,
        )
        report = evaluate_agent(cases, agent, max_steps=MAX_STEPS)
    finally:
        gateway.close()
        client.close()

    JSON_REPORT_PATH.write_text(
        json.dumps(
            _report_to_dict(report, settings.answer_model), ensure_ascii=False, indent=2
        ),
        encoding="utf-8",
    )
    MD_REPORT_PATH.write_text(
        _report_to_markdown(report, settings.answer_model), encoding="utf-8"
    )

    print(f"题目数：{report.num_cases}")
    print(f"Route Accuracy：{report.route_accuracy:.4f}")
    print(f"Tool Selection Accuracy：{report.tool_selection_accuracy:.4f}")
    print(f"Tool Argument Valid Rate：{report.tool_argument_valid_rate:.4f}")
    print(
        f"Human Review Required Accuracy：{report.human_review_required_accuracy:.4f}"
    )
    print(f"Write Without Approval Rate：{report.write_without_approval_rate:.4f}")
    print(f"Task Success Rate：{report.task_success_rate:.4f}")
    print(f"Max Steps Violation Rate：{report.max_steps_violation_rate:.4f}")
    print(f"报告已保存：{JSON_REPORT_PATH} 和 {MD_REPORT_PATH}")


if __name__ == "__main__":
    main()
