# Spec S6.5: Census 2011 + Administrative Boundaries

## Overview

Ingest India's Census 2011 data and administrative boundary geometries into PostGIS. This module populates the `states` and `districts` tables with population, area, local names, primary languages, seismic zones, and MultiPolygon geometries. The ResourceAllocation agent (S7.5) and ScenarioGenerator (S6.6) depend on this for spatial queries and demographic context.

## Depends On

- **S2.2** — PostgreSQL/PostGIS async connection (`src/shared/db.py`)

## Location

- `src/data/ingest/census.py`

## Requirements

### R1: State Data Model + Ingestion
- Define `StateRecord` Pydantic model with: name, name_local, primary_language, seismic_zone
- Provide a hardcoded dataset of all 36 Indian states/UTs with:
  - English name, local name, primary language
  - Seismic zone (2-5 per IS 1893:2002)
- Async function to upsert states into `states` table (ON CONFLICT UPDATE)

### R2: District Data Model + Ingestion
- Define `DistrictRecord` Pydantic model with: name, state_name, census_2011_code, population_2011, area_sq_km
- Provide a representative dataset of major districts (~100+ covering all states)
- Census 2011 codes, population, and area from Census of India 2011
- Async function to bulk insert/upsert districts into `districts` table

### R3: GeoJSON Boundary Loading
- Load state and district boundaries from GeoJSON files (data/boundaries/)
- Parse MultiPolygon geometries and insert as WKT into PostGIS
- Support both individual GeoJSON files and a combined FeatureCollection
- Handle coordinate reference system (SRID 4326 / WGS84)

### R4: Spatial Query Helpers
- `get_states()` — list all states
- `get_state_by_name(name)` — lookup state by name (case-insensitive)
- `get_districts_by_state(state_id)` — all districts in a state
- `get_district_by_name(name, state_name)` — lookup specific district
- `find_districts_in_polygon(polygon_wkt)` — districts whose geometry intersects a polygon
- `find_nearby_districts(lat, lon, radius_km)` — districts within radius of a point
- `get_population_in_area(polygon_wkt)` — total population within an area

### R5: Vulnerability Score Computation
- Compute vulnerability_score (0.0-1.0) per district based on:
  - Population density (people/sq_km)
  - Seismic zone of parent state
- Store computed score in districts.vulnerability_score column
- Formula: `0.5 * normalized_density + 0.5 * normalized_seismic_risk`

### R6: Ingestion Pipeline
- `ingest_census_data()` — full pipeline: states → districts → vulnerability scores
- Returns `CensusIngestionReport` with counts and errors
- Idempotent — safe to run multiple times (upsert semantics)

## Outcomes

1. `states` table populated with all 36 Indian states/UTs (name, local name, language, seismic zone)
2. `districts` table populated with 100+ major districts (name, code, population, area)
3. Spatial queries work: find districts by polygon intersection, radius search, population aggregation
4. Vulnerability scores computed and stored for all districts
5. All functions are async and use the shared db.py pool

## TDD Notes

- Mock `get_pool()` and `asyncpg` connections in all tests
- Test Pydantic validation (seismic zone range, population > 0, etc.)
- Test spatial query SQL generation (verify correct WKT, SRID)
- Test vulnerability score formula with known inputs
- Test idempotent upsert behavior
- Test ingestion report accuracy
