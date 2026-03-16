"""Unit tests for the Evaluation Engine (spec S8.4).

Tests the LLM-as-judge evaluation engine that scores agent decisions
across 5 dimensions. All LLM calls are mocked.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.benchmark.models import (
    AgentExpectation,
    BenchmarkScenario,
    DimensionCriteria,
    EvaluationRubric,
    EvaluationRun,
    GroundTruthDecisions,
    ScenarioEvent,
)
from src.shared.models import DisasterPhase

# =============================================================================
# Helpers
# =============================================================================

DIMENSIONS = [
    "situational_accuracy",
    "decision_timeliness",
    "resource_efficiency",
    "coordination_quality",
    "communication_appropriateness",
]


def _make_rubric() -> EvaluationRubric:
    return EvaluationRubric(
        situational_accuracy=DimensionCriteria(
            weight=0.25,
            criteria={"precision": "Match IMD bulletins", "recall": "Cover all events"},
            key_factors=["data fusion", "misinformation detection"],
        ),
        decision_timeliness=DimensionCriteria(
            weight=0.25,
            criteria={"sop_compliance": "Within NDMA time windows"},
            key_factors=["alert-to-action time"],
        ),
        resource_efficiency=DimensionCriteria(
            weight=0.20,
            criteria={"optimality": "Close to OR-Tools baseline"},
            key_factors=["shelter matching", "NDRF deployment"],
        ),
        coordination_quality=DimensionCriteria(
            weight=0.15,
            criteria={"info_sharing": "Complete inter-agent communication"},
            key_factors=["message completeness"],
        ),
        communication_appropriateness=DimensionCriteria(
            weight=0.15,
            criteria={"language": "Multilingual quality"},
            key_factors=["NDMA guideline adherence"],
        ),
    )


def _make_scenario() -> BenchmarkScenario:
    return BenchmarkScenario(
        category="cyclone",
        complexity="medium",
        affected_states=["Odisha"],
        event_sequence=[
            ScenarioEvent(
                time_offset_minutes=0,
                phase=DisasterPhase.ACTIVE_RESPONSE,
                event_type="sachet_alert",
                description="SACHET alert for Cyclone Fani",
            ),
            ScenarioEvent(
                time_offset_minutes=30,
                phase=DisasterPhase.ACTIVE_RESPONSE,
                event_type="evacuation_order",
                description="Evacuation order for coastal districts",
            ),
        ],
        ground_truth_decisions=GroundTruthDecisions(
            agent_expectations={
                "situation_sense": AgentExpectation(
                    key_observations=["Cyclone approaching Odisha coast"],
                    expected_actions=["Fuse IMD and SACHET data"],
                    time_window_minutes=(0, 15),
                ),
                "resource_allocation": AgentExpectation(
                    key_observations=["500K population in coastal districts"],
                    expected_actions=["Deploy NDRF battalions"],
                    time_window_minutes=(0, 30),
                ),
            },
            decision_timeline={"t0": "Alert received", "t30": "Evacuation ordered"},
            ndma_references=["NDMA-CYC-01", "NDMA-EVAC-03"],
        ),
        evaluation_rubric=_make_rubric(),
    )


def _make_evaluation_run(scenario_id: uuid.UUID) -> EvaluationRun:
    return EvaluationRun(
        scenario_id=scenario_id,
        agent_config={"acceleration": 5.0, "orchestrator_id": "orchestrator"},
        agent_decisions=[
            {
                "agent_id": "orchestrator",
                "event_type": "sachet_alert",
                "confidence": 0.85,
                "reasoning": "Fused IMD + SACHET data, identified Cat-4 cyclone",
                "simulated_elapsed_minutes": 0.0,
            },
            {
                "agent_id": "orchestrator",
                "event_type": "evacuation_order",
                "confidence": 0.9,
                "reasoning": "Deployed 5 NDRF battalions to coastal Odisha",
                "simulated_elapsed_minutes": 30.0,
            },
        ],
        total_tokens=500,
        total_cost_usd=0.005,
        duration_seconds=12.5,
    )


def _mock_llm_score_response(dimension: str, score: float = 4.0) -> str:
    """Return a JSON string mimicking LLM evaluation response."""
    return json.dumps({
        "score": score,
        "justification": f"Good performance on {dimension}",
        "key_factors": ["factor_1", "factor_2"],
    })


def _make_mock_router(scores: dict[str, float] | None = None):
    """Create a mock LLM Router that returns dimension-specific scores."""
    if scores is None:
        scores = {d: 4.0 for d in DIMENSIONS}

    router = MagicMock()
    call_count = 0

    async def mock_call(tier, messages, **kwargs):
        nonlocal call_count
        # Determine which dimension is being evaluated from the prompt
        prompt_text = str(messages)
        for dim in DIMENSIONS:
            if dim in prompt_text:
                content = _mock_llm_score_response(dim, scores.get(dim, 4.0))
                result = MagicMock()
                result.content = content
                result.provider = "mock"
                result.model = "mock-model"
                result.input_tokens = 200
                result.output_tokens = 100
                result.cost_usd = 0.001
                result.latency_s = 0.5
                result.tier = tier
                call_count += 1
                return result
        # Default response if no dimension matched
        content = _mock_llm_score_response("unknown", 3.0)
        result = MagicMock()
        result.content = content
        result.provider = "mock"
        result.model = "mock-model"
        result.input_tokens = 200
        result.output_tokens = 100
        result.cost_usd = 0.001
        result.latency_s = 0.5
        result.tier = tier
        call_count += 1
        return result

    router.call = AsyncMock(side_effect=mock_call)
    return router


# =============================================================================
# Test Group 1: DimensionScore + EvaluationResult Models
# =============================================================================


class TestModels:
    """Tests for evaluation engine Pydantic models."""

    def test_dimension_score_valid(self):
        from src.benchmark.evaluation_engine import DimensionScore

        score = DimensionScore(
            dimension="situational_accuracy",
            score=4.5,
            justification="Good data fusion accuracy",
            key_factors=["IMD data matched", "Timely alerts"],
        )
        assert score.dimension == "situational_accuracy"
        assert score.score == 4.5
        assert len(score.key_factors) == 2

    def test_dimension_score_bounds(self):
        from src.benchmark.evaluation_engine import DimensionScore

        # Score must be 1.0-5.0
        with pytest.raises(ValueError):
            DimensionScore(
                dimension="test", score=0.5,
                justification="Too low", key_factors=[],
            )
        with pytest.raises(ValueError):
            DimensionScore(
                dimension="test", score=5.5,
                justification="Too high", key_factors=[],
            )

    def test_evaluation_result_model(self):
        from src.benchmark.evaluation_engine import DimensionScore, EvaluationResult

        run_id = uuid.uuid4()
        scenario_id = uuid.uuid4()
        dim_scores = {
            "situational_accuracy": DimensionScore(
                dimension="situational_accuracy",
                score=4.0,
                justification="Good",
                key_factors=["factor1"],
            ),
        }
        result = EvaluationResult(
            run_id=run_id,
            scenario_id=scenario_id,
            dimension_scores=dim_scores,
            aggregate_drs=0.8,
            total_eval_tokens=300,
            total_eval_cost_usd=0.003,
        )
        assert result.run_id == run_id
        assert result.aggregate_drs == 0.8
        assert "situational_accuracy" in result.dimension_scores


# =============================================================================
# Test Group 2: Prompt Building
# =============================================================================


class TestPromptBuilding:
    """Tests for evaluation prompt construction."""

    def test_build_evaluation_prompt_contains_rubric(self):
        from src.benchmark.evaluation_engine import build_evaluation_prompt

        scenario = _make_scenario()
        run = _make_evaluation_run(scenario.id)

        messages = build_evaluation_prompt(
            dimension="situational_accuracy",
            scenario=scenario,
            evaluation_run=run,
        )

        # Should be a list of message dicts
        assert isinstance(messages, list)
        assert len(messages) >= 2  # system + user at minimum

        # System message should contain evaluator instructions
        system_msg = messages[0]
        assert system_msg["role"] == "system"
        assert "evaluator" in system_msg["content"].lower()

        # User message should contain rubric, ground truth, and decisions
        full_text = " ".join(m["content"] for m in messages)
        assert "situational_accuracy" in full_text
        assert "IMD bulletins" in full_text or "precision" in full_text.lower()

    def test_build_prompt_includes_ground_truth(self):
        from src.benchmark.evaluation_engine import build_evaluation_prompt

        scenario = _make_scenario()
        run = _make_evaluation_run(scenario.id)

        messages = build_evaluation_prompt(
            dimension="situational_accuracy",
            scenario=scenario,
            evaluation_run=run,
        )

        full_text = " ".join(m["content"] for m in messages)
        assert "Cyclone approaching" in full_text or "NDMA" in full_text

    def test_build_prompt_includes_agent_decisions(self):
        from src.benchmark.evaluation_engine import build_evaluation_prompt

        scenario = _make_scenario()
        run = _make_evaluation_run(scenario.id)

        messages = build_evaluation_prompt(
            dimension="situational_accuracy",
            scenario=scenario,
            evaluation_run=run,
        )

        full_text = " ".join(m["content"] for m in messages)
        # Agent decisions should be included
        assert "sachet_alert" in full_text or "orchestrator" in full_text

    def test_build_prompt_requests_json_output(self):
        from src.benchmark.evaluation_engine import build_evaluation_prompt

        scenario = _make_scenario()
        run = _make_evaluation_run(scenario.id)

        messages = build_evaluation_prompt(
            dimension="decision_timeliness",
            scenario=scenario,
            evaluation_run=run,
        )

        full_text = " ".join(m["content"] for m in messages)
        assert "json" in full_text.lower()


# =============================================================================
# Test Group 3: LLM Response Parsing
# =============================================================================


class TestResponseParsing:
    """Tests for parsing LLM evaluation responses."""

    def test_parse_valid_json_response(self):
        from src.benchmark.evaluation_engine import parse_score_response

        raw = json.dumps({
            "score": 4.2,
            "justification": "Accurate situation assessment",
            "key_factors": ["data fusion", "timely alerts"],
        })

        score = parse_score_response(raw, "situational_accuracy")
        assert score.score == 4.2
        assert score.dimension == "situational_accuracy"
        assert "data fusion" in score.key_factors

    def test_parse_malformed_json_returns_default(self):
        from src.benchmark.evaluation_engine import parse_score_response

        raw = "This is not JSON at all, sorry"
        score = parse_score_response(raw, "situational_accuracy")

        # Should return a default score (1.0 = unable to evaluate)
        assert score.score == 1.0
        assert "parse" in score.justification.lower() or "fail" in score.justification.lower()

    def test_parse_json_missing_score_field(self):
        from src.benchmark.evaluation_engine import parse_score_response

        raw = json.dumps({"justification": "No score field", "key_factors": []})
        score = parse_score_response(raw, "decision_timeliness")

        assert score.score == 1.0

    def test_parse_score_out_of_range_clamped(self):
        from src.benchmark.evaluation_engine import parse_score_response

        raw = json.dumps({
            "score": 7.0,
            "justification": "Way too high",
            "key_factors": [],
        })
        score = parse_score_response(raw, "resource_efficiency")
        assert score.score == 5.0  # Clamped to max

    def test_parse_json_embedded_in_text(self):
        from src.benchmark.evaluation_engine import parse_score_response

        raw = 'Here is my evaluation:\n```json\n{"score": 3.5, "justification": "Average", "key_factors": ["mixed results"]}\n```'
        score = parse_score_response(raw, "coordination_quality")
        assert score.score == 3.5


# =============================================================================
# Test Group 4: Single Dimension Evaluation
# =============================================================================


class TestSingleDimensionEvaluation:
    """Tests for evaluating one dimension via LLM."""

    @pytest.mark.asyncio
    async def test_evaluate_dimension_calls_router(self):
        from src.benchmark.evaluation_engine import EvaluationEngine

        router = _make_mock_router()
        engine = EvaluationEngine(router)

        scenario = _make_scenario()
        run = _make_evaluation_run(scenario.id)

        score = await engine.evaluate_dimension(
            "situational_accuracy", scenario, run,
        )

        # Router should have been called at critical tier
        router.call.assert_called()
        call_args = router.call.call_args
        assert call_args[0][0] == "critical"

        assert score.dimension == "situational_accuracy"
        assert 1.0 <= score.score <= 5.0

    @pytest.mark.asyncio
    async def test_evaluate_dimension_returns_dimension_score(self):
        from src.benchmark.evaluation_engine import DimensionScore, EvaluationEngine

        router = _make_mock_router({"situational_accuracy": 4.5})
        engine = EvaluationEngine(router)

        scenario = _make_scenario()
        run = _make_evaluation_run(scenario.id)

        score = await engine.evaluate_dimension(
            "situational_accuracy", scenario, run,
        )

        assert isinstance(score, DimensionScore)
        assert score.score == 4.5


# =============================================================================
# Test Group 5: Full Evaluation (All Dimensions)
# =============================================================================


class TestFullEvaluation:
    """Tests for evaluating all 5 dimensions and computing DRS."""

    @pytest.mark.asyncio
    async def test_evaluate_all_dimensions(self):
        from src.benchmark.evaluation_engine import EvaluationEngine

        scores = {d: 4.0 for d in DIMENSIONS}
        router = _make_mock_router(scores)
        engine = EvaluationEngine(router)

        scenario = _make_scenario()
        run = _make_evaluation_run(scenario.id)

        result = await engine.evaluate(scenario, run)

        # All 5 dimensions should be scored
        assert len(result.dimension_scores) == 5
        for dim in DIMENSIONS:
            assert dim in result.dimension_scores

    @pytest.mark.asyncio
    async def test_aggregate_drs_computation(self):
        from src.benchmark.evaluation_engine import EvaluationEngine

        # Known scores: all 4.0, all weights defined in rubric
        scores = {d: 4.0 for d in DIMENSIONS}
        router = _make_mock_router(scores)
        engine = EvaluationEngine(router)

        scenario = _make_scenario()
        run = _make_evaluation_run(scenario.id)

        result = await engine.evaluate(scenario, run)

        # All scores 4.0, weights sum to 1.0
        # DRS = weighted_sum / 5.0 = 4.0 / 5.0 = 0.8
        assert result.aggregate_drs == pytest.approx(0.8, abs=0.01)

    @pytest.mark.asyncio
    async def test_aggregate_drs_with_varying_scores(self):
        from src.benchmark.evaluation_engine import EvaluationEngine

        scores = {
            "situational_accuracy": 5.0,       # weight 0.25
            "decision_timeliness": 3.0,         # weight 0.25
            "resource_efficiency": 4.0,         # weight 0.20
            "coordination_quality": 2.0,        # weight 0.15
            "communication_appropriateness": 4.0,  # weight 0.15
        }
        router = _make_mock_router(scores)
        engine = EvaluationEngine(router)

        scenario = _make_scenario()
        run = _make_evaluation_run(scenario.id)

        result = await engine.evaluate(scenario, run)

        # DRS = (5*0.25 + 3*0.25 + 4*0.20 + 2*0.15 + 4*0.15) / 5.0
        # = (1.25 + 0.75 + 0.80 + 0.30 + 0.60) / 5.0
        # = 3.70 / 5.0 = 0.74
        assert result.aggregate_drs == pytest.approx(0.74, abs=0.01)

    @pytest.mark.asyncio
    async def test_evaluate_populates_run_scores(self):
        from src.benchmark.evaluation_engine import EvaluationEngine

        scores = {d: 4.0 for d in DIMENSIONS}
        router = _make_mock_router(scores)
        engine = EvaluationEngine(router)

        scenario = _make_scenario()
        run = _make_evaluation_run(scenario.id)

        result = await engine.evaluate(scenario, run)

        # Result should have eval token/cost tracking
        assert result.total_eval_tokens > 0
        assert result.total_eval_cost_usd > 0


# =============================================================================
# Test Group 6: Graceful Degradation
# =============================================================================


class TestGracefulDegradation:
    """Tests for handling LLM failures during evaluation."""

    @pytest.mark.asyncio
    async def test_llm_failure_marks_dimension_failed(self):
        from src.benchmark.evaluation_engine import EvaluationEngine
        from src.shared.errors import AllProvidersFailedError

        router = MagicMock()
        call_count = 0

        async def failing_call(tier, messages, **kwargs):
            nonlocal call_count
            call_count += 1
            prompt_text = str(messages)
            if "situational_accuracy" in prompt_text:
                raise AllProvidersFailedError("All providers down")
            # Other dimensions succeed
            content = _mock_llm_score_response("generic", 4.0)
            result = MagicMock()
            result.content = content
            result.provider = "mock"
            result.model = "mock-model"
            result.input_tokens = 200
            result.output_tokens = 100
            result.cost_usd = 0.001
            result.latency_s = 0.5
            result.tier = tier
            return result

        router.call = AsyncMock(side_effect=failing_call)
        engine = EvaluationEngine(router)

        scenario = _make_scenario()
        run = _make_evaluation_run(scenario.id)

        result = await engine.evaluate(scenario, run)

        # Failed dimension should have score 1.0 (minimum)
        assert result.dimension_scores["situational_accuracy"].score == 1.0
        # Other dimensions should still be scored
        assert len(result.dimension_scores) == 5

    @pytest.mark.asyncio
    async def test_all_dimensions_fail_still_returns_result(self):
        from src.benchmark.evaluation_engine import EvaluationEngine
        from src.shared.errors import AllProvidersFailedError

        router = MagicMock()
        router.call = AsyncMock(
            side_effect=AllProvidersFailedError("All providers down")
        )
        engine = EvaluationEngine(router)

        scenario = _make_scenario()
        run = _make_evaluation_run(scenario.id)

        result = await engine.evaluate(scenario, run)

        # All scores should be 1.0 (failed)
        for dim_score in result.dimension_scores.values():
            assert dim_score.score == 1.0
        # DRS should reflect all-failed state
        assert result.aggregate_drs == pytest.approx(0.2, abs=0.01)  # 1.0/5.0


# =============================================================================
# Test Group 7: Batch Evaluation
# =============================================================================


class TestBatchEvaluation:
    """Tests for evaluating multiple runs."""

    @pytest.mark.asyncio
    async def test_batch_evaluate_multiple_runs(self):
        from src.benchmark.evaluation_engine import EvaluationEngine

        router = _make_mock_router()
        engine = EvaluationEngine(router)

        scenario = _make_scenario()
        runs = [
            _make_evaluation_run(scenario.id),
            _make_evaluation_run(scenario.id),
        ]

        results = await engine.batch_evaluate(scenario, runs)

        assert len(results) == 2
        for result in results:
            assert len(result.dimension_scores) == 5

    @pytest.mark.asyncio
    async def test_batch_evaluate_empty_list(self):
        from src.benchmark.evaluation_engine import EvaluationEngine

        router = _make_mock_router()
        engine = EvaluationEngine(router)

        scenario = _make_scenario()
        results = await engine.batch_evaluate(scenario, [])

        assert results == []


# =============================================================================
# Test Group 8: No Rubric Scenario
# =============================================================================


class TestNoRubric:
    """Tests for scenarios without evaluation rubric."""

    @pytest.mark.asyncio
    async def test_evaluate_without_rubric_uses_defaults(self):
        from src.benchmark.evaluation_engine import EvaluationEngine

        router = _make_mock_router()
        engine = EvaluationEngine(router)

        # Scenario without rubric
        scenario = BenchmarkScenario(
            category="flood",
            complexity="low",
            affected_states=["Bihar"],
            event_sequence=[
                ScenarioEvent(
                    time_offset_minutes=0,
                    phase=DisasterPhase.ACTIVE_RESPONSE,
                    event_type="flood_alert",
                    description="Flood in Bihar",
                ),
            ],
            ground_truth_decisions=GroundTruthDecisions(
                agent_expectations={
                    "situation_sense": AgentExpectation(
                        key_observations=["Flooding"],
                        expected_actions=["Alert"],
                        time_window_minutes=(0, 10),
                    ),
                },
            ),
            evaluation_rubric=None,
        )
        run = _make_evaluation_run(scenario.id)

        result = await engine.evaluate(scenario, run)

        # Should still produce 5 dimension scores with equal weights
        assert len(result.dimension_scores) == 5
        assert result.aggregate_drs > 0
