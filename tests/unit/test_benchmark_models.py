"""Tests for benchmark scenario models and CRUD (spec S8.1).

Red → Green → Refactor: All tests written first, then implementation.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.shared.models import DisasterPhase

# =============================================================================
# Model Validation Tests
# =============================================================================


class TestScenarioEvent:
    """ScenarioEvent model validation."""

    def test_valid_event(self):
        from src.benchmark.models import ScenarioEvent

        evt = ScenarioEvent(
            time_offset_minutes=30,
            phase=DisasterPhase.PRE_EVENT,
            event_type="imd_warning",
            description="IMD issues red alert for Odisha coast",
            data_payload={"severity": 4, "wind_speed_kmph": 180},
        )
        assert evt.time_offset_minutes == 30
        assert evt.phase == DisasterPhase.PRE_EVENT
        assert evt.event_type == "imd_warning"
        assert evt.data_payload["severity"] == 4

    def test_default_payload(self):
        from src.benchmark.models import ScenarioEvent

        evt = ScenarioEvent(
            time_offset_minutes=0,
            phase=DisasterPhase.ACTIVE_RESPONSE,
            event_type="earthquake_detected",
            description="M6.2 earthquake detected",
        )
        assert evt.data_payload == {}

    def test_negative_offset_rejected(self):
        from src.benchmark.models import ScenarioEvent

        with pytest.raises(Exception):
            ScenarioEvent(
                time_offset_minutes=-1,
                phase=DisasterPhase.PRE_EVENT,
                event_type="test",
                description="test",
            )


class TestAgentExpectation:
    """AgentExpectation model validation."""

    def test_valid_expectation(self):
        from src.benchmark.models import AgentExpectation

        exp = AgentExpectation(
            key_observations=["Rainfall exceeds 100mm"],
            expected_actions=["Issue evacuation advisory"],
            time_window_minutes=(0, 60),
        )
        assert len(exp.key_observations) == 1
        assert exp.time_window_minutes == (0, 60)

    def test_empty_observations_allowed(self):
        from src.benchmark.models import AgentExpectation

        exp = AgentExpectation(
            key_observations=[],
            expected_actions=["Deploy NDRF"],
            time_window_minutes=(30, 120),
        )
        assert exp.key_observations == []


class TestGroundTruthDecisions:
    """GroundTruthDecisions model validation."""

    def test_valid_ground_truth(self):
        from src.benchmark.models import AgentExpectation, GroundTruthDecisions

        gt = GroundTruthDecisions(
            agent_expectations={
                "situation_sense": AgentExpectation(
                    key_observations=["High rainfall"],
                    expected_actions=["Report urgency 4"],
                    time_window_minutes=(0, 30),
                ),
            },
            decision_timeline={"minute_0_30": "Initial assessment"},
            ndma_references=["NDMA Flood Guidelines Section 3.1"],
        )
        assert "situation_sense" in gt.agent_expectations
        assert len(gt.ndma_references) == 1

    def test_empty_expectations(self):
        from src.benchmark.models import GroundTruthDecisions

        gt = GroundTruthDecisions(
            agent_expectations={},
            decision_timeline={},
            ndma_references=[],
        )
        assert gt.agent_expectations == {}


class TestDimensionCriteria:
    """DimensionCriteria model validation."""

    def test_valid_criteria(self):
        from src.benchmark.models import DimensionCriteria

        dc = DimensionCriteria(
            weight=0.25,
            criteria={"excellent": ">90% facts identified", "poor": "<50% facts"},
            key_factors=["rainfall_detection", "river_level_monitoring"],
        )
        assert dc.weight == 0.25
        assert len(dc.key_factors) == 2

    def test_weight_bounds(self):
        from src.benchmark.models import DimensionCriteria

        with pytest.raises(Exception):
            DimensionCriteria(weight=1.5, criteria={}, key_factors=[])

        with pytest.raises(Exception):
            DimensionCriteria(weight=-0.1, criteria={}, key_factors=[])


class TestEvaluationRubric:
    """EvaluationRubric model with weight sum validation."""

    def _make_criteria(self, weight: float):
        from src.benchmark.models import DimensionCriteria

        return DimensionCriteria(weight=weight, criteria={}, key_factors=[])

    def test_valid_rubric_equal_weights(self):
        from src.benchmark.models import EvaluationRubric

        rubric = EvaluationRubric(
            situational_accuracy=self._make_criteria(0.20),
            decision_timeliness=self._make_criteria(0.20),
            resource_efficiency=self._make_criteria(0.20),
            coordination_quality=self._make_criteria(0.20),
            communication_appropriateness=self._make_criteria(0.20),
        )
        assert rubric.total_weight == pytest.approx(1.0)

    def test_valid_rubric_custom_weights(self):
        from src.benchmark.models import EvaluationRubric

        rubric = EvaluationRubric(
            situational_accuracy=self._make_criteria(0.15),
            decision_timeliness=self._make_criteria(0.30),
            resource_efficiency=self._make_criteria(0.15),
            coordination_quality=self._make_criteria(0.25),
            communication_appropriateness=self._make_criteria(0.15),
        )
        assert rubric.total_weight == pytest.approx(1.0)

    def test_invalid_weights_rejected(self):
        from src.benchmark.models import EvaluationRubric

        with pytest.raises(Exception):
            EvaluationRubric(
                situational_accuracy=self._make_criteria(0.50),
                decision_timeliness=self._make_criteria(0.50),
                resource_efficiency=self._make_criteria(0.50),
                coordination_quality=self._make_criteria(0.50),
                communication_appropriateness=self._make_criteria(0.50),
            )


# =============================================================================
# BenchmarkScenario Enhanced Model
# =============================================================================


class TestBenchmarkScenarioModel:
    """Enhanced BenchmarkScenario with typed sub-models."""

    def _make_scenario(self):
        from src.benchmark.models import (
            AgentExpectation,
            BenchmarkScenario,
            DimensionCriteria,
            EvaluationRubric,
            GroundTruthDecisions,
            ScenarioEvent,
        )

        return BenchmarkScenario(
            category="cyclone",
            complexity="high",
            affected_states=["Odisha", "Andhra Pradesh"],
            primary_language="Odia",
            initial_state={"severity": 4, "description": "VSCS approaching Odisha"},
            event_sequence=[
                ScenarioEvent(
                    time_offset_minutes=0,
                    phase=DisasterPhase.PRE_EVENT,
                    event_type="imd_warning",
                    description="IMD issues red alert",
                ),
                ScenarioEvent(
                    time_offset_minutes=120,
                    phase=DisasterPhase.ACTIVE_RESPONSE,
                    event_type="landfall",
                    description="Cyclone makes landfall at Puri",
                ),
            ],
            ground_truth_decisions=GroundTruthDecisions(
                agent_expectations={
                    "situation_sense": AgentExpectation(
                        key_observations=["VSCS approaching"],
                        expected_actions=["Issue urgency 5"],
                        time_window_minutes=(0, 30),
                    ),
                },
                decision_timeline={"minute_0_30": "Initial alert"},
                ndma_references=["NDMA Cyclone Guidelines"],
            ),
            evaluation_rubric=EvaluationRubric(
                situational_accuracy=DimensionCriteria(
                    weight=0.20, criteria={}, key_factors=[]
                ),
                decision_timeliness=DimensionCriteria(
                    weight=0.20, criteria={}, key_factors=[]
                ),
                resource_efficiency=DimensionCriteria(
                    weight=0.20, criteria={}, key_factors=[]
                ),
                coordination_quality=DimensionCriteria(
                    weight=0.20, criteria={}, key_factors=[]
                ),
                communication_appropriateness=DimensionCriteria(
                    weight=0.20, criteria={}, key_factors=[]
                ),
            ),
            tags=["coastal", "multi-state"],
            source="synthetic",
        )

    def test_scenario_construction(self):
        s = self._make_scenario()
        assert s.category == "cyclone"
        assert s.complexity == "high"
        assert len(s.event_sequence) == 2
        assert s.tags == ["coastal", "multi-state"]
        assert s.source == "synthetic"

    def test_events_are_typed(self):
        from src.benchmark.models import ScenarioEvent

        s = self._make_scenario()
        assert isinstance(s.event_sequence[0], ScenarioEvent)
        assert s.event_sequence[0].phase == DisasterPhase.PRE_EVENT

    def test_ground_truth_is_typed(self):
        from src.benchmark.models import GroundTruthDecisions

        s = self._make_scenario()
        assert isinstance(s.ground_truth_decisions, GroundTruthDecisions)
        assert "situation_sense" in s.ground_truth_decisions.agent_expectations

    def test_rubric_is_typed(self):
        from src.benchmark.models import EvaluationRubric

        s = self._make_scenario()
        assert isinstance(s.evaluation_rubric, EvaluationRubric)

    def test_to_db_row(self):
        s = self._make_scenario()
        row = s.to_db_row()
        assert isinstance(row["id"], uuid.UUID)
        assert row["category"] == "cyclone"
        # JSONB fields should be JSON strings
        assert isinstance(row["event_sequence"], str)
        assert isinstance(row["ground_truth_decisions"], str)
        assert isinstance(row["evaluation_rubric"], str)
        parsed_events = json.loads(row["event_sequence"])
        assert len(parsed_events) == 2

    def test_from_db_row(self):
        from src.benchmark.models import BenchmarkScenario

        s = self._make_scenario()
        row = s.to_db_row()
        # Simulate DB record as dict
        restored = BenchmarkScenario.from_db_row(row)
        assert restored.category == s.category
        assert len(restored.event_sequence) == len(s.event_sequence)
        assert restored.event_sequence[0].event_type == "imd_warning"

    def test_serialization_roundtrip(self):
        from src.benchmark.models import BenchmarkScenario

        s = self._make_scenario()
        json_str = s.model_dump_json()
        restored = BenchmarkScenario.model_validate_json(json_str)
        assert restored.category == s.category
        assert len(restored.event_sequence) == 2
        assert restored.ground_truth_decisions.ndma_references == ["NDMA Cyclone Guidelines"]


# =============================================================================
# EvaluationRun Enhanced Model
# =============================================================================


class TestEvaluationRunModel:
    """Enhanced EvaluationRun model."""

    def test_valid_run(self):
        from src.benchmark.models import EvaluationRun

        run = EvaluationRun(
            scenario_id=uuid.uuid4(),
            agent_config={"primary_provider": "deepseek"},
            situational_accuracy=0.85,
            decision_timeliness=0.90,
            resource_efficiency=0.78,
            coordination_quality=0.88,
            communication_score=0.82,
            aggregate_drs=0.85,
            total_tokens=5000,
            total_cost_usd=0.05,
            primary_provider="deepseek",
            agent_decisions=[{"agent": "orchestrator", "action": "decompose"}],
            duration_seconds=42.5,
            error_log=[],
        )
        assert run.situational_accuracy == 0.85
        assert run.duration_seconds == 42.5
        assert len(run.agent_decisions) == 1

    def test_defaults(self):
        from src.benchmark.models import EvaluationRun

        run = EvaluationRun(
            scenario_id=uuid.uuid4(),
            agent_config={},
        )
        assert run.agent_decisions == []
        assert run.duration_seconds is None
        assert run.error_log == []


# =============================================================================
# CRUD Tests (mock asyncpg)
# =============================================================================


def _make_mock_pool():
    """Create a mock asyncpg pool with context manager support."""
    pool = MagicMock()
    conn = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = ctx
    return pool, conn


async def _mock_get_pool(pool):
    """Async wrapper that returns the mock pool."""
    return pool


class TestScenarioCRUD:
    """Scenario CRUD operations (mocked DB)."""

    @pytest.mark.asyncio
    async def test_create_scenario(self):
        from src.benchmark.models import (
            BenchmarkScenario,
            DimensionCriteria,
            EvaluationRubric,
            GroundTruthDecisions,
            ScenarioEvent,
            create_scenario,
        )

        pool, conn = _make_mock_pool()
        conn.execute = AsyncMock(return_value="INSERT 0 1")

        scenario = BenchmarkScenario(
            category="monsoon_flood",
            complexity="medium",
            affected_states=["Bihar"],
            primary_language="Hindi",
            initial_state={"severity": 3},
            event_sequence=[
                ScenarioEvent(
                    time_offset_minutes=0,
                    phase=DisasterPhase.PRE_EVENT,
                    event_type="rainfall_warning",
                    description="Heavy rainfall forecast",
                ),
            ],
            ground_truth_decisions=GroundTruthDecisions(
                agent_expectations={},
                decision_timeline={},
                ndma_references=[],
            ),
            evaluation_rubric=EvaluationRubric(
                situational_accuracy=DimensionCriteria(
                    weight=0.20, criteria={}, key_factors=[]
                ),
                decision_timeliness=DimensionCriteria(
                    weight=0.20, criteria={}, key_factors=[]
                ),
                resource_efficiency=DimensionCriteria(
                    weight=0.20, criteria={}, key_factors=[]
                ),
                coordination_quality=DimensionCriteria(
                    weight=0.20, criteria={}, key_factors=[]
                ),
                communication_appropriateness=DimensionCriteria(
                    weight=0.20, criteria={}, key_factors=[]
                ),
            ),
        )

        with patch("src.benchmark.models.get_pool", AsyncMock(return_value=pool)):
            result = await create_scenario(scenario)

        assert isinstance(result, uuid.UUID)
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_scenario_found(self):
        from src.benchmark.models import BenchmarkScenario, get_scenario

        scenario_id = uuid.uuid4()
        pool, conn = _make_mock_pool()
        conn.fetchrow = AsyncMock(
            return_value={
                "id": scenario_id,
                "category": "cyclone",
                "complexity": "high",
                "affected_states": ["Odisha"],
                "primary_language": "Odia",
                "initial_state": json.dumps({"severity": 4}),
                "event_sequence": json.dumps([]),
                "ground_truth_decisions": json.dumps(
                    {
                        "agent_expectations": {},
                        "decision_timeline": {},
                        "ndma_references": [],
                    }
                ),
                "evaluation_rubric": json.dumps(
                    {
                        "situational_accuracy": {
                            "weight": 0.20, "criteria": {}, "key_factors": []
                        },
                        "decision_timeliness": {
                            "weight": 0.20, "criteria": {}, "key_factors": []
                        },
                        "resource_efficiency": {
                            "weight": 0.20, "criteria": {}, "key_factors": []
                        },
                        "coordination_quality": {
                            "weight": 0.20, "criteria": {}, "key_factors": []
                        },
                        "communication_appropriateness": {
                            "weight": 0.20, "criteria": {}, "key_factors": []
                        },
                    }
                ),
                "version": 1,
                "tags": ["coastal"],
                "source": "synthetic",
                "created_at": datetime.now(tz=UTC),
            }
        )

        with patch("src.benchmark.models.get_pool", AsyncMock(return_value=pool)):
            result = await get_scenario(scenario_id)

        assert result is not None
        assert isinstance(result, BenchmarkScenario)
        assert result.category == "cyclone"

    @pytest.mark.asyncio
    async def test_get_scenario_not_found(self):
        from src.benchmark.models import get_scenario

        pool, conn = _make_mock_pool()
        conn.fetchrow = AsyncMock(return_value=None)

        with patch("src.benchmark.models.get_pool", AsyncMock(return_value=pool)):
            result = await get_scenario(uuid.uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_list_scenarios_no_filter(self):
        from src.benchmark.models import list_scenarios

        pool, conn = _make_mock_pool()
        conn.fetch = AsyncMock(return_value=[])

        with patch("src.benchmark.models.get_pool", AsyncMock(return_value=pool)):
            result = await list_scenarios()

        assert result == []
        conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_scenarios_with_category(self):
        from src.benchmark.models import list_scenarios

        pool, conn = _make_mock_pool()
        conn.fetch = AsyncMock(return_value=[])

        with patch("src.benchmark.models.get_pool", AsyncMock(return_value=pool)):
            await list_scenarios(category="cyclone")

        call_args = conn.fetch.call_args
        query = call_args[0][0]
        assert "category" in query

    @pytest.mark.asyncio
    async def test_count_scenarios(self):
        from src.benchmark.models import count_scenarios

        pool, conn = _make_mock_pool()
        conn.fetchval = AsyncMock(return_value=42)

        with patch("src.benchmark.models.get_pool", AsyncMock(return_value=pool)):
            result = await count_scenarios()

        assert result == 42

    @pytest.mark.asyncio
    async def test_update_scenario(self):
        from src.benchmark.models import update_scenario

        pool, conn = _make_mock_pool()
        conn.execute = AsyncMock(return_value="UPDATE 1")

        with patch("src.benchmark.models.get_pool", AsyncMock(return_value=pool)):
            result = await update_scenario(uuid.uuid4(), version=2)

        assert result is True

    @pytest.mark.asyncio
    async def test_update_scenario_not_found(self):
        from src.benchmark.models import update_scenario

        pool, conn = _make_mock_pool()
        conn.execute = AsyncMock(return_value="UPDATE 0")

        with patch("src.benchmark.models.get_pool", AsyncMock(return_value=pool)):
            result = await update_scenario(uuid.uuid4(), version=2)

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_scenario(self):
        from src.benchmark.models import delete_scenario

        pool, conn = _make_mock_pool()
        conn.execute = AsyncMock(return_value="DELETE 1")

        with patch("src.benchmark.models.get_pool", AsyncMock(return_value=pool)):
            result = await delete_scenario(uuid.uuid4())

        assert result is True


class TestEvaluationRunCRUD:
    """Evaluation run CRUD operations (mocked DB)."""

    @pytest.mark.asyncio
    async def test_create_evaluation_run(self):
        from src.benchmark.models import EvaluationRun, create_evaluation_run

        pool, conn = _make_mock_pool()
        conn.execute = AsyncMock(return_value="INSERT 0 1")

        run = EvaluationRun(
            scenario_id=uuid.uuid4(),
            agent_config={"primary_provider": "deepseek"},
            situational_accuracy=0.85,
            decision_timeliness=0.90,
            resource_efficiency=0.78,
            coordination_quality=0.88,
            communication_score=0.82,
            aggregate_drs=0.85,
        )

        with patch("src.benchmark.models.get_pool", AsyncMock(return_value=pool)):
            result = await create_evaluation_run(run)

        assert isinstance(result, uuid.UUID)

    @pytest.mark.asyncio
    async def test_get_evaluation_run(self):
        from src.benchmark.models import get_evaluation_run

        run_id = uuid.uuid4()
        pool, conn = _make_mock_pool()
        conn.fetchrow = AsyncMock(
            return_value={
                "id": run_id,
                "scenario_id": uuid.uuid4(),
                "agent_config": json.dumps({}),
                "situational_accuracy": 0.85,
                "decision_timeliness": 0.90,
                "resource_efficiency": 0.78,
                "coordination_quality": 0.88,
                "communication_score": 0.82,
                "aggregate_drs": 0.85,
                "total_tokens": 5000,
                "total_cost_usd": 0.05,
                "primary_provider": "deepseek",
                "agent_decisions": json.dumps([]),
                "duration_seconds": 42.5,
                "error_log": json.dumps([]),
                "completed_at": datetime.now(tz=UTC),
            }
        )

        with patch("src.benchmark.models.get_pool", AsyncMock(return_value=pool)):
            result = await get_evaluation_run(run_id)

        assert result is not None
        assert result.situational_accuracy == 0.85

    @pytest.mark.asyncio
    async def test_list_runs_for_scenario(self):
        from src.benchmark.models import list_runs_for_scenario

        pool, conn = _make_mock_pool()
        conn.fetch = AsyncMock(return_value=[])

        with patch("src.benchmark.models.get_pool", AsyncMock(return_value=pool)):
            result = await list_runs_for_scenario(uuid.uuid4())

        assert result == []

    @pytest.mark.asyncio
    async def test_list_recent_runs(self):
        from src.benchmark.models import list_recent_runs

        pool, conn = _make_mock_pool()
        conn.fetch = AsyncMock(return_value=[])

        with patch("src.benchmark.models.get_pool", AsyncMock(return_value=pool)):
            result = await list_recent_runs(limit=10)

        assert result == []
