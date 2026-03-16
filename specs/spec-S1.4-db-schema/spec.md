# Spec S1.4: PostgreSQL/PostGIS Database Schema

**Status**: done
**Phase**: 1 — Project Bootstrap
**Depends On**: S1.2 (Docker Compose) ✅ done
**Location**: `scripts/init_db.sql`

---

## 1. Overview

Create the PostgreSQL/PostGIS database schema for CRISIS-BENCH. This SQL init script defines all tables for Indian administrative boundaries, disaster tracking, time-series observations (IMD weather, CWC river levels), agent decision logging, and benchmark system storage.

### Why This Matters

- **Interview**: Demonstrates understanding of PostGIS spatial types, table partitioning, JSONB for flexible schemas, UUID primary keys, and spatial indexing (GiST) — all production-grade PostgreSQL patterns.
- **Project**: Every data-writing module (S2.2 DB connection, S6.4 IMD ingestion, S6.5 Census boundaries, S8.1 benchmark models) depends on these tables existing.

---

## 2. Schema Design

### 2.1 Extensions
- `postgis` — spatial types and functions
- `uuid-ossp` — UUID generation (fallback for older PG)

### 2.2 Custom Types
- `india_disaster_type` ENUM: `monsoon_flood`, `cyclone`, `urban_waterlogging`, `earthquake`, `heatwave`, `landslide`, `industrial_accident`, `tsunami`, `drought`, `glacial_lake_outburst`

### 2.3 Tables

#### Administrative Boundaries

**states**
| Column | Type | Constraints |
|--------|------|-------------|
| id | SERIAL | PRIMARY KEY |
| name | VARCHAR(100) | NOT NULL, UNIQUE |
| name_local | VARCHAR(200) | — |
| geometry | GEOMETRY(MULTIPOLYGON, 4326) | — |
| primary_language | VARCHAR(50) | — |
| seismic_zone | INT | CHECK (2-6) |

**districts**
| Column | Type | Constraints |
|--------|------|-------------|
| id | SERIAL | PRIMARY KEY |
| state_id | INT | FK → states(id) |
| name | VARCHAR(100) | NOT NULL |
| census_2011_code | VARCHAR(10) | — |
| population_2011 | INT | — |
| area_sq_km | FLOAT | — |
| geometry | GEOMETRY(MULTIPOLYGON, 4326) | — |
| vulnerability_score | FLOAT | — |

#### Disaster Tracking

**disasters**
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| type | india_disaster_type | NOT NULL |
| imd_classification | VARCHAR(50) | — |
| severity | INT | CHECK (1-5) |
| affected_state_ids | INT[] | — |
| affected_district_ids | INT[] | — |
| location | GEOMETRY(POINT, 4326) | — |
| affected_area | GEOMETRY(POLYGON, 4326) | — |
| start_time | TIMESTAMPTZ | NOT NULL |
| phase | VARCHAR(20) | DEFAULT 'pre_event' |
| sachet_alert_id | VARCHAR(100) | — |
| metadata | JSONB | DEFAULT '{}' |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

#### Time-Series (Partitioned)

**imd_observations** (PARTITION BY RANGE on `time`)
| Column | Type | Constraints |
|--------|------|-------------|
| time | TIMESTAMPTZ | NOT NULL |
| station_id | VARCHAR(50) | NOT NULL |
| district_id | INT | FK → districts(id) |
| location | GEOMETRY(POINT, 4326) | — |
| temperature_c | FLOAT | — |
| rainfall_mm | FLOAT | — |
| humidity_pct | FLOAT | — |
| wind_speed_kmph | FLOAT | — |
| wind_direction | VARCHAR(10) | — |
| pressure_hpa | FLOAT | — |
| source | VARCHAR(20) | DEFAULT 'imd_api' |

**cwc_river_levels** (PARTITION BY RANGE on `time`)
| Column | Type | Constraints |
|--------|------|-------------|
| time | TIMESTAMPTZ | NOT NULL |
| station_id | VARCHAR(50) | NOT NULL |
| river_name | VARCHAR(100) | — |
| state | VARCHAR(50) | — |
| location | GEOMETRY(POINT, 4326) | — |
| water_level_m | FLOAT | — |
| danger_level_m | FLOAT | — |
| warning_level_m | FLOAT | — |
| discharge_cumecs | FLOAT | — |
| source | VARCHAR(20) | DEFAULT 'cwc_guardian' |

