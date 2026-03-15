"""Tests for S3.2 — WebSocket Server.

Tests cover: ConnectionManager (connect, disconnect, broadcast, send_to_client,
channel subscriptions), WebSocket endpoint (ping/pong, subscribe/unsubscribe,
broadcast envelope), and app integration (route mounted at /ws).
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from starlette.testclient import TestClient

from src.api.main import create_app

# =============================================================================
# ConnectionManager Unit Tests
# =============================================================================


class TestConnectionManagerConnect:
    async def test_connect_returns_client_id(self):
        from src.api.websocket import ConnectionManager

        mgr = ConnectionManager()
        ws = AsyncMock()
        client_id = await mgr.connect(ws)
        assert isinstance(client_id, str)
        assert len(client_id) > 0

    async def test_connect_increments_count(self):
        from src.api.websocket import ConnectionManager

        mgr = ConnectionManager()
        assert mgr.active_count == 0
        await mgr.connect(AsyncMock())
        assert mgr.active_count == 1
        await mgr.connect(AsyncMock())
        assert mgr.active_count == 2

    async def test_connect_accepts_websocket(self):
        from src.api.websocket import ConnectionManager

        mgr = ConnectionManager()
        ws = AsyncMock()
        await mgr.connect(ws)
        ws.accept.assert_awaited_once()


class TestConnectionManagerDisconnect:
    async def test_disconnect_removes_client(self):
        from src.api.websocket import ConnectionManager

        mgr = ConnectionManager()
        ws = AsyncMock()
        client_id = await mgr.connect(ws)
        assert mgr.active_count == 1
        await mgr.disconnect(client_id)
        assert mgr.active_count == 0

    async def test_disconnect_unknown_client_is_noop(self):
        from src.api.websocket import ConnectionManager

        mgr = ConnectionManager()
        await mgr.disconnect("nonexistent")  # Should not raise


class TestConnectionManagerBroadcast:
    async def test_broadcast_to_subscribed(self):
        from src.api.websocket import ConnectionManager

        mgr = ConnectionManager()
        ws = AsyncMock()
        await mgr.connect(ws, channels={"disasters"})
        await mgr.broadcast("disaster.created", {"id": "abc"})
        ws.send_json.assert_awaited_once()
        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "disaster.created"
        assert sent["data"] == {"id": "abc"}

    async def test_broadcast_skips_unsubscribed(self):
        from src.api.websocket import ConnectionManager

        mgr = ConnectionManager()
        ws_disasters = AsyncMock()
        ws_agents = AsyncMock()
        await mgr.connect(ws_disasters, channels={"disasters"})
        await mgr.connect(ws_agents, channels={"agents"})
        await mgr.broadcast("disaster.created", {"id": "abc"})
        ws_disasters.send_json.assert_awaited_once()
        ws_agents.send_json.assert_not_awaited()

    async def test_broadcast_to_all_default_channels(self):
        from src.api.websocket import ConnectionManager

        mgr = ConnectionManager()
        ws = AsyncMock()
        await mgr.connect(ws)  # default = all channels
        await mgr.broadcast("disaster.created", {"id": "abc"})
        ws.send_json.assert_awaited_once()

    async def test_broadcast_handles_disconnected_client(self):
        """If send_json raises, broadcast removes the client gracefully."""
        from src.api.websocket import ConnectionManager

        mgr = ConnectionManager()
        ws = AsyncMock()
        ws.send_json.side_effect = RuntimeError("disconnected")
        await mgr.connect(ws)
        await mgr.broadcast("disaster.created", {"id": "abc"})
        assert mgr.active_count == 0  # auto-removed


class TestConnectionManagerSendToClient:
    async def test_send_to_client(self):
        from src.api.websocket import ConnectionManager

        mgr = ConnectionManager()
        ws = AsyncMock()
        client_id = await mgr.connect(ws)
        await mgr.send_to_client(client_id, {"type": "test", "data": {}})
        ws.send_json.assert_awaited_once_with({"type": "test", "data": {}})

    async def test_send_to_invalid_client(self):
        from src.api.websocket import ConnectionManager

        mgr = ConnectionManager()
        # Should not raise
        await mgr.send_to_client("nonexistent", {"type": "test"})


class TestChannelMapping:
    def test_disaster_events_map_to_disasters_channel(self):
        from src.api.websocket import ConnectionManager

        mgr = ConnectionManager()
        assert mgr.get_channel("disaster.created") == "disasters"
        assert mgr.get_channel("disaster.updated") == "disasters"

    def test_agent_events_map_to_agents_channel(self):
        from src.api.websocket import ConnectionManager

        mgr = ConnectionManager()
        assert mgr.get_channel("agent.status") == "agents"
        assert mgr.get_channel("agent.decision") == "agents"

    def test_metrics_events_map_to_metrics_channel(self):
        from src.api.websocket import ConnectionManager

        mgr = ConnectionManager()
        assert mgr.get_channel("metrics.update") == "metrics"

    def test_unknown_event_maps_to_general(self):
        from src.api.websocket import ConnectionManager

        mgr = ConnectionManager()
        assert mgr.get_channel("unknown.event") == "general"


class TestDefaultChannels:
    async def test_default_subscribes_to_all(self):
        from src.api.websocket import ALL_CHANNELS, ConnectionManager

        mgr = ConnectionManager()
        ws = AsyncMock()
        client_id = await mgr.connect(ws)
        subs = mgr.get_subscriptions(client_id)
        assert subs == ALL_CHANNELS

    async def test_custom_channels(self):
        from src.api.websocket import ConnectionManager

        mgr = ConnectionManager()
        ws = AsyncMock()
        client_id = await mgr.connect(ws, channels={"disasters"})
        subs = mgr.get_subscriptions(client_id)
        assert subs == {"disasters"}


class TestSubscriptionManagement:
    async def test_subscribe_adds_channels(self):
        from src.api.websocket import ConnectionManager

        mgr = ConnectionManager()
        ws = AsyncMock()
        client_id = await mgr.connect(ws, channels={"disasters"})
        mgr.subscribe(client_id, {"agents"})
        subs = mgr.get_subscriptions(client_id)
        assert "disasters" in subs
        assert "agents" in subs

    async def test_unsubscribe_removes_channels(self):
        from src.api.websocket import ConnectionManager

        mgr = ConnectionManager()
        ws = AsyncMock()
        client_id = await mgr.connect(ws)
        mgr.unsubscribe(client_id, {"disasters"})
        subs = mgr.get_subscriptions(client_id)
        assert "disasters" not in subs


class TestBroadcastEnvelope:
    async def test_envelope_has_required_fields(self):
        from src.api.websocket import ConnectionManager

        mgr = ConnectionManager()
        ws = AsyncMock()
        await mgr.connect(ws)
        await mgr.broadcast("disaster.created", {"id": "abc"})
        sent = ws.send_json.call_args[0][0]
        assert "type" in sent
        assert "data" in sent
        assert "timestamp" in sent
        assert "trace_id" in sent

    async def test_envelope_uses_provided_trace_id(self):
        from src.api.websocket import ConnectionManager

        mgr = ConnectionManager()
        ws = AsyncMock()
        await mgr.connect(ws)
        await mgr.broadcast("disaster.created", {"id": "abc"}, trace_id="test-trace")
        sent = ws.send_json.call_args[0][0]
        assert sent["trace_id"] == "test-trace"

    async def test_envelope_timestamp_is_iso(self):
        from src.api.websocket import ConnectionManager

        mgr = ConnectionManager()
        ws = AsyncMock()
        await mgr.connect(ws)
        await mgr.broadcast("disaster.created", {})
        sent = ws.send_json.call_args[0][0]
        # Should parse without error
        datetime.fromisoformat(sent["timestamp"])


# =============================================================================
# WebSocket Endpoint Integration Tests (via Starlette TestClient)
# =============================================================================


class TestWebSocketEndpoint:
    @pytest.fixture
    def app(self):
        return create_app()

    def test_websocket_connect_disconnect(self, app):
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            # Should receive a welcome message
            data = ws.receive_json()
            assert data["type"] == "connection.established"
            assert "client_id" in data["data"]

    def test_websocket_ping_pong(self, app):
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"command": "ping"})
            data = ws.receive_json()
            assert data["type"] == "pong"

    def test_websocket_subscribe_command(self, app):
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"command": "subscribe", "channels": ["disasters"]})
            data = ws.receive_json()
            assert data["type"] == "subscribed"
            assert "disasters" in data["data"]["channels"]

    def test_websocket_unsubscribe_command(self, app):
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"command": "unsubscribe", "channels": ["disasters"]})
            data = ws.receive_json()
            assert data["type"] == "unsubscribed"

    def test_websocket_invalid_command(self, app):
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"command": "invalid_cmd"})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "unknown" in data["data"]["message"].lower()

    def test_websocket_invalid_json_payload(self, app):
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"no_command_key": "bad"})
            data = ws.receive_json()
            assert data["type"] == "error"

    def test_websocket_channels_query_param(self, app):
        client = TestClient(app)
        with client.websocket_connect("/ws?channels=disasters,agents") as ws:
            data = ws.receive_json()
            assert data["type"] == "connection.established"
            # channels should be restricted
            assert set(data["data"]["channels"]) == {"disasters", "agents"}


class TestAppWebSocketRoute:
    def test_app_has_websocket_route(self):
        app = create_app()
        routes = [r.path for r in app.routes]
        assert "/ws" in routes
