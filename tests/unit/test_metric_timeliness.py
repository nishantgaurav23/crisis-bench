"""Unit tests for the Decision Timeliness metric (spec S8.6).

Tests decision timing against NDMA SOP time windows from ground truth.
All tests are pure computation — no external APIs.
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
            "situation_sense": AgentExpectation(
                key_observations=["Cyclone approaching Odisha coast"],
                expected_actions=["Fuse IMD and SACHET data"],
                time_window_minutes=(0, 15),
            ),
            "predictive_risk": AgentExpectation(
                key_observations=["Flooding expected in low-lying areas"],
                expected_actions=["Generate risk forecast"],
                time_window_minutes=(5, 30),
            ),
            "resource_allocation": AgentExpectation(
                key_observations=["NDRF deployment needed"],
                expected_actions=["Optimize resource deployment"],
                time_window_minutes=(10, 45),
            ),
        }
    return BenchmarkScenario(
        category="cyclone",
        complexity="medium",
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
                "agent_id": "situation_sense",
                "observations": ["Cyclone approaching Odisha coast"],
                "reasoning": "Fused IMD + SACHET data",
                "simulated_elapsed_minutes": 10.0,
            },
            {
                "agent_id": "predictive_risk",
                "observations": ["Flooding expected in low-lying areas"],
                "reasoning": "Risk model predicts flooding",
                "simulated_elapsed_minutes": 20.0,
            },
            {
                "agent_id": "resource_allocation",
                "observations": ["NDRF deployment planned"],
                "reasoning": "Optimized with OR-Tools",
                "simulated_elapsed_minutes": 35.0,
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

    def test_agent_timeliness_valid(self):
        from src.benchmark.metrics.timeliness import AgentTimeliness

        at = AgentTimeliness(
            agent_id="situation_sense",
            expected_window=(0, 15),
            actual_minutes=10.0,
            score=5.0,
            status="on_time",
        )
        assert at.agent_id == "situation_sense"
        assert at.expected_window == (0, 15)
        assert at.actual_minutes == 10.0
        assert at.score == 5.0
        assert at.status == "on_time"

    def test_agent_timeliness_missing_decision(self):
        from src.benchmark.metrics.timeliness import AgentTimeliness

        at = AgentTimeliness(
            agent_id="situation_sense",
            expected_window=(0, 15),
            actual_minutes=None,
            score=1.0,
            status="missing",
        )
        assert at.actual_minutes is None
        assert at.score == 1.0
        assert at.status == "missing"

    def test_agent_timeliness_score_bounds(self):
        from src.benchmark.metrics.timeliness import AgentTimeliness

        with pytest.raises(ValueError):
            AgentTimeliness(
                agent_id="x", expected_window=(0, 10),
                actual_minutes=5.0, score=0.5, status="on_time",
            )
        with pytest.raises(ValueError):
            AgentTimeliness(
                agent_id="x", expected_window=(0, 10),
                actual_minutes=5.0, score=5.5, status="on_time",
            )

    def test_decision_timeliness_result_valid(self):
        from src.benchmark.metrics.timeliness import (
            AgentTimeliness,
            DecisionTimelinessResult,
        )

        result = DecisionTimelinessResult(
            per_agent={
                "agent1": AgentTimeliness(
                    agent_id="agent1", expected_window=(0, 10),
                    actual_minutes=5.0, score=5.0, status="on_time",
                ),
            },
            score=5.0,
            on_time_count=1,
            early_count=0,
            late_count=0,
            missing_count=0,
        )
        assert result.score == 5.0
        assert result.on_time_count == 1
        assert len(result.per_agent) == 1

    def test_decision_timeliness_result_score_bounds(self):
        from src.benchmark.metrics.timeliness import DecisionTimelinessResult

        with pytest.raises(ValueError):
            DecisionTimelinessResult(
                per_agent={}, score=0.5,
                on_time_count=0, early_count=0, late_count=0, missing_count=0,
            )
        with pytest.raises(ValueError):
            DecisionTimelinessResult(
                per_agent={}, score=5.5,
                on_time_count=0, early_count=0, late_count=0, missing_count=0,
            )


# =============================================================================
# Test Group 2: Score Agent Timeliness
# =============================================================================


class TestScoreAgentTimeliness:
    """Tests for individual agent timeliness scoring."""

    def test_on_time_within_window(self):
        from src.benchmark.metrics.timeliness import score_agent_timeliness

        score, status = score_agent_timeliness(
            actual_minutes=10.0,
            window_start=0,
            window_end=15,
        )
        assert score == 5.0
        assert status == "on_time"

    def test_on_time_at_window_start(self):
        from src.benchmark.metrics.timeliness import score_agent_timeliness

        score, status = score_agent_timeliness(
            actual_minutes=0.0,
            window_start=0,
            window_end=15,
        )
        assert score == 5.0
        assert status == "on_time"

    def test_on_time_at_window_end(self):
        from src.benchmark.metrics.timeliness import score_agent_timeliness

        score, status = score_agent_timeliness(
            actual_minutes=15.0,
            window_start=0,
            window_end=15,
        )
        assert score == 5.0
        assert status == "on_time"

    def test_early_before_window(self):
        from src.benchmark.metrics.timeliness import score_agent_timeliness

        # Decided at t=0, but window starts at t=10
        # Early is penalized less than late
        score, status = score_agent_timeliness(
            actual_minutes=0.0,
            window_start=10,
            window_end=30,
        )
        assert 3.0 <= score < 5.0
        assert status == "early"

    def test_early_just_before_window(self):
        from src.benchmark.metrics.timeliness import score_agent_timeliness

        # Just 1 minute early — should still be close to 5.0
        score, status = score_agent_timeliness(
            actual_minutes=9.0,
            window_start=10,
            window_end=30,
        )
        assert score > 4.0
        assert status == "early"

    def test_late_after_window(self):
        from src.benchmark.metrics.timeliness import score_agent_timeliness

        # Decided at t=60, window was (10, 30)
        score, status = score_agent_timeliness(
            actual_minutes=60.0,
            window_start=10,
            window_end=30,
        )
        assert 1.0 <= score < 5.0
        assert status == "late"

    def test_late_just_after_window(self):
        from src.benchmark.metrics.timeliness import score_agent_timeliness

        # Just 1 minute late — should still be decent
        score, status = score_agent_timeliness(
            actual_minutes=31.0,
            window_start=10,
            window_end=30,
        )
        assert score > 3.0
        assert status == "late"

    def test_very_late_approaches_one(self):
        from src.benchmark.metrics.timeliness import score_agent_timeliness

        # Extremely late — should approach 1.0
        score, status = score_agent_timeliness(
            actual_minutes=500.0,
            window_start=0,
            window_end=15,
        )
        assert score < 2.0
        assert status == "late"

    def test_late_penalized_more_than_early(self):
        from src.benchmark.metrics.timeliness import score_agent_timeliness

        # Same offset (10 min) from window, but late should score lower
        early_score, _ = score_agent_timeliness(
            actual_minutes=0.0,
            window_start=10,
            window_end=30,
        )
        late_score, _ = score_agent_timeliness(
            actual_minutes=40.0,
            window_start=10,
            window_end=30,
        )
        assert early_score > late_score

    def test_custom_late_penalty_factor(self):
        from src.benchmark.metrics.timeliness import score_agent_timeliness

        # Higher penalty factor → harsher late scoring
        mild = score_agent_timeliness(
            actual_minutes=50.0,
            window_start=0,
            window_end=15,
            late_penalty_factor=1.0,
        )
        harsh = score_agent_timeliness(
            actual_minutes=50.0,
            window_start=0,
            window_end=15,
            late_penalty_factor=4.0,
        )
        assert mild[0] > harsh[0]


# =============================================================================
# Test Group 3: Extract Decision Times
# =============================================================================


class TestExtractDecisionTimes:
    """Tests for extracting agent decision times from run data."""

    def test_extract_from_decisions(self):
        from src.benchmark.metrics.timeliness import extract_decision_times

        decisions = [
            {"agent_id": "situation_sense", "simulated_elapsed_minutes": 10.0},
            {"agent_id": "predictive_risk", "simulated_elapsed_minutes": 20.0},
        ]
        times = extract_decision_times(decisions)
        assert times["situation_sense"] == 10.0
        assert times["predictive_risk"] == 20.0

    def test_extract_missing_time_field(self):
        from src.benchmark.metrics.timeliness import extract_decision_times

        decisions = [
            {"agent_id": "situation_sense", "reasoning": "no time field"},
        ]
        times = extract_decision_times(decisions)
        assert "situation_sense" not in times

    def test_extract_empty_decisions(self):
        from src.benchmark.metrics.timeliness import extract_decision_times

        times = extract_decision_times([])
        assert times == {}

    def test_extract_multiple_decisions_same_agent_uses_first(self):
        from src.benchmark.metrics.timeliness import extract_decision_times

        decisions = [
            {"agent_id": "situation_sense", "simulated_elapsed_minutes": 10.0},
            {"agent_id": "situation_sense", "simulated_elapsed_minutes": 20.0},
        ]
        times = extract_decision_times(decisions)
        # First decision time should be used
        assert times["situation_sense"] == 10.0


# =============================================================================
# Test Group 4: Extract Time Windows
# =============================================================================


class TestExtractTimeWindows:
    """Tests for extracting expected time windows from ground truth."""

    def test_extract_windows(self):
        from src.benchmark.metrics.timeliness import extract_time_windows

        gt = GroundTruthDecisions(
            agent_expectations={
                "situation_sense": AgentExpectation(
                    key_observations=["obs"],
                    expected_actions=["act"],
                    time_window_minutes=(0, 15),
                ),
            },
        )
        windows = extract_time_windows(gt)
        assert windows["situation_sense"] == (0, 15)

    def test_extract_empty_ground_truth(self):
        from src.benchmark.metrics.timeliness import extract_time_windows

        gt = GroundTruthDecisions(agent_expectations={})
        windows = extract_time_windows(gt)
        assert windows == {}


# =============================================================================
# Test Group 5: Full Compute
# =============================================================================


class TestFullCompute:
    """Tests for the complete DecisionTimelinessMetric.compute()."""

    @pytest.mark.asyncio
    async def test_compute_returns_result(self):
        from src.benchmark.metrics.timeliness import (
            DecisionTimelinessMetric,
            DecisionTimelinessResult,
        )

        metric = DecisionTimelinessMetric()
        scenario = _make_scenario()
        run = _make_run(scenario.id)

        result = await metric.compute(scenario, run)

        assert isinstance(result, DecisionTimelinessResult)
        assert 1.0 <= result.score <= 5.0
        assert len(result.per_agent) == 3

    @pytest.mark.asyncio
    async def test_compute_all_on_time(self):
        from src.benchmark.metrics.timeliness import DecisionTimelinessMetric

        scenario = _make_scenario()
        # All decisions within windows
        run = _make_run(scenario.id, agent_decisions=[
            {"agent_id": "situation_sense", "simulated_elapsed_minutes": 10.0},
            {"agent_id": "predictive_risk", "simulated_elapsed_minutes": 20.0},
            {"agent_id": "resource_allocation", "simulated_elapsed_minutes": 30.0},
        ])

        metric = DecisionTimelinessMetric()
        result = await metric.compute(scenario, run)

        assert result.score == 5.0
        assert result.on_time_count == 3
        assert result.early_count == 0
        assert result.late_count == 0
        assert result.missing_count == 0

    @pytest.mark.asyncio
    async def test_compute_all_missing(self):
        from src.benchmark.metrics.timeliness import DecisionTimelinessMetric

        scenario = _make_scenario()
        run = _make_run(scenario.id, agent_decisions=[])

        metric = DecisionTimelinessMetric()
        result = await metric.compute(scenario, run)

        assert result.score == 1.0
        assert result.missing_count == 3
        assert result.on_time_count == 0

    @pytest.mark.asyncio
    async def test_compute_mixed_timing(self):
        from src.benchmark.metrics.timeliness import DecisionTimelinessMetric

        scenario = _make_scenario()
        run = _make_run(scenario.id, agent_decisions=[
            # On time
            {"agent_id": "situation_sense", "simulated_elapsed_minutes": 10.0},
            # Late
            {"agent_id": "predictive_risk", "simulated_elapsed_minutes": 60.0},
            # Missing resource_allocation
        ])

        metric = DecisionTimelinessMetric()
        result = await metric.compute(scenario, run)

        assert 1.0 < result.score < 5.0
        assert result.on_time_count == 1
        assert result.late_count == 1
        assert result.missing_count == 1

    @pytest.mark.asyncio
    async def test_compute_no_ground_truth_windows(self):
        from src.benchmark.metrics.timeliness import DecisionTimelinessMetric

        scenario = _make_scenario(agent_expectations={})
        run = _make_run(scenario.id)

        metric = DecisionTimelinessMetric()
        result = await metric.compute(scenario, run)

        # No ground truth windows = nothing to evaluate
        assert result.score == 1.0
        assert len(result.per_agent) == 0

    @pytest.mark.asyncio
    async def test_compute_agent_not_in_ground_truth_excluded(self):
        from src.benchmark.metrics.timeliness import DecisionTimelinessMetric

        # Only situation_sense in ground truth
        agent_expectations = {
            "situation_sense": AgentExpectation(
                key_observations=["obs"],
                expected_actions=["act"],
                time_window_minutes=(0, 15),
            ),
        }
        scenario = _make_scenario(agent_expectations=agent_expectations)
        # Extra agent "unknown_agent" not in ground truth — should be excluded
        run = _make_run(scenario.id, agent_decisions=[
            {"agent_id": "situation_sense", "simulated_elapsed_minutes": 10.0},
            {"agent_id": "unknown_agent", "simulated_elapsed_minutes": 5.0},
        ])

        metric = DecisionTimelinessMetric()
        result = await metric.compute(scenario, run)

        assert "situation_sense" in result.per_agent
        assert "unknown_agent" not in result.per_agent
        assert result.score == 5.0

    @pytest.mark.asyncio
    async def test_compute_custom_penalty_factor(self):
        from src.benchmark.metrics.timeliness import DecisionTimelinessMetric

        scenario = _make_scenario()
        # All late decisions
        run = _make_run(scenario.id, agent_decisions=[
            {"agent_id": "situation_sense", "simulated_elapsed_minutes": 50.0},
            {"agent_id": "predictive_risk", "simulated_elapsed_minutes": 80.0},
            {"agent_id": "resource_allocation", "simulated_elapsed_minutes": 100.0},
        ])

        mild = DecisionTimelinessMetric(late_penalty_factor=1.0)
        harsh = DecisionTimelinessMetric(late_penalty_factor=4.0)

        result_mild = await mild.compute(scenario, run)
        result_harsh = await harsh.compute(scenario, run)

        assert result_mild.score > result_harsh.score


# =============================================================================
# Test Group 6: Aggregate Scoring
# =============================================================================


class TestAggregateScoring:
    """Tests for aggregate score computation."""

    @pytest.mark.asyncio
    async def test_aggregate_is_average_of_per_agent(self):
        from src.benchmark.metrics.timeliness import DecisionTimelinessMetric

        scenario = _make_scenario()
        run = _make_run(scenario.id)

        metric = DecisionTimelinessMetric()
        result = await metric.compute(scenario, run)

        if result.per_agent:
            expected_avg = sum(
                a.score for a in result.per_agent.values()
            ) / len(result.per_agent)
            assert result.score == pytest.approx(expected_avg, abs=0.01)
