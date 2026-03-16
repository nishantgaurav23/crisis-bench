"""Resource Efficiency metric for CRISIS-BENCH (spec S8.7).

Computes optimality gap by comparing agent resource allocation decisions
against OR-Tools baseline from ground truth. Evaluates utilization ratio,
demand coverage, routing efficiency, and waste.

Maps a composite score to 1.0-5.0 using linear interpolation between bands.
"""

from __future__ import annotations

import re
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


class AllocationEntry(BaseModel):
    """A single resource allocation decision."""

    resource_type: str
    source: str
    destination: str
    quantity: int = Field(..., ge=0)
    distance_km: float = Field(..., ge=0.0)


class ResourceEfficiencyResult(BaseModel):
    """Complete resource efficiency evaluation result."""

    utilization_ratio: float = Field(..., ge=0.0, le=1.0)
    coverage_score: float = Field(..., ge=0.0, le=1.0)
    optimality_gap: float = Field(..., ge=0.0)
    waste_ratio: float = Field(..., ge=0.0, le=1.0)
    component_scores: dict[str, float] = Field(default_factory=dict)
    score: float = Field(..., ge=1.0, le=5.0)


# =============================================================================
# Extraction
# =============================================================================

_KV_RE = re.compile(r"^(\w+)=(.+)$")


def extract_allocations_from_decisions(
    decisions: list[dict[str, Any]],
) -> tuple[list[AllocationEntry], dict[str, Any]]:
    """Extract allocation entries and stats from agent decisions.

    Looks for decisions from the 'resource_allocation' agent and parses
    the 'allocations' list and summary stats.

    Returns (allocations, stats) where stats contains total_allocated,
    total_available, total_demand, covered_demand, total_distance_km.
    """
    default_stats: dict[str, Any] = {
        "total_allocated": 0,
        "total_available": 0,
        "total_demand": 0,
        "covered_demand": 0,
        "total_distance_km": 0.0,
    }

    for decision in decisions:
        if decision.get("agent_id") != "resource_allocation":
            continue

        alloc_data = decision.get("allocations", [])
        entries = []
        for item in alloc_data:
            try:
                entries.append(AllocationEntry(**item))
            except (TypeError, ValueError):
                continue

        stats = {
            "total_allocated": decision.get("total_allocated", 0),
            "total_available": decision.get("total_available", 0),
            "total_demand": decision.get("total_demand", 0),
            "covered_demand": decision.get("covered_demand", 0),
            "total_distance_km": decision.get("total_distance_km", 0.0),
        }
        return entries, stats

    return [], default_stats


def extract_optimal_baseline(
    ground_truth: GroundTruthDecisions,
) -> dict[str, float | None]:
    """Extract OR-Tools optimal baseline from ground truth key_observations.

    Parses key=value pairs like 'optimal_total_distance_km=120.5'.
    """
    result: dict[str, float | None] = {
        "optimal_total_distance_km": None,
        "optimal_coverage_pct": None,
        "optimal_utilization_pct": None,
    }

    ra_expectation = ground_truth.agent_expectations.get("resource_allocation")
    if ra_expectation is None:
        return result

    for obs in ra_expectation.key_observations:
        match = _KV_RE.match(obs.strip())
        if match:
            key, val = match.group(1), match.group(2)
            if key in result:
                try:
                    result[key] = float(val)
                except ValueError:
                    pass

    return result


# =============================================================================
# Component Computations
# =============================================================================


def compute_utilization_ratio(allocated: int, available: int) -> float:
    """Compute resource utilization as allocated / available, clamped to [0, 1]."""
    if available <= 0:
        return 0.0
    return min(1.0, allocated / available)


def compute_coverage_score(covered_demand: int, total_demand: int) -> float:
    """Compute demand coverage as covered / total, clamped to [0, 1]."""
    if total_demand <= 0:
        return 0.0
    return min(1.0, covered_demand / total_demand)


def compute_optimality_gap(
    agent_distance: float,
    optimal_distance: float,
) -> float:
    """Compute optimality gap as (agent - optimal) / optimal.

    Returns 0.0 if agent is better than or equal to optimal,
    or if optimal distance is zero.
    """
    if optimal_distance <= 0.0:
        return 0.0
    gap = (agent_distance - optimal_distance) / optimal_distance
    return max(0.0, gap)


def compute_waste_ratio(
    allocated: int,
    covered_demand: int,
    total_demand: int,
) -> float:
    """Compute waste ratio based on how effectively allocated resources cover demand.

    If resources are allocated but don't cover demand, that's waste.
    waste = 1 - (covered_demand / total_demand) when resources are allocated.
    """
    if allocated <= 0:
        return 0.0
    if total_demand <= 0:
        return 0.0
    coverage = min(1.0, covered_demand / total_demand)
    return round(1.0 - coverage, 4)


# =============================================================================
# Gap-to-Score Mapping
# =============================================================================

