"""Agent 评测数据集：定义评测题结构并从 JSONL 读取（P6-07）。

跟 dataset.py（检索评测）是同一个模式，只是字段换成 Agent 场景需要的。
"""

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class AgentEvalCase:
    """一条 Agent 评测题。

    expected_route: 期望走的路线——工具名，或字面量 "none"（不该调任何工具）。
    expected_tool_calls: 期望被调用的工具名列表（允许多个，比如
        get_workflow_run 之后再 list_workflow_jobs）。
    requires_approval: 这道题是否应该触发 HITL 审批（目前只有涉及
        create_support_ticket 的题会是 True）。
    expected_keywords: 最终回答里应该出现的关键词/事实片段，用于判定
        Task Success（规则优先，不用 LLM Judge）。
    setup_question: 可选的铺垫轮——测 recall_user_memory 这类需要「先记住
        一件事，再另开一轮追问」的场景时，同一个 thread_id 先发这一轮
        （不计入打分），再发 question 那一轮（才是真正评测的对象）。
        大多数题目不需要这个字段，留空即可。
    """

    id: str
    question: str
    expected_route: str
    expected_tool_calls: list[str]
    requires_approval: bool
    expected_keywords: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    setup_question: str | None = None


def load_agent_eval_cases(path: Path) -> list[AgentEvalCase]:
    """把 JSONL 一行行读成 AgentEvalCase 列表。"""
    cases: list[AgentEvalCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        raw = json.loads(line)
        cases.append(
            AgentEvalCase(
                id=raw["id"],
                question=raw["question"],
                expected_route=raw["expected_route"],
                expected_tool_calls=raw["expected_tool_calls"],
                requires_approval=raw["requires_approval"],
                expected_keywords=raw.get("expected_keywords", []),
                tags=raw.get("tags", []),
                setup_question=raw.get("setup_question"),
            )
        )
    return cases
