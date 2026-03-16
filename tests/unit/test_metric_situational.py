"""Unit tests for the Situational Accuracy metric (spec S8.5).

Tests precision/recall/F1 computation against IMD/CWC ground truth
bulletin timelines. All tests are pure computation — no external APIs.
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
                key_observations=[
                    "Cyclone approaching Odisha coast",
                    "Wind speed exceeding 150 kmph",
                    "Storm surge warning for Puri district",
                ],
                expected_actions=["Fuse IMD and SACHET data"],
                time_window_minutes=(0, 15),
            ),
            "predictive_risk": AgentExpectation(
                key_observations=[
                    "Flooding expected in low-lying areas",
                    "Power grid failure likely in coastal belt",
                ],
                expected_actions=["Generate risk forecast"],
                time_window_minutes=(5, 30),
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
                "observations": [
                    "Cyclone approaching Odisha coast",
                    "Wind speed exceeding 150 kmph",
                ],
                "reasoning": "Fused IMD + SACHET data, identified cyclone threat",
                "simulated_elapsed_minutes": 5.0,
            },
            {
                "agent_id": "predictive_risk",
                "observations": [
                    "Flooding expected in low-lying areas",
                ],
                "reasoning": "Risk model predicts flooding in coastal districts",
                "simulated_elapsed_minutes": 15.0,
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

    def test_observation_match_valid(self):
        from src.benchmark.metrics.situational import ObservationMatch

        match = ObservationMatch(
            expected="Cyclone approaching coast",
            actual="Cyclone approaching Odisha coast",
            similarity=0.85,
        )
        assert match.expected == "Cyclone approaching coast"
        assert match.similarity == 0.85

    def test_observation_match_similarity_bounds(self):
        from src.benchmark.metrics.situational import ObservationMatch

        with pytest.raises(ValueError):
            ObservationMatch(expected="a", actual="b", similarity=-0.1)
        with pytest.raises(ValueError):
            ObservationMatch(expected="a", actual="b", similarity=1.1)

    def test_agent_accuracy_score_valid(self):
        from src.benchmark.metrics.situational import AgentAccuracyScore

        score = AgentAccuracyScore(
            agent_id="situation_sense",
            precision=0.8,
            recall=0.6,
            f1=0.685,
            matched=2,
            expected_total=3,
            actual_total=2,
        )
        assert score.agent_id == "situation_sense"
        assert score.matched == 2

    def test_situational_accuracy_result_valid(self):
        from src.benchmark.metrics.situational import (
            AgentAccuracyScore,
            ObservationMatch,
            SituationalAccuracyResult,
        )

        result = SituationalAccuracyResult(
            precision=0.75,
            recall=0.6,
            f1=0.667,
            score=3.34,
            matched_observations=[
                ObservationMatch(expected="a", actual="a", similarity=1.0),
            ],
            unmatched_expected=["b"],
            unmatched_actual=[],
            per_agent_scores={
                "agent1": AgentAccuracyScore(
                    agent_id="agent1",
                    precision=0.75, recall=0.6, f1=0.667,
                    matched=1, expected_total=2, actual_total=1,
                ),
            },
        )
        assert result.precision == 0.75
        assert result.score == 3.34
        assert len(result.matched_observations) == 1


# =============================================================================
# Test Group 2: Keyword Similarity
# =============================================================================


class TestKeywordSimilarity:
    """Tests for keyword-based similarity computation."""

    def test_exact_match_returns_one(self):
        from src.benchmark.metrics.situational import keyword_similarity

        assert keyword_similarity("cyclone approaching coast", "cyclone approaching coast") == 1.0

    def test_no_overlap_returns_zero(self):
        from src.benchmark.metrics.situational import keyword_similarity

        assert keyword_similarity("cyclone approaching coast", "earthquake in delhi") == 0.0

    def test_partial_overlap(self):
        from src.benchmark.metrics.situational import keyword_similarity

        sim = keyword_similarity(
            "Cyclone approaching Odisha coast",
            "Cyclone near Odisha shoreline",
        )
        # "cyclone" and "odisha" overlap out of larger union
        assert 0.0 < sim < 1.0

    def test_case_insensitive(self):
        from src.benchmark.metrics.situational import keyword_similarity

        assert keyword_similarity("CYCLONE", "cyclone") == 1.0

    def test_empty_strings_return_zero(self):
        from src.benchmark.metrics.situational import keyword_similarity

        assert keyword_similarity("", "") == 0.0
        assert keyword_similarity("something", "") == 0.0


# =============================================================================
# Test Group 3: Observation Extraction
# =============================================================================


class TestObservationExtraction:
    """Tests for extracting observations from decisions and ground truth."""

    def test_extract_expected_observations(self):
        from src.benchmark.metrics.situational import extract_expected_observations

        scenario = _make_scenario()
        expected = extract_expected_observations(scenario.ground_truth_decisions)

        assert "situation_sense" in expected
        assert len(expected["situation_sense"]) == 3
        assert "predictive_risk" in expected
        assert len(expected["predictive_risk"]) == 2

    def test_extract_expected_empty_ground_truth(self):
        from src.benchmark.metrics.situational import extract_expected_observations

        gt = GroundTruthDecisions(agent_expectations={})
        expected = extract_expected_observations(gt)
        assert expected == {}

    def test_extract_observations_from_decisions(self):
        from src.benchmark.metrics.situational import extract_observations_from_decisions

        decisions = [
            {
                "agent_id": "situation_sense",
                "observations": ["obs1", "obs2"],
                "reasoning": "Some reasoning with obs3 mentioned",
            },
            {
                "agent_id": "predictive_risk",
                "observations": ["obs4"],
            },
        ]
        actual = extract_observations_from_decisions(decisions)

        assert "situation_sense" in actual
        assert "obs1" in actual["situation_sense"]
        assert "obs2" in actual["situation_sense"]
        assert "predictive_risk" in actual
        assert "obs4" in actual["predictive_risk"]

    def test_extract_observations_no_observations_field(self):
        from src.benchmark.metrics.situational import extract_observations_from_decisions

        decisions = [
            {
                "agent_id": "situation_sense",
                "reasoning": "Cyclone detected approaching coast",
            },
        ]
        actual = extract_observations_from_decisions(decisions)

        # Should extract from reasoning as fallback
        assert "situation_sense" in actual
        assert len(actual["situation_sense"]) >= 1

    def test_extract_observations_empty_decisions(self):
        from src.benchmark.metrics.situational import extract_observations_from_decisions

        actual = extract_observations_from_decisions([])
        assert actual == {}


# =============================================================================
# Test Group 4: Observation Matching
# =============================================================================


class TestObservationMatching:
    """Tests for matching actual vs expected observations."""

    def test_match_perfect(self):
        from src.benchmark.metrics.situational import match_observations

        expected = ["cyclone approaching coast", "wind speed high"]
        actual = ["cyclone approaching coast", "wind speed high"]

        result = match_observations(expected, actual, threshold=0.5)
        assert len(result.matched) == 2
        assert len(result.unmatched_expected) == 0
        assert len(result.unmatched_actual) == 0

    def test_match_partial(self):
        from src.benchmark.metrics.situational import match_observations

        expected = ["cyclone approaching coast", "storm surge warning", "wind speed high"]
        actual = ["cyclone approaching coast", "wind speed exceeding limit"]

        result = match_observations(expected, actual, threshold=0.5)
        # At least "cyclone approaching coast" should match exactly
        assert len(result.matched) >= 1
        assert len(result.unmatched_expected) >= 1

    def test_match_no_overlap(self):
        from src.benchmark.metrics.situational import match_observations

        expected = ["cyclone approaching coast"]
        actual = ["earthquake in delhi region"]

        result = match_observations(expected, actual, threshold=0.5)
        assert len(result.matched) == 0
        assert len(result.unmatched_expected) == 1
        assert len(result.unmatched_actual) == 1

    def test_match_empty_expected(self):
        from src.benchmark.metrics.situational import match_observations

        result = match_observations([], ["some observation"], threshold=0.5)
        assert len(result.matched) == 0
        assert len(result.unmatched_actual) == 1

    def test_match_empty_actual(self):
        from src.benchmark.metrics.situational import match_observations

        result = match_observations(["expected obs"], [], threshold=0.5)
        assert len(result.matched) == 0
        assert len(result.unmatched_expected) == 1

    def test_match_both_empty(self):
        from src.benchmark.metrics.situational import match_observations

        result = match_observations([], [], threshold=0.5)
        assert len(result.matched) == 0

    def test_match_no_double_counting(self):
        from src.benchmark.metrics.situational import match_observations

        # One actual should only match one expected (greedy best-first)
        expected = ["cyclone approaching coast"]
        actual = ["cyclone approaching coast", "cyclone nearing coast"]

        result = match_observations(expected, actual, threshold=0.5)
        assert len(result.matched) == 1  # Only 1 expected, so max 1 match
        assert len(result.unmatched_actual) == 1


# =============================================================================
# Test Group 5: Precision / Recall / F1
# =============================================================================


class TestPrecisionRecallF1:
    """Tests for precision, recall, and F1 computation."""

    def test_compute_precision_recall_f1_perfect(self):
        from src.benchmark.metrics.situational import compute_precision_recall_f1

        p, r, f = compute_precision_recall_f1(
            matched=3, expected_total=3, actual_total=3,
        )
        assert p == 1.0
        assert r == 1.0
        assert f == 1.0

    def test_compute_precision_recall_f1_partial(self):
        from src.benchmark.metrics.situational import compute_precision_recall_f1

        p, r, f = compute_precision_recall_f1(
            matched=2, expected_total=4, actual_total=3,
        )
        assert p == pytest.approx(2 / 3, abs=0.01)
        assert r == pytest.approx(2 / 4, abs=0.01)
        expected_f1 = 2 * (2 / 3) * (2 / 4) / ((2 / 3) + (2 / 4))
        assert f == pytest.approx(expected_f1, abs=0.01)

    def test_compute_precision_recall_f1_zero(self):
        from src.benchmark.metrics.situational import compute_precision_recall_f1

        p, r, f = compute_precision_recall_f1(
            matched=0, expected_total=3, actual_total=2,
        )
        assert p == 0.0
        assert r == 0.0
        assert f == 0.0

    def test_compute_precision_recall_f1_empty(self):
        from src.benchmark.metrics.situational import compute_precision_recall_f1

        p, r, f = compute_precision_recall_f1(
            matched=0, expected_total=0, actual_total=0,
        )
        assert p == 0.0
        assert r == 0.0
        assert f == 0.0


# =============================================================================
# Test Group 6: F1 → Score Mapping
# =============================================================================


class TestF1ToScore:
    """Tests for mapping F1 to 1.0-5.0 score."""

    def test_perfect_f1_gives_five(self):
        from src.benchmark.metrics.situational import f1_to_score

        assert f1_to_score(1.0) == 5.0

    def test_f1_0_9_gives_five(self):
        from src.benchmark.metrics.situational import f1_to_score

        assert f1_to_score(0.9) == pytest.approx(5.0, abs=0.01)

    def test_f1_0_7_gives_four(self):
        from src.benchmark.metrics.situational import f1_to_score

        assert f1_to_score(0.7) == pytest.approx(4.0, abs=0.01)

    def test_f1_0_5_gives_three(self):
        from src.benchmark.metrics.situational import f1_to_score

        assert f1_to_score(0.5) == pytest.approx(3.0, abs=0.01)

    def test_f1_0_3_gives_two(self):
        from src.benchmark.metrics.situational import f1_to_score

        assert f1_to_score(0.3) == pytest.approx(2.0, abs=0.01)

    def test_f1_zero_gives_one(self):
        from src.benchmark.metrics.situational import f1_to_score

        assert f1_to_score(0.0) == pytest.approx(1.0, abs=0.1)

    def test_f1_between_bands_interpolates(self):
        from src.benchmark.metrics.situational import f1_to_score

        # F1 = 0.6 is between 0.5 (score 3.0) and 0.7 (score 4.0)
        score = f1_to_score(0.6)
        assert 3.0 < score < 4.0

    def test_f1_clamped_to_range(self):
        from src.benchmark.metrics.situational import f1_to_score

        assert f1_to_score(-0.1) >= 1.0
        assert f1_to_score(1.5) <= 5.0


# =============================================================================
# Test Group 7: Full Compute
# =============================================================================


class TestFullCompute:
    """Tests for the complete SituationalAccuracyMetric.compute()."""

    @pytest.mark.asyncio
    async def test_compute_returns_result(self):
        from src.benchmark.metrics.situational import (
            SituationalAccuracyMetric,
            SituationalAccuracyResult,
        )

        metric = SituationalAccuracyMetric()
        scenario = _make_scenario()
        run = _make_run(scenario.id)

        result = await metric.compute(scenario, run)

        assert isinstance(result, SituationalAccuracyResult)
        assert 0.0 <= result.precision <= 1.0
        assert 0.0 <= result.recall <= 1.0
        assert 0.0 <= result.f1 <= 1.0
        assert 1.0 <= result.score <= 5.0

    @pytest.mark.asyncio
    async def test_compute_perfect_match(self):
        from src.benchmark.metrics.situational import SituationalAccuracyMetric

        agent_expectations = {
            "situation_sense": AgentExpectation(
                key_observations=["cyclone approaching coast"],
                expected_actions=[],
                time_window_minutes=(0, 15),
            ),
        }
        scenario = _make_scenario(agent_expectations=agent_expectations)
        run = _make_run(
            scenario.id,
            agent_decisions=[
                {
                    "agent_id": "situation_sense",
                    "observations": ["cyclone approaching coast"],
                },
            ],
        )

        metric = SituationalAccuracyMetric()
        result = await metric.compute(scenario, run)

        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1 == 1.0
        assert result.score == pytest.approx(5.0, abs=0.1)

    @pytest.mark.asyncio
    async def test_compute_no_match(self):
        from src.benchmark.metrics.situational import SituationalAccuracyMetric

        agent_expectations = {
            "situation_sense": AgentExpectation(
                key_observations=["cyclone approaching coast"],
                expected_actions=[],
                time_window_minutes=(0, 15),
            ),
        }
        scenario = _make_scenario(agent_expectations=agent_expectations)
        run = _make_run(
            scenario.id,
            agent_decisions=[
                {
                    "agent_id": "situation_sense",
                    "observations": ["earthquake in delhi"],
                },
            ],
        )

        metric = SituationalAccuracyMetric()
        result = await metric.compute(scenario, run)

        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.f1 == 0.0
        assert result.score == pytest.approx(1.0, abs=0.5)

    @pytest.mark.asyncio
    async def test_compute_per_agent_scores(self):
        from src.benchmark.metrics.situational import SituationalAccuracyMetric

        metric = SituationalAccuracyMetric()
        scenario = _make_scenario()
        run = _make_run(scenario.id)

        result = await metric.compute(scenario, run)

        # Should have per-agent breakdown
        assert len(result.per_agent_scores) > 0
        for agent_id, agent_score in result.per_agent_scores.items():
            assert agent_score.agent_id == agent_id
            assert 0.0 <= agent_score.precision <= 1.0
            assert 0.0 <= agent_score.recall <= 1.0
            assert 0.0 <= agent_score.f1 <= 1.0


# =============================================================================
# Test Group 8: Graceful Degradation
# =============================================================================


class TestGracefulDegradation:
    """Tests for edge cases and empty data handling."""

    @pytest.mark.asyncio
    async def test_empty_agent_decisions(self):
        from src.benchmark.metrics.situational import SituationalAccuracyMetric

        metric = SituationalAccuracyMetric()
        scenario = _make_scenario()
        run = _make_run(scenario.id, agent_decisions=[])

        result = await metric.compute(scenario, run)

        assert result.recall == 0.0
        assert result.score >= 1.0

    @pytest.mark.asyncio
    async def test_empty_ground_truth(self):
        from src.benchmark.metrics.situational import SituationalAccuracyMetric

        metric = SituationalAccuracyMetric()
        scenario = _make_scenario(agent_expectations={})
        run = _make_run(scenario.id)

        result = await metric.compute(scenario, run)

        # No ground truth means nothing to match against
        assert result.score >= 1.0

    @pytest.mark.asyncio
    async def test_both_empty(self):
        from src.benchmark.metrics.situational import SituationalAccuracyMetric

        metric = SituationalAccuracyMetric()
        scenario = _make_scenario(agent_expectations={})
        run = _make_run(scenario.id, agent_decisions=[])

        result = await metric.compute(scenario, run)

        assert result.score >= 1.0
        assert result.f1 == 0.0

    @pytest.mark.asyncio
    async def test_custom_threshold(self):
        from src.benchmark.metrics.situational import SituationalAccuracyMetric

        # Higher threshold = fewer matches
        strict = SituationalAccuracyMetric(similarity_threshold=0.9)
        lenient = SituationalAccuracyMetric(similarity_threshold=0.3)

        scenario = _make_scenario()
        run = _make_run(scenario.id)

        result_strict = await strict.compute(scenario, run)
        result_lenient = await lenient.compute(scenario, run)

        # Lenient should match more (or equal)
        assert result_lenient.f1 >= result_strict.f1
