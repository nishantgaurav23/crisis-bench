"""Benchmark scenario models and CRUD for CRISIS-BENCH (spec S8.1).

Provides rich, typed Pydantic models for benchmark scenarios, evaluation runs,
and async CRUD functions for PostgreSQL storage via asyncpg.

The models here extend the basic shapes defined in src/shared/models.py with
properly typed sub-models for event sequences, ground truth decisions, and
evaluation rubrics (replacing loose dict[str, Any] fields).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.shared.db import get_pool
from src.shared.models import DisasterPhase

# =============================================================================
# Sub-Models
# =============================================================================


class ScenarioEvent(BaseModel):
    """A single temporal event in a benchmark scenario."""

    model_config = ConfigDict(from_attributes=True)

    time_offset_minutes: int = Field(..., ge=0)
    phase: DisasterPhase
    event_type: str
    description: str
    data_payload: dict[str, Any] = Field(default_factory=dict)


class AgentExpectation(BaseModel):
    """Expected behavior from a single agent for ground truth evaluation."""

    model_config = ConfigDict(from_attributes=True)

    key_observations: list[str] = Field(default_factory=list)
    expected_actions: list[str] = Field(default_factory=list)
    time_window_minutes: tuple[int, int]


class GroundTruthDecisions(BaseModel):
    """Ground truth: what agents should do, per NDMA SOPs."""

    model_config = ConfigDict(from_attributes=True)

    agent_expectations: dict[str, AgentExpectation] = Field(default_factory=dict)
    decision_timeline: dict[str, str] = Field(default_factory=dict)
    ndma_references: list[str] = Field(default_factory=list)


class DimensionCriteria(BaseModel):
    """Scoring criteria for one evaluation dimension."""

    model_config = ConfigDict(from_attributes=True)

    weight: float = Field(..., ge=0.0, le=1.0)
    criteria: dict[str, str] = Field(default_factory=dict)
    key_factors: list[str] = Field(default_factory=list)


class EvaluationRubric(BaseModel):
    """Five-dimension evaluation rubric with weight validation."""

    model_config = ConfigDict(from_attributes=True)

    situational_accuracy: DimensionCriteria
    decision_timeliness: DimensionCriteria
    resource_efficiency: DimensionCriteria
    coordination_quality: DimensionCriteria
    communication_appropriateness: DimensionCriteria

    @property
    def total_weight(self) -> float:
        return (
            self.situational_accuracy.weight
            + self.decision_timeliness.weight
            + self.resource_efficiency.weight
            + self.coordination_quality.weight
            + self.communication_appropriateness.weight
        )

    @model_validator(mode="after")
    def _validate_weights_sum(self) -> EvaluationRubric:
        if abs(self.total_weight - 1.0) > 0.01:
            raise ValueError(
                f"Rubric weights must sum to 1.0 (got {self.total_weight:.4f})"
            )
        return self


# =============================================================================
# Benchmark Scenario (enhanced)
# =============================================================================


class BenchmarkScenario(BaseModel):
    """A single benchmark disaster scenario with typed sub-models.

    Replaces the basic BenchmarkScenario from src/shared/models.py with
    properly typed event sequences, ground truth, and rubric.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    category: str
    complexity: str = Field(..., pattern=r"^(low|medium|high)$")
    affected_states: list[str] = Field(default_factory=list)
    primary_language: str | None = None
    initial_state: dict[str, Any] = Field(default_factory=dict)
    event_sequence: list[ScenarioEvent] = Field(default_factory=list)
    ground_truth_decisions: GroundTruthDecisions = Field(
        default_factory=lambda: GroundTruthDecisions(
            agent_expectations={}, decision_timeline={}, ndma_references=[]
        )
    )
    evaluation_rubric: EvaluationRubric | None = None
    version: int = 1
    tags: list[str] = Field(default_factory=list)
    source: str = "synthetic"
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

    def to_db_row(self) -> dict[str, Any]:
        """Serialize to a dict suitable for PostgreSQL INSERT.

        JSONB fields are serialized to JSON strings.
        """
        return {
            "id": self.id,
            "category": self.category,
            "complexity": self.complexity,
            "affected_states": self.affected_states,
            "primary_language": self.primary_language,
            "initial_state": json.dumps(self.initial_state),
            "event_sequence": json.dumps(
                [e.model_dump(mode="json") for e in self.event_sequence]
            ),
            "ground_truth_decisions": json.dumps(
                self.ground_truth_decisions.model_dump(mode="json")
            ),
            "evaluation_rubric": json.dumps(
                self.evaluation_rubric.model_dump(mode="json")
                if self.evaluation_rubric
                else {}
            ),
            "version": self.version,
            "tags": self.tags,
            "source": self.source,
            "created_at": self.created_at,
        }

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> BenchmarkScenario:
        """Deserialize from a DB record (dict or asyncpg.Record).

        Handles JSONB fields stored as strings or already-parsed dicts.
        """

        def _parse_json(val: Any) -> Any:
            if isinstance(val, str):
                return json.loads(val)
            return val

        event_data = _parse_json(row["event_sequence"])
        events = [ScenarioEvent(**e) for e in event_data] if event_data else []

        gt_data = _parse_json(row["ground_truth_decisions"])
        ground_truth = GroundTruthDecisions(**gt_data) if gt_data else GroundTruthDecisions(
            agent_expectations={}, decision_timeline={}, ndma_references=[]
        )

        rubric_data = _parse_json(row["evaluation_rubric"])
        rubric = EvaluationRubric(**rubric_data) if rubric_data else None

        return cls(
            id=row["id"],
            category=row["category"],
            complexity=row["complexity"],
            affected_states=row.get("affected_states", []),
            primary_language=row.get("primary_language"),
            initial_state=_parse_json(row.get("initial_state", "{}")),
            event_sequence=events,
            ground_truth_decisions=ground_truth,
            evaluation_rubric=rubric,
            version=row.get("version", 1),
            tags=row.get("tags", []),
            source=row.get("source", "synthetic"),
            created_at=row.get("created_at", datetime.now(tz=UTC)),
        )