#### Agent Decisions

**agent_decisions**
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| disaster_id | UUID | FK → disasters(id) |
| agent_id | VARCHAR(100) | NOT NULL |
| task_id | UUID | NOT NULL |
| decision_type | VARCHAR(50) | NOT NULL |
| decision_payload | JSONB | NOT NULL |
| confidence | FLOAT | — |
| reasoning | TEXT | — |
| provider | VARCHAR(50) | — |
| model | VARCHAR(100) | — |
| input_tokens | INT | — |
| output_tokens | INT | — |
| cost_usd | DECIMAL(10,6) | — |
| latency_ms | INT | — |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

#### Benchmark System

**benchmark_scenarios**
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| category | VARCHAR(50) | NOT NULL |
| complexity | VARCHAR(20) | NOT NULL |
| affected_states | TEXT[] | — |
| primary_language | VARCHAR(20) | — |
| initial_state | JSONB | NOT NULL |
| event_sequence | JSONB | NOT NULL |
| ground_truth_decisions | JSONB | NOT NULL |
| evaluation_rubric | JSONB | NOT NULL |
| version | INT | DEFAULT 1 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

**evaluation_runs**
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| scenario_id | UUID | FK → benchmark_scenarios(id) |
| agent_config | JSONB | NOT NULL |
| situational_accuracy | FLOAT | — |
| decision_timeliness | FLOAT | — |
| resource_efficiency | FLOAT | — |
| coordination_quality | FLOAT | — |
| communication_score | FLOAT | — |
| aggregate_drs | FLOAT | — |
| total_tokens | INT | — |
| total_cost_usd | DECIMAL(10,4) | — |
| primary_provider | VARCHAR(50) | — |
| completed_at | TIMESTAMPTZ | DEFAULT NOW() |

### 2.4 Indexes

- Spatial GiST indexes on all geometry columns
- BTREE index on `disasters(type)`, `disasters(start_time)`
- BTREE index on `agent_decisions(disaster_id)`, `agent_decisions(agent_id)`
- BTREE index on `evaluation_runs(scenario_id)`
- Composite (time, station_id) on partitioned tables

### 2.5 Default Partitions

Create default partitions for `imd_observations` and `cwc_river_levels` so INSERTs work immediately. Additional time-range partitions can be created as data is ingested.

---

## 3. Outcomes / Acceptance Criteria

1. `scripts/init_db.sql` is valid SQL that executes without errors on PostgreSQL 16 + PostGIS 3.4
2. PostGIS extension is created
3. All 8 tables are created with correct columns and types
4. `india_disaster_type` ENUM has all 10 disaster types
5. Foreign keys are enforced (states → districts, disasters → agent_decisions, etc.)
6. Spatial indexes exist on all geometry columns
7. Partitioned tables have default partitions
8. UUID columns use `gen_random_uuid()`
9. No hardcoded credentials in the SQL file
10. Script is idempotent (uses IF NOT EXISTS where appropriate)

---

## 4. TDD Notes

### What to Test

Since this is a SQL file (not Python), we test by:

1. **SQL parsing**: Read the SQL file and verify it's valid syntax
2. **Table presence**: Parse SQL for all CREATE TABLE statements, verify all 8 tables
3. **Column validation**: Check each table has the required columns with correct types
4. **ENUM values**: Verify all 10 india_disaster_type values
5. **Foreign keys**: Verify FK constraints exist
6. **Spatial indexes**: Verify GiST indexes on geometry columns
7. **Partitioning**: Verify imd_observations and cwc_river_levels are partitioned
8. **Idempotency**: Verify IF NOT EXISTS / CREATE OR REPLACE usage
9. **No hardcoded secrets**: Scan for password/secret patterns

### Test File
`tests/unit/test_db_schema.py`

### How to Test
- Read the SQL file as text
- Use regex/string matching to validate structure
- No database connection required for unit tests
