# Spec S4.3: A2A Client (Redis Streams Subscriber)

**Phase**: 4 — Communication Protocols
**Status**: spec-written
**Depends On**: S4.1 (A2A schemas), S2.3 (Redis utils)
**Location**: `src/protocols/a2a/client.py`
**Feature**: A2A client for subscribing to tasks, sending responses, and acknowledging messages via Redis Streams

---

## 1. Overview

Implement an async A2A client that allows agents to receive tasks, send results, discover other agents, and manage message acknowledgment over Redis Streams consumer groups. This is the subscriber/consumer side of A2A communication.

### Why This Spec Exists

Each agent needs to **listen** for incoming A2A messages (tasks, cancellations, discovery requests) and **respond** with results, status updates, or agent cards. Without a standardized client, each agent would implement its own Redis Streams consumer logic — duplicating stream creation, consumer group management, message parsing, acknowledgment, and deduplication. The A2A client centralizes this, giving every agent a consistent interface.

### Key Design Decisions

1. **Consumer group per agent**: Each agent gets its own Redis Streams consumer group on `crisis:agent:tasks`. This ensures messages are delivered to the intended agent and supports multiple instances of the same agent type (load balancing via consumer groups).
2. **Message filtering**: The client filters incoming messages by `target_agent` — agents only process messages addressed to them or broadcasts (`target_agent=None`).
3. **Message deduplication**: Track processed message IDs in a Redis set with TTL to prevent reprocessing on restart.
4. **Callback-based message handling**: Register async callbacks for each `A2AMessageType` — the client dispatches messages to the appropriate handler.
5. **Graceful shutdown**: Support cancellation of the listen loop via `asyncio.Event`.
6. **Uses S4.1 schemas**: All messages are `A2AMessage` instances, deserialized via `from_redis_dict()`.
7. **Uses S2.3 Redis utils**: Built on `stream_create_group`, `stream_read_group`, `stream_ack`, `stream_publish`.

---

## 2. Classes to Implement

### 2.1 A2AClient

```python
class A2AClient:
    """A2A protocol client for receiving and sending messages over Redis Streams."""

    def __init__(
        self,
        agent_id: str,
        agent_type: AgentType,
        task_stream: str = STREAM_AGENT_TASKS,
        response_stream: str = STREAM_AGENT_RESPONSES,
    ):
        ...

    async def start(self) -> None:
        """Initialize consumer group and dedup set."""

    async def stop(self) -> None:
        """Signal graceful shutdown."""

    def on_message(
        self, message_type: A2AMessageType, callback: MessageCallback
    ) -> None:
        """Register an async callback for a message type."""

    async def listen(self, poll_interval_ms: int = 1000, batch_size: int = 10) -> None:
        """Main listen loop — reads from consumer group, dispatches to callbacks."""

    async def send_result(self, result: A2ATaskResult) -> str:
        """Publish a task result to the response stream."""

    async def send_update(self, task_id: uuid.UUID, status: TaskStatus, payload: dict) -> str:
        """Publish a task status update."""

    async def send_agent_card(self, card: A2AAgentCard) -> str:
        """Publish agent card in response to discovery."""

    async def request_discovery(self) -> str:
        """Broadcast an AGENT_DISCOVER message."""

    async def cancel_task(self, task_id: uuid.UUID, target_agent: str) -> str:
        """Send a TASK_CANCEL message."""

    async def _is_duplicate(self, message_id: str) -> bool:
        """Check if message was already processed (Redis set with TTL)."""

    async def _mark_processed(self, message_id: str) -> None:
        """Add message ID to dedup set with TTL."""
```

### 2.2 Type Aliases

```python
MessageCallback = Callable[[A2AMessage], Awaitable[None]]
```

---

## 3. Behavior Details

### 3.1 Listen Loop

1. Call `stream_read_group()` with the agent's consumer group
2. For each message:
   a. Deserialize via `A2AMessage.from_redis_dict()`
   b. Check `target_agent` — skip if not addressed to this agent and not a broadcast
   c. Check deduplication — skip if already processed
   d. Dispatch to registered callback for `message_type`
   e. Acknowledge via `stream_ack()`
   f. Mark as processed in dedup set
3. If no callback is registered for a message type, acknowledge but log a warning
4. On `A2AError`, log and continue (don't crash the listen loop)
5. Exit when `_shutdown` event is set

### 3.2 Deduplication

- Redis SET key: `a2a:dedup:{agent_id}`
- Each processed message's `id` is added with `SADD`
- TTL on the set: 3600 seconds (1 hour)
- Check with `SISMEMBER` before processing

### 3.3 Sending Messages

All send methods:
1. Create an `A2AMessage` envelope
2. Serialize via `to_redis_dict()`
3. Publish via `stream_publish()` to the appropriate stream
4. Return the Redis stream message ID

---

## 4. TDD Notes

### Test File: `tests/unit/test_a2a_client.py`

All tests mock Redis — no real Redis connection needed.

#### Red Phase Tests (write first, all must fail):

1. **test_client_creation** — create with agent_id and agent_type, verify attributes
2. **test_client_start_creates_consumer_group** — `start()` calls `stream_create_group`
3. **test_register_callback** — `on_message()` stores callback for message type
4. **test_send_result** — publishes A2AMessage with TASK_RESULT type to response stream
5. **test_send_update** — publishes TASK_UPDATE with status and payload
6. **test_send_agent_card** — publishes AGENT_CARD message
7. **test_request_discovery** — publishes AGENT_DISCOVER broadcast (target_agent=None)
8. **test_cancel_task** — publishes TASK_CANCEL to target agent
9. **test_listen_dispatches_to_callback** — listen reads message, calls registered callback
10. **test_listen_filters_by_target_agent** — skips messages not addressed to this agent
11. **test_listen_accepts_broadcasts** — processes messages with target_agent=None
12. **test_listen_acknowledges_messages** — calls stream_ack after processing
13. **test_listen_deduplicates** — skips already-processed messages
14. **test_listen_handles_no_callback** — acknowledges but doesn't crash when no callback registered
15. **test_listen_continues_on_error** — catches A2AError in callback, keeps listening
16. **test_stop_signals_shutdown** — stop() sets shutdown event, listen exits
17. **test_send_result_message_format** — verify the A2AMessage envelope fields
18. **test_client_custom_streams** — custom task_stream and response_stream
19. **test_exports** — all public names in `__all__`

#### Green Phase:
- Implement minimum code to pass each test
- Use `unittest.mock.AsyncMock` for Redis operations

#### Refactor Phase:
- Run `ruff check --fix`
- Verify exports in `__all__`

---

## 5. Outcomes

- [ ] A2AClient class with full async lifecycle (start/listen/stop)
- [ ] Callback-based message dispatching for all A2AMessageType values
- [ ] Message filtering by target_agent (addressed + broadcasts)
- [ ] Message deduplication via Redis set
- [ ] Send methods for results, updates, agent cards, discovery, cancellation
- [ ] Graceful shutdown via asyncio.Event
- [ ] All 19 tests pass
- [ ] ruff clean
- [ ] No external API dependencies
- [ ] Uses S4.1 schemas (A2AMessage, A2ATask, A2ATaskResult, A2AAgentCard)
- [ ] Uses S2.3 Redis utils (stream_create_group, stream_read_group, stream_ack, stream_publish)
