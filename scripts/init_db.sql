-- =============================================================================
-- CRISIS-BENCH: PostgreSQL/PostGIS Database Schema
-- Spec S1.4 — Indian admin boundaries, disasters, time-series, agents, benchmark
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS postgis;

-- ---------------------------------------------------------------------------
-- Custom Types
-- ---------------------------------------------------------------------------

DO $$ BEGIN
    CREATE TYPE india_disaster_type AS ENUM (
        'monsoon_flood',
        'cyclone',
        'urban_waterlogging',
        'earthquake',
        'heatwave',
        'landslide',
        'industrial_accident',
        'tsunami',
        'drought',
        'glacial_lake_outburst'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- ---------------------------------------------------------------------------
-- Administrative Boundaries
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS states (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE,
    name_local      VARCHAR(200),
    geometry        GEOMETRY(MULTIPOLYGON, 4326),
    primary_language VARCHAR(50),
    seismic_zone    INT CHECK (seismic_zone BETWEEN 2 AND 6)
);

CREATE TABLE IF NOT EXISTS districts (
    id                SERIAL PRIMARY KEY,
    state_id          INT NOT NULL REFERENCES states(id),
    name              VARCHAR(100) NOT NULL,
    census_2011_code  VARCHAR(10),
    population_2011   INT,
    area_sq_km        FLOAT,
    geometry          GEOMETRY(MULTIPOLYGON, 4326),
    vulnerability_score FLOAT
);

-- ---------------------------------------------------------------------------
-- Disaster Tracking
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS disasters (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type                  india_disaster_type NOT NULL,
    imd_classification    VARCHAR(50),
    severity              INT CHECK (severity BETWEEN 1 AND 5),
    affected_state_ids    INT[],
    affected_district_ids INT[],
    location              GEOMETRY(POINT, 4326),
    affected_area         GEOMETRY(POLYGON, 4326),
    start_time            TIMESTAMPTZ NOT NULL,
    phase                 VARCHAR(20) DEFAULT 'pre_event',
    sachet_alert_id       VARCHAR(100),
    metadata              JSONB DEFAULT '{}',
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Time-Series: IMD Observations (Partitioned by time)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS imd_observations (
    time            TIMESTAMPTZ NOT NULL,
    station_id      VARCHAR(50) NOT NULL,
    district_id     INT REFERENCES districts(id),
    location        GEOMETRY(POINT, 4326),
    temperature_c   FLOAT,
    rainfall_mm     FLOAT,
    humidity_pct    FLOAT,
    wind_speed_kmph FLOAT,
    wind_direction  VARCHAR(10),
    pressure_hpa    FLOAT,
    source          VARCHAR(20) DEFAULT 'imd_api'
) PARTITION BY RANGE (time);

CREATE TABLE IF NOT EXISTS imd_observations_default PARTITION OF imd_observations DEFAULT;

-- ---------------------------------------------------------------------------
-- Time-Series: CWC River Levels (Partitioned by time)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cwc_river_levels (
    time             TIMESTAMPTZ NOT NULL,
    station_id       VARCHAR(50) NOT NULL,
    river_name       VARCHAR(100),
    state            VARCHAR(50),
    location         GEOMETRY(POINT, 4326),
    water_level_m    FLOAT,
    danger_level_m   FLOAT,
    warning_level_m  FLOAT,
    discharge_cumecs FLOAT,
    source           VARCHAR(20) DEFAULT 'cwc_guardian'
) PARTITION BY RANGE (time);

CREATE TABLE IF NOT EXISTS cwc_river_levels_default PARTITION OF cwc_river_levels DEFAULT;

-- ---------------------------------------------------------------------------
-- Agent Decision Tracking
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_decisions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    disaster_id       UUID REFERENCES disasters(id),
    agent_id          VARCHAR(100) NOT NULL,
    task_id           UUID NOT NULL,
    decision_type     VARCHAR(50) NOT NULL,
    decision_payload  JSONB NOT NULL,
    confidence        FLOAT,
    reasoning         TEXT,
    provider          VARCHAR(50),
    model             VARCHAR(100),
    input_tokens      INT,
    output_tokens     INT,
    cost_usd          DECIMAL(10, 6),
    latency_ms        INT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Benchmark System
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS benchmark_scenarios (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category                VARCHAR(50) NOT NULL,
    complexity              VARCHAR(20) NOT NULL,
    affected_states         TEXT[],
    primary_language        VARCHAR(20),
    initial_state           JSONB NOT NULL,
    event_sequence          JSONB NOT NULL,
    ground_truth_decisions  JSONB NOT NULL,
    evaluation_rubric       JSONB NOT NULL,
    version                 INT DEFAULT 1,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS evaluation_runs (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_id           UUID REFERENCES benchmark_scenarios(id),
    agent_config          JSONB NOT NULL,
    situational_accuracy  FLOAT,
    decision_timeliness   FLOAT,
    resource_efficiency   FLOAT,
    coordination_quality  FLOAT,
    communication_score   FLOAT,
    aggregate_drs         FLOAT,
    total_tokens          INT,
    total_cost_usd        DECIMAL(10, 4),
    primary_provider      VARCHAR(50),
    completed_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Spatial Indexes (GiST)
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_states_geometry ON states USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_districts_geometry ON districts USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_disasters_location ON disasters USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_disasters_affected_area ON disasters USING GIST (affected_area);
CREATE INDEX IF NOT EXISTS idx_imd_observations_location ON imd_observations USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_cwc_river_levels_location ON cwc_river_levels USING GIST (location);

-- ---------------------------------------------------------------------------
-- BTREE Indexes
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_disasters_type ON disasters (type);
CREATE INDEX IF NOT EXISTS idx_disasters_start_time ON disasters (start_time);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_disaster_id ON agent_decisions (disaster_id);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_agent_id ON agent_decisions (agent_id);
CREATE INDEX IF NOT EXISTS idx_evaluation_runs_scenario_id ON evaluation_runs (scenario_id);
CREATE INDEX IF NOT EXISTS idx_districts_state_id ON districts (state_id);
