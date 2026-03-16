# Spec S2.2: Async PostgreSQL/PostGIS Connection

**Status**: done
**Depends On**: S1.3 (Environment config), S1.4 (Database schema)
**Location**: `src/shared/db.py`
**Phase**: 2 — Shared Infrastructure

---

## 1. Purpose

Provide an async PostgreSQL/PostGIS connection layer using `asyncpg`. This module is used by every component that reads/writes from the database: agents, API endpoints, benchmark engine, and data ingestion pipelines. It must handle connection pooling, health checks, and spatial query helpers.

## 2. Features

### 2.1 Connection Pool Management

- **`create_pool()`** — Create an `asyncpg` connection pool using settings from `CrisisSettings`
- **`close_pool()`** — Gracefully close the pool
- **`get_pool()`** — Return the singleton pool (create if not exists)
- Pool config: `min_size=2`, `max_size=10`, `command_timeout=60`

### 2.2 Health Check

- **`check_health()`** — Execute `SELECT 1` and `SELECT PostGIS_Version()` to verify both PostgreSQL and PostGIS are operational
- Returns a `DBHealthStatus` dataclass with: `connected: bool`, `postgis_version: str | None`, `latency_ms: float`

### 2.3 Spatial Query Helpers

- **`point_to_wkt(lat, lon)`** — Convert lat/lon to WKT POINT string for PostGIS
- **`polygon_to_wkt(coordinates)`** — Convert list of (lat, lon) to WKT POLYGON string
- **`find_within_radius(table, location_col, lat, lon, radius_km)`** — Generic "find rows within N km" spatial query using `ST_DWithin` with geography cast
- **`find_in_polygon(table, location_col, polygon_wkt)`** — Find rows where location is within a polygon using `ST_Contains`

### 2.4 Query Execution Helpers

- **`execute(query, *args)`** — Execute a query (INSERT/UPDATE/DELETE)
- **`fetch_one(query, *args)`** — Fetch a single row
- **`fetch_all(query, *args)`** — Fetch all rows
- **`fetch_val(query, *args)`** — Fetch a single value

All helpers acquire a connection from the pool, execute, and release.

### 2.5 PostGIS Type Registration

- Register custom codecs for PostGIS geometry types on pool `init` callback
- Handle WKB ↔ Python conversion (using `shapely` for geometry parsing if needed, but keep it optional)

## 3. Design Decisions

- **asyncpg directly, no SQLAlchemy** — 3-5x faster, speaks PostgreSQL binary protocol, no ORM overhead needed
- **Singleton pool pattern** — One pool per process, created lazily, closed on shutdown
- **Parameterized queries only** — All queries use `$1, $2` parameters, never string formatting (SQL injection prevention)
- **Geography cast for distance queries** — `ST_DWithin(geog::geography, ...)` uses meters, handles Earth curvature correctly
- **No shapely hard dependency** — WKT helpers are pure string operations; shapely is only used if installed (for WKB decoding)

## 4. Outcomes

- [ ] `create_pool()` creates an asyncpg pool from CrisisSettings
- [ ] `close_pool()` gracefully shuts down the pool
- [ ] `get_pool()` returns singleton pool
- [ ] `check_health()` verifies PostgreSQL + PostGIS connectivity
- [ ] `execute()`, `fetch_one()`, `fetch_all()`, `fetch_val()` work correctly
- [ ] `point_to_wkt()` and `polygon_to_wkt()` produce valid WKT strings
- [ ] `find_within_radius()` generates correct spatial SQL
- [ ] `find_in_polygon()` generates correct spatial SQL
- [ ] All queries use parameterized arguments (no SQL injection)
- [ ] Tests pass without a real database (asyncpg is mocked)
- [ ] ruff clean

## 5. TDD Notes

### Red Phase (write tests first)
- Test `point_to_wkt()` with valid coordinates
- Test `polygon_to_wkt()` with valid polygon
- Test `create_pool()` calls `asyncpg.create_pool` with correct DSN
- Test `close_pool()` closes the pool
- Test `get_pool()` returns singleton (same object on repeated calls)
- Test `check_health()` returns healthy status when DB responds
- Test `check_health()` returns unhealthy when DB is down
- Test `execute()` acquires connection and runs query
- Test `fetch_one()`, `fetch_all()`, `fetch_val()` return correct results
- Test `find_within_radius()` generates correct SQL with ST_DWithin
- Test `find_in_polygon()` generates correct SQL with ST_Contains
- Test parameterized queries (no string interpolation of user values)

### Green Phase
- Implement all functions in `src/shared/db.py`

### Refactor Phase
- Ensure ruff clean, add `__all__` exports, consistent error handling
