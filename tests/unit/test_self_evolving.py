"""Tests for self-evolving benchmark generator (spec S8.11).

Red -> Green -> Refactor: All tests written first, then implementation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
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


def _make_rubric(weight: float = 0.20) -> EvaluationRubric:
    def dc(w: float = weight) -> DimensionCriteria:
        return DimensionCriteria(weight=w, criteria={}, key_factors=[])

    return EvaluationRubric(
        situational_accuracy=dc(),
        decision_timeliness=dc(),
        resource_efficiency=dc(),
        coordination_quality=dc(),
        communication_appropriateness=dc(),
    )


def _make_scenario(
    category: str = "cyclone",
    complexity: str = "high",
    affected_states: list[str] | None = None,
    primary_language: str = "Odia",
    tags: list[str] | None = None,
    initial_state: dict | None = None,
) -> BenchmarkScenario:
    return BenchmarkScenario(
        id=uuid.uuid4(),
        category=category,
        complexity=complexity,
        affected_states=affected_states or ["Odisha"],
        primary_language=primary_language,
        initial_state=initial_state or {
            "severity": 4,
            "description": "Test cyclone scenario",
            "affected_population": 500_000,
            "ndrf_battalions": 6,
            "shelters_available": 20,
            "season": "October",
            "time_of_day": "14:00",
        },
        event_sequence=[
            ScenarioEvent(
                time_offset_minutes=0,
                phase=DisasterPhase.PRE_EVENT,
                event_type="imd_warning",
                description="IMD issues red alert for cyclone",
            ),
            ScenarioEvent(
                time_offset_minutes=120,
                phase=DisasterPhase.ACTIVE_RESPONSE,
                event_type="evacuation_order",
                description="District collector orders evacuation",
            ),
            ScenarioEvent(
                time_offset_minutes=360,
                phase=DisasterPhase.RECOVERY,
                event_type="damage_assessment",
                description="Post-landfall damage assessment begins",
            ),
        ],
        ground_truth_decisions=GroundTruthDecisions(
            agent_expectations={
                "situation_sense": AgentExpectation(
                    key_observations=["Cyclone approaching coast"],
                    expected_actions=["Issue urgency 5 alert"],
                    time_window_minutes=(0, 30),
                ),
            },
            decision_timeline={"minute_0_30": "Initial alert"},
            ndma_references=["NDMA Cyclone Guidelines Ch.5"],
        ),
        evaluation_rubric=_make_rubric(),
        tags=tags or ["coastal"],
        source="synthetic",
    )


def _make_eval_run(
    scenario_id: uuid.UUID,
    aggregate_drs: float = 0.6,
    agent_config: dict | None = None,
) -> EvaluationRun:
    return EvaluationRun(
        id=uuid.uuid4(),
        scenario_id=scenario_id,
        agent_config=agent_config or {"model": "deepseek-v3", "version": "1.0"},
        aggregate_drs=aggregate_drs,
        completed_at=datetime.now(tz=UTC),
    )


# =============================================================================
# Perturbation: Geographic Swap
# =============================================================================


class TestGeographicSwap:
    """Geographic swap changes states and language but preserves category."""

    @pytest.mark.asyncio
    async def test_changes_affected_states(self):
        from src.benchmark.self_evolving import perturb_geographic_swap

        original = _make_scenario(affected_states=["Odisha"], primary_language="Odia")
        result = await perturb_geographic_swap(original, target_states=["Tamil Nadu"])

        assert result.affected_states == ["Tamil Nadu"]
        assert result.affected_states != original.affected_states

    @pytest.mark.asyncio
    async def test_changes_primary_language(self):
        from src.benchmark.self_evolving import perturb_geographic_swap

        original = _make_scenario(affected_states=["Odisha"], primary_language="Odia")
        result = await perturb_geographic_swap(
            original, target_states=["Tamil Nadu"], target_language="Tamil"
        )

        assert result.primary_language == "Tamil"

    @pytest.mark.asyncio
    async def test_preserves_category(self):
        from src.benchmark.self_evolving import perturb_geographic_swap

        original = _make_scenario(category="cyclone")
        result = await perturb_geographic_swap(original, target_states=["Gujarat"])

        assert result.category == "cyclone"

    @pytest.mark.asyncio
    async def test_preserves_event_count(self):
        from src.benchmark.self_evolving import perturb_geographic_swap

        original = _make_scenario()
        result = await perturb_geographic_swap(original, target_states=["Gujarat"])

        assert len(result.event_sequence) == len(original.event_sequence)

    @pytest.mark.asyncio
    async def test_new_id_assigned(self):
        from src.benchmark.self_evolving import perturb_geographic_swap

        original = _make_scenario()
        result = await perturb_geographic_swap(original, target_states=["Gujarat"])

        assert result.id != original.id

    @pytest.mark.asyncio
    async def test_version_reset_to_1(self):
        from src.benchmark.self_evolving import perturb_geographic_swap

        original = _make_scenario()
        result = await perturb_geographic_swap(original, target_states=["Gujarat"])

        assert result.version == 1

    @pytest.mark.asyncio
    async def test_source_set_to_perturbation(self):
        from src.benchmark.self_evolving import perturb_geographic_swap

        original = _make_scenario()
        result = await perturb_geographic_swap(original, target_states=["Gujarat"])

        assert result.source == "perturbation"


# =============================================================================
# Perturbation: Temporal Shift
# =============================================================================


class TestTemporalShift:
    """Temporal shift changes season/time but preserves geography."""

    @pytest.mark.asyncio
    async def test_changes_season(self):
        from src.benchmark.self_evolving import perturb_temporal_shift

        original = _make_scenario(
            initial_state={"season": "October", "time_of_day": "14:00", "severity": 4}
        )
        result = await perturb_temporal_shift(
            original, target_season="April", target_time="02:00"
        )

        assert result.initial_state["season"] == "April"

    @pytest.mark.asyncio
    async def test_changes_time_of_day(self):
        from src.benchmark.self_evolving import perturb_temporal_shift

        original = _make_scenario(
            initial_state={"season": "October", "time_of_day": "14:00", "severity": 4}
        )
        result = await perturb_temporal_shift(
            original, target_season="October", target_time="02:00"
        )

        assert result.initial_state["time_of_day"] == "02:00"

    @pytest.mark.asyncio
    async def test_preserves_geography(self):
        from src.benchmark.self_evolving import perturb_temporal_shift

        original = _make_scenario(affected_states=["Odisha"])
        result = await perturb_temporal_shift(original, target_season="April")

        assert result.affected_states == ["Odisha"]

    @pytest.mark.asyncio
    async def test_preserves_category(self):
        from src.benchmark.self_evolving import perturb_temporal_shift

        original = _make_scenario(category="cyclone")
        result = await perturb_temporal_shift(original, target_season="April")

        assert result.category == "cyclone"

    @pytest.mark.asyncio
    async def test_source_set_to_perturbation(self):
        from src.benchmark.self_evolving import perturb_temporal_shift

        original = _make_scenario()
        result = await perturb_temporal_shift(original, target_season="April")

        assert result.source == "perturbation"


# =============================================================================
# Perturbation: Resource Constraint
# =============================================================================


class TestResourceConstraint:
    """Resource constraint reduces available resources by 30-50%."""

    @pytest.mark.asyncio
    async def test_reduces_ndrf_battalions(self):
        from src.benchmark.self_evolving import perturb_resource_constraint

        original = _make_scenario(
            initial_state={
                "severity": 4,
                "ndrf_battalions": 10,
                "shelters_available": 20,
            }
        )
        result = await perturb_resource_constraint(original, reduction_factor=0.5)

        assert result.initial_state["ndrf_battalions"] == 5

    @pytest.mark.asyncio
    async def test_reduces_shelters(self):
        from src.benchmark.self_evolving import perturb_resource_constraint

        original = _make_scenario(
            initial_state={
                "severity": 4,
                "ndrf_battalions": 10,
                "shelters_available": 20,
            }
        )
        result = await perturb_resource_constraint(original, reduction_factor=0.5)

        assert result.initial_state["shelters_available"] == 10

    @pytest.mark.asyncio
    async def test_reduction_factor_bounds(self):
        from src.benchmark.self_evolving import perturb_resource_constraint

        original = _make_scenario(
            initial_state={
                "severity": 4,
                "ndrf_battalions": 10,
                "shelters_available": 20,
            }
        )
        # 30% reduction
        result = await perturb_resource_constraint(original, reduction_factor=0.3)
        assert result.initial_state["ndrf_battalions"] == 7

    @pytest.mark.asyncio
    async def test_preserves_category_and_states(self):
        from src.benchmark.self_evolving import perturb_resource_constraint

        original = _make_scenario(category="cyclone", affected_states=["Odisha"])
        result = await perturb_resource_constraint(original, reduction_factor=0.5)

        assert result.category == "cyclone"
        assert result.affected_states == ["Odisha"]

    @pytest.mark.asyncio
    async def test_source_set_to_perturbation(self):
        from src.benchmark.self_evolving import perturb_resource_constraint

        original = _make_scenario()
        result = await perturb_resource_constraint(original, reduction_factor=0.5)

        assert result.source == "perturbation"

    @pytest.mark.asyncio
    async def test_minimum_one_resource(self):
        from src.benchmark.self_evolving import perturb_resource_constraint

        original = _make_scenario(
            initial_state={
                "severity": 4,
                "ndrf_battalions": 1,
                "shelters_available": 1,
            }
        )
        result = await perturb_resource_constraint(original, reduction_factor=0.5)

        # Should not reduce below 1
        assert result.initial_state["ndrf_battalions"] >= 1
        assert result.initial_state["shelters_available"] >= 1


# =============================================================================
# Perturbation: Cascading Injection
# =============================================================================


class TestCascadingInjection:
    """Cascading injection adds a secondary disaster event."""

    @pytest.mark.asyncio
    async def test_adds_secondary_event(self):
        from src.benchmark.self_evolving import perturb_cascading_injection

        original = _make_scenario()
        event_count_before = len(original.event_sequence)
        result = await perturb_cascading_injection(
            original, secondary_type="earthquake", secondary_description="Aftershock M4.5"
        )

        assert len(result.event_sequence) > event_count_before

    @pytest.mark.asyncio
    async def test_secondary_event_type(self):
        from src.benchmark.self_evolving import perturb_cascading_injection

        original = _make_scenario()
        result = await perturb_cascading_injection(
            original, secondary_type="earthquake", secondary_description="Aftershock M4.5"
        )

        event_types = [e.event_type for e in result.event_sequence]
        assert "earthquake" in event_types

    @pytest.mark.asyncio
    async def test_preserves_original_events(self):
        from src.benchmark.self_evolving import perturb_cascading_injection

        original = _make_scenario()
        original_types = [e.event_type for e in original.event_sequence]
        result = await perturb_cascading_injection(
            original, secondary_type="earthquake", secondary_description="Aftershock"
        )

        result_types = [e.event_type for e in result.event_sequence]
        for t in original_types:
            assert t in result_types

    @pytest.mark.asyncio
    async def test_events_remain_chronological(self):
        from src.benchmark.self_evolving import perturb_cascading_injection

        original = _make_scenario()
        result = await perturb_cascading_injection(
            original, secondary_type="earthquake", secondary_description="Aftershock"
        )

        offsets = [e.time_offset_minutes for e in result.event_sequence]
        assert offsets == sorted(offsets)

    @pytest.mark.asyncio
    async def test_source_set_to_perturbation(self):
        from src.benchmark.self_evolving import perturb_cascading_injection

        original = _make_scenario()
        result = await perturb_cascading_injection(
            original, secondary_type="earthquake", secondary_description="Aftershock"
        )

        assert result.source == "perturbation"


# =============================================================================
# Perturbation: Communication Degradation
# =============================================================================


class TestCommunicationDegradation:
    """Communication degradation simulates telecom/internet failure."""

    @pytest.mark.asyncio
    async def test_adds_telecom_failure_event(self):
        from src.benchmark.self_evolving import perturb_communication_degradation

        original = _make_scenario()
        result = await perturb_communication_degradation(original)

        event_types = [e.event_type for e in result.event_sequence]
        assert "telecom_failure" in event_types

    @pytest.mark.asyncio
    async def test_marks_initial_state(self):
        from src.benchmark.self_evolving import perturb_communication_degradation

        original = _make_scenario()
        result = await perturb_communication_degradation(original)

        assert result.initial_state.get("telecom_degraded") is True

    @pytest.mark.asyncio
    async def test_preserves_original_events(self):
        from src.benchmark.self_evolving import perturb_communication_degradation

        original = _make_scenario()
        original_count = len(original.event_sequence)
        result = await perturb_communication_degradation(original)

        # Should have original events + telecom failure
        assert len(result.event_sequence) > original_count

    @pytest.mark.asyncio
    async def test_source_set_to_perturbation(self):
        from src.benchmark.self_evolving import perturb_communication_degradation

        original = _make_scenario()
        result = await perturb_communication_degradation(original)

        assert result.source == "perturbation"


# =============================================================================
# Contamination Detection
# =============================================================================


class TestContaminationDetection:
    """Contamination detection flags scenarios with suspicious score jumps."""

    @pytest.mark.asyncio
    async def test_no_flag_stable_scores(self):
        from src.benchmark.self_evolving import detect_contamination

        scenario_id = uuid.uuid4()
        runs = [
            _make_eval_run(scenario_id, aggregate_drs=0.60),
            _make_eval_run(scenario_id, aggregate_drs=0.62),
            _make_eval_run(scenario_id, aggregate_drs=0.58),
            _make_eval_run(scenario_id, aggregate_drs=0.61),
            _make_eval_run(scenario_id, aggregate_drs=0.63),
        ]

        flagged = await detect_contamination({scenario_id: runs})
        assert scenario_id not in flagged

    @pytest.mark.asyncio
    async def test_flags_performance_jump(self):
        from src.benchmark.self_evolving import detect_contamination

        scenario_id = uuid.uuid4()
        # Stable scores around 0.60, then sudden jump to 0.90
        runs = [
            _make_eval_run(scenario_id, aggregate_drs=0.58),
            _make_eval_run(scenario_id, aggregate_drs=0.60),
            _make_eval_run(scenario_id, aggregate_drs=0.62),
            _make_eval_run(scenario_id, aggregate_drs=0.59),
            _make_eval_run(scenario_id, aggregate_drs=0.90),  # suspicious jump
        ]

        flagged = await detect_contamination({scenario_id: runs})
        assert scenario_id in flagged

    @pytest.mark.asyncio
    async def test_no_flag_if_model_changed(self):
        from src.benchmark.self_evolving import detect_contamination

        scenario_id = uuid.uuid4()
        runs = [
            _make_eval_run(
                scenario_id, aggregate_drs=0.58,
                agent_config={"model": "deepseek-v3", "version": "1.0"},
            ),
            _make_eval_run(
                scenario_id, aggregate_drs=0.60,
                agent_config={"model": "deepseek-v3", "version": "1.0"},
            ),
            _make_eval_run(
                scenario_id, aggregate_drs=0.62,
                agent_config={"model": "deepseek-v3", "version": "1.0"},
            ),
            _make_eval_run(
                scenario_id, aggregate_drs=0.90,
                agent_config={"model": "deepseek-v4", "version": "2.0"},  # new model
            ),
        ]

        flagged = await detect_contamination({scenario_id: runs})
        assert scenario_id not in flagged

    @pytest.mark.asyncio
    async def test_insufficient_data_no_flag(self):
        from src.benchmark.self_evolving import detect_contamination

        scenario_id = uuid.uuid4()
        runs = [_make_eval_run(scenario_id, aggregate_drs=0.90)]

        flagged = await detect_contamination({scenario_id: runs})
        assert scenario_id not in flagged

    @pytest.mark.asyncio
    async def test_multiple_scenarios(self):
        from src.benchmark.self_evolving import detect_contamination

        sid1 = uuid.uuid4()
        sid2 = uuid.uuid4()

        runs_map = {
            sid1: [  # stable — no flag
                _make_eval_run(sid1, aggregate_drs=0.60),
                _make_eval_run(sid1, aggregate_drs=0.62),
                _make_eval_run(sid1, aggregate_drs=0.61),
            ],
            sid2: [  # jump — should flag
                _make_eval_run(sid2, aggregate_drs=0.50),
                _make_eval_run(sid2, aggregate_drs=0.52),
                _make_eval_run(sid2, aggregate_drs=0.48),
                _make_eval_run(sid2, aggregate_drs=0.85),
            ],
        }

        flagged = await detect_contamination(runs_map)
        assert sid1 not in flagged
        assert sid2 in flagged


# =============================================================================
# Generate from Historical
# =============================================================================


class TestGenerateFromHistorical:
    """Generate scenarios from historical disaster data via LLM."""

    @pytest.mark.asyncio
    async def test_returns_valid_scenario(self):
        from src.benchmark.self_evolving import SelfEvolvingGenerator

        mock_router = MagicMock()
        mock_gen = AsyncMock()
        mock_gen.generate_scenario = AsyncMock(return_value=_make_scenario())

        generator = SelfEvolvingGenerator(
            router=mock_router, scenario_generator=mock_gen
        )
        result = await generator.generate_from_historical(
            category="cyclone",
            complexity="high",
            historical_context="Cyclone Fani hit Odisha in May 2019",
        )

        assert isinstance(result, BenchmarkScenario)
        assert result.category == "cyclone"

    @pytest.mark.asyncio
    async def test_sets_source_to_historical(self):
        from src.benchmark.self_evolving import SelfEvolvingGenerator

        mock_router = MagicMock()
        scenario = _make_scenario()
        mock_gen = AsyncMock()
        mock_gen.generate_scenario = AsyncMock(return_value=scenario)

        generator = SelfEvolvingGenerator(
            router=mock_router, scenario_generator=mock_gen
        )
        result = await generator.generate_from_historical(
            category="cyclone",
            complexity="high",
            historical_context="Cyclone Fani 2019",
        )

        assert result.source == "historical"


# =============================================================================
# Evolve Benchmark (Orchestrator)
# =============================================================================


class TestEvolveBenchmark:
    """evolve_benchmark orchestrates perturbation + generation."""

    @pytest.mark.asyncio
    async def test_returns_new_scenarios(self):
        from src.benchmark.self_evolving import SelfEvolvingGenerator

        mock_router = MagicMock()
        mock_gen = AsyncMock()
        mock_gen.generate_scenario = AsyncMock(return_value=_make_scenario())

        mock_mgr = AsyncMock()
        mock_mgr.search = AsyncMock(return_value=[_make_scenario(), _make_scenario()])

        generator = SelfEvolvingGenerator(
            router=mock_router,
            scenario_generator=mock_gen,
            scenario_manager=mock_mgr,
        )

        results = await generator.evolve_benchmark(
            num_perturbations=2,
            num_historical=1,
        )

        assert len(results) >= 1  # at least some scenarios generated

    @pytest.mark.asyncio
    async def test_returns_list_of_benchmark_scenarios(self):
        from src.benchmark.self_evolving import SelfEvolvingGenerator

        mock_router = MagicMock()
        mock_gen = AsyncMock()
        mock_gen.generate_scenario = AsyncMock(return_value=_make_scenario())

        mock_mgr = AsyncMock()
        mock_mgr.search = AsyncMock(return_value=[_make_scenario()])

        generator = SelfEvolvingGenerator(
            router=mock_router,
            scenario_generator=mock_gen,
            scenario_manager=mock_mgr,
        )

        results = await generator.evolve_benchmark(
            num_perturbations=1,
            num_historical=1,
        )

        for r in results:
            assert isinstance(r, BenchmarkScenario)
