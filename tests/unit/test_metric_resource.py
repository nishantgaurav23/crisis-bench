"""Unit tests for the Resource Efficiency metric (spec S8.7).

Tests optimality gap computation comparing agent resource allocation
decisions against OR-Tools baseline. All tests are pure computation
— no external APIs.
"""

from __future__ import annotations

import uuid

import pytest

from src.benchmark.models import (
    AgentExpectation,
    BenchmarkScenario,
    EvaluationRun,
    GroundTruthDecisions,
    ScenarioEvent,
)
from src.shared.models import DisasterPhase

# =============================================================================
# Helpers
# =============================================================================


def _make_scenario(
    agent_expectations: dict[str, AgentExpectation] | None = None,
) -> BenchmarkScenario:
    if agent_expectations is None:
        agent_expectations = {
            "resource_allocation": AgentExpectation(
                key_observations=[
                    "optimal_total_distance_km=120.5",
                    "optimal_coverage_pct=0.95",
                    "optimal_utilization_pct=0.85",
                ],
                expected_actions=[
                    "Deploy 4 NDRF battalions to Puri",
                    "Assign 3 shelters in Khordha",
                    "Route supplies via NH-16",
                ],
                time_window_minutes=(0, 30),
            ),
        }
    return BenchmarkScenario(
        category="cyclone",
        complexity="high",
        affected_states=["Odisha"],
        event_sequence=[
            ScenarioEvent(
                time_offset_minutes=0,
                phase=DisasterPhase.ACTIVE_RESPONSE,
                event_type="sachet_alert",
                description="SACHET alert for cyclone",
            ),
        ],
        ground_truth_decisions=GroundTruthDecisions(
            agent_expectations=agent_expectations,
            decision_timeline={"t0": "Alert received"},
            ndma_references=["NDMA-CYC-01"],
        ),
    )


def _make_run(
    scenario_id: uuid.UUID,
    agent_decisions: list[dict] | None = None,
) -> EvaluationRun:
    if agent_decisions is None:
        agent_decisions = [
            {
                "agent_id": "resource_allocation",
                "allocations": [
                    {
                        "resource_type": "ndrf_battalion",
                        "source": "Bhubaneswar",
                        "destination": "Puri",
                        "quantity": 3,
                        "distance_km": 60.0,
                    },
                    {
                        "resource_type": "shelter",
                        "source": "Khordha_shelters",
                        "destination": "Khordha",
                        "quantity": 2,
                        "distance_km": 15.0,
                    },
                ],
                "total_allocated": 5,
                "total_available": 8,
                "total_demand": 50000,
                "covered_demand": 42000,
                "total_distance_km": 135.0,
                "reasoning": "Deployed battalions to most affected coastal areas",
            },
        ]
    return EvaluationRun(
        scenario_id=scenario_id,
        agent_config={"acceleration": 5.0},
        agent_decisions=agent_decisions,
    )


# =============================================================================
# Test Group 1: Pydantic Models
# =============================================================================


