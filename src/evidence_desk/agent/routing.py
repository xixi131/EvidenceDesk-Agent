"""条件边的路由函数。

路由函数是纯函数：只读 AgentState，返回「下一个节点的名字」（字符串），
不修改状态、不做副作用。它把「分支/重试/终止」的决策集中在一处，方便测试。

计划路由：
- route_after_intent(state)  按 intent → 去 retrieve / clarify / safe_refusal
- route_after_grade(state)   证据够 → generate_answer；
                             不够且未超检索上限 → rewrite_query；
                             否则 → safe_refusal
"""

from evidence_desk.agent.state import (
    INTENT_AMBIGUOUS,
    INTENT_KNOWLEDGE,
    AgentState,
    NodeName,
)

# 检索最多尝试 2 次（原始 1 次 + 最多 1 次改写重试）后不再改写。
MAX_RETRIEVAL_ATTEMPTS = 2


def route_after_intent(state: AgentState) -> NodeName:
    """分诊后：看 intent，决定去哪条分支。返回目标节点名。"""

    intent = state.get("intent")
    if intent == INTENT_KNOWLEDGE:
        return NodeName.RETRIEVE
    if intent == INTENT_AMBIGUOUS:
        return NodeName.CLARIFY
    return NodeName.SAFE_REFUSAL  # INTENT_UNSAFE 及任何意外值，都安全兜底


def route_after_grade(state: AgentState) -> NodeName:
    """评估后：看证据够不够 + 已检索次数，决定去哪。返回目标节点名。"""

    if state.get("retrieval_ok"):
        return NodeName.GENERATE_ANSWER
    if state.get("attempts", 0) < MAX_RETRIEVAL_ATTEMPTS:
        return NodeName.REWRITE_QUERY
    return NodeName.SAFE_REFUSAL
