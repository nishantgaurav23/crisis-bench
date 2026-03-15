"""Tests for S3.1 — FastAPI Gateway.

Tests cover: health endpoint, disaster CRUD, agent status,
CrisisError handling, and CORS configuration.
"""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import create_app


@pytest.fixture(autouse=True)
def _clear_stores():
    """Clear in-memory stores between tests."""
    from src.api.routes.disasters import _disasters

    _disasters.clear()
    yield
    _disasters.clear()


@pytest.fixture
def app():
    """Create a fresh FastAPI app for each test."""
    return create_app()


@pytest.fixture
async def client(app):
    """Async test client using httpx."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _disaster_payload() -> dict:
    """Valid disaster creation payload."""
    return {
        "type": "cyclone",
        "severity": 4,
        "start_time": datetime.now(tz=UTC).isoformat(),
        "affected_state_ids": [21],
        "location": {"latitude": 20.5, "longitude": 86.5},
        "metadata": {"name": "Cyclone Dana"},
    }


# ---- Health ----


async def test_health_returns_ok(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert "environment" in data


# ---- Disaster CRUD ----


async def test_create_disaster(client: AsyncClient):
    resp = await client.post("/api/v1/disasters", json=_disaster_payload())
    assert resp.status_code == 201
    data = resp.json()
    assert data["type"] == "cyclone"
    assert data["severity"] == 4
    assert "id" in data


async def test_list_disasters(client: AsyncClient):
    await client.post("/api/v1/disasters", json=_disaster_payload())
    resp = await client.get("/api/v1/disasters")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


async def test_get_disaster(client: AsyncClient):
    create_resp = await client.post("/api/v1/disasters", json=_disaster_payload())
    disaster_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/disasters/{disaster_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == disaster_id


async def test_get_disaster_not_found(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/disasters/{fake_id}")
    assert resp.status_code == 422
    data = resp.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "trace_id" in data


async def test_delete_disaster(client: AsyncClient):
    create_resp = await client.post("/api/v1/disasters", json=_disaster_payload())
    disaster_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/disasters/{disaster_id}")
    assert resp.status_code == 204
    # Verify gone
    get_resp = await client.get(f"/api/v1/disasters/{disaster_id}")
    assert get_resp.status_code == 422


async def test_create_disaster_invalid(client: AsyncClient):
    resp = await client.post("/api/v1/disasters", json={"type": "invalid", "severity": 99})
    assert resp.status_code == 422


# ---- Agent Status ----


async def test_list_agents(client: AsyncClient):
    resp = await client.get("/api/v1/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 7


async def test_get_agent(client: AsyncClient):
    resp = await client.get("/api/v1/agents/orchestrator")
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_type"] == "orchestrator"
    assert "capabilities" in data


async def test_get_agent_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/agents/invalid_agent")
    assert resp.status_code == 422
    data = resp.json()
    assert data["error_code"] == "VALIDATION_ERROR"


# ---- Error Handling ----


async def test_crisis_error_handler(client: AsyncClient):
    """CrisisError subclasses should produce structured JSON with correct HTTP status."""
    # Trigger via not-found disaster (uses CrisisValidationError with http_status=422)
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/disasters/{fake_id}")
    data = resp.json()
    assert "error_code" in data
    assert "message" in data
    assert "trace_id" in data
    assert "severity" in data


# ---- CORS ----


async def test_cors_headers(client: AsyncClient):
    resp = await client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