class TestModels:
    """Tests for metric-specific Pydantic models."""

    def test_allocation_entry_valid(self):
        from src.benchmark.metrics.resource import AllocationEntry

        entry = AllocationEntry(
            resource_type="ndrf_battalion",
            source="Bhubaneswar",
            destination="Puri",
            quantity=4,
            distance_km=60.0,
        )
        assert entry.resource_type == "ndrf_battalion"
        assert entry.quantity == 4
        assert entry.distance_km == 60.0

    def test_allocation_entry_quantity_must_be_positive(self):
        from src.benchmark.metrics.resource import AllocationEntry

        with pytest.raises(ValueError):
            AllocationEntry(
                resource_type="ndrf_battalion",
                source="A",
                destination="B",
                quantity=-1,
                distance_km=10.0,
            )

    def test_allocation_entry_distance_non_negative(self):
        from src.benchmark.metrics.resource import AllocationEntry

        entry = AllocationEntry(
            resource_type="shelter",
            source="A",
            destination="B",
            quantity=1,
            distance_km=0.0,
        )
        assert entry.distance_km == 0.0

        with pytest.raises(ValueError):
            AllocationEntry(
                resource_type="shelter",
                source="A",
                destination="B",
                quantity=1,
                distance_km=-5.0,
            )

    def test_resource_efficiency_result_valid(self):
        from src.benchmark.metrics.resource import ResourceEfficiencyResult

        result = ResourceEfficiencyResult(
            utilization_ratio=0.75,
            coverage_score=0.85,
            optimality_gap=0.12,
            waste_ratio=0.05,
            component_scores={
                "utilization": 4.2,
                "coverage": 4.5,
                "optimality": 3.8,
            },
            score=4.1,
        )
        assert result.utilization_ratio == 0.75
        assert result.score == 4.1

    def test_resource_efficiency_result_bounds(self):
        from src.benchmark.metrics.resource import ResourceEfficiencyResult

        with pytest.raises(ValueError):
            ResourceEfficiencyResult(
                utilization_ratio=1.5,  # Out of range
                coverage_score=0.5,
                optimality_gap=0.1,
                waste_ratio=0.0,
                component_scores={},
                score=3.0,
            )

        with pytest.raises(ValueError):
            ResourceEfficiencyResult(
                utilization_ratio=0.5,
                coverage_score=0.5,
                optimality_gap=0.1,
                waste_ratio=0.0,
                component_scores={},
                score=6.0,  # Out of range
            )


# =============================================================================
# Test Group 2: Extraction
# =============================================================================


class TestExtraction:
    """Tests for extracting allocation data from decisions and ground truth."""

    def test_extract_allocations_from_decisions(self):
        from src.benchmark.metrics.resource import extract_allocations_from_decisions

        scenario = _make_scenario()
        run = _make_run(scenario.id)
        allocs, stats = extract_allocations_from_decisions(run.agent_decisions)

        assert len(allocs) == 2
        assert allocs[0].resource_type == "ndrf_battalion"
        assert stats["total_allocated"] == 5
        assert stats["total_available"] == 8
        assert stats["total_demand"] == 50000
        assert stats["covered_demand"] == 42000
        assert stats["total_distance_km"] == 135.0

    def test_extract_allocations_empty_decisions(self):
        from src.benchmark.metrics.resource import extract_allocations_from_decisions

        allocs, stats = extract_allocations_from_decisions([])
        assert allocs == []
        assert stats["total_allocated"] == 0

    def test_extract_allocations_no_resource_agent(self):
        from src.benchmark.metrics.resource import extract_allocations_from_decisions

        decisions = [
            {"agent_id": "situation_sense", "observations": ["something"]},
        ]
        allocs, stats = extract_allocations_from_decisions(decisions)
        assert allocs == []

    def test_extract_optimal_baseline(self):
        from src.benchmark.metrics.resource import extract_optimal_baseline

        scenario = _make_scenario()
        baseline = extract_optimal_baseline(scenario.ground_truth_decisions)

        assert baseline["optimal_total_distance_km"] == pytest.approx(120.5)
        assert baseline["optimal_coverage_pct"] == pytest.approx(0.95)
        assert baseline["optimal_utilization_pct"] == pytest.approx(0.85)

    def test_extract_optimal_baseline_missing(self):
        from src.benchmark.metrics.resource import extract_optimal_baseline

        gt = GroundTruthDecisions(agent_expectations={})
        baseline = extract_optimal_baseline(gt)

        assert baseline["optimal_total_distance_km"] is None
        assert baseline["optimal_coverage_pct"] is None
        assert baseline["optimal_utilization_pct"] is None


# =============================================================================
# Test Group 3: Utilization Ratio
# =============================================================================


class TestUtilizationRatio:
    """Tests for utilization ratio computation."""

    def test_full_utilization(self):
        from src.benchmark.metrics.resource import compute_utilization_ratio

        assert compute_utilization_ratio(10, 10) == 1.0

    def test_partial_utilization(self):
        from src.benchmark.metrics.resource import compute_utilization_ratio

        assert compute_utilization_ratio(5, 10) == 0.5

    def test_zero_available(self):
        from src.benchmark.metrics.resource import compute_utilization_ratio

        assert compute_utilization_ratio(0, 0) == 0.0

    def test_over_allocation_clamped(self):
        from src.benchmark.metrics.resource import compute_utilization_ratio

        # If agent allocates more than available, clamp to 1.0
        assert compute_utilization_ratio(15, 10) == 1.0


