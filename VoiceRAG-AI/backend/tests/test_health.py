import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client() -> AsyncClient:  # type: ignore[misc]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac  # type: ignore[misc]


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert "env" in body
    assert "version" in body
    assert "dependencies" in body


async def test_health_includes_dependency_statuses(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    deps = response.json()["dependencies"]

    assert "postgres" in deps
    assert "chromadb" in deps


async def test_404_returns_structured_json(client: AsyncClient) -> None:
    response = await client.get("/api/v1/nonexistent")

    assert response.status_code == 404
