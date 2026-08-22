"""Agent 工作流的共享状态（AgentState）。

LangGraph 用一个 TypedDict 当「白板」：每个节点接收当前 State，
只返回它改动的字段，LangGraph 自动把这些片段合并回总 State。
``total=False`` 表示所有键都可选——节点会随流程逐步把它们填上。
"""

from enum import StrEnum
from typing import TypedDict

from evidence_desk.rag.models import Citation, RetrievalHit

# 意图分类的取值（阶段 4/5 再补 business_read / business_write）。
INTENT_KNOWLEDGE = "knowledge"  # 知识问题，走 RAG
INTENT_AMBIGUOUS = "ambiguous"  # 太模糊，需反问澄清
INTENT_UNSAFE = "unsafe"  # 不安全/越权，安全拒答


class NodeName(StrEnum):
    """图中各节点的名字，集中管理，避免到处写魔法字符串。"""

    CLASSIFY_INTENT = "classify_intent"
    RETRIEVE = "retrieve"
    GRADE_RETRIEVAL = "grade_retrieval"
    REWRITE_QUERY = "rewrite_query"
    GENERATE_ANSWER = "generate_answer"
    CLARIFY = "clarify"
    SAFE_REFUSAL = "safe_refusal"


class AgentState(TypedDict, total=False):
    """在各节点之间接力的共享状态。"""

    # —— 输入 ——
    question: str

    # —— 路由与检索控制 ——
    intent: str  # 见上面 INTENT_* 常量
    queries: list[str]  # 用过的查询：原始问题 +（可选）一次改写
    attempts: int  # 已检索次数，用于「最多 2 次」的终止判断

    # —— 检索结果 ——
    hits: list[RetrievalHit]  # 最近一次检索的命中
    retrieval_ok: bool  # 评估节点判断：检索到的证据够不够回答

    # —— 最终产物 ——
    answer: str
    answered: bool
    citations: list[Citation]

    # —— 异常路径 ——
    error: str  # 任一节点失败时写入，走安全结束
