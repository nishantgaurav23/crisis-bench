"""Tests for S9.2 — Agent decisions API route.

Tests cover: listing decisions for a specific agent, decisions store.
"""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import create_app


@pytest.fixture(autouse=True)
def _clear_stores():
    """Clear decision store between tests."""
    from src.api.routes.agents import _agent_decisions

    _agent_decisions.clear()
    yield
    _agent_decisions.clear()


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _decision_data(agent_type: str = "orchestrator") -> dict:
    return {
        "id": str(uuid.uuid4()),
        "agent_type": agent_type,
        "decision_type": "evacuation_plan",
        "confidence": 0.92,
        "reasoning": "Optimal deployment for Cyclone Dana",
        "cost_usd": 0.15,
        "latency_ms": 2345,
        "created_at": datetime.now(tz=UTC).isoformat(),
    }


async def test_list_decisions_empty(client: AsyncClient):
    resp = await client.get("/api/v1/agents/orchestrator/decisions")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_decisions_for_agent(client: AsyncClient):
    # Seed decisions via internal API
    from src.api.routes.agents import _agent_decisions

    d1 = _decision_data("orchestrator")
    d2 = _decision_data("orchestrator")
    d3 = _decision_data("situation_sense")
    _agent_decisions.setdefault("orchestrator", []).append(d1)
    _agent_decisions["orchestrator"].append(d2)
    _agent_decisions.setdefault("situation_sense", []).append(d3)

    resp = await client.get("/api/v1/agents/orchestrator/decisions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2

    resp2 = await client.get("/api/v1/agents/situation_sense/decisions")
    data2 = resp2.json()
    assert len(data2) == 1


async def test_list_decisions_invalid_agent(client: AsyncClient):
    resp = await client.get("/api/v1/agents/nonexistent/decisions")
    assert resp.status_code == 422
