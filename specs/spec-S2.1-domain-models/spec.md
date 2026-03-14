# Spec S2.1: Pydantic Domain Models

**Status**: spec-written
**Depends On**: S1.3 (Environment config)
**Location**: `src/shared/models.py`
**Phase**: 2 — Shared Infrastructure

---

## 1. Purpose

Define all Pydantic domain models used across the CRISIS-BENCH system. These models are the shared language between agents, the API, the benchmark engine, and the data layer. Every module imports from `src/shared/models.py`.

## 2. Models Required

Based on the DB schema (`scripts/init_db.sql`), the design doc, and requirements:

### 2.1 Enums

- **IndiaDisasterType** — Enum matching `india_disaster_type` PostgreSQL enum: `monsoon_flood`, `cyclone`, `urban_waterlogging`, `earthquake`, `heatwave`, `landslide`, `industrial_accident`, `tsunami`, `drought`, `glacial_lake_outburst`
- **DisasterPhase** — `pre_event`, `active_response`, `recovery`, `post_event`
- **Severity** — Integer 1-5 (maps to IMD color codes: Green=1, Yellow=2, Orange=3, Red=4, Red+=5)
- **AgentType** — `orchestrator`, `situation_sense`, `predictive_risk`, `resource_allocation`, `community_comms`, `infra_status`, `historical_memory`
- **LLMTier** — `critical`, `standard`, `routine`, `vision`, `free`
- **TaskStatus** — `pending`, `in_progress`, `completed`, `failed`, `cancelled`
- **IMDCycloneClass** — `D`, `DD`, `CS`, `SCS`, `VSCS`, `ESCS`, `SuCS` (IMD cyclone classification)
- **AlertChannel** — `whatsapp`, `sms`, `social_media`, `media_briefing`, `tts_audio`

### 2.2 Core Domain Models

- **GeoPoint** — latitude, longitude (WGS84, SRID 4326)
- **GeoPolygon** — list of GeoPoint coordinates forming a polygon
- **State** — id, name, name_local, primary_language, seismic_zone, geometry (optional)
- **District** — id, state_id, name, census_2011_code, population_2011, area_sq_km, vulnerability_score, geometry (optional)
- **Disaster** — id (UUID), type (IndiaDisasterType), imd_classification, severity, affected_state_ids, affected_district_ids, location (GeoPoint), affected_area (GeoPolygon, optional), start_time, phase, sachet_alert_id, metadata (dict)
- **IMDObservation** — time, station_id, district_id, location, temperature_c, rainfall_mm, humidity_pct, wind_speed_kmph, wind_direction, pressure_hpa, source
- **CWCRiverLevel** — time, station_id, river_name, state, location, water_level_m, danger_level_m, warning_level_m, discharge_cumecs, source

### 2.3 Agent Models

- **AgentCard** — agent_id, agent_type (AgentType), name, description, capabilities (list[str]), status, llm_tier
- **AgentDecision** — id (UUID), disaster_id, agent_id, task_id, decision_type, decision_payload (dict), confidence, reasoning, provider, model, input_tokens, output_tokens, cost_usd, latency_ms, created_at
- **TaskRequest** — id (UUID), source_agent, target_agent, disaster_id, task_type, payload (dict), priority, status, created_at, deadline
- **TaskResult** — task_id, agent_id, status, result_payload (dict), confidence, error_message, completed_at

### 2.4 Resource Models

- **Resource** — id, resource_type, name, location, capacity, available, metadata
- **Shelter** — id, name, location, capacity, current_occupancy, district_id, amenities (list[str])
- **NDRFBattalion** — id, name, base_location, strength, deployed_to, status

### 2.5 Alert/Communication Models

- **Alert** — id (UUID), disaster_id, severity, title, message, language, channel (AlertChannel), target_audience, source_authority, issued_at, expires_at
- **SACHETAlert** — cap_id, sender, event_type, severity, urgency, certainty, headline, description, area_desc, polygon (optional), onset, expires

### 2.6 Benchmark Models

- **BenchmarkScenario** — id (UUID), category, complexity, affected_states, primary_language, initial_state (dict), event_sequence (list[dict]), ground_truth_decisions (dict), evaluation_rubric (dict), version, created_at
- **EvaluationRun** — id (UUID), scenario_id, agent_config (dict), situational_accuracy, decision_timeliness, resource_efficiency, coordination_quality, communication_score, aggregate_drs, total_tokens, total_cost_usd, primary_provider, completed_at
- **EvaluationMetrics** — situational_accuracy, decision_timeliness, resource_efficiency, coordination_quality, communication_score, aggregate_drs (computed weighted average)

### 2.7 LLM Router Models

- **LLMRequest** — tier (LLMTier), messages (list[dict]), kwargs (dict)
- **LLMResponse** — content (str), provider, model, input_tokens, output_tokens, cost_usd, latency_ms

## 3. Design Decisions

- All models inherit from Pydantic `BaseModel` with `model_config = ConfigDict(from_attributes=True)` for ORM compatibility
- UUIDs use `uuid4` default factory
- Timestamps use `datetime` with timezone awareness (`UTC`)
- GeoPoint validated: latitude [-90, 90], longitude [-180, 180]
- All optional fields explicitly typed as `X | None`
- No database-specific code — pure data schemas

## 4. Outcomes

- [ ] All models importable from `src.shared.models`
- [ ] All enums match DB schema values exactly
- [ ] GeoPoint validates coordinate bounds
- [ ] Models serialize to/from JSON correctly
- [ ] Models can be constructed from DB rows (`from_attributes=True`)
- [ ] No external dependencies beyond pydantic
- [ ] Tests cover: construction, validation, serialization, edge cases

## 5. TDD Notes

### Red Phase (write tests first)
- Test each enum has all expected values
- Test each model can be constructed with valid data
- Test validation rejects invalid data (bad coordinates, out-of-range severity, etc.)
- Test JSON serialization round-trip
- Test `from_attributes=True` works with mock ORM-like objects
- Test computed fields (e.g., EvaluationMetrics.aggregate_drs)
- Test optional fields default to None

### Green Phase
- Implement all models in `src/shared/models.py`

### Refactor Phase
- Ensure ruff clean, consistent style, proper `__all__` exports