# =============================================================================
# Test Group 4: Coverage Score
# =============================================================================


class TestCoverageScore:
    """Tests for demand coverage computation."""

    def test_full_coverage(self):
        from src.benchmark.metrics.resource import compute_coverage_score

        assert compute_coverage_score(50000, 50000) == 1.0

    def test_partial_coverage(self):
        from src.benchmark.metrics.resource import compute_coverage_score

        assert compute_coverage_score(25000, 50000) == 0.5

    def test_zero_demand(self):
        from src.benchmark.metrics.resource import compute_coverage_score

        assert compute_coverage_score(0, 0) == 0.0

    def test_over_coverage_clamped(self):
        from src.benchmark.metrics.resource import compute_coverage_score

        # More covered than demanded — clamp to 1.0
        assert compute_coverage_score(60000, 50000) == 1.0


# =============================================================================
# Test Group 5: Optimality Gap
# =============================================================================


class TestOptimalityGap:
    """Tests for optimality gap computation."""

    def test_perfect_match(self):
        from src.benchmark.metrics.resource import compute_optimality_gap

        gap = compute_optimality_gap(
            agent_distance=120.0,
            optimal_distance=120.0,
        )
        assert gap == 0.0

    def test_agent_worse(self):
        from src.benchmark.metrics.resource import compute_optimality_gap

        gap = compute_optimality_gap(
            agent_distance=180.0,
            optimal_distance=120.0,
        )
        assert gap == pytest.approx(0.5, abs=0.01)

    def test_agent_better_than_baseline(self):
        from src.benchmark.metrics.resource import compute_optimality_gap

        # Agent somehow found a shorter route — gap should be 0
        gap = compute_optimality_gap(
            agent_distance=100.0,
            optimal_distance=120.0,
        )
        assert gap == 0.0

    def test_zero_optimal_distance(self):
        from src.benchmark.metrics.resource import compute_optimality_gap

        gap = compute_optimality_gap(
            agent_distance=50.0,
            optimal_distance=0.0,
        )
        # Can't compute gap with zero baseline, return 0.0
        assert gap == 0.0

    def test_both_zero(self):
        from src.benchmark.metrics.resource import compute_optimality_gap

        gap = compute_optimality_gap(
            agent_distance=0.0,
            optimal_distance=0.0,
        )
        assert gap == 0.0


# =============================================================================
# Test Group 6: Waste Ratio
# =============================================================================


class TestWasteRatio:
    """Tests for waste ratio computation."""

    def test_no_waste(self):
        from src.benchmark.metrics.resource import compute_waste_ratio

        assert compute_waste_ratio(
            allocated=10, covered_demand=50000, total_demand=50000,
        ) == 0.0

    def test_some_waste(self):
        from src.benchmark.metrics.resource import compute_waste_ratio

        # Allocated 10, but only 5 were needed (coverage < 100% but resources idle)
        ratio = compute_waste_ratio(
            allocated=10, covered_demand=25000, total_demand=50000,
        )
        assert 0.0 < ratio <= 1.0

    def test_zero_allocated(self):
        from src.benchmark.metrics.resource import compute_waste_ratio

        assert compute_waste_ratio(
            allocated=0, covered_demand=0, total_demand=50000,
        ) == 0.0

    def test_full_waste(self):
        from src.benchmark.metrics.resource import compute_waste_ratio

        # Resources allocated but zero demand covered
        ratio = compute_waste_ratio(
            allocated=10, covered_demand=0, total_demand=50000,
        )
        assert ratio == 1.0


# =============================================================================
# Test Group 7: Composite Score
# =============================================================================


