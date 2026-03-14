# Spec S2.3: Redis Streams + Cache Utilities

**Status**: spec-written
**Depends On**: S1.3 (Environment config)
**Location**: `src/shared/redis_utils.py`
**Phase**: 2 — Shared Infrastructure

---

## 1. Purpose

Provide async Redis Streams (event bus) and cache utilities for the entire CRISIS-BENCH system. Every agent publishes/subscribes to events via Redis Streams, and uses Redis as a TTL cache. This is the same Redis instance — no separate services needed.

Redis Streams was chosen over Pub/Sub because messages persist until acknowledged, consumer groups enable work sharing, and messages can be replayed — critical for disaster response where losing an alert is unacceptable.

## 2. Features

### 2.1 Connection Management

- **`create_redis()`** — Create a `redis.asyncio.Redis` client from `CrisisSettings.redis_url`
- **`close_redis()`** — Gracefully close the connection
- **`get_redis()`** — Return the singleton client (create if not exists)
- Connection uses `decode_responses=True` for string handling

### 2.2 Health Check

- **`check_health()`** — Execute `PING` to verify Redis connectivity
- Returns a `RedisHealthStatus` dataclass with: `connected: bool`, `latency_ms: float`, `version: str | None`

### 2.3 Cache Operations

- **`cache_get(key)`** — Get a cached value (returns `str | None`)
- **`cache_set(key, value, ttl_seconds=300)`** — Set a value with TTL (default 5 min)
- **`cache_delete(key)`** — Delete a cached key
- **`cache_get_json(key)`** — Get and deserialize JSON
- **`cache_set_json(key, data, ttl_seconds=300)`** — Serialize to JSON and set with TTL

### 2.4 Streams — Publishing

- **`stream_publish(stream, data)`** — Publish a dict to a Redis Stream via `XADD`
- **`stream_publish_event(stream, event_type, payload)`** — Publish with standard envelope: `{event_type, payload_json, timestamp, trace_id}`
- Auto-generates `trace_id` (UUID4) if not provided in payload

### 2.5 Streams — Consumer Groups

- **`stream_create_group(stream, group, start_id="0")`** — Create a consumer group via `XGROUP CREATE` (idempotent — ignores "already exists" error)
- **`stream_read_group(stream, group, consumer, count=10, block_ms=5000)`** — Read messages via `XREADGROUP` with blocking
- **`stream_ack(stream, group, *message_ids)`** — Acknowledge processed messages via `XACK`

### 2.6 Streams — Simple Read

- **`stream_read(stream, last_id="0-0", count=10)`** — Read messages from a stream via `XREAD` (no consumer group)
- **`stream_len(stream)`** — Get the number of messages in a stream via `XLEN`
- **`stream_trim(stream, maxlen)`** — Trim a stream to maxlen via `XTRIM`

### 2.7 Predefined Stream Names

Constants for all application streams (from design.md):

```python
STREAM_IMD = "crisis:data:imd"
STREAM_SACHET = "crisis:data:sachet"
STREAM_SEISMIC = "crisis:data:seismic"
STREAM_SOCIAL = "crisis:data:social"
STREAM_BHUVAN = "crisis:data:bhuvan"
STREAM_AGENT_TASKS = "crisis:agent:tasks"
STREAM_AGENT_RESPONSES = "crisis:agent:responses"
STREAM_EVAL = "crisis:eval:results"
```

## 3. Design Decisions

- **`redis.asyncio` (redis-py)** — Official async Redis client, well-maintained, supports Streams natively
- **Singleton connection pattern** — Same pattern as `db.py` (module-level global, lazy init)
- **`decode_responses=True`** — All values are strings; JSON serialization/deserialization is explicit
- **Consumer group idempotency** — `XGROUP CREATE` wrapped to ignore "BUSYGROUP" error (safe to call on startup)
- **Standard event envelope** — All stream messages include `event_type`, `payload_json`, `timestamp`, `trace_id` for audit and tracing
- **5-second block on XREADGROUP** — Balances responsiveness with CPU usage; configurable per call

## 4. Outcomes

- [ ] `create_redis()` creates a redis.asyncio client from settings
- [ ] `close_redis()` gracefully closes the connection
- [ ] `get_redis()` returns singleton client
- [ ] `check_health()` verifies Redis connectivity and returns version
- [ ] `cache_get/set/delete` work with string values and TTL
- [ ] `cache_get_json/set_json` handle JSON serialization
- [ ] `stream_publish()` adds messages to a stream
- [ ] `stream_publish_event()` adds standard envelope with trace_id
- [ ] `stream_create_group()` is idempotent
- [ ] `stream_read_group()` reads with consumer groups and blocking
- [ ] `stream_ack()` acknowledges messages
- [ ] `stream_read()` reads without consumer groups
- [ ] `stream_len()` returns message count
- [ ] `stream_trim()` trims stream to maxlen
- [ ] All stream constants are defined
- [ ] Tests pass without a real Redis (redis is mocked)
- [ ] ruff clean

## 5. TDD Notes

### Red Phase (write tests first)
- Test `create_redis()` creates client with correct URL
- Test `close_redis()` closes the client
- Test `get_redis()` returns singleton (same object on repeated calls)
- Test `check_health()` returns healthy when Redis responds
- Test `check_health()` returns unhealthy when Redis is down
- Test `cache_set()` calls `setex` with correct TTL
- Test `cache_get()` returns value when key exists
- Test `cache_get()` returns None when key missing
- Test `cache_delete()` calls `delete`
- Test `cache_set_json()` serializes dict to JSON string
- Test `cache_get_json()` deserializes JSON string to dict
- Test `stream_publish()` calls `xadd` with data
- Test `stream_publish_event()` includes event_type, payload_json, timestamp, trace_id
- Test `stream_create_group()` calls `xgroup_create`
- Test `stream_create_group()` ignores "BUSYGROUP" error
- Test `stream_read_group()` calls `xreadgroup` with correct params
- Test `stream_ack()` calls `xack` with message IDs
- Test `stream_read()` calls `xread`
- Test `stream_len()` calls `xlen`
- Test `stream_trim()` calls `xtrim`

### Green Phase
- Implement all functions in `src/shared/redis_utils.py`

### Refactor Phase
- Ensure ruff clean, add `__all__` exports, consistent patterns with db.py
