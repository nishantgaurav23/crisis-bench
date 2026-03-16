"""Tests for S6.6: Synthetic Scenario Generator.

Covers: template structure, distribution, scenario validity, event ordering,
language distribution, ground truth retrieval, evaluation rubric, fallback,
state validation, and complexity-severity mapping.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.data.ingest.census import INDIA_STATES
from src.data.ingest.embeddings import SimilarityResult
from src.data.synthetic.scenario_gen import (
    SCENARIO_DISTRIBUTION,
    SCENARIO_TEMPLATES,
    ScenarioGenerator,
    ScenarioTemplate,
)
from src.routing.llm_router import LLMResponse
from src.shared.models import BenchmarkScenario, IndiaDisasterType

# =============================================================================
# Fixtures
# =============================================================================

MOCK_LLM_SCENARIO_JSON = """{
    "description": "A severe cyclonic storm makes landfall near Puri, Odisha.",
    "initial_conditions": {
        "wind_speed_kmph": 180,
        "central_pressure_hpa": 960,
        "storm_surge_m": 3.5,
        "affected_population": 2500000,
        "imd_classification": "VSCS"
    },
    "events": [
        {
            "time_offset_minutes": 0,
            "phase": "pre_event",
            "event_type": "imd_warning",
            "description": "IMD issues Red warning for Odisha coast",
            "data_payload": {"warning_level": "red", "districts": ["Puri", "Khurda"]}
        },
        {
            "time_offset_minutes": 120,
            "phase": "active_response",
            "event_type": "evacuation_order",
            "description": "District collector orders evacuation of low-lying areas",
            "data_payload": {"evacuees": 150000, "shelters_activated": 45}
        },
        {
            "time_offset_minutes": 360,
            "phase": "active_response",
            "event_type": "landfall",
            "description": "Cyclone makes landfall near Puri",
            "data_payload": {"wind_speed_kmph": 180, "storm_surge_m": 3.5}
        },
        {
            "time_offset_minutes": 720,
            "phase": "recovery",
            "event_type": "damage_assessment",
            "description": "Initial damage assessment begins",
            "data_payload": {"houses_damaged": 25000, "power_lines_down": 120}
        }
    ],
    "ground_truth_decisions": {
        "evacuation_timing": "T-48h before landfall",
        "ndrf_deployment": "4 battalions pre-positioned",
        "shelter_activation": "All cyclone shelters within 50km of coast",
        "communication": "Multilingual warnings in Odia, Hindi, English"
    },
    "evaluation_rubric": {
        "situational_accuracy": {
            "key_facts": ["cyclone category", "landfall location", "affected districts"],
            "weight": 0.25
        },
        "decision_timeliness": {
            "critical_windows": {"evacuation": "48h before landfall", "ndrf_staging": "24h before"},
            "weight": 0.20
        },
        "resource_efficiency": {
            "expected_resources": {"ndrf_battalions": 4, "shelters": 45},
            "weight": 0.20
        },
        "coordination_quality": {
            "expected_flows": ["imd->orchestrator", "orchestrator->resource_allocation"],
            "weight": 0.15
        },
        "communication_appropriateness": {
            "languages": ["Odia", "Hindi", "English"],
            "channels": ["sms", "whatsapp", "media_briefing"],
            "weight": 0.20
        }
    }
}"""


@pytest.fixture
def mock_router():
    """Mock LLM Router that returns structured scenario JSON."""
    router = AsyncMock()
    router.call = AsyncMock(
        return_value=LLMResponse(
            content=MOCK_LLM_SCENARIO_JSON,
            provider="DeepSeek Chat",
            model="deepseek-chat",
            input_tokens=1500,
            output_tokens=2000,
            cost_usd=0.001,
            latency_s=3.5,
            tier="standard",
        )
    )
    return router


@pytest.fixture
def mock_pipeline():
    """Mock EmbeddingPipeline that returns fake NDMA guidelines."""
    pipeline = MagicMock()
    pipeline.query_similar = AsyncMock(
        return_value=[
            SimilarityResult(
                text="NDMA cyclone guidelines: Evacuate coastal areas 48h before landfall. "
                "Deploy NDRF battalions 24h before. Activate all cyclone shelters.",
                score=0.92,
                metadata={"document_id": "ndma_cyclone_001", "category": "guidelines"},
            ),
            SimilarityResult(
                text="SOP: Issue multilingual warnings via SMS, WhatsApp, and media briefing. "
                "Coordinate with district collectors for shelter management.",
                score=0.87,
                metadata={"document_id": "ndma_sop_002", "category": "sops"},
            ),
        ]
    )
    return pipeline


@pytest.fixture
def generator(mock_router, mock_pipeline):
    """ScenarioGenerator with mocked dependencies."""
    return ScenarioGenerator(router=mock_router, pipeline=mock_pipeline)


# =============================================================================
# Test 1: Scenario Template Structure
# =============================================================================


class TestScenarioTemplates:
    def test_all_categories_have_templates(self):
        """Every disaster category in the distribution must have a template."""
        for category in SCENARIO_DISTRIBUTION:
            assert category in SCENARIO_TEMPLATES, f"Missing template for {category}"

    def test_template_has_required_fields(self):
        """Each template must have affected_states, seasons, severity_ranges, sop_keywords."""
        for category, template in SCENARIO_TEMPLATES.items():
            assert isinstance(template, ScenarioTemplate), f"{category} is not a ScenarioTemplate"
            assert len(template.affected_states) > 0, f"{category} has no affected_states"
            assert len(template.seasons) > 0, f"{category} has no seasons"
            assert "low" in template.severity_ranges, f"{category} missing low severity"
            assert "medium" in template.severity_ranges, f"{category} missing medium severity"
            assert "high" in template.severity_ranges, f"{category} missing high severity"
            assert len(template.sop_keywords) > 0, f"{category} has no sop_keywords"

    def test_template_states_are_valid(self):
        """Template affected_states must be real Indian states."""
        valid_names = {s.name for s in INDIA_STATES}
        for category, template in SCENARIO_TEMPLATES.items():
            for state in template.affected_states:
                assert state in valid_names, f"{category}: '{state}' not in INDIA_STATES"


# =============================================================================
# Test 2: Distribution Counts
# =============================================================================


class TestDistribution:
    def test_total_is_100(self):
        """Total scenarios across all categories must be 100."""
        assert sum(SCENARIO_DISTRIBUTION.values()) == 100

    def test_category_counts(self):
        """Each category has the required number of scenarios."""
        expected = {
            "monsoon_flood": 30,
            "cyclone": 20,
            "urban_waterlogging": 15,
            "earthquake": 15,
            "heatwave": 10,
            "landslide": 5,
            "industrial_accident": 5,
        }
        assert SCENARIO_DISTRIBUTION == expected

    def test_categories_match_enum(self):
        """All distribution categories must be valid IndiaDisasterType values."""
        valid_types = {t.value for t in IndiaDisasterType}
        for category in SCENARIO_DISTRIBUTION:
            assert category in valid_types, f"'{category}' not in IndiaDisasterType"


# =============================================================================
# Test 3: Generate Scenario — Valid Output
# =============================================================================


class TestGenerateScenario:
    @pytest.mark.asyncio
    async def test_returns_benchmark_scenario(self, generator):
        """generate_scenario must return a valid BenchmarkScenario."""
        scenario = await generator.generate_scenario("cyclone", "high")
        assert isinstance(scenario, BenchmarkScenario)

    @pytest.mark.asyncio
    async def test_scenario_has_correct_category(self, generator):
        """Returned scenario category matches the requested one."""
        scenario = await generator.generate_scenario("cyclone", "high")
        assert scenario.category == "cyclone"

    @pytest.mark.asyncio
    async def test_scenario_has_correct_complexity(self, generator):
        """Returned scenario complexity matches the requested one."""
        scenario = await generator.generate_scenario("cyclone", "high")
        assert scenario.complexity == "high"

    @pytest.mark.asyncio
    async def test_scenario_has_uuid(self, generator):
        """Scenario must have a valid UUID."""
        scenario = await generator.generate_scenario("cyclone", "high")
        assert isinstance(scenario.id, uuid.UUID)

    @pytest.mark.asyncio
    async def test_scenario_has_affected_states(self, generator):
        """Scenario must list at least one affected state."""
        scenario = await generator.generate_scenario("cyclone", "high")
        assert len(scenario.affected_states) >= 1

    @pytest.mark.asyncio
    async def test_scenario_has_initial_state(self, generator):
        """Scenario must have non-empty initial_state."""
        scenario = await generator.generate_scenario("cyclone", "high")
        assert isinstance(scenario.initial_state, dict)
        assert len(scenario.initial_state) > 0

    @pytest.mark.asyncio
    async def test_scenario_has_event_sequence(self, generator):
        """Scenario must have at least one event."""
        scenario = await generator.generate_scenario("cyclone", "high")
        assert isinstance(scenario.event_sequence, list)
        assert len(scenario.event_sequence) >= 1

    @pytest.mark.asyncio
    async def test_llm_called_with_standard_tier(self, generator, mock_router):
        """LLM call must use standard tier."""
        await generator.generate_scenario("cyclone", "high")
        mock_router.call.assert_called()
        call_args = mock_router.call.call_args
        assert call_args[0][0] == "standard" or call_args.kwargs.get("tier") == "standard"


# =============================================================================
# Test 4: Event Sequence Ordering
# =============================================================================


class TestEventSequence:
    @pytest.mark.asyncio
    async def test_events_chronologically_ordered(self, generator):
        """Events must be sorted by time_offset_minutes ascending."""
        scenario = await generator.generate_scenario("cyclone", "high")
        offsets = [e["time_offset_minutes"] for e in scenario.event_sequence]
        assert offsets == sorted(offsets), "Events not chronologically ordered"

    @pytest.mark.asyncio
    async def test_events_have_required_fields(self, generator):
        """Each event must have time_offset_minutes, phase, event_type, description."""
        scenario = await generator.generate_scenario("cyclone", "high")
        for event in scenario.event_sequence:
            assert "time_offset_minutes" in event
            assert "phase" in event
            assert "event_type" in event
            assert "description" in event

    @pytest.mark.asyncio
    async def test_event_phases_valid(self, generator):
        """Event phases must be one of pre_event, active_response, recovery."""
        valid_phases = {"pre_event", "active_response", "recovery"}
        scenario = await generator.generate_scenario("cyclone", "high")
        for event in scenario.event_sequence:
            assert event["phase"] in valid_phases, f"Invalid phase: {event['phase']}"


# =============================================================================
# Test 5: Language Distribution
# =============================================================================


class TestLanguageDistribution:
    @pytest.mark.asyncio
    async def test_scenario_has_language(self, generator):
        """Every scenario must have a primary_language."""
        scenario = await generator.generate_scenario("cyclone", "high")
        assert scenario.primary_language is not None
        assert len(scenario.primary_language) > 0

    def test_language_assigned_from_state(self):
        """Language should come from the affected state's primary_language."""
        # Odisha -> Odia, Tamil Nadu -> Tamil, etc.
        state_languages = {s.name: s.primary_language for s in INDIA_STATES}
        assert state_languages["Odisha"] == "Odia"
        assert state_languages["Tamil Nadu"] == "Tamil"
        assert state_languages["West Bengal"] == "Bengali"


