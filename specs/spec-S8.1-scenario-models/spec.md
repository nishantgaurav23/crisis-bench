# Spec S8.1 — Benchmark Scenario Models + Storage

**Status**: done

## Overview

**Location**: `src/benchmark/models.py`
**Depends On**: S2.1 (domain models), S2.2 (DB connection)
**Downstream**: S8.2 (Scenario Manager), S8.3 (Scenario Runner), S8.4 (Evaluation Engine)

Create rich, typed Pydantic models for the benchmark system and async CRUD functions for PostgreSQL storage. The current `BenchmarkScenario` in `src/shared/models.py` uses loose `dict[str, Any]` fields — this spec replaces those with properly typed sub-models for event sequences, ground truth decisions, and evaluation rubrics.

## Outcomes

1. **Typed event sequence model** (`ScenarioEvent`) — time offset, phase, event type, structured payload
2. **Typed ground truth model** (`GroundTruthDecisions`) — per-agent expected decisions with time windows
3. **Typed evaluation rubric model** (`EvaluationRubric`) with per-dimension criteria and configurable weights
4. **Enhanced `BenchmarkScenario`** model using typed sub-models (backward-compatible with DB JSONB)
5. **Enhanced `EvaluationRun`** with agent trace data
6. **Async CRUD** — create, get_by_id, list_by_category, list_by_complexity, update, delete for scenarios
7. **Async CRUD** — create, get_by_scenario_id, list_recent for evaluation runs
8. **All CRUD functions** use `src/shared/db.py` helpers (asyncpg pool)

## Data Models

### ScenarioEvent
- `time_offset_minutes: int` — minutes from scenario start
- `phase: DisasterPhase` — pre_event | active_response | recovery
- `event_type: str` — e.g., "imd_warning", "evacuation_order"
- `description: str` — human-readable
- `data_payload: dict[str, Any]` — structured event data

### AgentExpectation
- `key_observations: list[str]`
- `expected_actions: list[str]`
- `time_window_minutes: tuple[int, int]` — (earliest, latest)

### GroundTruthDecisions
- `agent_expectations: dict[str, AgentExpectation]` — keyed by AgentType value
- `decision_timeline: dict[str, str]` — phase descriptions
- `ndma_references: list[str]` — guideline section references

### DimensionCriteria
- `weight: float` — 0.0-1.0
- `criteria: dict[str, str]` — excellent/good/fair/poor descriptions
- `key_factors: list[str]` — what to look for

### EvaluationRubric
- `situational_accuracy: DimensionCriteria`
- `decision_timeliness: DimensionCriteria`
- `resource_efficiency: DimensionCriteria`
- `coordination_quality: DimensionCriteria`
- `communication_appropriateness: DimensionCriteria`
- Validator: weights must sum to 1.0 (within 0.01 tolerance)

### EnhancedBenchmarkScenario (extends/replaces shared BenchmarkScenario)
- All existing fields from `BenchmarkScenario`
- `event_sequence: list[ScenarioEvent]` (typed, not `list[dict]`)
- `ground_truth_decisions: GroundTruthDecisions` (typed, not `dict`)
- `evaluation_rubric: EvaluationRubric` (typed, not `dict`)
- `tags: list[str]` — for filtering (e.g., "cascading", "multi-state")
- `source: str` — "synthetic" | "historical" | "perturbed"
- Methods: `to_db_row()`, `from_db_row()` for JSONB serialization

### EnhancedEvaluationRun (extends shared EvaluationRun)
- All existing fields
- `agent_decisions: list[dict[str, Any]]` — trace of each decision
- `duration_seconds: float | None` — wall-clock run time
- `error_log: list[str]` — any errors during run

## CRUD Functions

### Scenarios
- `async def create_scenario(scenario: BenchmarkScenario) -> uuid.UUID`
- `async def get_scenario(scenario_id: uuid.UUID) -> BenchmarkScenario | None`
- `async def list_scenarios(category: str | None, complexity: str | None, limit: int, offset: int) -> list[BenchmarkScenario]`
- `async def count_scenarios(category: str | None, complexity: str | None) -> int`
- `async def update_scenario(scenario_id: uuid.UUID, **fields) -> bool`
- `async def delete_scenario(scenario_id: uuid.UUID) -> bool`

### Evaluation Runs
- `async def create_evaluation_run(run: EvaluationRun) -> uuid.UUID`
- `async def get_evaluation_run(run_id: uuid.UUID) -> EvaluationRun | None`
- `async def list_runs_for_scenario(scenario_id: uuid.UUID) -> list[EvaluationRun]`
- `async def list_recent_runs(limit: int) -> list[EvaluationRun]`

## TDD Notes

### Test File: `tests/unit/test_benchmark_models.py`

1. **Model validation tests**: ScenarioEvent, GroundTruthDecisions, EvaluationRubric construction + validation
2. **Rubric weight validation**: weights must sum to 1.0
3. **Serialization round-trip**: model -> dict -> JSON -> model
4. **CRUD tests** (mock asyncpg): create, get, list, update, delete scenarios
5. **CRUD tests** (mock asyncpg): create, get, list evaluation runs
6. **Edge cases**: empty event sequence, missing agent expectations, zero weights

## Non-Goals

- Scenario generation (S6.6 + S8.11)
- Scenario execution/running (S8.3)
- Metric calculation (S8.5-S8.9)
- Aggregate DRS scoring (S8.10)