# =============================================================================
# Evaluation Run (enhanced)
# =============================================================================


class EvaluationRun(BaseModel):
    """Results of a single benchmark evaluation run (enhanced)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    scenario_id: uuid.UUID
    agent_config: dict[str, Any] = Field(default_factory=dict)
    situational_accuracy: float | None = None
    decision_timeliness: float | None = None
    resource_efficiency: float | None = None
    coordination_quality: float | None = None
    communication_score: float | None = None
    aggregate_drs: float | None = None
    total_tokens: int | None = None
    total_cost_usd: float | None = None
    primary_provider: str | None = None
    agent_decisions: list[dict[str, Any]] = Field(default_factory=list)
    duration_seconds: float | None = None
    error_log: list[str] = Field(default_factory=list)
    completed_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


# =============================================================================
# Scenario CRUD
# =============================================================================


async def create_scenario(scenario: BenchmarkScenario) -> uuid.UUID:
    """Insert a benchmark scenario into PostgreSQL."""
    pool = await get_pool()
    row = scenario.to_db_row()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO benchmark_scenarios
               (id, category, complexity, affected_states, primary_language,
                initial_state, event_sequence, ground_truth_decisions,
                evaluation_rubric, version, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
            row["id"],
            row["category"],
            row["complexity"],
            row["affected_states"],
            row["primary_language"],
            row["initial_state"],
            row["event_sequence"],
            row["ground_truth_decisions"],
            row["evaluation_rubric"],
            row["version"],
            row["created_at"],
        )
    return scenario.id


async def get_scenario(scenario_id: uuid.UUID) -> BenchmarkScenario | None:
    """Fetch a single scenario by ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM benchmark_scenarios WHERE id = $1",
            scenario_id,
        )
    if row is None:
        return None
    return BenchmarkScenario.from_db_row(dict(row))


async def list_scenarios(
    category: str | None = None,
    complexity: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[BenchmarkScenario]:
    """List scenarios with optional filters."""
    pool = await get_pool()
    conditions: list[str] = []
    args: list[Any] = []
    idx = 1

    if category is not None:
        conditions.append(f"category = ${idx}")
        args.append(category)
        idx += 1
    if complexity is not None:
        conditions.append(f"complexity = ${idx}")
        args.append(complexity)
        idx += 1

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    query = (
        f"SELECT * FROM benchmark_scenarios{where}"
        f" ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}"
    )
    args.extend([limit, offset])

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)

    return [BenchmarkScenario.from_db_row(dict(r)) for r in rows]


async def count_scenarios(
    category: str | None = None,
    complexity: str | None = None,
) -> int:
    """Count scenarios with optional filters."""
    pool = await get_pool()
    conditions: list[str] = []
    args: list[Any] = []
    idx = 1

    if category is not None:
        conditions.append(f"category = ${idx}")
        args.append(category)
        idx += 1
    if complexity is not None:
        conditions.append(f"complexity = ${idx}")
        args.append(complexity)
        idx += 1

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"SELECT COUNT(*) FROM benchmark_scenarios{where}"

    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)


