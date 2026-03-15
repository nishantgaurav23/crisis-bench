# Explanation: S4.3 — A2A Client (Redis Streams Subscriber)

## Why This Spec Exists

The A2A server (S4.2) handles **publishing** messages to Redis Streams. But agents also need to **receive** messages — listen for incoming tasks, discovery requests, and cancellations. Without a standardized client, each of the 7 agents would duplicate consumer group management, message parsing, deduplication, filtering, and acknowledgment logic. The A2A client centralizes all of this into a single reusable class.

Together, S4.1 (schemas) + S4.2 (server/publisher) + S4.3 (client/subscriber) form the complete A2A communication layer that every agent in Phase 7 will use.

## What It Does

`A2AClient` provides each agent with:

1. **Consumer group lifecycle** — `start()` creates a Redis Streams consumer group for the agent; `stop()` signals graceful shutdown
2. **Callback-based message dispatch** — agents register async handlers per `A2AMessageType` via `on_message()`, and the client routes incoming messages to the right handler
3. **Message filtering** — only processes messages addressed to this specific agent or broadcasts (`target_agent=None`)
4. **Deduplication** — tracks processed message IDs in a Redis set with 1-hour TTL to prevent reprocessing on agent restart
5. **Send methods** — `send_result()`, `send_update()`, `send_agent_card()`, `request_discovery()`, `cancel_task()` create properly-typed A2AMessage envelopes and publish them
6. **Error resilience** — catches `A2AError` in callbacks without crashing the listen loop

## How It Works

### Listen Loop (`listen()`)

```
while not shutdown:
    messages = stream_read_group(task_stream, agent_id, consumer_name)
    for each message:
        1. Deserialize via A2AMessage.from_redis_dict()
        2. Filter: skip if target_agent != self.agent_id and not broadcast
        3. Dedup: skip if message ID already in Redis set
        4. Dispatch: call registered callback for message_type
        5. Acknowledge: stream_ack() to Redis
        6. Mark processed: add to dedup set
```

### Deduplication

- Redis SET key: `a2a:dedup:{agent_id}`
- Check: `SISMEMBER` before processing
- Mark: `SADD` after processing
- TTL: 3600 seconds (1 hour), refreshed on each write

### Send Methods

All follow the same pattern:
1. Create `A2AMessage` envelope with appropriate `message_type`
2. Serialize payload via `model_dump_json()` or dict construction
3. Publish via `stream_publish()` to task or response stream
4. Return Redis stream message ID

## How It Connects

| Dependency | What It Provides |
|-----------|-----------------|
| **S4.1** (A2A schemas) | `A2AMessage`, `A2AMessageType`, `A2ATaskResult`, `A2AAgentCard` — all message types |
| **S2.3** (Redis utils) | `stream_create_group`, `stream_read_group`, `stream_ack`, `stream_publish`, `get_redis` |
| **S2.4** (Error handling) | `A2AError` for typed error handling in callbacks |
| **S2.1** (Domain models) | `AgentType`, `TaskStatus` enums |

| Dependent | How It Uses This |
|----------|-----------------|
| **S7.1** (Base agent) | Every agent will embed an `A2AClient` to listen for tasks and send results |
| **S7.2-S7.8** (All agents) | Inherit A2A communication from base agent via this client |

## Key Design Decisions

1. **Consumer group per agent** — ensures messages are delivered to the intended agent and supports future horizontal scaling (multiple instances of same agent type share a consumer group)
2. **Callback pattern over inheritance** — agents register handlers via `on_message()` rather than subclassing, making the client composable and testable
3. **Dedup via Redis SET** — survives agent restarts (unlike in-memory sets) with automatic TTL cleanup
4. **`asyncio.sleep(0)` on empty reads** — yields control to the event loop when no messages are available, preventing CPU busy-loops in the listen loop

## Interview Talking Points

**Q: Why callback-based dispatch instead of a single `handle_message()` method?**
A: The callback pattern (similar to Express.js route handlers or event emitters) lets each agent register only the message types it cares about. The SituationSense agent registers for `TASK_SEND` and `AGENT_DISCOVER`; it doesn't need to handle `TASK_CANCEL`. This is the Observer pattern — the client is the subject, callbacks are observers. It's more flexible than a switch statement and easier to test (mock individual callbacks).

**Q: Why dedup in Redis instead of in-memory?**
A: If an agent crashes and restarts, an in-memory dedup set is lost — the agent would reprocess all pending messages in the consumer group. Redis SET persists across restarts. The 1-hour TTL bounds memory usage while covering the window where duplicate delivery is likely (Redis Streams guarantee at-least-once, not exactly-once).

**Q: How does this relate to the A2A server?**
A: The server (S4.2) is the **publisher** — it creates and sends messages. The client (S4.3) is the **subscriber** — it receives, filters, and dispatches messages. Together they form a complete pub/sub layer over Redis Streams. The server is typically used by the Orchestrator to assign tasks; the client is used by all agents to receive and respond.
