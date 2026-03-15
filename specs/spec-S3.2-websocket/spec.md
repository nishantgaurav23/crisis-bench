# Spec S3.2 — WebSocket Server

**Phase**: 3 (API + Dashboard MVP)
**Status**: spec-written
**Depends On**: S3.1 (FastAPI gateway), S2.3 (Redis utils)
**Location**: `src/api/websocket.py`

---

## 1. Purpose

Provide real-time bidirectional communication between the FastAPI backend and the Next.js dashboard. Agents publish events to Redis Streams; the WebSocket server bridges those events to connected dashboard clients. Clients can also send commands back (pause scenario, subscribe to specific disaster channels).

## 2. Requirements

### 2.1 WebSocket Endpoint
- Mount at `/ws` on the FastAPI app
- Accept optional query param `?channels=disasters,agents,metrics` to filter which event types a client receives (default: all)
- Support multiple concurrent clients
- Send JSON messages with standard envelope: `{"type": "<event_type>", "data": {...}, "timestamp": "<iso>", "trace_id": "<id>"}`

### 2.2 Connection Management
- `ConnectionManager` class tracking active WebSocket connections
- Each connection gets a unique `client_id` (UUID)
- Track per-client channel subscriptions
- Graceful disconnect handling (remove client on close/error)
- Connection count exposed for monitoring

### 2.3 Event Types (server → client)
| Event Type | Description | Channel |
|-----------|-------------|---------|
| `disaster.created` | New disaster registered | `disasters` |
| `disaster.updated` | Disaster phase/severity changed | `disasters` |
| `agent.status` | Agent status change (idle → active → done) | `agents` |
| `agent.decision` | Agent made a decision | `agents` |
| `metrics.update` | Token usage / cost update | `metrics` |

### 2.4 Client Commands (client → server)
| Command | Description |
|---------|-------------|
| `subscribe` | `{"command": "subscribe", "channels": ["disasters"]}` |
| `unsubscribe` | `{"command": "unsubscribe", "channels": ["agents"]}` |
| `ping` | `{"command": "ping"}` → server replies `{"type": "pong"}` |

### 2.5 Broadcasting
- `broadcast(event_type, data)` — send to all clients subscribed to the relevant channel
- `send_to_client(client_id, message)` — send to a specific client
- Messages are JSON serialized with timestamp and trace_id envelope

### 2.6 Integration Points
- FastAPI app mounts the WebSocket route via `create_app()` (modify `src/api/main.py`)
- Future specs (S7.x agents) will call `broadcast()` to push events
- Redis Streams bridge is a future concern (S7.9) — this spec provides the WebSocket layer only

## 3. Non-Requirements (Out of Scope)
- Redis Streams → WebSocket bridge (will be added in S7.9)
- Authentication/authorization on WebSocket (future)
- Message persistence / replay on reconnect (future)
- Rate limiting on WebSocket messages (future)

## 4. Technical Design

```python
# src/api/websocket.py

class ConnectionManager:
    """Manages active WebSocket connections and channel subscriptions."""

    def __init__(self):
        self._connections: dict[str, WebSocket] = {}  # client_id → ws
        self._subscriptions: dict[str, set[str]] = {}  # client_id → channels

    async def connect(self, websocket, channels=None) -> str: ...
    async def disconnect(self, client_id) -> None: ...
    async def broadcast(self, event_type, data, trace_id=None) -> None: ...
    async def send_to_client(self, client_id, message) -> None: ...
    def _get_channel(self, event_type) -> str: ...
    @property
    def active_count(self) -> int: ...

# Global manager instance
manager = ConnectionManager()

# WebSocket endpoint
async def websocket_endpoint(websocket: WebSocket, channels: str | None = None): ...
```

## 5. Files to Create/Modify
- **Create**: `src/api/websocket.py`
- **Modify**: `src/api/main.py` (add WebSocket route)
- **Create**: `tests/unit/test_websocket.py`

## 6. TDD Plan

### Red Phase — Tests to Write First
1. `test_connection_manager_connect` — connect returns client_id, increments count
2. `test_connection_manager_disconnect` — removes client, decrements count
3. `test_connection_manager_broadcast_to_subscribed` — only sends to subscribed clients
4. `test_connection_manager_broadcast_skips_unsubscribed` — doesn't send to non-matching channels
5. `test_connection_manager_send_to_client` — sends to specific client
6. `test_connection_manager_send_to_invalid_client` — handles missing client gracefully
7. `test_channel_mapping` — event types map to correct channels
8. `test_default_channels` — new connection subscribes to all channels by default
9. `test_custom_channels` — connection with specific channels only receives those
10. `test_websocket_endpoint_connect_disconnect` — full endpoint lifecycle via TestClient
11. `test_websocket_ping_pong` — client sends ping, gets pong
12. `test_websocket_subscribe_command` — client changes subscription
13. `test_websocket_unsubscribe_command` — client removes channel subscription
14. `test_websocket_broadcast_message_envelope` — broadcast message has type, data, timestamp, trace_id
15. `test_websocket_invalid_command` — unknown command returns error message
16. `test_app_has_websocket_route` — create_app includes /ws route

### Green Phase
- Implement `ConnectionManager` class
- Implement `websocket_endpoint` function
- Wire into `create_app()`

### Refactor Phase
- Run ruff, fix any style issues
- Ensure all tests pass
- Verify no secrets or paid dependencies

## 7. Acceptance Criteria
- [ ] `ConnectionManager` tracks connections with unique client_ids
- [ ] Channel-based subscription filtering works
- [ ] `broadcast()` sends only to subscribed clients
- [ ] Ping/pong heartbeat works
- [ ] Subscribe/unsubscribe commands work
- [ ] Message envelope includes type, data, timestamp, trace_id
- [ ] WebSocket route mounted at `/ws` in FastAPI app
- [ ] All tests pass, ruff clean, >80% coverage
