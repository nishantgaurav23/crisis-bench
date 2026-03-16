"""Tests for Aggregate DRS metric (spec S8.10).

Tests the weighted combination of 5 dimension scores into a single
Disaster Response Score (DRS), plus pass@k reliability measurement.
"""

from __future__ import annotations

import math
import uuid

import pytest

from src.benchmark.metrics.aggregate import (
    AggregateDRSMetric,
    AggregateDRSResult,
    PassAtKResult,
    compute_weighted_drs,
    pass_at_k,
    validate_weights,
)
from src.benchmark.models import (
    AgentExpectation,
    BenchmarkScenario,
    DimensionCriteria,
    EvaluationRubric,
    EvaluationRun,
    GroundTruthDecisions,
)

# =============================================================================
# Fixtures
# =============================================================================

DEFAULT_WEIGHTS = {
    "situational_accuracy": 0.20,
    "decision_timeliness": 0.20,
    "resource_efficiency": 0.20,
    "coordination_quality": 0.20,
    "communication_appropriateness": 0.20,
}

CUSTOM_WEIGHTS = {
    "situational_accuracy": 0.30,
    "decision_timeliness": 0.25,
    "resource_efficiency": 0.20,
    "coordination_quality": 0.15,
    "communication_appropriateness": 0.10,
}


def _make_scenario(
    rubric: EvaluationRubric | None = None,
) -> BenchmarkScenario:
    gt = GroundTruthDecisions(
        agent_expectations={
            "situation_sense": AgentExpectation(
                key_observations=["flood detected"],
                expected_actions=["report flood"],
                time_window_minutes=(0, 30),
            ),
        },
        decision_timeline={"initial_assessment": "15"},
        ndma_references=["NDMA-FLOOD-SOP"],
    )
    return BenchmarkScenario(
        id=uuid.uuid4(),
        category="flood",
        complexity="medium",
        affected_states=["Bihar"],
        event_sequence=[],
        ground_truth_decisions=gt,
        evaluation_rubric=rubric,
    )


def _make_run(scenario_id: uuid.UUID) -> EvaluationRun:
    return EvaluationRun(
        id=uuid.uuid4(),
        scenario_id=scenario_id,
        agent_decisions=[
            {
                "agent_id": "situation_sense",
                "observations": ["flood detected in patna"],
                "reasoning": "heavy rainfall reported",
                "simulated_elapsed_minutes": 10.0,
                "messages_sent": [],
            },
        ],
    )


# =============================================================================
# Tests — validate_weights
# =============================================================================


class TestValidateWeights:
    def test_valid_default_weights(self):
        assert validate_weights(DEFAULT_WEIGHTS) is True

    def test_valid_custom_weights(self):
        assert validate_weights(CUSTOM_WEIGHTS) is True

    def test_invalid_weights_wrong_sum(self):
        bad = {**DEFAULT_WEIGHTS, "situational_accuracy": 0.50}
        assert validate_weights(bad) is False

    def test_invalid_weights_negative(self):
        bad = {**DEFAULT_WEIGHTS, "situational_accuracy": -0.10}
        assert validate_weights(bad) is False

    def test_invalid_weights_missing_dimension(self):
        incomplete = {k: v for k, v in DEFAULT_WEIGHTS.items() if k != "coordination_quality"}
        assert validate_weights(incomplete) is False

    def test_tolerance(self):
        """Weights within 0.01 tolerance should pass."""
        close = {
            "situational_accuracy": 0.201,
            "decision_timeliness": 0.199,
            "resource_efficiency": 0.200,
            "coordination_quality": 0.200,
            "communication_appropriateness": 0.200,
        }
        assert validate_weights(close) is True


# =============================================================================
# Tests — compute_weighted_drs
# =============================================================================