async def update_scenario(scenario_id: uuid.UUID, **fields: Any) -> bool:
    """Update specific fields on a scenario. Returns True if row was found."""
    if not fields:
        return False
    pool = await get_pool()

    set_parts: list[str] = []
    args: list[Any] = []
    idx = 1
    for key, val in fields.items():
        set_parts.append(f"{key} = ${idx}")
        args.append(val)
        idx += 1

    args.append(scenario_id)
    query = (
        f"UPDATE benchmark_scenarios SET {', '.join(set_parts)}"
        f" WHERE id = ${idx}"
    )

    async with pool.acquire() as conn:
        result = await conn.execute(query, *args)

    return result.endswith("1")


async def delete_scenario(scenario_id: uuid.UUID) -> bool:
    """Delete a scenario by ID. Returns True if row was deleted."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM benchmark_scenarios WHERE id = $1",
            scenario_id,
        )
    return result.endswith("1")


# =============================================================================
# Evaluation Run CRUD
# =============================================================================


async def create_evaluation_run(run: EvaluationRun) -> uuid.UUID:
    """Insert an evaluation run."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO evaluation_runs
               (id, scenario_id, agent_config,
                situational_accuracy, decision_timeliness,
                resource_efficiency, coordination_quality,
                communication_score, aggregate_drs,
                total_tokens, total_cost_usd, primary_provider,
                completed_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)""",
            run.id,
            run.scenario_id,
            json.dumps(run.agent_config),
            run.situational_accuracy,
            run.decision_timeliness,
            run.resource_efficiency,
            run.coordination_quality,
            run.communication_score,
            run.aggregate_drs,
            run.total_tokens,
            run.total_cost_usd,
            run.primary_provider,
            run.completed_at,
        )
    return run.id


async def get_evaluation_run(run_id: uuid.UUID) -> EvaluationRun | None:
    """Fetch an evaluation run by ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM evaluation_runs WHERE id = $1",
            run_id,
        )
    if row is None:
        return None
    return _row_to_evaluation_run(dict(row))


async def list_runs_for_scenario(
    scenario_id: uuid.UUID,
) -> list[EvaluationRun]:
    """List all evaluation runs for a given scenario."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM evaluation_runs WHERE scenario_id = $1"
            " ORDER BY completed_at DESC",
            scenario_id,
        )
    return [_row_to_evaluation_run(dict(r)) for r in rows]


async def list_recent_runs(limit: int = 20) -> list[EvaluationRun]:
    """List the most recent evaluation runs."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM evaluation_runs ORDER BY completed_at DESC LIMIT $1",
            limit,
        )
    return [_row_to_evaluation_run(dict(r)) for r in rows]


def _row_to_evaluation_run(row: dict[str, Any]) -> EvaluationRun:
    """Convert a DB row dict to an EvaluationRun."""

    def _parse_json(val: Any) -> Any:
        if isinstance(val, str):
            return json.loads(val)
        return val

    return EvaluationRun(
        id=row["id"],
        scenario_id=row["scenario_id"],
        agent_config=_parse_json(row.get("agent_config", "{}")),
        situational_accuracy=row.get("situational_accuracy"),
        decision_timeliness=row.get("decision_timeliness"),
        resource_efficiency=row.get("resource_efficiency"),
        coordination_quality=row.get("coordination_quality"),
        communication_score=row.get("communication_score"),
        aggregate_drs=row.get("aggregate_drs"),
        total_tokens=row.get("total_tokens"),
        total_cost_usd=float(row["total_cost_usd"]) if row.get("total_cost_usd") else None,
        primary_provider=row.get("primary_provider"),
        agent_decisions=_parse_json(row.get("agent_decisions", "[]")),
        duration_seconds=row.get("duration_seconds"),
        error_log=_parse_json(row.get("error_log", "[]")),
        completed_at=row.get("completed_at", datetime.now(tz=UTC)),
    )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Sub-models
    "AgentExpectation",
    "DimensionCriteria",
    "EvaluationRubric",
    "GroundTruthDecisions",
    "ScenarioEvent",
    # Main models
    "BenchmarkScenario",
    "EvaluationRun",
    # Scenario CRUD
    "count_scenarios",
    "create_scenario",
    "delete_scenario",
    "get_scenario",
    "list_scenarios",
    "update_scenario",
    # Evaluation Run CRUD
    "create_evaluation_run",
    "get_evaluation_run",
    "list_recent_runs",
    "list_runs_for_scenario",
]
