"""POST /api/v1/agent/chat 的集成测试。

用假聊天模型（脚本化 tool_call）+ 假依赖装配真实的 ReAct Agent 放进 app.state，
从而在不连真实模型/网络的情况下，验证「HTTP → ReAct 循环 → 工具 → 回答」这条链路，
以及问候不调工具、返回 conversation_id 等行为。
"""

from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langgraph.checkpoint.memory import InMemorySaver

from evidence_desk.agent.react import build_react_agent
from evidence_desk.application.ports import WorkflowJob, WorkflowRun
from evidence_desk.main import app
from evidence_desk.rag.models import RetrievalHit


class FakeToolModel(GenericFakeChatModel):
    """假聊天模型：重写 bind_tools 返回自身，按脚本吐消息（含 tool_calls）。"""

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        return self


class FakeEmbedder:
    def embed_query(self, query: str) -> list[float]:
        return [0.1]


class FakeRetriever:
    def search(self, query_vector: list[float], *, top_k: int) -> list[RetrievalHit]:
        return []


class FakeGitHubGateway:
    def get_workflow_run(self, owner: str, repo: str, run_id: int) -> WorkflowRun:
        return WorkflowRun(
            run_id=run_id,
            name="CI",
            status="completed",
            conclusion="failure",
            head_branch="main",
            event="push",
            html_url="https://github.com/github/docs/actions/runs/123",
        )

    def list_workflow_jobs(
        self, owner: str, repo: str, run_id: int
    ) -> list[WorkflowJob]:
        return []


def install_agent(scripted: list[BaseMessage]) -> None:
    app.state.agent = build_react_agent(
        FakeToolModel(messages=iter(scripted)),
        FakeEmbedder(),
        FakeRetriever(),
        FakeGitHubGateway(),
        top_k=5,
        checkpointer=InMemorySaver(),
    )


@pytest.mark.asyncio
async def test_agent_greeting_does_not_call_tools() -> None:
    install_agent([AIMessage(content="你好！有什么 GitHub Actions 问题我可以帮你？")])

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/agent/chat", json={"question": "你好"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["tools_used"] == []
    assert body["data"]["conversation_id"]
    assert "你好" in body["data"]["answer"]


@pytest.mark.asyncio
async def test_agent_calls_github_tool_for_run_question() -> None:
    install_agent(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_workflow_run",
                        "args": {"owner": "github", "repo": "docs", "run_id": 123},
                        "id": "call_1",
                    }
                ],
            ),
            AIMessage(content="运行 #123 失败了，结论是 failure。"),
        ]
    )

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/agent/chat",
            json={"question": "github/docs 运行 123 为什么失败"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert "get_workflow_run" in body["data"]["tools_used"]
    assert "failure" in body["data"]["answer"]