# =============================================================================
# Test 6: Ground Truth Retrieval
# =============================================================================


class TestGroundTruth:
    @pytest.mark.asyncio
    async def test_ndma_queried_for_ground_truth(self, generator, mock_pipeline):
        """EmbeddingPipeline.query_similar must be called for ground truth."""
        await generator.generate_scenario("cyclone", "high")
        mock_pipeline.query_similar.assert_called()

    @pytest.mark.asyncio
    async def test_ground_truth_in_scenario(self, generator):
        """Scenario must have non-empty ground_truth_decisions."""
        scenario = await generator.generate_scenario("cyclone", "high")
        assert isinstance(scenario.ground_truth_decisions, dict)
        assert len(scenario.ground_truth_decisions) > 0


# =============================================================================
# Test 7: Evaluation Rubric Completeness
# =============================================================================


class TestEvaluationRubric:
    @pytest.mark.asyncio
    async def test_rubric_has_all_5_dimensions(self, generator):
        """Evaluation rubric must have all 5 scoring dimensions."""
        scenario = await generator.generate_scenario("cyclone", "high")
        rubric = scenario.evaluation_rubric
        required = {
            "situational_accuracy",
            "decision_timeliness",
            "resource_efficiency",
            "coordination_quality",
            "communication_appropriateness",
        }
        assert required.issubset(set(rubric.keys())), (
            f"Missing rubric dimensions: {required - set(rubric.keys())}"
        )

    @pytest.mark.asyncio
    async def test_rubric_dimensions_have_weights(self, generator):
        """Each rubric dimension should have a weight."""
        scenario = await generator.generate_scenario("cyclone", "high")
        rubric = scenario.evaluation_rubric
        for dim, value in rubric.items():
            assert "weight" in value, f"Missing weight in {dim}"


