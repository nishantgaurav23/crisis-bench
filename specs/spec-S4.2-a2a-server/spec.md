# Spec S4.2: A2A Server (Redis Streams Publisher)

**Status**: spec-written
**Depends On**: S4.1 (A2A schemas), S2.3 (Redis utils)
**Location**: `src/protocols/a2a/server.py`
**Phase**: 4 — Communication Protocols

---

## Overview

The A2A server is the **publisher side** of agent-to-agent communication over Redis Streams. It provides a high-level async API for agents to:

1. **Send tasks** — publish `A2ATask` to target agents via `crisis:agent:tasks`
2. **Send results** — publish `A2ATaskResult` back to requesting agents via `crisis:agent:responses`
3. **Broadcast updates** — publish `TASK_UPDATE` messages to all listeners
4. **Discover agents** — broadcast `AGENT_DISCOVER` requests
5. **Register agent cards** — publish `AGENT_CARD` responses with capabilities
6. **Cancel tasks** — publish `TASK_CANCEL` messages
7. **Manage consumer groups** — create/ensure groups for agents on startup

The server wraps `redis_utils.stream_publish()` and `stream_create_group()` with A2A-specific logic, using `A2AMessage.to_redis_dict()` for serialization.

---

## Key Design Decisions

- **Two streams**: `crisis:agent:tasks` for outbound tasks, `crisis:agent:responses` for results/updates
- **Message deduplication**: Track published message IDs to prevent re-publishing
- **Structured logging**: All publishes logged via structlog with trace_id
- **Graceful error handling**: Redis failures raise `A2AError` (from S2.4)
- **Stream trimming**: Configurable max stream length (default 10,000) to prevent unbounded growth
- **Consumer group auto-creation**: `ensure_groups()` creates groups for all known agent types

---

## Public API

```python
class A2AServer:
    def __init__(self, agent_id: str, max_stream_len: int = 10_000) -> None: ...
    async def send_task(self, task: A2ATask) -> str: ...
    async def send_result(self, result: A2ATaskResult) -> str: ...
    async def broadcast_update(self, task_id: UUID, source_agent: str, payload: dict) -> str: ...
    async def cancel_task(self, task_id: UUID, source_agent: str, target_agent: str) -> str: ...
    async def discover_agents(self, source_agent: str) -> str: ...
    async def register_agent_card(self, card: A2AAgentCard) -> str: ...
    async def ensure_groups(self, agent_ids: list[str]) -> None: ...
    async def get_stream_info(self) -> dict[str, int]: ...
```

---

## Outcomes

1. All 6 A2AMessageType operations supported (TASK_SEND, TASK_UPDATE, TASK_RESULT, TASK_CANCEL, AGENT_DISCOVER, AGENT_CARD)
2. Messages serialized via `A2AMessage.to_redis_dict()` and published to correct streams
3. Consumer groups created idempotently for any list of agent IDs
4. Redis failures wrapped in `A2AError` with trace_id
5. Stream trimming prevents unbounded growth
6. All methods are async
7. Structured logging on every publish

---

## TDD Notes

### Test Strategy
- Mock `redis_utils` functions (no real Redis in unit tests)
- Verify correct stream names, message serialization, group creation
- Test error handling (Redis down → A2AError)
- Test deduplication of identical messages
- Test stream info reporting

### Test File
`tests/unit/test_a2a_server.py`
