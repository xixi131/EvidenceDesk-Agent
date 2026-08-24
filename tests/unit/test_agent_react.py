"""ReAct Agent 的离线测试：用假聊天模型脚本化 tool_call，验证 ReAct 循环可见、可控。

这也是「亲眼看到链路」的地方：断言消息序列里出现了
AIMessage(tool_calls) → ToolMessage(观察) → AIMessage(最终答案)。
"""

from typing import Any

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolMessage

from evidence_desk.agent.react import build_react_agent
from evidence_desk.application.ports import WorkflowJob, WorkflowRun
from evidence_desk.rag.models import RetrievalHit


class FakeToolModel(GenericFakeChatModel):
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


def _agent(scripted: list[AIMessage]) -> Any:
    return build_react_agent(
        FakeToolModel(messages=iter(scripted)),
        FakeEmbedder(),
        FakeRetriever(),
        FakeGitHubGateway(),
        top_k=5,
    )


def test_react_loop_calls_tool_then_answers() -> None:
    agent = _agent(
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
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "github/docs 运行 123 为什么失败"}]}
    )
    messages = result["messages"]

    # 循环发生过：序列里有「观察(ToolMessage)」这一步
    assert any(isinstance(m, ToolMessage) for m in messages)
    # 第一条带 tool_calls 的 AI 消息发起了 get_workflow_run
    calls = [m for m in messages if isinstance(m, AIMessage) and m.tool_calls]
    assert calls and calls[0].tool_calls[0]["name"] == "get_workflow_run"
    # 最终答案带上了工具结果里的结论
    assert "failure" in messages[-1].content


def test_react_greeting_skips_tools() -> None:
    agent = _agent([AIMessage(content="你好！")])
    result = agent.invoke({"messages": [{"role": "user", "content": "hello"}]})
    messages = result["messages"]

    assert not any(isinstance(m, ToolMessage) for m in messages)
    assert "你好" in messages[-1].content