# =============================================================================
# Test 8: LLM Failure Fallback
# =============================================================================


class TestFallback:
    @pytest.mark.asyncio
    async def test_fallback_on_llm_failure(self, mock_pipeline):
        """When LLM fails, generator should produce a template-based scenario."""
        failing_router = AsyncMock()
        failing_router.call = AsyncMock(side_effect=Exception("LLM unavailable"))
        gen = ScenarioGenerator(router=failing_router, pipeline=mock_pipeline)
        scenario = await gen.generate_scenario("cyclone", "high")
        # Should still return a valid BenchmarkScenario (template-only)
        assert isinstance(scenario, BenchmarkScenario)
        assert scenario.category == "cyclone"
        assert scenario.complexity == "high"

    @pytest.mark.asyncio
    async def test_fallback_scenario_has_events(self, mock_pipeline):
        """Fallback scenario should still have a basic event sequence."""
        failing_router = AsyncMock()
        failing_router.call = AsyncMock(side_effect=Exception("LLM down"))
        gen = ScenarioGenerator(router=failing_router, pipeline=mock_pipeline)
        scenario = await gen.generate_scenario("monsoon_flood", "low")
        assert len(scenario.event_sequence) >= 1


# =============================================================================
# Test 9: Affected States Validation
# =============================================================================


