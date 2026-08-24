"""ReAct 工具的单元测试：用假依赖直接调用工具，验证返回文本。"""

from evidence_desk.agent.tools import build_agent_tools
from evidence_desk.application.ports import WorkflowJob, WorkflowRun
from evidence_desk.rag.models import RetrievalHit


class FakeEmbedder:
    def embed_query(self, query: str) -> list[float]:
        return [0.0, 0.0, 0.0]


class FakeRetriever:
    def __init__(self, hits: list[RetrievalHit]) -> None:
        self._hits = hits

    def search(self, query_vector: list[float], *, top_k: int) -> list[RetrievalHit]:
        return self._hits[:top_k]


class FakeGitHubGateway:
    def __init__(self, run: WorkflowRun) -> None:
        self._run = run

    def get_workflow_run(self, owner: str, repo: str, run_id: int) -> WorkflowRun:
        return self._run

    def list_workflow_jobs(
        self, owner: str, repo: str, run_id: int
    ) -> list[WorkflowJob]:
        return []


def _hit() -> RetrievalHit:
    return RetrievalHit(
        rank=1,
        distance=0.1,
        score=0.9,
        chunk_id="c1",
        parent_doc_id="doc-1",
        title="启用调试日志",
        section_path=["监控工作流"],
        content="设置 ACTIONS_STEP_DEBUG=true。",
        source_url="https://docs.github.com/zh/actions/x",
    )


def _run() -> WorkflowRun:
    return WorkflowRun(
        run_id=123,
        name="CI",
        status="completed",
        conclusion="failure",
        head_branch="main",
        event="push",
        html_url="https://github.com/o/r/actions/runs/123",
    )


def _tools() -> dict:
    tools = build_agent_tools(
        FakeEmbedder(), FakeRetriever([_hit()]), FakeGitHubGateway(_run()), top_k=5
    )
    return {t.name: t for t in tools}


def test_tools_have_expected_names_and_descriptions() -> None:
    tools = _tools()
    assert set(tools) == {"search_docs", "get_workflow_run", "list_workflow_jobs"}
    # docstring 变成给 LLM 的说明
    assert "官方文档" in tools["search_docs"].description


def test_search_docs_returns_sources() -> None:
    out = _tools()["search_docs"].invoke({"query": "调试日志"})
    assert "来源" in out
    assert "docs.github.com" in out


def test_get_workflow_run_reports_conclusion() -> None:
    out = _tools()["get_workflow_run"].invoke(
        {"owner": "o", "repo": "r", "run_id": 123}
    )
    assert "failure" in out
    assert "#123" in out