class TestCompositeScore:
    """Tests for weighted composite score computation."""

    def test_all_perfect(self):
        from src.benchmark.metrics.resource import compute_composite_score

        score = compute_composite_score(
            utilization_ratio=0.85,
            coverage_score=0.95,
            optimality_gap=0.0,
            waste_ratio=0.0,
        )
        assert score == pytest.approx(5.0, abs=0.3)

    def test_all_worst(self):
        from src.benchmark.metrics.resource import compute_composite_score

        score = compute_composite_score(
            utilization_ratio=0.0,
            coverage_score=0.0,
            optimality_gap=1.0,
            waste_ratio=1.0,
        )
        assert 1.0 <= score <= 2.0

    def test_mixed_performance(self):
        from src.benchmark.metrics.resource import compute_composite_score

        score = compute_composite_score(
            utilization_ratio=0.6,
            coverage_score=0.7,
            optimality_gap=0.2,
            waste_ratio=0.1,
        )
        assert 2.5 <= score <= 4.5


# =============================================================================
# Test Group 8: Gap-to-Score Mapping
# =============================================================================


class TestGapToScore:
    """Tests for mapping optimality gap to 1.0-5.0 score."""

    def test_zero_gap_gives_five(self):
        from src.benchmark.metrics.resource import gap_to_score

        assert gap_to_score(0.0) == 5.0

    def test_small_gap_gives_high_score(self):
        from src.benchmark.metrics.resource import gap_to_score

        score = gap_to_score(0.03)
        assert score == pytest.approx(5.0, abs=0.1)

    def test_gap_0_15_gives_four(self):
        from src.benchmark.metrics.resource import gap_to_score

        score = gap_to_score(0.15)
        assert score == pytest.approx(4.0, abs=0.1)

    def test_gap_0_30_gives_three(self):
        from src.benchmark.metrics.resource import gap_to_score

        score = gap_to_score(0.30)
        assert score == pytest.approx(3.0, abs=0.1)

    def test_gap_0_50_gives_two(self):
        from src.benchmark.metrics.resource import gap_to_score

        score = gap_to_score(0.50)
        assert score == pytest.approx(2.0, abs=0.1)

    def test_large_gap_gives_one(self):
        from src.benchmark.metrics.resource import gap_to_score

        score = gap_to_score(1.0)
        assert score == pytest.approx(1.0, abs=0.1)

    def test_gap_between_bands_interpolates(self):
        from src.benchmark.metrics.resource import gap_to_score

        score = gap_to_score(0.10)
        assert 4.0 < score < 5.0

    def test_negative_gap_clamped(self):
        from src.benchmark.metrics.resource import gap_to_score

        assert gap_to_score(-0.1) == 5.0

    def test_huge_gap_clamped(self):
        from src.benchmark.metrics.resource import gap_to_score

        assert gap_to_score(5.0) >= 1.0


# =============================================================================
# Test Group 9: Full Compute
# =============================================================================


