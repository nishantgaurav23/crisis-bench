"""Aggregate Disaster Response Score (DRS) for CRISIS-BENCH (spec S8.10).

Combines the 5 individual metric scores (situational accuracy, decision
timeliness, resource efficiency, coordination quality, communication
appropriateness) into a single weighted DRS normalized to 0.0-1.0.

Supports pass@k reliability measurement for statistical robustness
across multiple evaluation runs.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, Field

from src.benchmark.metrics.communication import CommunicationAppropriatenessMetric
from src.benchmark.metrics.coordination import CoordinationQualityMetric
from src.benchmark.metrics.resource import ResourceEfficiencyMetric
from src.benchmark.metrics.situational import SituationalAccuracyMetric
from src.benchmark.metrics.timeliness import DecisionTimelinessMetric
from src.benchmark.models import (
    BenchmarkScenario,
    EvaluationRun,
)

# =============================================================================
# Constants
# =============================================================================

DIMENSIONS = [
    "situational_accuracy",
    "decision_timeliness",
    "resource_efficiency",
    "coordination_quality",
    "communication_appropriateness",
]

DEFAULT_WEIGHTS: dict[str, float] = {
    "situational_accuracy": 0.20,
    "decision_timeliness": 0.20,
    "resource_efficiency": 0.20,
    "coordination_quality": 0.20,
    "communication_appropriateness": 0.20,
}

# =============================================================================
# Models
# =============================================================================


class AggregateDRSResult(BaseModel):
    """Complete aggregate DRS result with per-dimension breakdown."""

    dimension_scores: dict[str, float] = Field(default_factory=dict)
    weights: dict[str, float] = Field(default_factory=dict)
    weighted_sum: float = Field(..., ge=0.0)
    drs: float = Field(..., ge=0.0, le=1.0)


class PassAtKResult(BaseModel):
    """pass@k reliability statistics from multiple runs."""

    k: int = Field(..., ge=0)
    best: float = Field(..., ge=0.0, le=1.0)
    mean: float = Field(..., ge=0.0, le=1.0)
    std_dev: float = Field(..., ge=0.0)
    pass_rate: float = Field(..., ge=0.0, le=1.0)


# =============================================================================
# Weight Validation
# =============================================================================


def validate_weights(weights: dict[str, float]) -> bool:
    """Validate that weights cover all 5 dimensions and sum to 1.0.

    Returns True if valid, False otherwise. Tolerance of 0.01.
    """
    if set(weights.keys()) != set(DIMENSIONS):
        return False
    if any(v < 0.0 for v in weights.values()):
        return False
    return abs(sum(weights.values()) - 1.0) <= 0.01


# =============================================================================
# DRS Computation
# =============================================================================


def compute_weighted_drs(
    scores: dict[str, float],
    weights: dict[str, float],
) -> float:
    """Compute weighted DRS from dimension scores.

    Missing dimensions are treated as 1.0 (worst score).
    DRS = weighted_sum / 5.0, normalized to 0.0-1.0.

    Args:
        scores: dimension name -> score (1.0-5.0)
        weights: dimension name -> weight (sum to 1.0)

    Returns:
        DRS value in [0.0, 1.0]
    """
    weighted_sum = 0.0
    for dim in DIMENSIONS:
        dim_score = scores.get(dim, 1.0)  # Default to worst
        dim_weight = weights.get(dim, 0.0)
        weighted_sum += dim_score * dim_weight

    drs = weighted_sum / 5.0
    return round(max(0.0, min(1.0, drs)), 4)


# =============================================================================
# pass@k
# =============================================================================


def pass_at_k(
    drs_scores: list[float],
    threshold: float = 0.5,
) -> PassAtKResult:
    """Compute pass@k reliability statistics from multiple DRS scores.

    Args:
        drs_scores: list of DRS values from k runs
        threshold: minimum DRS to count as "pass"

    Returns:
        PassAtKResult with best, mean, std_dev, pass_rate
    """
    k = len(drs_scores)
    if k == 0:
        return PassAtKResult(k=0, best=0.0, mean=0.0, std_dev=0.0, pass_rate=0.0)

    best = max(drs_scores)
    mean = sum(drs_scores) / k

    if k == 1:
        std_dev = 0.0
    else:
        variance = sum((s - mean) ** 2 for s in drs_scores) / k
        std_dev = math.sqrt(variance)

    passing = sum(1 for s in drs_scores if s >= threshold)
    pass_rate = passing / k

    return PassAtKResult(
        k=k,
        best=round(best, 4),
        mean=round(mean, 4),
        std_dev=round(std_dev, 4),
        pass_rate=round(pass_rate, 4),
    )


# =============================================================================
# Metric Class
# =============================================================================


class AggregateDRSMetric:
    """Computes aggregate DRS by orchestrating all 5 individual metrics.

    Calls each metric's compute() method, extracts the score, and
    combines them with configurable weights.
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        similarity_threshold: float = 0.5,
        late_penalty_factor: float = 2.0,
    ) -> None:
        self._custom_weights = weights
        self._situational = SituationalAccuracyMetric(
            similarity_threshold=similarity_threshold,
        )
        self._timeliness = DecisionTimelinessMetric(
            late_penalty_factor=late_penalty_factor,
        )
        self._resource = ResourceEfficiencyMetric()
        self._coordination = CoordinationQualityMetric()
        self._communication = CommunicationAppropriatenessMetric()

    def _resolve_weights(self, scenario: BenchmarkScenario) -> dict[str, float]:
        """Resolve weights: custom > rubric > default."""
        if self._custom_weights is not None:
            return self._custom_weights

        rubric = scenario.evaluation_rubric
        if rubric is not None:
            return {
                "situational_accuracy": rubric.situational_accuracy.weight,
                "decision_timeliness": rubric.decision_timeliness.weight,
                "resource_efficiency": rubric.resource_efficiency.weight,
                "coordination_quality": rubric.coordination_quality.weight,
                "communication_appropriateness": (
                    rubric.communication_appropriateness.weight
                ),
            }

        return dict(DEFAULT_WEIGHTS)

    async def compute(
        self,
        scenario: BenchmarkScenario,
        evaluation_run: EvaluationRun,
    ) -> AggregateDRSResult:
        """Compute aggregate DRS for a single benchmark run."""
        # Run all 5 metrics
        sit_result = await self._situational.compute(scenario, evaluation_run)
        time_result = await self._timeliness.compute(scenario, evaluation_run)
        res_result = await self._resource.compute(scenario, evaluation_run)
        coord_result = await self._coordination.compute(scenario, evaluation_run)
        comm_result = await self._communication.compute(scenario, evaluation_run)

        # Collect scores
        dimension_scores = {
            "situational_accuracy": sit_result.score,
            "decision_timeliness": time_result.score,
            "resource_efficiency": res_result.score,
            "coordination_quality": coord_result.score,
            "communication_appropriateness": comm_result.score,
        }

        # Resolve weights
        weights = self._resolve_weights(scenario)

        # Compute DRS
        drs = compute_weighted_drs(dimension_scores, weights)
        weighted_sum = sum(
            dimension_scores.get(d, 1.0) * weights.get(d, 0.0) for d in DIMENSIONS
        )

        return AggregateDRSResult(
            dimension_scores=dimension_scores,
            weights=weights,
            weighted_sum=round(weighted_sum, 4),
            drs=drs,
        )

    async def compute_batch(
        self,
        scenario: BenchmarkScenario,
        runs: list[EvaluationRun],
    ) -> list[AggregateDRSResult]:
        """Compute aggregate DRS for multiple runs of the same scenario."""
        results = []
        for run in runs:
            result = await self.compute(scenario, run)
            results.append(result)
        return results


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "DIMENSIONS",
    "DEFAULT_WEIGHTS",
    "AggregateDRSMetric",
    "AggregateDRSResult",
    "PassAtKResult",
    "compute_weighted_drs",
    "pass_at_k",
    "validate_weights",
]
