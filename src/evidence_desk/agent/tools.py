"""ReAct Agent 可调用的工具集合。

每个工具用 ``@tool`` 封装：函数的 **docstring 和参数类型** 会被序列化成
「工具说明 + 参数 schema」塞给 LLM，LLM 据此自己决定调不调、填什么参数。
工具通过工厂闭包注入依赖（检索器 / GitHub 网关），并返回给 LLM 阅读的纯文本。
"""

from langchain_core.tools import BaseTool, tool

from evidence_desk.application.ports import (
    ChunkRetriever,
    GitHubGateway,
    QueryEmbedder,
)
from evidence_desk.core.errors import AppError


def build_agent_tools(
    embedder: QueryEmbedder,
    retriever: ChunkRetriever,
    gateway: GitHubGateway,
    *,
    top_k: int,
) -> list[BaseTool]:
    """注入依赖，返回 ReAct Agent 使用的工具列表。"""

    @tool
    def search_docs(query: str) -> str:
        """检索 GitHub Actions 官方文档，返回最相关的片段与来源链接。

        当用户询问 GitHub Actions 的用法、概念、配置或故障排查等知识性问题时使用。
        query 请用简洁的检索关键词（可对用户口语做提炼）。回答时应引用返回的来源链接。
        """
        hits = retriever.search(embedder.embed_query(query), top_k=top_k)
        if not hits:
            return "未检索到相关文档。"
        blocks = [
            f"[资料{i}] {hit.title}\n来源：{hit.source_url}\n内容：{hit.content}"
            for i, hit in enumerate(hits, start=1)
        ]
        return "\n\n".join(blocks)

    @tool
    def get_workflow_run(owner: str, repo: str, run_id: int) -> str:
        """查询某次 GitHub Actions workflow 运行的真实状态与结论。

        当用户询问某次具体运行（需给出 owner、repo 和 run_id）是否成功、为何失败等
        实时事实时使用。不要用文档去猜运行结果——运行状态必须来自本工具。
        """
        try:
            run = gateway.get_workflow_run(owner, repo, run_id)
        except AppError as exc:
            return f"查询失败：{exc.message}"
        conclusion = run.conclusion or "尚无结论（可能仍在运行）"
        return (
            f"工作流「{run.name}」运行 #{run.run_id}"
            f"（{owner}/{repo}，分支 {run.head_branch or '未知'}，事件 {run.event}）："
            f"状态 {run.status}，结论 {conclusion}。详情：{run.html_url}"
        )

    @tool
    def list_workflow_jobs(owner: str, repo: str, run_id: int) -> str:
        """列出某次 workflow 运行下所有作业(job)的状态与结论。

        当需要进一步定位是哪一个作业/步骤失败时使用。
        """
        try:
            jobs = gateway.list_workflow_jobs(owner, repo, run_id)
        except AppError as exc:
            return f"查询失败：{exc.message}"
        if not jobs:
            return "该运行没有作业记录。"
        lines = [
            f"- {job.name}：状态 {job.status}，结论 {job.conclusion or '尚无'}"
            for job in jobs
        ]
        return "作业列表：\n" + "\n".join(lines)

    return [search_docs, get_workflow_run, list_workflow_jobs]
