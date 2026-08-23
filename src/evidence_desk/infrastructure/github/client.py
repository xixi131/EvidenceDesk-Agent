"""基于 GitHub REST API 的只读 ``GitHubGateway`` 适配器。

把 GitHub 的原始响应「挑字段」映射成我们自己的干净模型；把 httpx / GitHub 的
各种错误（404、限流、超时、网络）收敛成稳定的 ``AppError`` 错误码。
Token 只放进请求头，绝不打进日志、不进 state、不进 Prompt。
"""

from typing import Any, cast

import httpx

from evidence_desk.application.ports.github import WorkflowJob, WorkflowRun
from evidence_desk.core.errors import AppError


class GitHubRestClient:
    """用 GitHub 官方 REST API 实现应用层的 ``GitHubGateway`` 端口。"""

    def __init__(
        self,
        *,
        base_url: str,
        api_version: str,
        token: str | None = None,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": api_version,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        # transport 只在测试里注入 MockTransport；生产环境传 None 用真实网络。
        self._client = httpx.Client(
            base_url=base_url,
            headers=headers,
            timeout=timeout,
            transport=transport,
        )

    def get_workflow_run(self, owner: str, repo: str, run_id: int) -> WorkflowRun:
        data = self._get(f"/repos/{owner}/{repo}/actions/runs/{run_id}")
        return WorkflowRun(
            run_id=int(data["id"]),
            name=str(data.get("name") or ""),
            status=str(data["status"]),
            conclusion=data.get("conclusion"),
            head_branch=data.get("head_branch"),
            event=str(data["event"]),
            html_url=str(data["html_url"]),
        )

    def list_workflow_jobs(
        self, owner: str, repo: str, run_id: int
    ) -> list[WorkflowJob]:
        data = self._get(f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs")
        jobs = cast(list[dict[str, Any]], data.get("jobs", []))
        return [
            WorkflowJob(
                job_id=int(job["id"]),
                name=str(job["name"]),
                status=str(job["status"]),
                conclusion=job.get("conclusion"),
                html_url=str(job["html_url"]),
            )
            for job in jobs
        ]

    def _get(self, path: str) -> dict[str, Any]:
        """发一个 GET，并把各种失败收敛成稳定的 AppError。"""

        try:
            response = self._client.get(path)
        except httpx.TimeoutException as exc:
            raise AppError(
                code="GITHUB_TIMEOUT",
                message="GitHub 请求超时",
                status_code=504,
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise AppError(
                code="GITHUB_UNAVAILABLE",
                message="GitHub 暂时不可用",
                status_code=502,
                retryable=True,
            ) from exc

        if response.status_code == 404:
            raise AppError(
                code="GITHUB_NOT_FOUND",
                message="未找到该 workflow 运行",
                status_code=404,
            )
        if response.status_code in (403, 429):
            raise AppError(
                code="GITHUB_RATE_LIMITED",
                message="GitHub 访问受限或超出速率限制",
                status_code=429,
                retryable=True,
            )
        if response.status_code >= 400:
            raise AppError(
                code="GITHUB_UNAVAILABLE",
                message="GitHub 返回错误",
                status_code=502,
                retryable=True,
            )

        return cast(dict[str, Any], response.json())

    def close(self) -> None:
        """关闭底层连接。"""

        self._client.close()
