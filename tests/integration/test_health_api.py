from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from evidence_desk.main import app


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_health_endpoint_returns_stable_json(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "req_health"})

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["data"] == {"status": "ok"}
    assert response.json()["error"] is None
    assert response.json()["meta"]["request_id"] == "req_health"
    assert response.headers["X-Request-ID"] == "req_health"


@pytest.mark.asyncio
async def test_version_endpoint_returns_stable_json(client: AsyncClient) -> None:
    response = await client.get("/api/v1/version")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "service": "evidence-desk",
        "version": "0.1.0",
    }
    assert response.json()["meta"]["request_id"].startswith("req_")


@pytest.mark.asyncio
async def test_ready_returns_ok_when_dependencies_are_available(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from evidence_desk.application.readiness import ReadinessResult

    async def fake_evaluate(settings: object) -> ReadinessResult:
        return ReadinessResult(
            dependencies={"postgresql": "ok", "weaviate": "ok"},
            unavailable=(),
        )

    monkeypatch.setattr(app.state.readiness_service, "evaluate", fake_evaluate)

    response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "status": "ready",
        "dependencies": {"postgresql": "ok", "weaviate": "ok"},
    }


@pytest.mark.asyncio
async def test_ready_identifies_unavailable_dependencies(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from evidence_desk.application.readiness import ReadinessResult

    async def fake_evaluate(settings: object) -> ReadinessResult:
        return ReadinessResult(
            dependencies={"postgresql": "ok", "weaviate": "unavailable"},
            unavailable=("weaviate",),
        )

    monkeypatch.setattr(app.state.readiness_service, "evaluate", fake_evaluate)

    response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DEPENDENCIES_UNAVAILABLE"
    assert response.json()["error"]["details"] == {
        "dependencies": {"postgresql": "ok", "weaviate": "unavailable"},
        "unavailable": ["weaviate"],
    }


@pytest.mark.asyncio
async def test_swagger_and_openapi_are_available(client: AsyncClient) -> None:
    docs_response = await client.get("/docs")
    openapi_response = await client.get("/openapi.json")

    assert docs_response.status_code == 200
    assert "Swagger UI" in docs_response.text
    assert openapi_response.status_code == 200
    assert "/health" in openapi_response.json()["paths"]
    assert "/ready" in openapi_response.json()["paths"]
    assert "/api/v1/version" in openapi_response.json()["paths"]


@pytest.mark.asyncio
async def test_unknown_endpoint_returns_standard_error(client: AsyncClient) -> None:
    response = await client.get("/not-found")

    assert response.status_code == 404
    assert response.json()["ok"] is False
    assert response.json()["error"]["code"] == "HTTP_ERROR"
