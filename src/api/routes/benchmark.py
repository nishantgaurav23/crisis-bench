"""Benchmark scenarios and evaluation runs API (in-memory store for MVP).

Provides REST endpoints for listing/viewing benchmark scenarios and
their evaluation run results. Uses in-memory storage — will be replaced
by PostgreSQL CRUD from src/benchmark/models.py when DB is connected.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/benchmark", tags=["benchmark"])

# In-memory stores
_scenarios: dict[str, dict[str, Any]] = {}
_evaluation_runs: dict[str, dict[str, Any]] = {}


# ---- Request/Response Models ----


class ScenarioSummary(BaseModel):
    id: str
    category: str
    complexity: str
    affected_states: list[str] = Field(default_factory=list)
    event_count: int = 0
    source: str = "synthetic"
    created_at: str = ""


class EvaluationRunSummary(BaseModel):
    id: str
    scenario_id: str
    situational_accuracy: float | None = None
    decision_timeliness: float | None = None
    resource_efficiency: float | None = None
    coordination_quality: float | None = None
    communication_score: float | None = None
    aggregate_drs: float | None = None
    total_tokens: int | None = None
    total_cost_usd: float | None = None
    primary_provider: str | None = None
    duration_seconds: float | None = None
    completed_at: str = ""


# ---- Scenario Endpoints ----


@router.post("/scenarios", status_code=201)
async def create_scenario(scenario: ScenarioSummary) -> dict[str, Any]:
    """Seed a benchmark scenario (for testing/demo)."""
    _scenarios[scenario.id] = scenario.model_dump()
    return scenario.model_dump()


@router.get("/scenarios", response_model=list[dict[str, Any]])
async def list_scenarios(
    category: str | None = None,
    complexity: str | None = None,
) -> list[dict[str, Any]]:
    """List benchmark scenarios with optional filters."""
    results = list(_scenarios.values())
    if category:
        results = [s for s in results if s.get("category") == category]
    if complexity:
        results = [s for s in results if s.get("complexity") == complexity]
    return results


@router.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str) -> dict[str, Any]:
    """Get a single scenario by ID."""
    scenario = _scenarios.get(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")
    return scenario


# ---- Evaluation Run Endpoints ----


@router.post("/runs", status_code=201)
async def create_run(run: EvaluationRunSummary) -> dict[str, Any]:
    """Seed an evaluation run (for testing/demo)."""
    _evaluation_runs[run.id] = run.model_dump()
    return run.model_dump()


@router.get("/runs", response_model=list[dict[str, Any]])
async def list_runs(
    scenario_id: str | None = None,
) -> list[dict[str, Any]]:
    """List evaluation runs with optional scenario filter."""
    results = list(_evaluation_runs.values())
    if scenario_id:
        results = [r for r in results if r.get("scenario_id") == scenario_id]
    return results


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    """Get a single evaluation run by ID."""
    run = _evaluation_runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run
