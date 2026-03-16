"""Tests for S9.2 — WebSocket broadcast on disaster creation.

Tests cover: disaster creation triggers WebSocket broadcast event.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import create_app


@pytest.fixture(autouse=True)
def _clear_stores():
    from src.api.routes.disasters import _disasters

    _disasters.clear()
    yield
    _disasters.clear()


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _disaster_payload() -> dict:
    return {
        "type": "cyclone",
        "severity": 4,
        "start_time": datetime.now(tz=UTC).isoformat(),
        "affected_state_ids": [21],
        "location": {"latitude": 20.5, "longitude": 86.5},
        "metadata": {"name": "Cyclone Dana"},
    }


async def test_create_disaster_broadcasts_websocket(client: AsyncClient):
    """Creating a disaster should broadcast a disaster.created event via WebSocket."""
    with patch("src.api.routes.disasters.manager") as mock_manager:
        mock_manager.broadcast = AsyncMock()

        resp = await client.post("/api/v1/disasters", json=_disaster_payload())
        assert resp.status_code == 201

        mock_manager.broadcast.assert_called_once()
        call_args = mock_manager.broadcast.call_args
        assert call_args[0][0] == "disaster.created"
        event_data = call_args[0][1]
        assert event_data["type"] == "cyclone"
        assert event_data["severity"] == 4
