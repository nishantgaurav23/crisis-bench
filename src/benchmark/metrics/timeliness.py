"""Decision Timeliness metric for CRISIS-BENCH (spec S8.6).

Measures how quickly agents make decisions relative to NDMA SOP time
windows defined in ground truth. Scores based on whether decisions fall
within, before, or after expected windows.

Late decisions are penalized more heavily than early ones — in disaster
response, a late evacuation order can cost lives, while an early warning
(even if premature) is less harmful.
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, Field

from src.benchmark.models import (
    BenchmarkScenario,
    EvaluationRun,
    GroundTruthDecisions,
)

# =============================================================================
# Models
# =============================================================================


class AgentTimeliness(BaseModel):
    """Timeliness score for a single agent."""

    agent_id: str
    expected_window: tuple[int, int]
    actual_minutes: float | None = None
    score: float = Field(..., ge=1.0, le=5.0)
    status: str  # "on_time", "early", "late", "missing"


class DecisionTimelinessResult(BaseModel):
    """Complete decision timeliness result."""

    per_agent: dict[str, AgentTimeliness] = Field(default_factory=dict)
    score: float = Field(..., ge=1.0, le=5.0)
    on_time_count: int = Field(default=0, ge=0)
    early_count: int = Field(default=0, ge=0)
    late_count: int = Field(default=0, ge=0)
    missing_count: int = Field(default=0, ge=0)


# =============================================================================
# Scoring Logic
# =============================================================================


def score_agent_timeliness(
    actual_minutes: float,
    window_start: int,
    window_end: int,
    late_penalty_factor: float = 2.0,
) -> tuple[float, str]:
    """Score a single agent's decision timeliness.

    Returns (score, status) where score is 1.0-5.0 and status is one of
    "on_time", "early", "late".

    Scoring:
    - Within window: 5.0
    - Early: Linear decay from 5.0 toward 3.0 based on how early
    - Late: Exponential decay from 5.0 toward 1.0 (harsher than early)
    """
    window_size = max(window_end - window_start, 1)

    if window_start <= actual_minutes <= window_end:
        return 5.0, "on_time"

    if actual_minutes < window_start:
        # Early: linear decay toward 3.0
        early_by = window_start - actual_minutes
        fraction = min(early_by / window_size, 1.0)
        score = 5.0 - 2.0 * fraction  # 5.0 → 3.0
        return round(max(3.0, score), 2), "early"

    # Late: exponential decay toward 1.0
    late_by = actual_minutes - window_end
    decay = math.exp(-late_penalty_factor * late_by / window_size)
    score = 1.0 + 4.0 * decay  # 5.0 → 1.0
    return round(max(1.0, min(5.0, score)), 2), "late"


# =============================================================================
# Extraction Helpers
# =============================================================================


def extract_decision_times(
    decisions: list[dict[str, Any]],
) -> dict[str, float]:
    """Extract per-agent decision times from agent decision records.

    Uses the first decision for each agent if there are duplicates.
    Only includes agents that have a `simulated_elapsed_minutes` field.
    """
    result: dict[str, float] = {}
    for decision in decisions:
        agent_id = decision.get("agent_id", "unknown")
        elapsed = decision.get("simulated_elapsed_minutes")
        if elapsed is not None and agent_id not in result:
            result[agent_id] = float(elapsed)
    return result


def extract_time_windows(
    ground_truth: GroundTruthDecisions,
) -> dict[str, tuple[int, int]]:
    """Extract per-agent expected time windows from ground truth."""
    result: dict[str, tuple[int, int]] = {}
    for agent_id, expectation in ground_truth.agent_expectations.items():
        result[agent_id] = expectation.time_window_minutes
    return result


# =============================================================================
# Metric Class
# =============================================================================


class DecisionTimelinessMetric:
    """Computes decision timeliness against NDMA SOP time windows.

    Compares agent decision timestamps against expected time windows
    from ground truth. Late decisions are penalized more heavily than
    early ones.
    """

    def __init__(self, late_penalty_factor: float = 2.0) -> None:
        self._late_penalty_factor = late_penalty_factor

    async def compute(
        self,
        scenario: BenchmarkScenario,
        evaluation_run: EvaluationRun,
    ) -> DecisionTimelinessResult:
        """Compute decision timeliness for a benchmark run."""
        windows = extract_time_windows(scenario.ground_truth_decisions)
        times = extract_decision_times(evaluation_run.agent_decisions)

        if not windows:
            return DecisionTimelinessResult(
                per_agent={},
                score=1.0,
                on_time_count=0,
                early_count=0,
                late_count=0,
                missing_count=0,
            )

        per_agent: dict[str, AgentTimeliness] = {}
        on_time = 0
        early = 0
        late = 0
        missing = 0

        for agent_id, (w_start, w_end) in windows.items():
            actual = times.get(agent_id)
            if actual is None:
                per_agent[agent_id] = AgentTimeliness(
                    agent_id=agent_id,
                    expected_window=(w_start, w_end),
                    actual_minutes=None,
                    score=1.0,
                    status="missing",
                )
                missing += 1
            else:
                score, status = score_agent_timeliness(
                    actual, w_start, w_end, self._late_penalty_factor,
                )
                per_agent[agent_id] = AgentTimeliness(
                    agent_id=agent_id,
                    expected_window=(w_start, w_end),
                    actual_minutes=actual,
                    score=score,
                    status=status,
                )
                if status == "on_time":
                    on_time += 1
                elif status == "early":
                    early += 1
                else:
                    late += 1

        avg_score = sum(a.score for a in per_agent.values()) / len(per_agent)
        avg_score = round(max(1.0, min(5.0, avg_score)), 2)

        return DecisionTimelinessResult(
            per_agent=per_agent,
            score=avg_score,
            on_time_count=on_time,
            early_count=early,
            late_count=late,
            missing_count=missing,
        )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "AgentTimeliness",
    "DecisionTimelinessMetric",
    "DecisionTimelinessResult",
    "extract_decision_times",
    "extract_time_windows",
    "score_agent_timeliness",
]
