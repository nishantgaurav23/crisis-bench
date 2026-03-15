# Spec S4.2: A2A Server — Explanation

## Why This Exists

Agents need a standardized way to send tasks, results, and discovery messages to each other. The A2A server is the **publish side** of the agent communication bus. Without it, each agent would need to manually construct Redis messages, serialize schemas, handle errors, and manage stream trimming — duplicated logic across 7+ agents.

## What It Does

`A2AServer` provides a high-level async API for publishing all 6 A2A message types:

| Method | Message Type | Stream | Purpose |
|--------|-------------|--------|---------|
| `send_task()` | TASK_SEND | tasks | Delegate work to another agent |
| `send_result()` | TASK_RESULT | responses | Return completed work |
| `broadcast_update()` | TASK_UPDATE | tasks | Progress updates (no specific target) |
| `cancel_task()` | TASK_CANCEL | tasks | Cancel a running task |
| `discover_agents()` | AGENT_DISCOVER | tasks | Find available agents |
| `register_agent_card()` | AGENT_CARD | responses | Advertise capabilities |

Additionally:
- `ensure_groups()` — creates Redis consumer groups for agents on both streams
- `get_stream_info()` — returns current stream lengths for monitoring

## How It Works

1. Each method constructs an `A2AMessage` envelope (from S4.1) with the appropriate `A2AMessageType`
2. The message is serialized via `A2AMessage.to_redis_dict()` (flat string dict for Redis)
3. Published to the correct stream (`crisis:agent:tasks` or `crisis:agent:responses`) via `redis_utils.stream_publish()`
4. After publishing, checks stream length and trims to `max_stream_len` if needed
5. All Redis errors are caught and wrapped in `A2AError` with trace context
6. Every publish is logged via structlog with trace_id, stream, and message type

## How It Connects

- **Depends on S4.1** (A2A schemas) — uses `A2AMessage`, `A2ATask`, `A2ATaskResult`, `A2AAgentCard` for typed messages
- **Depends on S2.3** (Redis utils) — uses `stream_publish`, `stream_create_group`, `stream_len`, `stream_trim`
- **Uses S2.4** (errors) — wraps Redis failures in `A2AError`
- **Uses S2.5** (telemetry) — structured logging via `get_logger`
- **Used by S4.3** (A2A client) — the client reads what the server publishes
- **Used by S7.1+** (all agents) — every agent uses `A2AServer` to send tasks and results

## Interview Q&A

**Q: Why separate the server (publisher) from the client (subscriber)?**
A: Single Responsibility Principle. Publishing and consuming have different concerns: the server handles serialization, stream selection, and trimming; the client handles consumer groups, message filtering, and acknowledgment. An agent may only need to publish (e.g., the orchestrator sending tasks) or only consume (e.g., a worker waiting for tasks). Separating them also makes testing cleaner — you can mock publishes without setting up consumer groups.

**Q: Why trim streams instead of using TTL?**
A: Redis Streams don't support per-message TTL. The options are: (1) `XTRIM` to cap at N messages (what we do), or (2) `MINID` to remove messages older than a timestamp. We chose XTRIM with `maxlen` because it's simpler and predictable — we always keep the last 10,000 messages regardless of time. In a disaster scenario, message rate varies wildly (quiet periods vs. cyclone landfall), so time-based trimming would either waste memory during quiet times or lose messages during spikes.

**Q: Why does `ensure_groups()` create groups on both streams for each agent?**
A: Any agent might need to read from either stream. The orchestrator reads responses (to collect results) but also reads tasks (to handle escalations). Worker agents read tasks (to receive assignments) but also read responses (to see peer results for coordination). Creating groups on both streams upfront avoids race conditions where an agent tries to read before its group exists.
