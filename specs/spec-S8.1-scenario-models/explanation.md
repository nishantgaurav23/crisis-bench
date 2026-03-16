# S8.1 Explanation — Benchmark Scenario Models + Storage

## Why This Spec Exists

The benchmark system (Phase 8) needs properly typed data models for disaster scenarios and evaluation runs. The shared `BenchmarkScenario` model (S2.1) uses loose `dict[str, Any]` fields for event sequences, ground truth, and rubrics — fine for initial prototyping but insufficient for the benchmark engine that needs to validate, iterate, and score these structures programmatically.

S8.1 creates the typed foundation that all downstream benchmark specs (S8.2-S8.11) build upon.

## What It Does

### Typed Sub-Models
- **ScenarioEvent** — A single temporal event with `time_offset_minutes`, `phase` (DisasterPhase enum), `event_type`, `description`, and `data_payload`. Time offset validated `>= 0`.
- **AgentExpectation** — Per-agent expected behavior: observations, actions, and time window (tuple of earliest/latest minutes).
- **GroundTruthDecisions** — Dict of `AgentExpectation` keyed by agent type, plus decision timeline descriptions and NDMA SOP references.
- **DimensionCriteria** — Weight (0.0-1.0), scoring criteria dict (excellent/good/fair/poor), and key evaluation factors.
- **EvaluationRubric** — Five dimensions (SA, DT, RE, CQ, CA) each as `DimensionCriteria`. Model validator ensures weights sum to 1.0 (±0.01 tolerance).

### Enhanced Models
- **BenchmarkScenario** — Replaces dict fields with typed sub-models. Adds `tags` (for filtering: "cascading", "multi-state"), `source` ("synthetic"/"historical"/"perturbed"). Provides `to_db_row()` (serializes JSONB fields to JSON strings) and `from_db_row()` (deserializes back).
- **EvaluationRun** — Extended with `agent_decisions` trace, `duration_seconds`, and `error_log`.

### CRUD Functions
Six async functions for scenarios (create, get, list with filters, count, update, delete) and four for evaluation runs (create, get, list by scenario, list recent). All use `src/shared/db.get_pool()` for asyncpg connection pooling.

## How It Works

### Serialization Strategy
PostgreSQL stores `event_sequence`, `ground_truth_decisions`, and `evaluation_rubric` as JSONB. The `to_db_row()` method calls `model_dump(mode="json")` on each sub-model and serializes to JSON strings. `from_db_row()` parses JSON strings back into typed Pydantic models, handling both string and already-parsed dict inputs (for flexibility with different DB drivers).

### Weight Validation
The `EvaluationRubric` uses a Pydantic `model_validator(mode="after")` to check that the five dimension weights sum to 1.0. This catches misconfigured rubrics at construction time rather than at scoring time.

### Dynamic Query Building
`list_scenarios()` and `count_scenarios()` build SQL queries dynamically based on which filters are provided, using parameterized `$N` placeholders to prevent SQL injection.

## How It Connects

| Upstream | Connection |
|----------|------------|
| S2.1 (domain models) | Reuses `DisasterPhase` enum from `src/shared/models.py` |
| S2.2 (DB connection) | Uses `get_pool()` from `src/shared/db.py` for all CRUD |
| S1.4 (DB schema) | Reads/writes `benchmark_scenarios` and `evaluation_runs` tables |

| Downstream | Connection |
|------------|------------|
| S8.2 (Scenario Manager) | Uses `BenchmarkScenario` model + CRUD functions for scenario management |
| S8.3 (Scenario Runner) | Reads `ScenarioEvent` list for deterministic replay with simulated clock |
| S8.4 (Evaluation Engine) | Creates `EvaluationRun` records, uses `EvaluationRubric` for scoring |
| S8.5-S8.9 (Metrics) | Use `DimensionCriteria` for per-dimension scoring configuration |
| S8.10 (Aggregate DRS) | Reads dimension weights from `EvaluationRubric` for weighted combination |
| S8.11 (Self-Evolving) | Creates new `BenchmarkScenario` instances via CRUD |
| S6.6 (Scenario Gen) | Currently uses shared `BenchmarkScenario` — can be migrated to this enhanced version |

## Interview Talking Points

**Q: Why typed sub-models instead of keeping `dict[str, Any]`?**
A: Type safety at construction time. With dicts, a missing `time_window_minutes` key in ground truth would only surface as a `KeyError` during evaluation (runtime). With Pydantic models, it fails at scenario load time with a clear validation error. This is especially important for a benchmark — invalid scenarios waste expensive LLM evaluation runs.

**Q: Why `to_db_row()`/`from_db_row()` instead of using an ORM?**
A: We use raw asyncpg for performance (3-5x faster than SQLAlchemy async). The trade-off is manual serialization, but since our JSONB fields contain nested Pydantic models, we get the best of both worlds — typed Python objects with efficient PostgreSQL storage. The serialization is a thin layer (~20 lines) that's easy to test and maintain.

**Q: Why validate rubric weights at model construction?**
A: Fail fast. If weights don't sum to 1.0, the aggregate DRS score will be mathematically wrong. Catching this at construction time (when the scenario is created or loaded) prevents silent scoring errors that would only be discovered after expensive benchmark runs.
