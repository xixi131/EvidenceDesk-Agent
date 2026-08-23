"""GitHubRestClient 的单元测试：用 MockTransport 假装 GitHub，不连真实网络。"""

from collections.abc import Callable

import httpx
import pytest

from evidence_desk.core.errors import AppError
from evidence_desk.infrastructure.github import GitHubRestClient


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> GitHubRestClient:
    return GitHubRestClient(
        base_url="https://api.github.com",
        api_version="2026-03-10",
        transport=httpx.MockTransport(handler),
    )


def test_get_workflow_run_picks_fields_from_raw_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/o/r/actions/runs/123"
        # 故意塞一堆多余字段，验证我们只挑需要的、结果模型不被污染。
        return httpx.Response(
            200,
            json={
                "id": 123,
                "name": "CI",
                "status": "completed",
                "conclusion": "failure",
                "head_branch": "main",
                "event": "push",
                "html_url": "https://github.com/o/r/actions/runs/123",
                "unused_a": "x",
                "unused_b": {"nested": 1},
            },
        )

    run = _client(handler).get_workflow_run("o", "r", 123)
    assert run.run_id == 123
    assert run.conclusion == "failure"
    assert run.html_url.endswith("/runs/123")


def test_running_workflow_has_none_conclusion() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": 9,
                "name": "CI",
                "status": "in_progress",
                "conclusion": None,
                "head_branch": "dev",
                "event": "push",
                "html_url": "https://github.com/o/r/actions/runs/9",
            },
        )

    run = _client(handler).get_workflow_run("o", "r", 9)
    assert run.status == "in_progress"
    assert run.conclusion is None


def test_404_maps_to_stable_error_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    with pytest.raises(AppError) as exc_info:
        _client(handler).get_workflow_run("o", "r", 999)
    assert exc_info.value.code == "GITHUB_NOT_FOUND"


def test_rate_limit_maps_to_retryable_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "rate limit"})

    with pytest.raises(AppError) as exc_info:
        _client(handler).list_workflow_jobs("o", "r", 123)
    assert exc_info.value.code == "GITHUB_RATE_LIMITED"
    assert exc_info.value.retryable is True
