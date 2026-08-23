"""Agent 图的装配（Agent 的组合根）。

职责：用 StateGraph 把节点加进来、连边、设置条件路由与终止熔断，最后 compile。
它是唯一「知道全图长什么样」的地方，节点和路由都只关心自己那一小块。

终止/熔断（阶段 3）：
- MAX_RETRIEVAL_ATTEMPTS = 2   最多检索 2 次（原始 + 最多一次改写）
- MAX_GRAPH_STEPS = 12         整图最大步数，兜底防死循环

预留接口（阶段 5，不在本阶段实现）：
- compile(checkpointer=PostgresSaver(...)) 处接入检查点，实现「中断恢复 / 人工审批暂停继续」。
"""

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from evidence_desk.agent.nodes import (
    clarify,
    classify_intent,
    grade_retrieval,
    make_fetch_workflow_run_node,
    make_generate_answer_node,
    make_retrieve_node,
    rewrite_query,
    safe_refusal,
)
from evidence_desk.agent.routing import route_after_grade, route_after_intent
from evidence_desk.agent.state import AgentState, NodeName
from evidence_desk.application.ports import (
    ChunkRetriever,
    GitHubGateway,
    QueryEmbedder,
)
from evidence_desk.application.rag_answer_service import RagAnswerService

MAX_GRAPH_STEPS = 12


def build_agent_graph(
    embedder: QueryEmbedder,
    retriever: ChunkRetriever,
    answer_service: RagAnswerService,
    gateway: GitHubGateway,
    *,
    top_k: int,
) -> CompiledStateGraph[AgentState, Any, Any, Any]:
    """把 7 个节点 + 2 个路由装配成图并编译"""

    builder = StateGraph(AgentState)

    # 1) 注册 7 个节点（名字 → 函数）
    builder.add_node(NodeName.CLASSIFY_INTENT, classify_intent)
    builder.add_node(
        NodeName.RETRIEVE,
        make_retrieve_node(embedder, retriever, top_k=top_k),  # type: ignore[arg-type]
    )
    builder.add_node(NodeName.GRADE_RETRIEVAL, grade_retrieval)
    builder.add_node(NodeName.REWRITE_QUERY, rewrite_query)
    builder.add_node(
        NodeName.GENERATE_ANSWER,
        make_generate_answer_node(answer_service),  # type: ignore[arg-type]
    )
    builder.add_node(
        NodeName.FETCH_WORKFLOW_RUN,
        make_fetch_workflow_run_node(gateway),  # type: ignore[arg-type]
    )
    builder.add_node(NodeName.CLARIFY, clarify)
    builder.add_node(NodeName.SAFE_REFUSAL, safe_refusal)

    # 2) 入口：START → 分诊
    builder.add_edge(START, NodeName.CLASSIFY_INTENT)

    # 3) 分诊后的条件分支
    builder.add_conditional_edges(
        NodeName.CLASSIFY_INTENT,
        route_after_intent,
        [
            NodeName.RETRIEVE,
            NodeName.FETCH_WORKFLOW_RUN,
            NodeName.CLARIFY,
            NodeName.SAFE_REFUSAL,
        ],
    )

    # 4) 检索 → 评估（固定边）
    builder.add_edge(NodeName.RETRIEVE, NodeName.GRADE_RETRIEVAL)

    # 5) 评估后的条件分支（够→答；不够未超限→改写；否则→拒答）
    builder.add_conditional_edges(
        NodeName.GRADE_RETRIEVAL,
        route_after_grade,
        [NodeName.GENERATE_ANSWER, NodeName.REWRITE_QUERY, NodeName.SAFE_REFUSAL],
    )

    # 6) 改写后回到检索，形成"最多 2 次"的循环
    builder.add_edge(NodeName.REWRITE_QUERY, NodeName.RETRIEVE)

    # 7) 各终点 → END
    builder.add_edge(NodeName.GENERATE_ANSWER, END)
    builder.add_edge(NodeName.FETCH_WORKFLOW_RUN, END)
    builder.add_edge(NodeName.CLARIFY, END)
    builder.add_edge(NodeName.SAFE_REFUSAL, END)

    return builder.compile()
