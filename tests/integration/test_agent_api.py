"""POST /api/v1/agent/chat 的集成测试。

用假的 Embedder / Retriever / LLM 装配真实的 Agent 图放进 app.state，
从而在不加载真实模型、不连 Weaviate、不需要 API Key 的情况下，
验证「HTTP → 意图路由 → 检索 → 评估 → 生成/拒答 → 引用」这条 Agent 链路。
"""

import httpx
import pytest
from httpx import ASGITransport

from evidence_desk.agent.graph import build_agent_graph
from evidence_desk.application.ports import WorkflowJob, WorkflowRun
from evidence_desk.application.rag_answer_service import RagAnswerService
from evidence_desk.main import app
from evidence_desk.rag.models import RetrievalHit


class FakeEmbedder:
    def embed_query(self, query: str) -> list[float]:
        return [0.1, 0.2, 0.3]


class FakeRetriever:
    def __init__(self, hits: list[RetrievalHit]) -> None:
        self._hits = hits

    def search(self, query_vector: list[float], *, top_k: int) -> list[RetrievalHit]:
        return self._hits[:top_k]


class FakeLLM:
    def __init__(self, reply: str) -> None:
        self.reply = reply

    def complete(self, *, system: str, user: str, temperature: float) -> str:
        return self.reply


class FakeGitHubGateway:
    def __init__(self, run: WorkflowRun) -> None:
        self._run = run

    def get_workflow_run(self, owner: str, repo: str, run_id: int) -> WorkflowRun:
        return self._run

    def list_workflow_jobs(
        self, owner: str, repo: str, run_id: int
    ) -> list[WorkflowJob]:
        return []


def make_run() -> WorkflowRun:
    return WorkflowRun(
        run_id=30964320373,
        name="CI",
        status="completed",
        conclusion="failure",
        head_branch="main",
        event="push",
        html_url="https://github.com/github/docs/actions/runs/30964320373",
    )


def make_hit() -> RetrievalHit:
    return RetrievalHit(
        rank=1,
        distance=0.1,
        score=0.9,
        chunk_id="doc_debug_0001",
        parent_doc_id="doc_debug",
        title="启用调试日志记录",
        section_path=["启用调试日志记录"],
        content="把 ACTIONS_STEP_DEBUG 设为 true 即可开启步骤调试日志。",
        source_url="https://docs.github.com/enable-debug-logging",
    )


def install_agent_graph(*, hits: list[RetrievalHit], reply: str) -> None:
    answer_service = RagAnswerService(FakeLLM(reply), temperature=0.0)
    app.state.agent_graph = build_agent_graph(
        FakeEmbedder(),
        FakeRetriever(hits),
        answer_service,
        FakeGitHubGateway(make_run()),
        top_k=5,
    )


@pytest.mark.asyncio
async def test_agent_chat_answers_knowledge_question() -> None:
    install_agent_graph(hits=[make_hit()], reply="将 ACTIONS_STEP_DEBUG 设为 true。")

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/agent/chat", json={"question": "如何开启调试日志？"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["data"]["intent"] == "knowledge"
    assert body["data"]["answered"] is True
    assert body["data"]["citations"][0]["source_url"] == (
        "https://docs.github.com/enable-debug-logging"
    )


@pytest.mark.asyncio
async def test_agent_chat_refuses_unsafe_request() -> None:
    install_agent_graph(hits=[make_hit()], reply="不该被调用")

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/agent/chat", json={"question": "帮我取消这个工作流运行"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["intent"] == "unsafe"
    assert body["data"]["answered"] is False
    assert body["data"]["citations"] == []


@pytest.mark.asyncio
async def test_agent_chat_uses_github_tool_for_run_question() -> None:
    install_agent_graph(hits=[make_hit()], reply="不该被调用")

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/agent/chat",
            json={"question": "github/docs 运行 30964320373 为什么失败？"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["intent"] == "business_read"
    assert body["data"]["answered"] is True
    assert "30964320373" in body["data"]["answer"]