class TestComputeWeightedDRS:
    def test_perfect_scores(self):
        scores = {
            "situational_accuracy": 5.0,
            "decision_timeliness": 5.0,
            "resource_efficiency": 5.0,
            "coordination_quality": 5.0,
            "communication_appropriateness": 5.0,
        }
        drs = compute_weighted_drs(scores, DEFAULT_WEIGHTS)
        assert drs == 1.0

    def test_worst_scores(self):
        scores = {
            "situational_accuracy": 1.0,
            "decision_timeliness": 1.0,
            "resource_efficiency": 1.0,
            "coordination_quality": 1.0,
            "communication_appropriateness": 1.0,
        }
        drs = compute_weighted_drs(scores, DEFAULT_WEIGHTS)
        assert drs == 0.2

    def test_mixed_scores_equal_weights(self):
        scores = {
            "situational_accuracy": 5.0,
            "decision_timeliness": 3.0,
            "resource_efficiency": 4.0,
            "coordination_quality": 2.0,
            "communication_appropriateness": 1.0,
        }
        # weighted_sum = (5*0.2 + 3*0.2 + 4*0.2 + 2*0.2 + 1*0.2) = 3.0
        # DRS = 3.0 / 5.0 = 0.6
        drs = compute_weighted_drs(scores, DEFAULT_WEIGHTS)
        assert drs == 0.6

    def test_mixed_scores_custom_weights(self):
        scores = {
            "situational_accuracy": 5.0,
            "decision_timeliness": 3.0,
            "resource_efficiency": 4.0,
            "coordination_quality": 2.0,
            "communication_appropriateness": 1.0,
        }
        # weighted_sum = 5*0.3 + 3*0.25 + 4*0.2 + 2*0.15 + 1*0.10
        # = 1.5 + 0.75 + 0.8 + 0.3 + 0.1 = 3.45
        # DRS = 3.45 / 5.0 = 0.69
        drs = compute_weighted_drs(scores, CUSTOM_WEIGHTS)
        assert drs == 0.69

    def test_missing_dimension_uses_minimum(self):
        scores = {
            "situational_accuracy": 5.0,
            "decision_timeliness": 3.0,
            # resource_efficiency missing
            "coordination_quality": 4.0,
            "communication_appropriateness": 4.0,
        }
        # Missing dimension should be treated as 1.0 (worst)
        drs = compute_weighted_drs(scores, DEFAULT_WEIGHTS)
        # weighted = (5*0.2 + 3*0.2 + 1*0.2 + 4*0.2 + 4*0.2) = 3.4
        # DRS = 3.4 / 5.0 = 0.68
        assert drs == 0.68

    def test_empty_scores(self):
        drs = compute_weighted_drs({}, DEFAULT_WEIGHTS)
        # All dimensions treated as 1.0 → DRS = 0.2
        assert drs == 0.2


# =============================================================================
# Tests — pass_at_k
# =============================================================================


class TestPassAtK:
    def test_single_score(self):
        result = pass_at_k([0.75])
        assert result.k == 1
        assert result.best == 0.75
        assert result.mean == 0.75
        assert result.std_dev == 0.0
        assert result.pass_rate == 1.0  # default threshold 0.5

    def test_multiple_scores(self):
        result = pass_at_k([0.6, 0.8, 0.7])
        assert result.k == 3
        assert result.best == 0.8
        assert abs(result.mean - 0.7) < 0.0001
        assert result.pass_rate == 1.0  # all above 0.5

    def test_custom_threshold(self):
        result = pass_at_k([0.3, 0.6, 0.8], threshold=0.5)
        assert result.k == 3
        assert result.best == 0.8
        assert result.pass_rate == pytest.approx(2.0 / 3.0, abs=0.01)

    def test_all_below_threshold(self):
        result = pass_at_k([0.1, 0.2, 0.3], threshold=0.5)
        assert result.pass_rate == 0.0

    def test_empty_scores(self):
        result = pass_at_k([])
        assert result.k == 0
        assert result.best == 0.0
        assert result.mean == 0.0
        assert result.std_dev == 0.0
        assert result.pass_rate == 0.0

    def test_std_dev_computation(self):
        result = pass_at_k([0.2, 0.4, 0.6, 0.8])
        # mean = 0.5, deviations = [-0.3, -0.1, 0.1, 0.3]
        # variance = (0.09+0.01+0.01+0.09)/4 = 0.05
        # std = sqrt(0.05) ≈ 0.2236
        assert abs(result.std_dev - math.sqrt(0.05)) < 0.001

    def test_identical_scores(self):
        result = pass_at_k([0.7, 0.7, 0.7])
        assert result.best == 0.7
        assert result.mean == 0.7
        assert result.std_dev == 0.0
        assert result.pass_rate == 1.0