# Bands: (gap_lower, gap_upper, score_upper, score_lower)
# Note: higher gap = lower score (inverse of F1 mapping)
_SCORE_BANDS: list[tuple[float, float, float, float]] = [
    (0.00, 0.05, 5.0, 5.0),
    (0.05, 0.15, 5.0, 4.0),
    (0.15, 0.30, 4.0, 3.0),
    (0.30, 0.50, 3.0, 2.0),
    (0.50, 1.00, 2.0, 1.0),
]


def gap_to_score(gap: float) -> float:
    """Map optimality gap (0.0+) to score (1.0-5.0) with linear interpolation.

    Lower gap = higher score (inverse relationship).
    """
    gap = max(0.0, gap)

    if gap <= 0.0:
        return 5.0

    for gap_lo, gap_hi, score_hi, score_lo in _SCORE_BANDS:
        if gap <= gap_hi:
            if gap_hi == gap_lo:
                return score_hi
            t = (gap - gap_lo) / (gap_hi - gap_lo)
            return round(score_hi - t * (score_hi - score_lo), 2)

    return 1.0


# =============================================================================
# Composite Score
# =============================================================================

# Weights for combining components into final score
_WEIGHTS = {
    "utilization": 0.20,
    "coverage": 0.30,
    "optimality": 0.35,
    "waste": 0.15,
}


def compute_composite_score(
    utilization_ratio: float,
    coverage_score: float,
    optimality_gap: float,
    waste_ratio: float,
) -> float:
    """Compute weighted composite score from components.

    Each component is mapped to a 1.0-5.0 sub-score, then combined
    with weights.
    """
    # Map each component to 1-5 score
    # Utilization: 0.0 -> 1.0, 1.0 -> 5.0 (linear)
    util_score = 1.0 + utilization_ratio * 4.0

    # Coverage: 0.0 -> 1.0, 1.0 -> 5.0 (linear)
    cov_score = 1.0 + coverage_score * 4.0

    # Optimality: use gap_to_score
    opt_score = gap_to_score(optimality_gap)

    # Waste: 0.0 -> 5.0, 1.0 -> 1.0 (inverse linear)
    waste_score = 5.0 - waste_ratio * 4.0

    composite = (
        _WEIGHTS["utilization"] * util_score
        + _WEIGHTS["coverage"] * cov_score
        + _WEIGHTS["optimality"] * opt_score
        + _WEIGHTS["waste"] * waste_score
    )

    return round(max(1.0, min(5.0, composite)), 2)


# =============================================================================
# Metric Class
# =============================================================================


class ResourceEfficiencyMetric:
    """Computes resource efficiency as optimality gap vs OR-Tools baseline.

    Compares agent resource allocation decisions against ground truth
    optimal allocations. Evaluates utilization, coverage, routing
    efficiency, and waste.
    """

    async def compute(
        self,
        scenario: BenchmarkScenario,
        evaluation_run: EvaluationRun,
    ) -> ResourceEfficiencyResult:
        """Compute resource efficiency for a benchmark run."""
        # Extract agent allocation data
        allocs, stats = extract_allocations_from_decisions(
            evaluation_run.agent_decisions,
        )

        # Extract OR-Tools baseline from ground truth
        baseline = extract_optimal_baseline(scenario.ground_truth_decisions)

        # Compute components
        util_ratio = compute_utilization_ratio(
            stats["total_allocated"],
            stats["total_available"],
        )

        cov_score = compute_coverage_score(
            stats["covered_demand"],
            stats["total_demand"],
        )

        # Optimality gap — compare agent distance vs optimal
        optimal_dist = baseline.get("optimal_total_distance_km")
        if optimal_dist is not None and optimal_dist > 0:
            opt_gap = compute_optimality_gap(
                stats["total_distance_km"], optimal_dist,
            )
        else:
            # No baseline available — estimate from coverage/utilization
            opt_gap = max(0.0, 1.0 - (cov_score + util_ratio) / 2.0)

        waste = compute_waste_ratio(
            stats["total_allocated"],
            stats["covered_demand"],
            stats["total_demand"],
        )

        # Compute composite score
        score = compute_composite_score(util_ratio, cov_score, opt_gap, waste)

        component_scores = {
            "utilization": round(1.0 + util_ratio * 4.0, 2),
            "coverage": round(1.0 + cov_score * 4.0, 2),
            "optimality": gap_to_score(opt_gap),
            "waste": round(5.0 - waste * 4.0, 2),
        }

        return ResourceEfficiencyResult(
            utilization_ratio=round(util_ratio, 4),
            coverage_score=round(cov_score, 4),
            optimality_gap=round(opt_gap, 4),
            waste_ratio=round(waste, 4),
            component_scores=component_scores,
            score=score,
        )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "AllocationEntry",
    "ResourceEfficiencyMetric",
    "ResourceEfficiencyResult",
    "compute_composite_score",
    "compute_coverage_score",
    "compute_optimality_gap",
    "compute_utilization_ratio",
    "compute_waste_ratio",
    "extract_allocations_from_decisions",
    "extract_optimal_baseline",
    "gap_to_score",
]
