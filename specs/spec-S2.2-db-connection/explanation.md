# Spec S2.2: Explanation — Async PostgreSQL/PostGIS Connection

## Why This Spec Exists

Every component in CRISIS-BENCH that stores or queries persistent data needs a database connection: agents writing decisions, the benchmark engine storing scenarios, the API serving queries, and data ingestion pipelines loading census/IMD data. This spec provides the shared async database layer that all of them depend on.

Without this, every module would independently manage connection pools, construct DSN strings, and handle spatial queries — leading to duplicated code, connection leaks, and inconsistent error handling.

## What It Does

`src/shared/db.py` provides:

1. **Connection Pool Management** — A singleton `asyncpg.Pool` (2-10 connections, 60s timeout) created from `CrisisSettings`. One pool per process, created lazily, cleaned up on shutdown.

2. **Query Helpers** — `execute()`, `fetch_one()`, `fetch_all()`, `fetch_val()` — thin wrappers that acquire a connection, run a parameterized query, and release. All use `$1, $2` placeholders (never string interpolation) to prevent SQL injection.

3. **Spatial Query Helpers** — `find_within_radius()` uses `ST_DWithin` with `::geography` cast for Earth-curvature-correct distance queries in meters. `find_in_polygon()` uses `ST_Contains` for point-in-polygon tests.

4. **WKT Helpers** — `point_to_wkt()` and `polygon_to_wkt()` convert Python coordinates to Well-Known Text format for PostGIS. WKT uses longitude-first order (`POINT(lon lat)`).

5. **Health Check** — `check_health()` tests both PostgreSQL (`SELECT 1`) and PostGIS (`SELECT PostGIS_Version()`) and returns a `DBHealthStatus` with connection state, PostGIS version, and latency.

## How It Works

### Key Design Decisions

- **asyncpg, not SQLAlchemy** — asyncpg speaks PostgreSQL's binary protocol directly, giving 3-5x better performance than SQLAlchemy's async mode. For a real-time disaster system, every millisecond counts. We use raw SQL with parameterized queries — no ORM needed.

- **Geography cast for distances** — `ST_DWithin(col::geography, point::geography, meters)` uses geodesic distance on the WGS84 spheroid. Without `::geography`, PostGIS would compute Cartesian distance in degrees, which is meaningless for "find shelters within 5km."

- **Singleton pool** — One pool per process avoids connection exhaustion. `get_pool()` creates it lazily on first call, so the module can be imported without triggering a connection attempt (important for tests).

## How It Connects

### Upstream Dependencies
- **S1.3 (config.py)** — Reads `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` from `CrisisSettings`
- **S1.4 (init_db.sql)** — The schema this module queries against (states, districts, disasters, etc.)

### Downstream Dependents
- **S6.4 (IMD historical data)** — Uses `execute()` / `fetch_all()` to store/query gridded rainfall data
- **S6.5 (Census + admin boundaries)** — Uses spatial helpers to load/query state/district geometries
- **S8.1 (Benchmark scenario models)** — CRUD operations for benchmark scenarios and evaluation runs
- **S3.1 (API gateway)** — Health check endpoint calls `check_health()`
- **Any module** that needs PostgreSQL access imports from `src.shared.db`

## Interview Q&A

**Q: Why asyncpg instead of SQLAlchemy?**
A: asyncpg speaks PostgreSQL's binary protocol directly — no ORM layer, no SQL compilation step. It's 3-5x faster for raw queries. We don't need an ORM because our queries are straightforward SQL with PostGIS functions. Trade-off: no migrations, no relationship loading — but we handle schema with `init_db.sql` and relationships with explicit JOINs.

**Q: What's the difference between `ST_DWithin` on geometry vs geography?**
A: `geometry` operates in the coordinate system's units (degrees for WGS84). `ST_DWithin(geom, point, 0.05)` means "within 0.05 degrees" — which is ~5.5km at the equator but ~4km at Delhi's latitude. `geography` uses meters on the actual Earth spheroid: `ST_DWithin(geog::geography, point::geography, 5000)` means "within 5000 meters" everywhere. For a disaster response system operating across India (8°N to 37°N latitude), geography is essential for correct distance queries.

**Q: Why a singleton pool pattern instead of creating connections per request?**
A: Creating a PostgreSQL connection takes 50-100ms (TCP handshake + auth + SSL). A pool maintains pre-established connections, so acquiring one takes <1ms. With 7 agents + API + benchmark potentially running concurrently, connection pooling prevents exhausting PostgreSQL's `max_connections` (default 100). The singleton ensures all modules share the same pool.
