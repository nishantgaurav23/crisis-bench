# Spec S1.4: Database Schema — Explanation

## Why This Spec Exists

Every module that persists data — from IMD weather ingestion (S6.4) to benchmark evaluation runs (S8.1) — needs a predefined schema. Without `init_db.sql`, downstream specs would each need to define their own tables ad hoc, leading to inconsistent naming, missing spatial indexes, and no foreign key integrity. This spec establishes the canonical data model for the entire system.

## What It Does

Creates `scripts/init_db.sql` — a single, idempotent SQL script that initializes the PostgreSQL/PostGIS database with:

- **PostGIS extension** for spatial geometry types and spatial queries
- **1 custom ENUM** (`india_disaster_type`) with 10 India-specific disaster categories
- **8 tables** across 4 domains:
  - **Administrative**: `states`, `districts` (Census 2011 boundaries with PostGIS geometries)
  - **Disaster tracking**: `disasters` (UUID-keyed, JSONB metadata, spatial polygons for affected areas)
  - **Time-series**: `imd_observations`, `cwc_river_levels` (partitioned by time range for efficient ingestion)
  - **Agent system**: `agent_decisions` (logs every LLM call with cost, tokens, latency)
  - **Benchmark**: `benchmark_scenarios`, `evaluation_runs` (stores 100-scenario benchmark with 5-metric scoring)
- **Spatial GiST indexes** on all geometry columns for fast `ST_Contains`, `ST_Distance`, `ST_Within` queries
- **BTREE indexes** on frequently queried columns (disaster type, timestamps, foreign keys)
- **Default partitions** for time-series tables so INSERTs work immediately

## How It Works

The script is designed to run via Docker's `docker-entrypoint-initdb.d/` mechanism or manually via `psql -f scripts/init_db.sql`. Key design decisions:

1. **Idempotent**: All statements use `IF NOT EXISTS` / `DO $$ ... EXCEPTION` blocks — safe to re-run
2. **SRID 4326**: All geometries use WGS84 (standard GPS coordinates) — compatible with Leaflet/OpenStreetMap tiles
3. **Table partitioning**: `imd_observations` and `cwc_river_levels` use `PARTITION BY RANGE (time)` — new year/month partitions can be added without schema changes, and PostgreSQL automatically routes INSERTs
4. **UUID primary keys**: `disasters`, `agent_decisions`, `benchmark_scenarios`, `evaluation_runs` use `gen_random_uuid()` — no coordination needed between distributed agents
5. **JSONB flexibility**: `metadata`, `decision_payload`, `initial_state`, `event_sequence`, etc. use JSONB for schema evolution without ALTER TABLE
6. **Array columns**: `affected_state_ids INT[]` and `affected_district_ids INT[]` avoid junction tables for simple membership queries

## How It Connects

```
S1.2 (Docker Compose) → PostgreSQL container is running
    ↓
S1.4 (this spec) → Schema exists in the database
    ↓
S2.2 (DB Connection) → asyncpg pool connects, runs queries against these tables
    ↓
S6.4 (IMD Ingestion) → Writes to imd_observations
S6.5 (Census Boundaries) → Writes to states, districts
S7.x (Agents) → Write to agent_decisions
S8.1 (Benchmark Models) → Maps Pydantic models to benchmark_scenarios, evaluation_runs
```

## Interview Talking Points

- **Why partitioning?** Time-series data grows unbounded. Partitioning lets PostgreSQL prune irrelevant partitions during queries (e.g., "show rainfall for March 2024" only scans the March partition, not 10 years of data). Also enables easy data lifecycle management — drop old partitions instead of DELETE.
- **Why GiST indexes?** R-tree spatial indexing makes "find all shelters within 5km" an O(log n) operation instead of O(n) full table scan with haversine distance computation.
- **Why UUIDs over SERIAL?** Multiple agents running concurrently can generate IDs independently without database round-trips. Also makes data migration/federation easier.
- **Why JSONB over separate columns?** Disaster metadata varies wildly by type — a cyclone has wind_speed/pressure/track, an earthquake has magnitude/depth/focal_mechanism. JSONB lets each type store its specific fields without 50 nullable columns.
