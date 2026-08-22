"""Agent 工作流的节点。

节点是「薄编排」：读 AgentState → 调用已有的 application/infrastructure 服务
→ 只返回自己改动的字段。重活（检索、生成）不在这里重写，只做委托。

本阶段（3）的 RAG 节点都放这一个文件；等阶段 4/5 的工具、审批节点进来，
再把本文件提升为 nodes/ 包，按关注点拆分（rag.py / tools.py / approval.py）。

计划节点（自上而下逐个手写、写一个验一个）：
- classify_intent(state)   规则判定 knowledge / ambiguous / unsafe
- retrieve(state)          向量化 + 检索，attempts += 1
- grade_retrieval(state)   判断检索到的证据够不够回答
- rewrite_query(state)     证据不足时改写一次查询
- generate_answer(state)   调 RagAnswerService 生成带引用的回答
- clarify(state)           意图模糊时反问澄清
- safe_refusal(state)      不安全 / 无证据时安全拒答
"""

from collections.abc import Callable

from evidence_desk.agent.state import (
    INTENT_AMBIGUOUS,
    INTENT_KNOWLEDGE,
    INTENT_UNSAFE,
    AgentState,
)
from evidence_desk.application.ports import ChunkRetriever, QueryEmbedder
from evidence_desk.application.rag_answer_service import (
    NO_EVIDENCE_REPLY,
    RagAnswerService,
)

# 触发「越权/危险操作」判定的关键词（都是写操作，本阶段暂不支持）。
_WRITE_ACTION_KEYWORDS = (
    "取消",
    "重跑",
    "重新运行",
    "删除",
    "cancel",
    "rerun",
    "delete",
)


# 判定"证据够不够"的最低 Top-1 相似度阈值（启发式，之后用评测集调）。
_MIN_TOP_SCORE = 0.4

# 结束点话术
_CLARIFY_REPLY = "你的问题不太具体，能补充一下你想了解 GitHub Actions 的哪个方面吗？"
_UNSAFE_REPLY = "该请求涉及取消/重跑等写操作，当前暂不支持，请通过官方界面手动操作。"

# 改写时要剔除的口语填充词和标点（去口语化，让查询更聚焦）。
_QUERY_NOISE = (
    "请问",
    "我想问",
    "帮我看看",
    "帮我",
    "好像",
    "怎么办",
    "怎么",
    "如何",
    "能不能",
    "可以吗",
    "，",
    "。",
    "？",
    "！",
    "、",
    ",",
    ".",
    "?",
    "!",
)


def classify_intent(state: AgentState) -> AgentState:
    """分诊节点：看一眼问题，判定意图，只写回 intent 字段。"""

    question = state["question"].strip()
    lowered = question.lower()

    # 1) 空或太短 → 太模糊，稍后反问澄清
    if len(question) < 4:
        return {"intent": INTENT_AMBIGUOUS}

    # 2) 含写操作关键词 → 越权/危险，稍后安全拒答
    if any(keyword in lowered for keyword in _WRITE_ACTION_KEYWORDS):
        return {"intent": INTENT_UNSAFE}

    # 3) 其它 → 当作知识问题，走检索
    return {"intent": INTENT_KNOWLEDGE}


def make_retrieve_node(
    embedder: QueryEmbedder,
    retriever: ChunkRetriever,
    *,
    top_k: int,
) -> Callable[[AgentState], AgentState]:
    """工厂：注入依赖，返回一个 LangGraph 可用的 retrieve 节点。"""

    def retrieve(state: AgentState) -> AgentState:
        # 有改写后的查询就用最新那条；否则用原始问题（保证第一次用原始 query）
        queries = state.get("queries")
        query = queries[-1] if queries else state["question"]

        vector = embedder.embed_query(query)
        hits = retriever.search(vector, top_k=top_k)

        attempts = state.get("attempts", 0) + 1
        return {"hits": hits, "attempts": attempts}

    return retrieve


def grade_retrieval(state: AgentState) -> AgentState:
    """评估节点：判断检索到的证据够不够回答，只写回 retrieval_ok。"""

    hits = state.get("hits") or []
    top_score = hits[0].score if hits else 0.0
    retrieval_ok = bool(hits) and top_score >= _MIN_TOP_SCORE
    return {"retrieval_ok": retrieval_ok}


def make_generate_answer_node(
    answer_service: RagAnswerService,
) -> Callable[[AgentState], AgentState]:
    """工厂：注入 RagAnswerService，返回 generate_answer 节点。"""

    def generate_answer(state: AgentState) -> AgentState:
        result = answer_service.answer(state["question"], state.get("hits") or [])
        return {
            "answer": result.answer,
            "answered": result.answered,
            "citations": result.citations,
        }

    return generate_answer


def rewrite_query(state: AgentState) -> AgentState:
    """改写节点：去口语化得到更聚焦的查询，追加到 queries 供下次检索。"""

    rewritten = state["question"]
    for token in _QUERY_NOISE:
        rewritten = rewritten.replace(token, " ")
    rewritten = " ".join(rewritten.split()).strip() or state["question"]

    queries = list(state.get("queries") or [state["question"]])
    queries.append(rewritten)
    return {"queries": queries}


def clarify(state: AgentState) -> AgentState:
    """结束点：意图模糊时反问澄清。"""

    return {"answer": _CLARIFY_REPLY, "answered": False, "citations": []}


def safe_refusal(state: AgentState) -> AgentState:
    """结束点：越权操作或无证据时安全拒答。"""

    if state.get("intent") == INTENT_UNSAFE:
        answer = _UNSAFE_REPLY
    else:
        answer = NO_EVIDENCE_REPLY
    return {"answer": answer, "answered": False, "citations": []}
