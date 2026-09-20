"""Agent 评测 Runner：对每道题跑一次 Agent，用 agent_metrics.py 打分（P6-07）。

只依赖一个已经 build_react_agent(...) 编译好的 agent 对象（LangGraph 编译
状态图）+ AgentEvalCase 列表，不认识 ChatOpenAI/真实 Postgres 的细节——
既能接真实模型跑正式评测（scripts/run_agent_eval.py），也能用
tests/integration 里那套 FakeToolModel 装配的 agent 做离线单元测试。

离线单元测试跑出来的指标数值没有意义（FakeToolModel 的工具选择是脚本硬
编码的，不是模型真的决定的），那类测试只用来验证这个 runner 自身的编排
逻辑有没有写对（比如遇到 pending_approval 真的会调用 resume）。
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, cast

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from evidence_desk.evaluation.agent_dataset import AgentEvalCase
from evidence_desk.evaluation.agent_metrics import (
    human_review_required_correct,
    max_steps_violated,
    route_correct,
    task_success,
    tool_arguments_valid,
    tool_selection_correct,
    write_without_approval,
)


@dataclass(frozen=True)
class AgentCaseResult:
    """单题的评测结果：实际轨迹 + 每个指标的判定结果。"""

    id: str
    question: str
    actual_tool_calls: list[str]
    tool_call_args: list[tuple[str, dict[str, Any]]]
    got_pending_approval: bool
    answer: str
    step_count: int
    route_ok: bool
    tool_selection_ok: bool
    tool_argument_checks: list[bool]
    human_review_ok: bool
    write_violation: bool
    task_success_ok: bool
    max_steps_bad: bool


@dataclass(frozen=True)
class AgentEvalReport:
    """整个数据集的评测汇总（P6-07 的 7 个指标）。"""

    num_cases: int
    route_accuracy: float
    tool_selection_accuracy: float
    tool_argument_valid_rate: float
    human_review_required_accuracy: float
    write_without_approval_rate: float
    task_success_rate: float
    max_steps_violation_rate: float
    cases: list[AgentCaseResult]


def evaluate_agent(
    cases: Sequence[AgentEvalCase],
    agent: CompiledStateGraph[Any, Any, Any, Any],
    *,
    max_steps: int = 6,
) -> AgentEvalReport:
    """对每道题跑一次 Agent，汇总成整个数据集的评测报告。"""

    results = [_run_case(case, agent, max_steps=max_steps) for case in cases]
    n = len(results)

    # Tool Argument Valid Rate 的分母是「工具调用次数」，不是题目数——
    # 把所有题目里发生的每一次工具调用的判定结果拍平成一个列表再算比例。
    all_arg_checks = [ok for r in results for ok in r.tool_argument_checks]

    return AgentEvalReport(
        num_cases=n,
        route_accuracy=_rate(r.route_ok for r in results),
        tool_selection_accuracy=_rate(r.tool_selection_ok for r in results),
        tool_argument_valid_rate=_rate(all_arg_checks),
        human_review_required_accuracy=_rate(r.human_review_ok for r in results),
        write_without_approval_rate=_rate(r.write_violation for r in results),
        task_success_rate=_rate(r.task_success_ok for r in results),
        max_steps_violation_rate=_rate(r.max_steps_bad for r in results),
        cases=results,
    )


def _run_case(
    case: AgentEvalCase,
    agent: CompiledStateGraph[Any, Any, Any, Any],
    *,
    max_steps: int,
) -> AgentCaseResult:
    """跑一道题：铺垫轮（如果有）→ 正式提问 → 遇到审批自动批准 → 打分。"""

    # 每道题用独立的 thread_id/user_id，题目之间互不干扰（不会因为跑题目
    # 的顺序不同而互相污染长期记忆）。
    # 注意：这里的类型标注必须是 RunnableConfig（TypedDict），不能是
    # dict[str, Any]——mypy 只在「字面量直接传参」或「变量标注成 TypedDict」
    # 这两种情况下才认它满足 agent.invoke() 要求的 TypedDict 参数类型，
    # 标成普通 dict[str, Any] 反而会被当成类型不匹配。
    config: RunnableConfig = {
        "configurable": {
            "thread_id": f"eval-{case.id}",
            "user_id": f"eval-user-{case.id}",
        }
    }

    if case.setup_question is not None:
        # 铺垫轮不计入打分，只是为了让 recall_user_memory 这类题目
        # 在正式提问之前，长期记忆里已经有东西可查。
        agent.invoke(
            {"messages": [{"role": "user", "content": case.setup_question}]}, config
        )

    result = cast(
        dict[str, Any],
        agent.invoke(
            {"messages": [{"role": "user", "content": case.question}]}, config
        ),
    )

    # 卡在审批点：评测场景下自动批准，让写操作真的执行，才能验证幂等/
    # 落库这些下游行为；有没有正确卡审批点，由 human_review_ok 单独判断。
    got_pending_approval = bool(result.get("__interrupt__"))
    if got_pending_approval:
        result = cast(
            dict[str, Any],
            agent.invoke(Command(resume={"decisions": [{"type": "approve"}]}), config),
        )

    messages = result["messages"]
    # 步数口径：这段对话里 AIMessage 的条数，模型被调用一次算一步。
    step_count = sum(1 for m in messages if isinstance(m, AIMessage))

    # 跟 agent.py 路由层同样的处理：被拒绝的工具调用不算「真的执行了」。
    rejected_call_ids = {
        m.tool_call_id
        for m in messages
        if isinstance(m, ToolMessage) and m.status == "error"
    }
    tool_calls: list[tuple[str, dict[str, Any]]] = [
        (tool_call["name"], tool_call["args"])
        for message in messages
        if isinstance(message, AIMessage)
        for tool_call in message.tool_calls
        if tool_call["id"] not in rejected_call_ids
    ]
    actual_tool_calls = [name for name, _ in tool_calls]
    answer = str(messages[-1].content) if messages else ""

    return AgentCaseResult(
        id=case.id,
        question=case.question,
        actual_tool_calls=actual_tool_calls,
        tool_call_args=tool_calls,
        got_pending_approval=got_pending_approval,
        answer=answer,
        step_count=step_count,
        route_ok=route_correct(case.expected_route, actual_tool_calls),
        tool_selection_ok=tool_selection_correct(
            case.expected_tool_calls, actual_tool_calls
        ),
        tool_argument_checks=[
            tool_arguments_valid(name, args) for name, args in tool_calls
        ],
        human_review_ok=human_review_required_correct(
            case.requires_approval, got_pending_approval
        ),
        write_violation=write_without_approval(actual_tool_calls, got_pending_approval),
        task_success_ok=task_success(answer, case.expected_keywords),
        max_steps_bad=max_steps_violated(step_count, max_steps),
    )


def _rate(flags: Iterable[bool]) -> float:
    """对一串布尔值求「True 的比例」，空列表返回 0.0。"""
    values = list(flags)
    return sum(values) / len(values) if values else 0.0
