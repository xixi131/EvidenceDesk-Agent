"""Agent 图的离线测试：用 Fake 依赖验证各分支与终止条件（不连真实模型/检索）。"""

from evidence_desk.agent.graph import MAX_GRAPH_STEPS, build_agent_graph
from evidence_desk.agent.state import (
    INTENT_AMBIGUOUS,
    INTENT_BUSINESS_READ,
    INTENT_KNOWLEDGE,
    INTENT_UNSAFE,
)
from evidence_desk.application.ports import WorkflowJob, WorkflowRun
from evidence_desk.application.rag_answer_service import RagAnswerService
from evidence_desk.rag.models import RetrievalHit


class FakeEmbedder:
    """假向量化器：返回一个固定向量，不加载任何模型。"""

    def embed_query(self, query: str) -> list[float]:
        return [0.0, 0.0, 0.0]


class FakeRetriever:
    """假检索器：返回构造时预设好的命中列表。"""

    def __init__(self, hits: list[RetrievalHit]) -> None:
        self._hits = hits

    def search(self, query_vector: list[float], *, top_k: int) -> list[RetrievalHit]:
        return self._hits[:top_k]


class FakeLLM:
    """假大模型：complete 永远返回同一句话。"""

    def __init__(self, reply: str) -> None:
        self._reply = reply

    def complete(self, *, system: str, user: str, temperature: float) -> str:
        return self._reply


class FakeGitHubGateway:
    def __init__(self, run: WorkflowRun) -> None:
        self._run = run

    def get_workflow_run(self, owner: str, repo: str, run_id: int) -> WorkflowRun:
        return self._run

    def list_workflow_jobs(
        self, owner: str, repo: str, run_id: int
    ) -> list[WorkflowJob]:
        return []


def _run_fact() -> WorkflowRun:
    return WorkflowRun(
        run_id=30964320373,
        name="CI",
        status="completed",
        conclusion="failure",
        head_branch="main",
        event="push",
        html_url="https://github.com/github/docs/actions/runs/30964320373",
    )


def _hit(score: float) -> RetrievalHit:
    """造一条相似度为 score 的命中。"""
    return RetrievalHit(
        rank=1,
        distance=1.0 - score,
        score=score,
        chunk_id="chunk-1",
        parent_doc_id="doc-1",
        title="启用调试日志",
        section_path=["监控工作流", "启用调试日志"],
        content="设置 ACTIONS_STEP_DEBUG=true。",
        source_url="https://docs.github.com/zh/actions/x",
    )


def _build(hits: list[RetrievalHit], reply: str = "基于官方文档的回答。"):
    """用 Fake 依赖装配一张图。"""
    answer_service = RagAnswerService(FakeLLM(reply), temperature=0.0)
    gateway = FakeGitHubGateway(_run_fact())
    return build_agent_graph(
        FakeEmbedder(), FakeRetriever(hits), answer_service, gateway, top_k=5
    )


def _run(graph, question: str) -> dict:
    return graph.invoke(
        {"question": question},
        {"recursion_limit": MAX_GRAPH_STEPS},
    )


def test_knowledge_with_good_evidence_answers() -> None:
    # 证据够（高分命中）→ 走 retrieve→grade→generate_answer
    graph = _build([_hit(0.9)])
    result = _run(graph, "如何启用 ACTIONS_STEP_DEBUG 调试日志？")

    assert result["intent"] == INTENT_KNOWLEDGE
    assert result["answered"] is True
    assert result["citations"]  # 有引用
    assert result["attempts"] == 1  # 一次检索就够


def test_unsafe_request_is_refused() -> None:
    # 写操作 → 分诊判 unsafe → safe_refusal，不检索
    graph = _build([_hit(0.9)])
    result = _run(graph, "帮我取消这个工作流运行")

    assert result["intent"] == INTENT_UNSAFE
    assert result["answered"] is False
    assert result["citations"] == []


def test_ambiguous_question_is_clarified() -> None:
    # 太短 → 分诊判 ambiguous → clarify
    graph = _build([_hit(0.9)])
    result = _run(graph, "嗯?")

    assert result["intent"] == INTENT_AMBIGUOUS
    assert result["answered"] is False


def test_weak_evidence_retries_once_then_refuses() -> None:
    # 证据不足（低分命中）→ 改写重试一次 → 仍不足 → 拒答，且检索恰好 2 次
    graph = _build([_hit(0.1)])
    result = _run(graph, "关于某个很偏门的问题怎么处理？")

    assert result["intent"] == INTENT_KNOWLEDGE
    assert result["answered"] is False
    assert result["attempts"] == 2  # 触发了"最多 2 次"的终止


def test_business_read_calls_github_tool() -> None:
    # 含 owner/repo + run_id → 走 GitHub 工具，返回运行事实（不走 RAG）
    graph = _build([_hit(0.9)])
    result = _run(graph, "github/docs 运行 30964320373 为什么失败？")

    assert result["intent"] == INTENT_BUSINESS_READ
    assert result["answered"] is True
    assert "30964320373" in result["answer"]
    assert result["citations"] == []
