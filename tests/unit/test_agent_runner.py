"""agent_runner.py 编排逻辑的单元测试（假模型，不代表真实指标数值）。

用跟 tests/integration/test_agent_api.py 一样的 FakeToolModel 装配一个真实
可跑的 Agent，只验证 evaluate_agent 有没有正确处理「铺垫轮」「审批自动放行」
「拒绝工具调用不算真的执行」这几条编排逻辑本身，不验证 Route/Tool Selection
这些指标的真实数值（那些必须接真实模型才有意义，见 run_agent_eval.py 顶部
说明）。
"""

from typing import Any

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from evidence_desk.agent.react import build_react_agent
from evidence_desk.application.ports import Ticket, WorkflowJob, WorkflowRun
from evidence_desk.evaluation.agent_dataset import AgentEvalCase
from evidence_desk.evaluation.agent_runner import evaluate_agent


class FakeToolModel(GenericFakeChatModel):
    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        return self


class FakeEmbedder:
    def embed_query(self, query: str) -> list[float]:
        return [0.1]


class FakeRetriever:
    def search(self, query_vector: list[float], *, top_k: int) -> list[Any]:
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

    def list_workflow_jobs(self, owner: str, repo: str, run_id: int) -> list[WorkflowJob]:
        return []


class FakeTicketService:
    def __init__(self) -> None:
        self._next_id = 1

    def create_ticket(
        self, *, idempotency_key: str, title: str, description: str, context_summary: str
    ) -> tuple[Ticket, bool]:
        from datetime import UTC, datetime

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
        return ticket, True


def _build_fake_agent(scripted: list[AIMessage]) -> Any:
    # FakeTicketService 只是结构上匹配 TicketService（跟 test_agent_api.py
    # 里的 FakeTicketService 一样），不是它的子类，mypy 看不出来，用 Any 绕过。
    fake_ticket_service: Any = FakeTicketService()
    return build_react_agent(
        FakeToolModel(messages=iter(scripted)),
        FakeEmbedder(),
        FakeRetriever(),
        FakeGitHubGateway(),
        top_k=5,
        checkpointer=InMemorySaver(),
        ticket_service=fake_ticket_service,
    )


def test_evaluate_agent_resumes_pending_approval_automatically() -> None:
    """轨迹里应该出现 got_pending_approval=True，且写工具最终真的被执行了。"""
    agent = _build_fake_agent(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "create_support_ticket",
                        "args": {
                            "title": "t",
                            "description": "d",
                            "context_summary": "c",
                        },
                        "id": "call_1",
                    }
                ],
            ),
            AIMessage(content="已创建支持工单。"),
        ]
    )
    case = AgentEvalCase(
        id="t1",
        question="帮我建个工单",
        expected_route="create_support_ticket",
        expected_tool_calls=["create_support_ticket"],
        requires_approval=True,
    )

    report = evaluate_agent([case], agent)

    result = report.cases[0]
    assert result.got_pending_approval is True
    assert "create_support_ticket" in result.actual_tool_calls
    assert result.answer == "已创建支持工单。"


def test_evaluate_agent_runs_setup_question_before_scored_question() -> None:
    """有 setup_question 时应该先发一轮铺垫，评测对象是第二轮的结果。"""
    agent = _build_fake_agent(
        [
            AIMessage(content="好的，记住了。"),  # 铺垫轮的回复（不计入打分）
            AIMessage(content="你之前说过喜欢用 GitHub 托管的 runner。"),
        ]
    )
    case = AgentEvalCase(
        id="t2",
        question="我之前说过喜欢什么类型的 runner 吗？",
        expected_route="none",
        expected_tool_calls=[],
        requires_approval=False,
        setup_question="我喜欢用 GitHub 托管的 runner，请记住。",
    )

    report = evaluate_agent([case], agent)

    assert report.cases[0].answer == "你之前说过喜欢用 GitHub 托管的 runner。"
