"""GitHub Gateway 端口与数据契约的单元测试。"""

import pytest
from pydantic import ValidationError

from evidence_desk.application.ports import GitHubGateway, WorkflowJob, WorkflowRun


class FakeGitHubGateway:
    """测试用假实现：返回构造时预设好的运行与作业。

    注意它没有写 `class FakeGitHubGateway(GitHubGateway)`——因为 GitHubGateway 是
    Protocol，只要方法签名对得上，它就自动被当作一个 GitHubGateway（结构化类型）。
    """

    def __init__(self, run: WorkflowRun, jobs: list[WorkflowJob]) -> None:
        self._run = run
        self._jobs = jobs

    def get_workflow_run(self, owner: str, repo: str, run_id: int) -> WorkflowRun:
        return self._run

    def list_workflow_jobs(
        self, owner: str, repo: str, run_id: int
    ) -> list[WorkflowJob]:
        return self._jobs


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


def test_fake_gateway_satisfies_protocol_and_returns_facts() -> None:
    gateway: GitHubGateway = FakeGitHubGateway(  # 结构匹配即可赋给端口类型
        _run(),
        [
            WorkflowJob(
                job_id=1,
                name="build",
                status="completed",
                conclusion="failure",
                html_url="https://github.com/o/r/actions/runs/123/job/1",
            )
        ],
    )

    run = gateway.get_workflow_run("o", "r", 123)
    assert run.conclusion == "failure"
    assert gateway.list_workflow_jobs("o", "r", 123)[0].name == "build"


def test_workflow_run_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        WorkflowRun.model_validate(
            {
                "run_id": 1,
                "name": "CI",
                "status": "completed",
                "conclusion": None,
                "head_branch": "main",
                "event": "push",
                "html_url": "https://x",
                "unexpected": "boom",  # 未知字段 → extra=forbid 拒绝
            }
        )
