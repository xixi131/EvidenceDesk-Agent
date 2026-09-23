"""ReAct 工具的单元测试：用假依赖直接调用工具，验证返回文本。"""

from evidence_desk.agent.tools import build_agent_tools
from evidence_desk.application.ports import WorkflowJob, WorkflowRun
from evidence_desk.rag.models import RetrievalHit


class FakeEmbedder:
    def embed_query(self, query: str) -> list[float]:
        return [0.0, 0.0, 0.0]


class FakeRetriever:
    """假检索器。签名必须跟 ChunkRetriever 端口**完全一致**。

    以前这里少写了 query_text 参数，结果生产换成 Hybrid 检索（需要原始问题
    文本做 BM25 关键词匹配）之后，调用方忘了传也没人发现——假对象根本不接
    这个参数，测试自然测不出来。假对象偷工减料，测试就会假绿。

    现在把收到的 query_text 记下来，让测试能断言「确实传了」。
    """

    def __init__(self, hits: list[RetrievalHit]) -> None:
        self._hits = hits
        self.received_query_text: str | None = None

    def search(
        self, query_vector: list[float], *, top_k: int, query_text: str | None = None
    ) -> list[RetrievalHit]:
        self.received_query_text = query_text
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


def test_search_docs_passes_query_text_to_the_retriever() -> None:
    """漏传 query_text 会让生产的 Hybrid 检索直接抛错，这里钉住它。

    这正是 P6-09 把生产检索从 Dense 换成 Hybrid 之后炸掉的地方：
    端口上 query_text 是可选参数（Dense 用不着），但 Hybrid 实现里是必需的，
    所以类型检查看着没问题，一到真机就 500。
    """
    retriever = FakeRetriever([_hit()])
    tools = build_agent_tools(
        FakeEmbedder(), retriever, FakeGitHubGateway(_run()), top_k=5
    )
    {t.name: t for t in tools}["search_docs"].invoke({"query": "调试日志"})

    assert retriever.received_query_text == "调试日志"


def test_get_workflow_run_reports_conclusion() -> None:
    out = _tools()["get_workflow_run"].invoke(
        {"owner": "o", "repo": "r", "run_id": 123}
    )
    assert "failure" in out
    assert "#123" in out
