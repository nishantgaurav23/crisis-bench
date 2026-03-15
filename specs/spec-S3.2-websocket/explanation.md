# Spec S3.2 — WebSocket Server: Explanation

## Why This Spec Exists

The CRISIS-BENCH dashboard needs real-time updates — when an agent makes a decision, a disaster phase changes, or cost metrics update, the dashboard should reflect those changes immediately without polling. WebSocket provides bidirectional communication: the server pushes events to the dashboard, and the dashboard can send commands back (subscribe/unsubscribe to channels, ping for heartbeat).

This spec builds the WebSocket infrastructure layer that future specs (S7.x agents, S9.2 dashboard integration) will use to push live data to the frontend.

## What It Does

### ConnectionManager
A centralized manager that tracks all active WebSocket connections:
- **Connection lifecycle**: Each client gets a unique `client_id` on connect; cleanup on disconnect
- **Channel-based subscriptions**: Clients subscribe to channels (`disasters`, `agents`, `metrics`, `general`). Broadcasts only reach clients subscribed to the matching channel
- **Automatic cleanup**: If a `send_json()` fails (client disconnected without clean close), the manager removes the dead connection automatically

### Event Type → Channel Mapping
Event types use dot-notation (e.g., `disaster.created`, `agent.status`). The first segment maps to a channel:
- `disaster.*` → `disasters` channel
- `agent.*` → `agents` channel
- `metrics.*` → `metrics` channel
- Everything else → `general` channel

### Message Envelope
Every message (both broadcast and command responses) uses a standard envelope:
```json
{
  "type": "disaster.created",
  "data": {"id": "abc", "severity": 4},
  "timestamp": "2026-03-15T10:00:00+00:00",
  "trace_id": "a1b2c3d4"
}
```

### Client Commands
- `ping` → `pong` (heartbeat)
- `subscribe` → add channels to subscription
- `unsubscribe` → remove channels from subscription
- Unknown commands → error response

### Integration
The WebSocket endpoint is mounted at `/ws` on the FastAPI app via `app.add_api_websocket_route()`. Clients can pass `?channels=disasters,agents` query param to subscribe to specific channels on connect.

## How It Works

1. Dashboard opens `ws://localhost:8000/ws?channels=disasters,agents`
2. Server accepts, assigns `client_id`, sends `connection.established` message
3. Server-side code (agents, API routes) calls `manager.broadcast("disaster.created", {...})`
4. `ConnectionManager` checks each client's subscriptions, sends only to matching clients
5. Dashboard can send `{"command": "subscribe", "channels": ["metrics"]}` to add channels
6. On disconnect (clean or error), client is removed from the manager

## How It Connects to the Rest of the Project

| Spec | Relationship |
|------|-------------|
| **S3.1** (FastAPI gateway) | WebSocket route is mounted on the FastAPI app created by S3.1 |
| **S2.3** (Redis utils) | Future Redis Streams → WebSocket bridge will use S2.3's consumer groups |
| **S7.x** (Agents) | Agents will call `manager.broadcast()` to push status/decision events |
| **S7.9** (Agent integration) | Integration test verifies WebSocket dashboard update within 45s |
| **S9.2** (Dashboard integration) | Dashboard components connect to `/ws` and render live data |
| **S3.3-S3.7** (Dashboard components) | Will consume WebSocket events for map markers, agent panels, metrics, timeline |

## Interview Q&A

**Q: Why a global `ConnectionManager` instead of per-request state?**
A: WebSocket connections are long-lived — they span the entire session, not a single request. A global manager is the standard pattern (used by FastAPI docs, Django Channels, Socket.IO) because it needs to track connections across multiple coroutines. The `broadcast()` method iterates over all connections, which requires a shared registry.

**Q: Why channel-based subscriptions instead of sending everything?**
A: Bandwidth efficiency. A dashboard showing only the map doesn't need agent decisions or cost metrics. With channels, clients opt-in to what they need. This matters when 10+ agents are broadcasting decisions every few seconds — the map component only receives `disasters` events, not the full firehose.

**Q: How do you handle a client that disconnects without sending a close frame?**
A: The `broadcast()` method wraps `send_json()` in a try/except. If sending fails (broken pipe, connection reset), the client is added to a `disconnected` list and removed after the broadcast loop completes. This prevents stale connections from accumulating and causing errors on every broadcast.