class TestFullCompute:
    """Tests for the complete ResourceEfficiencyMetric.compute()."""

    @pytest.mark.asyncio
    async def test_compute_returns_result(self):
        from src.benchmark.metrics.resource import (
            ResourceEfficiencyMetric,
            ResourceEfficiencyResult,
        )

        metric = ResourceEfficiencyMetric()
        scenario = _make_scenario()
        run = _make_run(scenario.id)

        result = await metric.compute(scenario, run)

        assert isinstance(result, ResourceEfficiencyResult)
        assert 0.0 <= result.utilization_ratio <= 1.0
        assert 0.0 <= result.coverage_score <= 1.0
        assert result.optimality_gap >= 0.0
        assert 0.0 <= result.waste_ratio <= 1.0
        assert 1.0 <= result.score <= 5.0

    @pytest.mark.asyncio
    async def test_compute_with_perfect_allocation(self):
        from src.benchmark.metrics.resource import ResourceEfficiencyMetric

        agent_expectations = {
            "resource_allocation": AgentExpectation(
                key_observations=[
                    "optimal_total_distance_km=100.0",
                    "optimal_coverage_pct=1.0",
                    "optimal_utilization_pct=1.0",
                ],
                expected_actions=["Deploy all resources"],
                time_window_minutes=(0, 30),
            ),
        }
        scenario = _make_scenario(agent_expectations=agent_expectations)
        run = _make_run(
            scenario.id,
            agent_decisions=[
                {
                    "agent_id": "resource_allocation",
                    "allocations": [
                        {
                            "resource_type": "ndrf_battalion",
                            "source": "Base",
                            "destination": "Target",
                            "quantity": 10,
                            "distance_km": 100.0,
                        },
                    ],
                    "total_allocated": 10,
                    "total_available": 10,
                    "total_demand": 50000,
                    "covered_demand": 50000,
                    "total_distance_km": 100.0,
                },
            ],
        )

        metric = ResourceEfficiencyMetric()
        result = await metric.compute(scenario, run)

        assert result.utilization_ratio == 1.0
        assert result.coverage_score == 1.0
        assert result.optimality_gap == 0.0
        assert result.score >= 4.5

    @pytest.mark.asyncio
    async def test_compute_with_poor_allocation(self):
        from src.benchmark.metrics.resource import ResourceEfficiencyMetric

        agent_expectations = {
            "resource_allocation": AgentExpectation(
                key_observations=[
                    "optimal_total_distance_km=100.0",
                    "optimal_coverage_pct=0.95",
                    "optimal_utilization_pct=0.90",
                ],
                expected_actions=["Deploy resources"],
                time_window_minutes=(0, 30),
            ),
        }
        scenario = _make_scenario(agent_expectations=agent_expectations)
        run = _make_run(
            scenario.id,
            agent_decisions=[
                {
                    "agent_id": "resource_allocation",
                    "allocations": [
                        {
                            "resource_type": "ndrf_battalion",
                            "source": "Base",
                            "destination": "Wrong_Target",
                            "quantity": 2,
                            "distance_km": 250.0,
                        },
                    ],
                    "total_allocated": 2,
                    "total_available": 10,
                    "total_demand": 50000,
                    "covered_demand": 10000,
                    "total_distance_km": 250.0,
                },
            ],
        )

        metric = ResourceEfficiencyMetric()
        result = await metric.compute(scenario, run)

        assert result.utilization_ratio < 0.5
        assert result.coverage_score < 0.5
        assert result.optimality_gap > 0.5
        assert result.score < 3.0


# =============================================================================
# Test Group 10: Graceful Degradation
# =============================================================================


class TestGracefulDegradation:
    """Tests for edge cases and empty data handling."""

    @pytest.mark.asyncio
    async def test_empty_agent_decisions(self):
        from src.benchmark.metrics.resource import ResourceEfficiencyMetric

        metric = ResourceEfficiencyMetric()
        scenario = _make_scenario()
        run = _make_run(scenario.id, agent_decisions=[])

        result = await metric.compute(scenario, run)
        assert result.score >= 1.0
        assert result.utilization_ratio == 0.0

    @pytest.mark.asyncio
    async def test_no_resource_agent_decisions(self):
        from src.benchmark.metrics.resource import ResourceEfficiencyMetric

        metric = ResourceEfficiencyMetric()
        scenario = _make_scenario()
        run = _make_run(
            scenario.id,
            agent_decisions=[
                {"agent_id": "situation_sense", "observations": ["something"]},
            ],
        )

        result = await metric.compute(scenario, run)
        assert result.score >= 1.0

    @pytest.mark.asyncio
    async def test_missing_ground_truth(self):
        from src.benchmark.metrics.resource import ResourceEfficiencyMetric

        metric = ResourceEfficiencyMetric()
        scenario = _make_scenario(agent_expectations={})
        run = _make_run(scenario.id)

        result = await metric.compute(scenario, run)
        assert result.score >= 1.0

    @pytest.mark.asyncio
    async def test_missing_allocations_field(self):
        from src.benchmark.metrics.resource import ResourceEfficiencyMetric

        metric = ResourceEfficiencyMetric()
        scenario = _make_scenario()
        run = _make_run(
            scenario.id,
            agent_decisions=[
                {
                    "agent_id": "resource_allocation",
                    "reasoning": "Deployed some resources",
                    # No allocations field
                    "total_allocated": 3,
                    "total_available": 10,
                    "total_demand": 50000,
                    "covered_demand": 20000,
                    "total_distance_km": 150.0,
                },
            ],
        )

        result = await metric.compute(scenario, run)
        assert result.score >= 1.0
        assert 1.0 <= result.score <= 5.0