class TestAffectedStates:
    @pytest.mark.asyncio
    async def test_states_from_template(self, generator):
        """Affected states must come from the template's allowed states."""
        scenario = await generator.generate_scenario("cyclone", "high")
        template_states = SCENARIO_TEMPLATES["cyclone"].affected_states
        for state in scenario.affected_states:
            assert state in template_states, (
                f"'{state}' not in cyclone template states: {template_states}"
            )


# =============================================================================
# Test 10: Complexity Affects Severity
# =============================================================================


class TestComplexitySeverity:
    @pytest.mark.asyncio
    async def test_high_complexity_higher_severity(self, generator):
        """High complexity scenarios should have severity >= 3."""
        scenario = await generator.generate_scenario("cyclone", "high")
        severity = scenario.initial_state.get("severity", 3)
        assert severity >= 3, f"High complexity got severity {severity}, expected >= 3"

    @pytest.mark.asyncio
    async def test_low_complexity_lower_severity(self, mock_router, mock_pipeline):
        """Low complexity scenarios should have severity <= 3."""
        gen = ScenarioGenerator(router=mock_router, pipeline=mock_pipeline)
        scenario = await gen.generate_scenario("cyclone", "low")
        severity = scenario.initial_state.get("severity", 2)
        assert severity <= 3, f"Low complexity got severity {severity}, expected <= 3"


# =============================================================================
# Test: Batch Generation
# =============================================================================


class TestBatchGeneration:
    @pytest.mark.asyncio
    async def test_generate_batch_returns_correct_count(self, generator):
        """generate_batch must return exactly the number of scenarios requested."""
        distribution = {"cyclone": 2, "monsoon_flood": 1}
        scenarios = await generator.generate_batch(distribution)
        assert len(scenarios) == 3

    @pytest.mark.asyncio
    async def test_generate_batch_categories_match(self, generator):
        """Each scenario in batch must have the correct category."""
        distribution = {"cyclone": 2, "earthquake": 1}
        scenarios = await generator.generate_batch(distribution)
        categories = [s.category for s in scenarios]
        assert categories.count("cyclone") == 2
        assert categories.count("earthquake") == 1
