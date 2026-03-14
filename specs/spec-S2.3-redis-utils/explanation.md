# Explanation: S2.3 — Redis Streams + Cache Utilities

## Why This Spec Exists

Every agent in CRISIS-BENCH needs two things from Redis: (1) an **event bus** to publish/subscribe to disaster events and agent messages, and (2) a **TTL cache** for fast lookups. This spec provides both through a single `redis_utils.py` module, using the same Redis instance for both Streams and cache — no extra services needed.

Redis Streams was chosen over Redis Pub/Sub because Streams provide message persistence (messages survive subscriber downtime), consumer groups (multiple agents share work), and replay capability — all critical for a disaster response system where losing an alert because an agent restarted is unacceptable.

## What It Does

### Connection Management
- Singleton `redis.asyncio` client, lazily created from `CrisisSettings.redis_url`
- Same pattern as `db.py`: `create_redis()`, `close_redis()`, `get_redis()`
- Health check via `PING` returning `RedisHealthStatus` with version and latency

### Cache Operations
- `cache_get/set/delete` for string values with configurable TTL (default 5 min)
- `cache_get_json/set_json` for automatic JSON serialization/deserialization
- Used by agents and API endpoints for caching expensive computations

### Stream Publishing
- `stream_publish(stream, data)` — raw `XADD` for arbitrary dict data
- `stream_publish_event(stream, event_type, payload)` — standard envelope with `event_type`, `payload_json`, `timestamp`, and `trace_id` (auto-generated UUID4 if not provided)
- Standard envelope enables tracing, auditing, and replay across the entire system

### Consumer Groups
- `stream_create_group()` — idempotent (ignores `BUSYGROUP` error, safe to call on startup)
- `stream_read_group()` — blocking `XREADGROUP` with configurable count and block timeout
- `stream_ack()` — acknowledge processed messages for at-least-once delivery

### Simple Stream Operations
- `stream_read()` — non-group `XREAD` for simple consumers
- `stream_len()` / `stream_trim()` — stream management utilities

### Predefined Stream Names
8 constants matching the design document's stream topology:
- 5 data streams: `crisis:data:{imd,sachet,seismic,social,bhuvan}`
- 2 agent streams: `crisis:agent:{tasks,responses}`
- 1 eval stream: `crisis:eval:results`

## How It Works

The module follows the same singleton pattern as `db.py`:

```
get_redis() → creates client if None → returns redis.asyncio.Redis
```

All stream operations are thin async wrappers around `redis-py` commands (`XADD`, `XREADGROUP`, `XACK`, etc.), keeping the API surface small and predictable.

The event envelope (`stream_publish_event`) standardizes all messages:
```json
{
  "event_type": "cyclone_warning",
  "payload_json": "{\"name\": \"FANI\", \"category\": 4}",
  "timestamp": "2026-03-14T10:30:00+00:00",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## How It Connects

### Upstream (depends on)
- **S1.3 (config.py)** — `get_settings().redis_url` provides connection URL

### Downstream (used by)
- **S4.2/S4.3 (A2A server/client)** — A2A protocol over Redis Streams uses `stream_publish`, `stream_create_group`, `stream_read_group`, `stream_ack`
- **S3.2 (WebSocket)** — WebSocket server subscribes to agent streams for real-time dashboard updates
- **S7.1+ (All agents)** — Agents publish decisions and subscribe to events via these utilities
- **S2.5 (Telemetry)** — `trace_id` in event envelope connects to distributed tracing

### Key Design Choices
- **Single Redis instance** for both Streams and cache — simple deployment, no Kafka overhead for a single-machine system
- **`decode_responses=True`** — all values are strings; JSON serialization is explicit and controlled
- **Consumer group idempotency** — safe to call `stream_create_group()` on every startup without error handling
- **5-second default block** on `XREADGROUP` — balances CPU usage with responsiveness for disaster events
