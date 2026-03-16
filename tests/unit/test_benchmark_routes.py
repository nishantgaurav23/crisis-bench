"""Tests for S9.2 — Benchmark API routes.

Tests cover: scenario listing/detail, evaluation run listing/detail,
filtering by category and complexity.
"""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import create_app


@pytest.fixture(autouse=True)
def _clear_stores():
    """Clear in-memory stores between tests."""
    from src.api.routes.benchmark import _evaluation_runs, _scenarios

    _scenarios.clear()
    _evaluation_runs.clear()
    yield
    _scenarios.clear()
    _evaluation_runs.clear()


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _scenario_data(**overrides) -> dict:
    """Valid benchmark scenario payload."""
    base = {
        "id": str(uuid.uuid4()),
        "category": "cyclone",
        "complexity": "high",
        "affected_states": ["Odisha", "Andhra Pradesh"],
        "event_count": 8,
        "source": "synthetic",
        "created_at": datetime.now(tz=UTC).isoformat(),
    }
    base.update(overrides)
    return base


def _run_data(scenario_id: str, **overrides) -> dict:
    """Valid evaluation run payload."""
    base = {
        "id": str(uuid.uuid4()),
        "scenario_id": scenario_id,
        "situational_accuracy": 4.2,
        "decision_timeliness": 3.8,
        "resource_efficiency": 4.0,
        "coordination_quality": 3.5,
        "communication_score": 4.1,
        "aggregate_drs": 0.78,
        "total_tokens": 150000,
        "total_cost_usd": 1.25,
        "primary_provider": "deepseek_chat",
        "duration_seconds": 42.5,
        "completed_at": datetime.now(tz=UTC).isoformat(),
    }
    base.update(overrides)
    return base


# ---- Scenario Listing ----


async def test_list_scenarios_empty(client: AsyncClient):
    resp = await client.get("/api/v1/benchmark/scenarios")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_scenarios(client: AsyncClient):
    # Seed two scenarios
    s1 = _scenario_data(category="cyclone")
    s2 = _scenario_data(category="flood")
    await client.post("/api/v1/benchmark/scenarios", json=s1)
    await client.post("/api/v1/benchmark/scenarios", json=s2)

    resp = await client.get("/api/v1/benchmark/scenarios")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


async def test_list_scenarios_filter_category(client: AsyncClient):
    s1 = _scenario_data(category="cyclone")
    s2 = _scenario_data(category="flood")
    await client.post("/api/v1/benchmark/scenarios", json=s1)
    await client.post("/api/v1/benchmark/scenarios", json=s2)

    resp = await client.get("/api/v1/benchmark/scenarios?category=flood")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["category"] == "flood"


async def test_list_scenarios_filter_complexity(client: AsyncClient):
    s1 = _scenario_data(complexity="high")
    s2 = _scenario_data(complexity="low")
    await client.post("/api/v1/benchmark/scenarios", json=s1)
    await client.post("/api/v1/benchmark/scenarios", json=s2)

    resp = await client.get("/api/v1/benchmark/scenarios?complexity=low")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["complexity"] == "low"


# ---- Scenario Detail ----


async def test_get_scenario(client: AsyncClient):
    s = _scenario_data()
    await client.post("/api/v1/benchmark/scenarios", json=s)

    resp = await client.get(f"/api/v1/benchmark/scenarios/{s['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == s["id"]
    assert data["category"] == "cyclone"


async def test_get_scenario_not_found(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/benchmark/scenarios/{fake_id}")
    assert resp.status_code == 404


# ---- Evaluation Run Listing ----


async def test_list_runs_empty(client: AsyncClient):
    resp = await client.get("/api/v1/benchmark/runs")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_runs(client: AsyncClient):
    s = _scenario_data()
    await client.post("/api/v1/benchmark/scenarios", json=s)

    r1 = _run_data(s["id"])
    r2 = _run_data(s["id"])
    await client.post("/api/v1/benchmark/runs", json=r1)
    await client.post("/api/v1/benchmark/runs", json=r2)

    resp = await client.get("/api/v1/benchmark/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


async def test_list_runs_filter_scenario(client: AsyncClient):
    s1 = _scenario_data()
    s2 = _scenario_data()
    await client.post("/api/v1/benchmark/scenarios", json=s1)
    await client.post("/api/v1/benchmark/scenarios", json=s2)

    r1 = _run_data(s1["id"])
    r2 = _run_data(s2["id"])
    await client.post("/api/v1/benchmark/runs", json=r1)
    await client.post("/api/v1/benchmark/runs", json=r2)

    resp = await client.get(f"/api/v1/benchmark/runs?scenario_id={s1['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["scenario_id"] == s1["id"]


# ---- Evaluation Run Detail ----


async def test_get_run(client: AsyncClient):
    s = _scenario_data()
    await client.post("/api/v1/benchmark/scenarios", json=s)

    r = _run_data(s["id"])
    await client.post("/api/v1/benchmark/runs", json=r)

    resp = await client.get(f"/api/v1/benchmark/runs/{r['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == r["id"]
    assert data["aggregate_drs"] == 0.78


async def test_get_run_not_found(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/benchmark/runs/{fake_id}")
    assert resp.status_code == 404
