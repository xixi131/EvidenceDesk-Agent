"""GitHub 只读 Gateway 端口及其数据契约。

应用层只依赖这个端口来获取「真实运行事实」（某次 workflow 运行的状态、作业列表），
不关心背后是真实 GitHub REST API 还是测试用的假实现。

约定：实现类在出错时抛 ``AppError``（稳定错误码），而不是让 httpx / GitHub 的
原始异常泄漏到上层——具体映射在 infrastructure 的适配器里做。
"""

from typing import Protocol

from pydantic import BaseModel, ConfigDict


class _GitHubModel(BaseModel):
    """本端口数据契约的公共基类：拒绝未知字段，保持我们自己的干净结构。"""

    model_config = ConfigDict(extra="forbid")


class WorkflowRun(_GitHubModel):
    """一次 workflow 运行的关键事实（从 GitHub 原始响应里挑出我们要用的字段）。"""

    run_id: int
    name: str
    status: str  # queued / in_progress / completed
    conclusion: str | None  # success / failure / cancelled…；未完成时为 None
    head_branch: str | None
    event: str  # push / pull_request / workflow_dispatch…
    html_url: str


class WorkflowJob(_GitHubModel):
    """运行中的一个作业（job）的关键事实。"""

    job_id: int
    name: str
    status: str
    conclusion: str | None
    html_url: str


class GitHubGateway(Protocol):
    """读取 GitHub Actions 运行事实的最小只读接口。"""

    def get_workflow_run(self, owner: str, repo: str, run_id: int) -> WorkflowRun:
        """取一次 workflow 运行的状态与结论。"""
        ...

    def list_workflow_jobs(
        self, owner: str, repo: str, run_id: int
    ) -> list[WorkflowJob]:
        """列出该次运行下的所有作业。"""
        ...
