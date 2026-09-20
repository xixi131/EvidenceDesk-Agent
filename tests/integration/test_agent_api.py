"""POST /api/v1/agent/chat 的集成测试。

用假聊天模型（脚本化 tool_call）+ 假依赖装配真实的 ReAct Agent 放进 app.state，
从而在不连真实模型/网络的情况下，验证「HTTP → ReAct 循环 → 工具 → 回答」这条链路，
以及问候不调工具、返回 conversation_id 等行为。
"""

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langgraph.checkpoint.memory import InMemorySaver

from evidence_desk.agent.react import build_react_agent
from evidence_desk.application.ports import Ticket, WorkflowJob, WorkflowRun
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


class FakeTicketService:
    """假工单服务：内存 dict 模拟 idempotency_key -> Ticket 的去重存储。

    跟真实 TicketService 拥有相同签名的 create_ticket 方法（结构类型），
    build_react_agent/build_agent_tools 不关心它是不是同一个类，能这么用就行。
    """

    def __init__(self) -> None:
        self._by_key: dict[str, Ticket] = {}
        self._next_id = 1

    def create_ticket(
        self,
        *,
        idempotency_key: str,
        title: str,
        description: str,
        context_summary: str,
    ) -> tuple[Ticket, bool]:
        existing = self._by_key.get(idempotency_key)
        if existing is not None:
            return existing, False
        ticket = Ticket(
            id=self._next_id,
            idempotency_key=idempotency_key,
            title=title,
            description=description,
            context_summary=context_summary,
            status="open",
            created_at=datetime.now(tz=UTC),
        )
        self._next_id += 1
        self._by_key[idempotency_key] = ticket
        return ticket, True


def install_agent(scripted: list[BaseMessage], *, ticket_service: Any = None) -> None:
    app.state.agent = build_react_agent(
        FakeToolModel(messages=iter(scripted)),
        FakeEmbedder(),
        FakeRetriever(),
        FakeGitHubGateway(),
        top_k=5,
        checkpointer=InMemorySaver(),
        ticket_service=ticket_service,
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


def _ticket_tool_call(call_id: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "create_support_ticket",
                "args": {
                    "title": "self-hosted runner 排队",
                    "description": "并发任务经常排队，需要人工协助排查。",
                    "context_summary": "用户已确认需要建单。",
                },
                "id": call_id,
            }
        ],
    )


@pytest.mark.asyncio
async def test_agent_create_ticket_requires_approval_then_is_idempotent() -> None:
    """建单会先卡在审批点；批准后才真正执行；同一 conversation_id 重复批准不重复建单。"""

    ticket_service = FakeTicketService()
    install_agent(
        [
            _ticket_tool_call("call_1"),
            AIMessage(content="已经帮你创建了支持工单 #1。"),
            _ticket_tool_call("call_2"),
            AIMessage(content="这段对话此前已经创建过工单了，不会重复创建。"),
        ],
        ticket_service=ticket_service,
    )

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 第一轮：模型决定建单，应该卡在审批点，不应该已经真正建了工单。
        pending = await client.post(
            "/api/v1/agent/chat",
            json={"question": "帮我建个工单", "conversation_id": "conv-ticket"},
        )
        assert pending.json()["data"]["status"] == "pending_approval"
        assert (
            pending.json()["data"]["pending_approval"]["tool_name"]
            == "create_support_ticket"
        )
        assert ticket_service._by_key == {}  # 还没批准，不应该已经落库

        # 批准 -> 真正执行，工单被创建。
        approved = await client.post(
            "/api/v1/agent/chat/conv-ticket/decisions", json={"decision": "approve"}
        )
        assert approved.json()["data"]["status"] == "completed"
        assert "create_support_ticket" in approved.json()["data"]["tools_used"]
        assert len(ticket_service._by_key) == 1

        # 第二轮：同一段对话再次触发建单，同样先卡审批点，批准后应该命中去重。
        pending_again = await client.post(
            "/api/v1/agent/chat",
            json={"question": "再帮我建一次", "conversation_id": "conv-ticket"},
        )
        assert pending_again.json()["data"]["status"] == "pending_approval"

        approved_again = await client.post(
            "/api/v1/agent/chat/conv-ticket/decisions", json={"decision": "approve"}
        )

    assert approved_again.status_code == 200
    assert "create_support_ticket" in approved_again.json()["data"]["tools_used"]
    # 核心断言：批准了两次，底层只应该真正落了一条工单记录（幂等去重生效）。
    assert len(ticket_service._by_key) == 1


@pytest.mark.asyncio
async def test_agent_reject_ticket_decision_does_not_create() -> None:
    """拒绝审批：工具函数根本不会被真正调用，也不应该出现在 tools_used 里。"""

    ticket_service = FakeTicketService()
    install_agent(
        [_ticket_tool_call("call_1"), AIMessage(content="好的，不创建工单了。")],
        ticket_service=ticket_service,
    )

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        pending = await client.post(
            "/api/v1/agent/chat",
            json={"question": "帮我建个工单", "conversation_id": "conv-reject"},
        )
        assert pending.json()["data"]["status"] == "pending_approval"

        rejected = await client.post(
            "/api/v1/agent/chat/conv-reject/decisions",
            json={"decision": "reject", "reason": "用户还没确认"},
        )

    assert rejected.status_code == 200
    body = rejected.json()["data"]
    assert body["status"] == "completed"
    assert "create_support_ticket" not in body["tools_used"]
    assert ticket_service._by_key == {}
