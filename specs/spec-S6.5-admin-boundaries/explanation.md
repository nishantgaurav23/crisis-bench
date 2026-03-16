# Spec S6.5: Census 2011 + Administrative Boundaries — Explanation

## Why This Spec Exists

Every disaster-response decision is spatially grounded: "Which districts are affected?", "What is the population at risk?", "Which state's SDRF should deploy?" Without administrative boundaries and demographic data in PostGIS, agents cannot answer these questions. This spec provides the foundational geographic reference layer that the ResourceAllocation agent (S7.5) uses for shelter matching and NDRF deployment, and the ScenarioGenerator (S6.6) uses to create geographically realistic disaster scenarios.

## What It Does

1. **Populates 36 states/UTs** into the `states` table with English names, local script names, primary languages, and seismic zones (IS 1893:2002).

2. **Populates 100+ major districts** into the `districts` table with Census 2011 codes, population, area, and parent state linkage. Districts are specifically chosen to include disaster-prone areas (cyclone belt: Odisha coast, flood belt: Bihar/Assam, seismic belt: NE India, urban flood: Mumbai/Chennai).

3. **Computes vulnerability scores** (0.0-1.0) per district using a weighted formula: `0.5 * normalized_population_density + 0.5 * normalized_seismic_risk`. This gives agents a quick risk heuristic without complex models.

4. **Provides spatial query helpers** for downstream modules:
   - `find_districts_in_polygon()` — which districts are inside a flood polygon?
   - `find_nearby_districts()` — which districts are within 50km of an earthquake epicenter?
   - `get_population_in_area()` — how many people are at risk in this affected zone?

## How It Works

### Data Flow
```
INDIA_STATES (hardcoded) → upsert_states() → states table
INDIA_DISTRICTS (hardcoded) → upsert_districts() → districts table (with state_id FK)
districts + states → compute_vulnerability_score() → districts.vulnerability_score
```

### Key Design Decisions

- **Hardcoded data instead of API/file download**: Census 2011 data is static (next census is 2025+). Hardcoding eliminates external dependencies and makes the module work offline. The 100+ districts cover all 36 states/UTs with emphasis on disaster-prone regions.

- **Upsert semantics (ON CONFLICT)**: Makes the pipeline idempotent — safe to run multiple times without duplicating data. States use `ON CONFLICT (name) DO UPDATE`, districts use `ON CONFLICT (state_id, name) DO NOTHING`.

- **Vulnerability score formula**: Simple 2-factor model (density + seismic). Intentionally simple because the benchmark scenarios can override this with more nuanced risk models. The score serves as a default heuristic for the ResourceAllocation agent's initial triage.

- **Spatial queries use PostGIS native functions**: `ST_Intersects`, `ST_DWithin`, `ST_GeomFromText` — these leverage GiST indexes for O(log n) spatial lookups instead of O(n) scans.

## How It Connects

### Upstream Dependencies
- **S2.2 (db.py)** — Uses `get_pool()`, `fetch_all()`, `fetch_one()`, `fetch_val()` for all database operations.
- **S1.4 (init_db.sql)** — Populates the `states` and `districts` tables defined there.

### Downstream Dependents
- **S6.6 (Scenario Generator)** — Uses district populations and state data to generate geographically realistic disaster scenarios with correct demographic context.
- **S7.5 (ResourceAllocation agent)** — Uses `find_nearby_districts()` and `get_population_in_area()` to calculate affected populations and match shelters.
- **S6.4 (IMD Historical)** — `query_district_rainfall()` in imd.py joins with the districts table populated by this spec.

### Interview Talking Points

**Q: Why hardcode Census data instead of downloading from data.gov.in?**
A: Census 2011 data is static and won't change. Downloading from data.gov.in adds an API dependency, rate limiting, and parsing complexity for data that's been the same since 2011. Hardcoding makes the system work offline and removes a failure mode. When Census 2025 data is released, we update the constants.

**Q: How does the vulnerability score work and what are its limitations?**
A: It's a normalized 2-factor score: population density (higher density = more people at risk per sq km) and seismic zone (higher zone = more earthquake risk). Limitations: (1) it ignores flood risk, cyclone exposure, and socioeconomic factors, (2) seismic zone is state-level, not district-level, (3) Census 2011 data is 15 years old. For production, you'd want a multi-hazard vulnerability index from NDMA, but this serves as a useful default heuristic.

**Q: Why use PostGIS spatial queries instead of computing distances in Python?**
A: PostGIS operations like `ST_DWithin` use GiST (Generalized Search Tree) indexes — O(log n) spatial lookups. Computing haversine distances in Python would require loading all districts into memory and scanning all of them — O(n). For "find districts within 50km of this point" with 700+ districts, the PostGIS approach is both faster and uses constant memory.
