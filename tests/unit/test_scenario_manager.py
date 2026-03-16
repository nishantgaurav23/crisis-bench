"""Tests for ScenarioManager (spec S8.2).

Red -> Green -> Refactor: All tests written first, then implementation.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from src.benchmark.models import (
    AgentExpectation,
    BenchmarkScenario,
    DimensionCriteria,
    EvaluationRubric,
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
    tags: list[str] | None = None,
    source: str = "synthetic",
    with_events: bool = True,
    with_ground_truth: bool = True,
    with_rubric: bool = True,
) -> BenchmarkScenario:
    events = []
    if with_events:
        events = [
            ScenarioEvent(
                time_offset_minutes=0,
                phase=DisasterPhase.PRE_EVENT,
                event_type="imd_warning",
                description="IMD issues red alert",
            ),
        ]
    gt = GroundTruthDecisions(
        agent_expectations={},
        decision_timeline={},
        ndma_references=[],
    )
    if with_ground_truth:
        gt = GroundTruthDecisions(
            agent_expectations={
                "situation_sense": AgentExpectation(
                    key_observations=["Cyclone approaching"],
                    expected_actions=["Issue urgency 5"],
                    time_window_minutes=(0, 30),
                ),
            },
            decision_timeline={"minute_0_30": "Initial alert"},
            ndma_references=["NDMA Cyclone Guidelines"],
        )
    return BenchmarkScenario(
        category=category,
        complexity=complexity,
        affected_states=["Odisha"],
        event_sequence=events,
        ground_truth_decisions=gt,
        evaluation_rubric=_make_rubric() if with_rubric else None,
        tags=tags or ["coastal"],
        source=source,
    )


# =============================================================================
# Category Constants
# =============================================================================


class TestConstants:
    """Verify DISASTER_CATEGORIES and COMPLEXITY_LEVELS."""

    def test_seven_categories(self):
        from src.benchmark.scenario_manager import DISASTER_CATEGORIES

        assert len(DISASTER_CATEGORIES) == 7

    def test_categories_sum_to_100(self):
        from src.benchmark.scenario_manager import DISASTER_CATEGORIES

        assert sum(DISASTER_CATEGORIES.values()) == 100

    def test_all_expected_categories(self):
        from src.benchmark.scenario_manager import DISASTER_CATEGORIES

        expected = {
            "flood",
            "cyclone",
            "urban_waterlogging",
            "earthquake",
            "heatwave",
            "landslide",
            "industrial_accident",
        }
        assert set(DISASTER_CATEGORIES.keys()) == expected

    def test_complexity_levels(self):
        from src.benchmark.scenario_manager import COMPLEXITY_LEVELS

        assert COMPLEXITY_LEVELS == ("low", "medium", "high")


# =============================================================================
# Validation
# =============================================================================


class TestValidation:
    """validate_scenario returns list of error strings."""

    def test_valid_scenario_no_errors(self):
        from src.benchmark.scenario_manager import validate_scenario

        scenario = _make_scenario()
        errors = validate_scenario(scenario)
        assert errors == []

    def test_missing_events(self):
        from src.benchmark.scenario_manager import validate_scenario

        scenario = _make_scenario(with_events=False)
        errors = validate_scenario(scenario)
        assert any("event" in e.lower() for e in errors)

    def test_invalid_category(self):
        from src.benchmark.scenario_manager import validate_scenario

        scenario = _make_scenario(category="tornado")
        errors = validate_scenario(scenario)
        assert any("category" in e.lower() for e in errors)

    def test_invalid_complexity(self):
        from src.benchmark.scenario_manager import validate_scenario

        # Construct with valid complexity then override to bypass Pydantic regex
        scenario = _make_scenario(complexity="medium")
        # Directly override field to simulate bad data from import
        object.__setattr__(scenario, "complexity", "extreme")
        errors = validate_scenario(scenario)
        assert any("complexity" in e.lower() for e in errors)

    def test_missing_ground_truth(self):
        from src.benchmark.scenario_manager import validate_scenario

        scenario = _make_scenario(with_ground_truth=False)
        errors = validate_scenario(scenario)
        assert any("ground truth" in e.lower() or "agent_expectations" in e.lower() for e in errors)

    def test_valid_no_rubric_ok(self):
        from src.benchmark.scenario_manager import validate_scenario

        scenario = _make_scenario(with_rubric=False)
        errors = validate_scenario(scenario)
        assert errors == []


# =============================================================================
# ScenarioManager CRUD delegation
# =============================================================================


def _mock_crud():
    """Patch all S8.1 CRUD functions."""
    return {
        "create_scenario": AsyncMock(return_value=uuid.uuid4()),
        "get_scenario": AsyncMock(return_value=None),
        "list_scenarios": AsyncMock(return_value=[]),
        "count_scenarios": AsyncMock(return_value=0),
        "update_scenario": AsyncMock(return_value=True),
        "delete_scenario": AsyncMock(return_value=True),
    }


class TestScenarioManagerCreate:
    """ScenarioManager.create validates then delegates."""

    @pytest.mark.asyncio
    async def test_create_valid(self):
        from src.benchmark.scenario_manager import ScenarioManager

        mocks = _mock_crud()
        mgr = ScenarioManager()
        scenario = _make_scenario()

        with patch.multiple("src.benchmark.scenario_manager", **mocks):
            result = await mgr.create(scenario)

        assert isinstance(result, uuid.UUID)

    @pytest.mark.asyncio
    async def test_create_invalid_raises(self):
        from src.benchmark.scenario_manager import ScenarioManager

        mgr = ScenarioManager()
        scenario = _make_scenario(with_events=False)

        with pytest.raises(ValueError, match="validation"):
            await mgr.create(scenario)


class TestScenarioManagerGet:
    """ScenarioManager.get and delete delegate to CRUD."""

    @pytest.mark.asyncio
    async def test_get_found(self):
        from src.benchmark.scenario_manager import ScenarioManager

        scenario = _make_scenario()
        mocks = _mock_crud()
        mocks["get_scenario"] = AsyncMock(return_value=scenario)
        mgr = ScenarioManager()

        with patch.multiple("src.benchmark.scenario_manager", **mocks):
            result = await mgr.get(scenario.id)

        assert result is not None
        assert result.category == "cyclone"

    @pytest.mark.asyncio
    async def test_get_not_found(self):
        from src.benchmark.scenario_manager import ScenarioManager

        mocks = _mock_crud()
        mgr = ScenarioManager()

        with patch.multiple("src.benchmark.scenario_manager", **mocks):
            result = await mgr.get(uuid.uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self):
        from src.benchmark.scenario_manager import ScenarioManager

        mocks = _mock_crud()
        mgr = ScenarioManager()

        with patch.multiple("src.benchmark.scenario_manager", **mocks):
            result = await mgr.delete(uuid.uuid4())

        assert result is True


# =============================================================================
# Filtering
# =============================================================================


class TestFiltering:
    """Filtering by category, complexity, tags, combined search."""

    @pytest.mark.asyncio
    async def test_list_by_category(self):
        from src.benchmark.scenario_manager import ScenarioManager

        scenarios = [_make_scenario(category="flood")]
        mocks = _mock_crud()
        mocks["list_scenarios"] = AsyncMock(return_value=scenarios)
        mgr = ScenarioManager()

        with patch.multiple("src.benchmark.scenario_manager", **mocks):
            result = await mgr.list_by_category("flood")

        assert len(result) == 1
        mocks["list_scenarios"].assert_called_once_with(
            category="flood",
            complexity=None,
            limit=50,
            offset=0,
        )

    @pytest.mark.asyncio
    async def test_list_by_complexity(self):
        from src.benchmark.scenario_manager import ScenarioManager

        mocks = _mock_crud()
        mocks["list_scenarios"] = AsyncMock(return_value=[])
        mgr = ScenarioManager()

        with patch.multiple("src.benchmark.scenario_manager", **mocks):
            result = await mgr.list_by_complexity("low")

        assert result == []
        mocks["list_scenarios"].assert_called_once_with(
            category=None,
            complexity="low",
            limit=50,
            offset=0,
        )

    @pytest.mark.asyncio
    async def test_list_by_tags(self):
        from src.benchmark.scenario_manager import ScenarioManager

        s1 = _make_scenario(tags=["coastal", "multi-state"])
        s2 = _make_scenario(tags=["coastal"])
        s3 = _make_scenario(tags=["inland"])
        mocks = _mock_crud()
        mocks["list_scenarios"] = AsyncMock(return_value=[s1, s2, s3])
        mgr = ScenarioManager()

        with patch.multiple("src.benchmark.scenario_manager", **mocks):
            result = await mgr.list_by_tags(["coastal"])

        # s1 and s2 have "coastal", s3 does not
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_by_tags_intersection(self):
        from src.benchmark.scenario_manager import ScenarioManager

        s1 = _make_scenario(tags=["coastal", "multi-state"])
        s2 = _make_scenario(tags=["coastal"])
        mocks = _mock_crud()
        mocks["list_scenarios"] = AsyncMock(return_value=[s1, s2])
        mgr = ScenarioManager()

        with patch.multiple("src.benchmark.scenario_manager", **mocks):
            result = await mgr.list_by_tags(["coastal", "multi-state"])

        # Only s1 has both tags
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_combined(self):
        from src.benchmark.scenario_manager import ScenarioManager

        s1 = _make_scenario(category="cyclone", complexity="high", tags=["coastal"])
        mocks = _mock_crud()
        mocks["list_scenarios"] = AsyncMock(return_value=[s1])
        mgr = ScenarioManager()

        with patch.multiple("src.benchmark.scenario_manager", **mocks):
            result = await mgr.search(
                category="cyclone",
                complexity="high",
                tags=["coastal"],
            )

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_source_filter(self):
        from src.benchmark.scenario_manager import ScenarioManager

        s1 = _make_scenario(source="synthetic")
        s2 = _make_scenario(source="historical")
        mocks = _mock_crud()
        mocks["list_scenarios"] = AsyncMock(return_value=[s1, s2])
        mgr = ScenarioManager()

        with patch.multiple("src.benchmark.scenario_manager", **mocks):
            result = await mgr.search(source="historical")

        assert len(result) == 1
        assert result[0].source == "historical"


# =============================================================================
# Version Tracking
# =============================================================================


class TestVersionTracking:
    """bump_version increments version and applies updates."""

    @pytest.mark.asyncio
    async def test_bump_version(self):
        from src.benchmark.scenario_manager import ScenarioManager

        scenario = _make_scenario()
        assert scenario.version == 1

        mocks = _mock_crud()
        mocks["get_scenario"] = AsyncMock(return_value=scenario)
        mocks["update_scenario"] = AsyncMock(return_value=True)
        mgr = ScenarioManager()

        with patch.multiple("src.benchmark.scenario_manager", **mocks):
            result = await mgr.bump_version(scenario.id, category="flood")

        assert result is not None
        # update_scenario should have been called with version=2 and category="flood"
        call_kwargs = mocks["update_scenario"].call_args
        assert call_kwargs[1]["version"] == 2
        assert call_kwargs[1]["category"] == "flood"

    @pytest.mark.asyncio
    async def test_bump_version_not_found(self):
        from src.benchmark.scenario_manager import ScenarioManager

        mocks = _mock_crud()
        mocks["get_scenario"] = AsyncMock(return_value=None)
        mgr = ScenarioManager()

        with patch.multiple("src.benchmark.scenario_manager", **mocks):
            result = await mgr.bump_version(uuid.uuid4())

        assert result is None


# =============================================================================
# Bulk Operations
# =============================================================================


class TestBulkOperations:
    """Export and import scenario sets."""

    @pytest.mark.asyncio
    async def test_export_scenarios(self):
        from src.benchmark.scenario_manager import ScenarioManager

        scenarios = [_make_scenario(), _make_scenario(category="flood")]
        mocks = _mock_crud()
        mocks["list_scenarios"] = AsyncMock(return_value=scenarios)
        mgr = ScenarioManager()

        with patch.multiple("src.benchmark.scenario_manager", **mocks):
            result = await mgr.export_scenarios()

        assert len(result) == 2
        assert isinstance(result[0], dict)
        # Must be JSON-serializable
        json.dumps(result)

    @pytest.mark.asyncio
    async def test_import_scenarios_valid(self):
        from src.benchmark.scenario_manager import ScenarioManager

        scenario = _make_scenario()
        data = [json.loads(scenario.model_dump_json())]
        mocks = _mock_crud()
        mgr = ScenarioManager()

        with patch.multiple("src.benchmark.scenario_manager", **mocks):
            count, errors = await mgr.import_scenarios(data)

        assert count == 1
        assert errors == []

    @pytest.mark.asyncio
    async def test_import_scenarios_with_errors(self):
        from src.benchmark.scenario_manager import ScenarioManager

        valid = json.loads(_make_scenario().model_dump_json())
        invalid = {"category": "tornado", "complexity": "extreme"}
        mocks = _mock_crud()
        mgr = ScenarioManager()

        with patch.multiple("src.benchmark.scenario_manager", **mocks):
            count, errors = await mgr.import_scenarios([valid, invalid])

        # At least the invalid one should produce an error
        assert len(errors) >= 1


# =============================================================================
# Statistics
# =============================================================================


class TestStatistics:
    """get_stats and get_coverage_report."""

    @pytest.mark.asyncio
    async def test_get_stats(self):
        from src.benchmark.scenario_manager import ScenarioManager

        scenarios = [
            _make_scenario(category="cyclone", complexity="high", source="synthetic"),
            _make_scenario(category="cyclone", complexity="medium", source="synthetic"),
            _make_scenario(category="flood", complexity="low", source="historical"),
        ]
        mocks = _mock_crud()
        mocks["list_scenarios"] = AsyncMock(return_value=scenarios)
        mocks["count_scenarios"] = AsyncMock(return_value=3)
        mgr = ScenarioManager()

        with patch.multiple("src.benchmark.scenario_manager", **mocks):
            stats = await mgr.get_stats()

        assert stats["total"] == 3
        assert "by_category" in stats
        assert "by_complexity" in stats
        assert "by_source" in stats

    @pytest.mark.asyncio
    async def test_get_coverage_report(self):
        from src.benchmark.scenario_manager import ScenarioManager

        scenarios = [
            _make_scenario(category="cyclone"),
            _make_scenario(category="cyclone"),
        ]
        mocks = _mock_crud()
        mocks["list_scenarios"] = AsyncMock(return_value=scenarios)
        mocks["count_scenarios"] = AsyncMock(return_value=2)
        mgr = ScenarioManager()

        with patch.multiple("src.benchmark.scenario_manager", **mocks):
            report = await mgr.get_coverage_report()

        assert "cyclone" in report
        assert report["cyclone"]["current"] == 2
        assert report["cyclone"]["target"] == 20
        assert report["cyclone"]["gap"] == 18
        # Other categories should show 0 current
        assert report["flood"]["current"] == 0
        assert report["flood"]["gap"] == 30
