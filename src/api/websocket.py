"""WebSocket server for real-time dashboard updates.

Provides bidirectional communication between the FastAPI backend and
the Next.js dashboard. Agents broadcast events via ConnectionManager;
connected clients receive events filtered by channel subscription.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

# =============================================================================
# Constants
# =============================================================================

ALL_CHANNELS: set[str] = {"disasters", "agents", "metrics", "general"}

# Event type prefix → channel mapping
_CHANNEL_MAP: dict[str, str] = {
    "disaster": "disasters",
    "agent": "agents",
    "metrics": "metrics",
}


# =============================================================================
# ConnectionManager
# =============================================================================


class ConnectionManager:
    """Manages active WebSocket connections and channel subscriptions."""

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}
        self._subscriptions: dict[str, set[str]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        channels: set[str] | None = None,
    ) -> str:
        """Accept a WebSocket connection and register it.

        Args:
            websocket: The WebSocket to accept.
            channels: Channel subscriptions. Defaults to ALL_CHANNELS.

        Returns:
            A unique client_id string.
        """
        await websocket.accept()
        client_id = uuid.uuid4().hex[:12]
        self._connections[client_id] = websocket
        self._subscriptions[client_id] = set(channels) if channels else set(ALL_CHANNELS)
        return client_id

    async def disconnect(self, client_id: str) -> None:
        """Remove a client connection."""
        self._connections.pop(client_id, None)
        self._subscriptions.pop(client_id, None)

    async def broadcast(
        self,
        event_type: str,
        data: dict[str, Any],
        *,
        trace_id: str | None = None,
    ) -> None:
        """Send an event to all clients subscribed to the matching channel."""
        channel = self.get_channel(event_type)
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(UTC).isoformat(),
            "trace_id": trace_id or uuid.uuid4().hex[:8],
        }
        disconnected: list[str] = []
        for client_id, ws in self._connections.items():
            if channel in self._subscriptions.get(client_id, set()):
                try:
                    await ws.send_json(message)
                except Exception:
                    disconnected.append(client_id)
        for client_id in disconnected:
            await self.disconnect(client_id)

    async def send_to_client(self, client_id: str, message: dict[str, Any]) -> None:
        """Send a message to a specific client."""
        ws = self._connections.get(client_id)
        if ws is not None:
            try:
                await ws.send_json(message)
            except Exception:
                await self.disconnect(client_id)

    def get_channel(self, event_type: str) -> str:
        """Map an event type to its channel name."""
        prefix = event_type.split(".")[0]
        return _CHANNEL_MAP.get(prefix, "general")

    def subscribe(self, client_id: str, channels: set[str]) -> None:
        """Add channels to a client's subscriptions."""
        if client_id in self._subscriptions:
            self._subscriptions[client_id] |= channels

    def unsubscribe(self, client_id: str, channels: set[str]) -> None:
        """Remove channels from a client's subscriptions."""
        if client_id in self._subscriptions:
            self._subscriptions[client_id] -= channels

    def get_subscriptions(self, client_id: str) -> set[str]:
        """Return the current channel subscriptions for a client."""
        return set(self._subscriptions.get(client_id, set()))

    @property
    def active_count(self) -> int:
        """Number of currently connected clients."""
        return len(self._connections)


# =============================================================================
# Global Manager Instance
# =============================================================================

manager = ConnectionManager()


# =============================================================================
# WebSocket Endpoint
# =============================================================================


async def websocket_endpoint(websocket: WebSocket, channels: str | None = None) -> None:
    """WebSocket endpoint handler mounted at /ws.

    Args:
        websocket: The incoming WebSocket connection.
        channels: Comma-separated channel names (query param). Defaults to all.
    """
    # Parse channels query param
    channel_set: set[str] | None = None
    if channels:
        channel_set = {c.strip() for c in channels.split(",") if c.strip()}

    client_id = await manager.connect(websocket, channels=channel_set)

    # Send welcome message
    welcome = {
        "type": "connection.established",
        "data": {
            "client_id": client_id,
            "channels": sorted(manager.get_subscriptions(client_id)),
        },
        "timestamp": datetime.now(UTC).isoformat(),
        "trace_id": uuid.uuid4().hex[:8],
    }
    await websocket.send_json(welcome)

    try:
        while True:
            raw = await websocket.receive_json()
            await _handle_command(client_id, websocket, raw)
    except WebSocketDisconnect:
        await manager.disconnect(client_id)
    except Exception:
        await manager.disconnect(client_id)


async def _handle_command(
    client_id: str,
    websocket: WebSocket,
    payload: dict[str, Any],
) -> None:
    """Process a client command."""
    command = payload.get("command")

    if command is None:
        await websocket.send_json({
            "type": "error",
            "data": {"message": "Missing 'command' field"},
            "timestamp": datetime.now(UTC).isoformat(),
            "trace_id": uuid.uuid4().hex[:8],
        })
        return

    if command == "ping":
        await websocket.send_json({
            "type": "pong",
            "data": {},
            "timestamp": datetime.now(UTC).isoformat(),
            "trace_id": uuid.uuid4().hex[:8],
        })

    elif command == "subscribe":
        new_channels = set(payload.get("channels", []))
        manager.subscribe(client_id, new_channels)
        await websocket.send_json({
            "type": "subscribed",
            "data": {"channels": sorted(manager.get_subscriptions(client_id))},
            "timestamp": datetime.now(UTC).isoformat(),
            "trace_id": uuid.uuid4().hex[:8],
        })

    elif command == "unsubscribe":
        rm_channels = set(payload.get("channels", []))
        manager.unsubscribe(client_id, rm_channels)
        await websocket.send_json({
            "type": "unsubscribed",
            "data": {"channels": sorted(manager.get_subscriptions(client_id))},
            "timestamp": datetime.now(UTC).isoformat(),
            "trace_id": uuid.uuid4().hex[:8],
        })

    else:
        await websocket.send_json({
            "type": "error",
            "data": {"message": f"Unknown command: {command}"},
            "timestamp": datetime.now(UTC).isoformat(),
            "trace_id": uuid.uuid4().hex[:8],
        })