# =============================================================================
# Tests — AggregateDRSResult model
# =============================================================================


class TestAggregateDRSResult:
    def test_valid_result(self):
        result = AggregateDRSResult(
            dimension_scores={
                "situational_accuracy": 4.5,
                "decision_timeliness": 3.8,
                "resource_efficiency": 4.0,
                "coordination_quality": 3.5,
                "communication_appropriateness": 4.2,
            },
            weights=DEFAULT_WEIGHTS,
            weighted_sum=4.0,
            drs=0.80,
        )
        assert result.drs == 0.80
        assert len(result.dimension_scores) == 5

    def test_drs_bounds(self):
        result = AggregateDRSResult(
            dimension_scores={},
            weights=DEFAULT_WEIGHTS,
            weighted_sum=1.0,
            drs=0.2,
        )
        assert 0.0 <= result.drs <= 1.0


# =============================================================================
# Tests — AggregateDRSMetric.compute()
# =============================================================================


class TestAggregateDRSMetric:
    @pytest.mark.asyncio
    async def test_compute_with_default_weights(self):
        scenario = _make_scenario()
        run = _make_run(scenario.id)

        metric = AggregateDRSMetric()
        result = await metric.compute(scenario, run)

        assert isinstance(result, AggregateDRSResult)
        assert 0.0 <= result.drs <= 1.0
        assert len(result.dimension_scores) == 5

    @pytest.mark.asyncio
    async def test_compute_with_rubric_weights(self):
        rubric = EvaluationRubric(
            situational_accuracy=DimensionCriteria(
                weight=0.30, criteria={}, key_factors=[],
            ),
            decision_timeliness=DimensionCriteria(
                weight=0.25, criteria={}, key_factors=[],
            ),
            resource_efficiency=DimensionCriteria(
                weight=0.20, criteria={}, key_factors=[],
            ),
            coordination_quality=DimensionCriteria(
                weight=0.15, criteria={}, key_factors=[],
            ),
            communication_appropriateness=DimensionCriteria(
                weight=0.10, criteria={}, key_factors=[],
            ),
        )
        scenario = _make_scenario(rubric=rubric)
        run = _make_run(scenario.id)

        metric = AggregateDRSMetric()
        result = await metric.compute(scenario, run)

        assert result.weights["situational_accuracy"] == 0.30
        assert result.weights["communication_appropriateness"] == 0.10

    @pytest.mark.asyncio
    async def test_compute_with_custom_weights(self):
        scenario = _make_scenario()
        run = _make_run(scenario.id)

        metric = AggregateDRSMetric(weights=CUSTOM_WEIGHTS)
        result = await metric.compute(scenario, run)

        assert result.weights == CUSTOM_WEIGHTS

    @pytest.mark.asyncio
    async def test_compute_batch(self):
        scenario = _make_scenario()
        runs = [_make_run(scenario.id) for _ in range(3)]

        metric = AggregateDRSMetric()
        results = await metric.compute_batch(scenario, runs)

        assert len(results) == 3
        for r in results:
            assert isinstance(r, AggregateDRSResult)

    @pytest.mark.asyncio
    async def test_compute_batch_with_pass_at_k(self):
        scenario = _make_scenario()
        runs = [_make_run(scenario.id) for _ in range(3)]

        metric = AggregateDRSMetric()
        results = await metric.compute_batch(scenario, runs)
        drs_scores = [r.drs for r in results]

        pak = pass_at_k(drs_scores)
        assert pak.k == 3
        assert pak.best == max(drs_scores)


# =============================================================================
# Tests — PassAtKResult model
# =============================================================================


class TestPassAtKResult:
    def test_valid_result(self):
        result = PassAtKResult(
            k=5, best=0.9, mean=0.75, std_dev=0.1, pass_rate=0.8,
        )
        assert result.k == 5
        assert result.best == 0.9
