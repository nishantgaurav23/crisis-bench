"""Redis Streams + cache utilities for CRISIS-BENCH.

Provides async Redis Streams (event bus) and cache operations. All agents
publish/subscribe to events via Redis Streams, and use Redis as a TTL cache.
Single Redis instance handles both Streams and cache.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as redis_async

from src.shared.config import get_settings

# =============================================================================
# Stream Name Constants
# =============================================================================

STREAM_IMD = "crisis:data:imd"
STREAM_SACHET = "crisis:data:sachet"
STREAM_SEISMIC = "crisis:data:seismic"
STREAM_SOCIAL = "crisis:data:social"
STREAM_BHUVAN = "crisis:data:bhuvan"
STREAM_AGENT_TASKS = "crisis:agent:tasks"
STREAM_AGENT_RESPONSES = "crisis:agent:responses"
STREAM_EVAL = "crisis:eval:results"

# =============================================================================
# Connection Management
# =============================================================================

_redis: redis_async.Redis | None = None


async def create_redis() -> redis_async.Redis:
    """Create a redis.asyncio client from CrisisSettings."""
    global _redis
    settings = get_settings()
    _redis = redis_async.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    """Gracefully close the Redis connection."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def get_redis() -> redis_async.Redis:
    """Return the singleton Redis client, creating it if necessary."""
    global _redis
    if _redis is None:
        _redis = await create_redis()
    return _redis


# =============================================================================
# Health Check
# =============================================================================


@dataclass
class RedisHealthStatus:
    """Result of a Redis health check."""

    connected: bool
    latency_ms: float
    version: str | None


async def check_health() -> RedisHealthStatus:
    """Check Redis connectivity via PING."""
    start = time.monotonic()
    try:
        client = await get_redis()
        await client.ping()
        info = await client.info()
        latency_ms = (time.monotonic() - start) * 1000
        return RedisHealthStatus(
            connected=True,
            latency_ms=latency_ms,
            version=info.get("redis_version"),
        )
    except Exception:
        latency_ms = (time.monotonic() - start) * 1000
        return RedisHealthStatus(connected=False, latency_ms=latency_ms, version=None)


# =============================================================================
# Cache Operations
# =============================================================================


async def cache_get(key: str) -> str | None:
    """Get a cached string value."""
    client = await get_redis()
    return await client.get(key)


async def cache_set(key: str, value: str, ttl_seconds: int = 300) -> None:
    """Set a string value with TTL (default 5 minutes)."""
    client = await get_redis()
    await client.setex(key, ttl_seconds, value)


async def cache_delete(key: str) -> None:
    """Delete a cached key."""
    client = await get_redis()
    await client.delete(key)


async def cache_get_json(key: str) -> dict[str, Any] | None:
    """Get and deserialize a JSON-cached value."""
    raw = await cache_get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def cache_set_json(key: str, data: dict[str, Any], ttl_seconds: int = 300) -> None:
    """Serialize to JSON and cache with TTL."""
    await cache_set(key, json.dumps(data), ttl_seconds=ttl_seconds)


# =============================================================================
# Stream Publishing
# =============================================================================


async def stream_publish(stream: str, data: dict[str, str]) -> str:
    """Publish a dict to a Redis Stream via XADD. Returns the message ID."""
    client = await get_redis()
    return await client.xadd(stream, data)


async def stream_publish_event(
    stream: str,
    event_type: str,
    payload: dict[str, Any],
    *,
    trace_id: str | None = None,
) -> str:
    """Publish with standard envelope: event_type, payload_json, timestamp, trace_id."""
    message = {
        "event_type": event_type,
        "payload_json": json.dumps(payload),
        "timestamp": datetime.now(UTC).isoformat(),
        "trace_id": trace_id or str(uuid.uuid4()),
    }
    return await stream_publish(stream, message)


# =============================================================================
# Consumer Groups
# =============================================================================


async def stream_create_group(stream: str, group: str, start_id: str = "0") -> None:
    """Create a consumer group (idempotent — ignores BUSYGROUP error)."""
    client = await get_redis()
    try:
        await client.xgroup_create(stream, group, id=start_id, mkstream=True)
    except Exception as e:
        if "BUSYGROUP" in str(e):
            return
        raise


async def stream_read_group(
    stream: str,
    group: str,
    consumer: str,
    count: int = 10,
    block_ms: int = 5000,
) -> list[Any]:
    """Read messages via XREADGROUP with blocking."""
    client = await get_redis()
    return await client.xreadgroup(
        group,
        consumer,
        {stream: ">"},
        count=count,
        block=block_ms,
    )


async def stream_ack(stream: str, group: str, *message_ids: str) -> int:
    """Acknowledge processed messages via XACK."""
    client = await get_redis()
    return await client.xack(stream, group, *message_ids)


# =============================================================================
# Simple Stream Operations
# =============================================================================


async def stream_read(stream: str, last_id: str = "0-0", count: int = 10) -> list[Any]:
    """Read messages from a stream via XREAD (no consumer group)."""
    client = await get_redis()
    return await client.xread({stream: last_id}, count=count)


async def stream_len(stream: str) -> int:
    """Get the number of messages in a stream."""
    client = await get_redis()
    return await client.xlen(stream)


async def stream_trim(stream: str, maxlen: int) -> int:
    """Trim a stream to maxlen entries."""
    client = await get_redis()
    return await client.xtrim(stream, maxlen=maxlen)


__all__ = [
    "STREAM_AGENT_RESPONSES",
    "STREAM_AGENT_TASKS",
    "STREAM_BHUVAN",
    "STREAM_EVAL",
    "STREAM_IMD",
    "STREAM_SACHET",
    "STREAM_SEISMIC",
    "STREAM_SOCIAL",
    "RedisHealthStatus",
    "cache_delete",
    "cache_get",
    "cache_get_json",
    "cache_set",
    "cache_set_json",
    "check_health",
    "close_redis",
    "create_redis",
    "get_redis",
    "stream_ack",
    "stream_create_group",
    "stream_len",
    "stream_publish",
    "stream_publish_event",
    "stream_read",
    "stream_read_group",
    "stream_trim",
]
