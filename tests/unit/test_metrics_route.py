"""Tests for S9.2 — Metrics summary API route.

Tests cover: metrics summary endpoint returning provider cost/token data.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_metrics_summary_returns_structure(client: AsyncClient):
    resp = await client.get("/api/v1/metrics/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data
    assert "total_cost" in data
    assert "total_input_tokens" in data
    assert "total_output_tokens" in data
    assert "total_requests" in data
    assert "period_start" in data
    assert "period_end" in data
    assert isinstance(data["providers"], list)


async def test_metrics_summary_providers_have_fields(client: AsyncClient):
    resp = await client.get("/api/v1/metrics/summary")
    data = resp.json()
    if data["providers"]:
        p = data["providers"][0]
        assert "provider" in p
        assert "tier" in p
        assert "total_cost" in p
        assert "input_tokens" in p
        assert "output_tokens" in p
        assert "requests" in p
        assert "avg_latency_ms" in p


async def test_metrics_summary_totals_are_numeric(client: AsyncClient):
    resp = await client.get("/api/v1/metrics/summary")
    data = resp.json()
    assert isinstance(data["total_cost"], (int, float))
    assert isinstance(data["total_input_tokens"], int)
    assert isinstance(data["total_output_tokens"], int)
    assert isinstance(data["total_requests"], int)
