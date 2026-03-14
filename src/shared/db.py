"""Async PostgreSQL/PostGIS connection layer for CRISIS-BENCH.

Provides connection pooling via asyncpg, health checks, query helpers,
and spatial query utilities. All queries use parameterized arguments.
"""

import time
from dataclasses import dataclass

import asyncpg

from src.shared.config import get_settings

# Module-level singleton pool
_pool: asyncpg.Pool | None = None


@dataclass
class DBHealthStatus:
    """Result of a database health check."""

    connected: bool
    postgis_version: str | None
    latency_ms: float


# =============================================================================
# WKT Helpers
# =============================================================================


def point_to_wkt(lat: float, lon: float) -> str:
    """Convert latitude/longitude to WKT POINT string (lon lat order)."""
    return f"POINT({lon} {lat})"


def polygon_to_wkt(coordinates: list[tuple[float, float]]) -> str:
    """Convert list of (lat, lon) tuples to WKT POLYGON string.

    Automatically closes the polygon if not already closed.
    """
    if coordinates[0] != coordinates[-1]:
        coordinates = list(coordinates) + [coordinates[0]]
    points = ",".join(f"{lon} {lat}" for lat, lon in coordinates)
    return f"POLYGON(({points}))"


# =============================================================================
# Pool Management
# =============================================================================


async def create_pool() -> asyncpg.Pool:
    """Create an asyncpg connection pool from CrisisSettings."""
    global _pool
    settings = get_settings()
    dsn = (
        f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )
    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=2,
        max_size=10,
        command_timeout=60,
    )
    return _pool


async def close_pool() -> None:
    """Gracefully close the connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def get_pool() -> asyncpg.Pool:
    """Return the singleton pool, creating it if necessary."""
    global _pool
    if _pool is None:
        _pool = await create_pool()
    return _pool


# =============================================================================
# Health Check
# =============================================================================


async def check_health() -> DBHealthStatus:
    """Check PostgreSQL and PostGIS connectivity."""
    start = time.monotonic()
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
            postgis_version = await conn.fetchval("SELECT PostGIS_Version()")
        latency_ms = (time.monotonic() - start) * 1000
        return DBHealthStatus(
            connected=True,
            postgis_version=postgis_version,
            latency_ms=latency_ms,
        )
    except Exception:
        latency_ms = (time.monotonic() - start) * 1000
        return DBHealthStatus(
            connected=False,
            postgis_version=None,
            latency_ms=latency_ms,
        )


# =============================================================================
# Query Helpers
# =============================================================================


async def execute(query: str, *args) -> str:
    """Execute a query (INSERT/UPDATE/DELETE)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)


async def fetch_one(query: str, *args) -> asyncpg.Record | None:
    """Fetch a single row."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)


async def fetch_all(query: str, *args) -> list[asyncpg.Record]:
    """Fetch all rows."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)


async def fetch_val(query: str, *args):
    """Fetch a single value."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)


# =============================================================================
# Spatial Query Helpers
# =============================================================================


async def find_within_radius(
    table: str,
    location_col: str,
    lat: float,
    lon: float,
    radius_km: float,
) -> list[asyncpg.Record]:
    """Find rows within radius_km of a point using ST_DWithin with geography cast."""
    radius_m = radius_km * 1000.0
    query = (
        f"SELECT * FROM {table} "
        f"WHERE ST_DWithin({location_col}::geography, "
        f"ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography, $3)"
    )
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(query, lon, lat, radius_m)


async def find_in_polygon(
    table: str,
    location_col: str,
    polygon_wkt: str,
) -> list[asyncpg.Record]:
    """Find rows where location is within a polygon using ST_Contains."""
    query = f"SELECT * FROM {table} WHERE ST_Contains(ST_GeomFromText($1, 4326), {location_col})"
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(query, polygon_wkt)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "DBHealthStatus",
    "check_health",
    "close_pool",
    "create_pool",
    "execute",
    "fetch_all",
    "fetch_one",
    "fetch_val",
    "find_in_polygon",
    "find_within_radius",
    "get_pool",
    "point_to_wkt",
    "polygon_to_wkt",
]
