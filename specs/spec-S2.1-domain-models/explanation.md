# Spec S2.1: Domain Models — Explanation

## Why This Spec Exists

Every module in CRISIS-BENCH (agents, API, benchmark, data pipeline) needs to share a common vocabulary for disasters, agents, tasks, alerts, and evaluation results. Without centralized domain models, each module would define its own ad-hoc dictionaries, leading to serialization bugs, missing validations, and inconsistent field names. `src/shared/models.py` is the single source of truth for all data shapes.

## What It Does

Defines **22 Pydantic models** and **8 enums** in `src/shared/models.py`:

### Enums (8)
- **IndiaDisasterType** (10 values) — matches the PostgreSQL `india_disaster_type` enum exactly
- **DisasterPhase** (4 values) — pre_event → active_response → recovery → post_event
- **AgentType** (7 values) — one per specialist agent
- **LLMTier** (5 values) — critical/standard/routine/vision/free routing tiers
- **TaskStatus** (5 values) — pending → in_progress → completed/failed/cancelled
- **IMDCycloneClass** (7 values) — D → DD → CS → SCS → VSCS → ESCS → SuCS
- **AlertChannel** (5 values) — whatsapp/sms/social_media/media_briefing/tts_audio

### Models (22)
| Category | Models |
|----------|--------|
| Geo | GeoPoint, GeoPolygon |
| Core | State, District, Disaster, IMDObservation, CWCRiverLevel |
| Agent | AgentCard, AgentDecision, TaskRequest, TaskResult |
| Resource | Resource, Shelter, NDRFBattalion |
| Alert | Alert, SACHETAlert |
| Benchmark | BenchmarkScenario, EvaluationRun, EvaluationMetrics |
| LLM | LLMRequest, LLMResponse |

## How It Works

- All models use `ConfigDict(from_attributes=True)` so they can be constructed from asyncpg Row objects or SQLAlchemy models
- UUIDs auto-generate via `Field(default_factory=uuid.uuid4)`
- GeoPoint validates latitude [-90, 90] and longitude [-180, 180] using Pydantic `Field(ge=, le=)`
- GeoPolygon requires minimum 3 points via `Field(min_length=3)`
- Severity and priority fields use `Field(ge=1, le=5)` to enforce 1-5 range
- State.seismic_zone uses `Field(ge=2, le=6)` matching Indian seismic zone system
- EvaluationMetrics.aggregate_drs is a `@computed_field` with weighted average (SA=0.25, DT=0.20, RE=0.20, CQ=0.15, CA=0.20)
- BenchmarkScenario.complexity uses `Field(pattern=r"^(low|medium|high)$")` for validation
- All str Enums inherit from `(str, Enum)` for JSON serialization compatibility

## How It Connects

| Downstream Spec | Uses |
|-----------------|------|
| S2.2 (DB connection) | Models map to PostgreSQL tables |
| S2.4 (Error handling) | Models may carry error trace IDs |
| S2.6 (LLM Router) | LLMRequest, LLMResponse |
| S3.1 (API gateway) | Request/response schemas for FastAPI |
| S4.1 (A2A schemas) | TaskRequest, TaskResult for A2A messages |
| S7.1-S7.8 (Agents) | AgentCard, AgentDecision, Disaster, etc. |
| S8.1 (Benchmark models) | BenchmarkScenario, EvaluationRun, EvaluationMetrics |

## Interview Q&A

**Q: Why use `str, Enum` instead of plain `Enum` for the string enums?**
A: `str, Enum` makes enum values serialize as strings in JSON (e.g., `"cyclone"` instead of `"IndiaDisasterType.CYCLONE"`). This is critical for: (1) JSON API responses that frontends consume, (2) PostgreSQL enum values that must match exactly, (3) Redis Streams messages that are plain text. Without `str`, you'd need custom serializers everywhere.

**Q: Why `ConfigDict(from_attributes=True)` on every model?**
A: This enables `Model.model_validate(db_row, from_attributes=True)` — constructing a Pydantic model from an asyncpg Row or any object with matching attributes. Without it, you'd need to manually convert every DB row to a dict first. It's the Pydantic v2 equivalent of `orm_mode=True` from v1.

**Q: Why separate GeoPoint/GeoPolygon instead of using Shapely geometries?**
A: Pydantic can't natively validate Shapely objects — they'd be opaque `Any` types with no JSON serialization. GeoPoint/GeoPolygon are pure Pydantic with validation (lat/lng bounds, min polygon points). We convert to/from Shapely at the PostGIS boundary only.

**Q: Why is EvaluationMetrics.aggregate_drs a computed_field rather than stored?**
A: The DRS formula may change (different weights for different disaster types). A computed field always reflects the current formula. If we stored it, changing weights would require recalculating all historical scores. The trade-off: slightly slower access, but always consistent.
