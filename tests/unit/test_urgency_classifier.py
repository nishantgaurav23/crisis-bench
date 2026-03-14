"""Tests for Urgency Classifier — maps disaster data to urgency (1-5) and LLM tier.

Tests cover: IMD color codes, earthquake magnitude, cyclone classification,
river level status, disaster type defaults, multi-signal aggregation,
phase escalation, population factor, tier mapping, edge cases, validation.
No external APIs — all logic is pure/deterministic.
"""

import pytest
from pydantic import ValidationError

from src.routing.urgency_classifier import (
    DisasterData,
    UrgencyClassifier,
    UrgencyResult,
)
from src.shared.models import (
    DisasterPhase,
    IMDColorCode,
    IMDCycloneClass,
    IndiaDisasterType,
    LLMTier,
    RiverLevelStatus,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def classifier() -> UrgencyClassifier:
    return UrgencyClassifier()


# =============================================================================
# IMD Color Code Mapping
# =============================================================================


class TestIMDColorCode:
    def test_green_maps_to_urgency_1(self, classifier: UrgencyClassifier):
        data = DisasterData(
            disaster_type=IndiaDisasterType.MONSOON_FLOOD,
            imd_color_code=IMDColorCode.GREEN,
        )
        result = classifier.classify(data)
        assert result.raw_scores["imd_color"] == 1

    def test_yellow_maps_to_urgency_2(self, classifier: UrgencyClassifier):
        data = DisasterData(
            disaster_type=IndiaDisasterType.MONSOON_FLOOD,
            imd_color_code=IMDColorCode.YELLOW,
        )
        result = classifier.classify(data)
        assert result.raw_scores["imd_color"] == 2

    def test_orange_maps_to_urgency_3(self, classifier: UrgencyClassifier):
        data = DisasterData(
            disaster_type=IndiaDisasterType.MONSOON_FLOOD,
            imd_color_code=IMDColorCode.ORANGE,
        )
        result = classifier.classify(data)
        assert result.raw_scores["imd_color"] == 3

    def test_red_maps_to_urgency_5(self, classifier: UrgencyClassifier):
        data = DisasterData(
            disaster_type=IndiaDisasterType.MONSOON_FLOOD,
            imd_color_code=IMDColorCode.RED,
        )
        result = classifier.classify(data)
        assert result.raw_scores["imd_color"] == 5


# =============================================================================
# Earthquake Magnitude Mapping
# =============================================================================


class TestEarthquakeMagnitude:
    @pytest.mark.parametrize(
        "magnitude, expected",
        [
            (2.0, 1),
            (3.9, 1),
            (4.0, 2),
            (4.9, 2),
            (5.0, 3),
            (5.9, 3),
            (6.0, 4),
            (6.9, 4),
            (7.0, 5),
            (8.5, 5),
        ],
    )
    def test_magnitude_to_urgency(
        self, classifier: UrgencyClassifier, magnitude: float, expected: int
    ):
        data = DisasterData(
            disaster_type=IndiaDisasterType.EARTHQUAKE,
            earthquake_magnitude=magnitude,
        )
        result = classifier.classify(data)
        assert result.raw_scores["earthquake"] == expected


# =============================================================================
# IMD Cyclone Classification Mapping
# =============================================================================


class TestCycloneClassification:
    @pytest.mark.parametrize(
        "cyclone_class, expected",
        [
            (IMDCycloneClass.D, 2),
            (IMDCycloneClass.DD, 2),
            (IMDCycloneClass.CS, 3),
            (IMDCycloneClass.SCS, 4),
            (IMDCycloneClass.VSCS, 4),
            (IMDCycloneClass.ESCS, 5),
            (IMDCycloneClass.SuCS, 5),
        ],
    )
    def test_cyclone_class_to_urgency(
        self, classifier: UrgencyClassifier, cyclone_class: IMDCycloneClass, expected: int
    ):
        data = DisasterData(
            disaster_type=IndiaDisasterType.CYCLONE,
            cyclone_class=cyclone_class,
        )
        result = classifier.classify(data)
        assert result.raw_scores["cyclone"] == expected


# =============================================================================
# CWC River Level Mapping
# =============================================================================


class TestRiverLevel:
    @pytest.mark.parametrize(
        "status, expected",
        [
            (RiverLevelStatus.NORMAL, 1),
            (RiverLevelStatus.WARNING, 3),
            (RiverLevelStatus.DANGER, 4),
            (RiverLevelStatus.EXTREME_DANGER, 5),
        ],
    )
    def test_river_level_to_urgency(
        self, classifier: UrgencyClassifier, status: RiverLevelStatus, expected: int
    ):
        data = DisasterData(
            disaster_type=IndiaDisasterType.MONSOON_FLOOD,
            river_level_status=status,
        )
        result = classifier.classify(data)
        assert result.raw_scores["river_level"] == expected


# =============================================================================
# Disaster Type Defaults
# =============================================================================


class TestDisasterTypeDefaults:
    @pytest.mark.parametrize(
        "disaster_type, min_urgency",
        [
            (IndiaDisasterType.MONSOON_FLOOD, 2),
            (IndiaDisasterType.CYCLONE, 3),
            (IndiaDisasterType.EARTHQUAKE, 3),
            (IndiaDisasterType.TSUNAMI, 4),
            (IndiaDisasterType.HEATWAVE, 2),
            (IndiaDisasterType.LANDSLIDE, 3),
            (IndiaDisasterType.URBAN_WATERLOGGING, 1),
            (IndiaDisasterType.INDUSTRIAL_ACCIDENT, 3),
            (IndiaDisasterType.DROUGHT, 1),
            (IndiaDisasterType.GLACIAL_LAKE_OUTBURST, 4),
        ],
    )
    def test_disaster_type_has_base_urgency(
        self, classifier: UrgencyClassifier, disaster_type: IndiaDisasterType, min_urgency: int
    ):
        """Each disaster type should have a sensible base urgency when no signals provided."""
        data = DisasterData(disaster_type=disaster_type)
        result = classifier.classify(data)
        assert result.raw_scores["disaster_type"] == min_urgency


# =============================================================================
# Multi-Signal Aggregation
# =============================================================================


class TestMultiSignalAggregation:
    def test_max_of_signals_wins(self, classifier: UrgencyClassifier):
        """When multiple signals are present, the maximum urgency wins."""
        data = DisasterData(
            disaster_type=IndiaDisasterType.CYCLONE,
            imd_color_code=IMDColorCode.RED,  # 5
            cyclone_class=IMDCycloneClass.CS,  # 3
        )
        result = classifier.classify(data)
        # Red (5) > CS (3), so urgency should be 5
        assert result.urgency == 5

    def test_all_signals_combined(self, classifier: UrgencyClassifier):
        """Combine IMD color, earthquake, cyclone, and river level."""
        data = DisasterData(
            disaster_type=IndiaDisasterType.CYCLONE,
            imd_color_code=IMDColorCode.ORANGE,  # 3
            cyclone_class=IMDCycloneClass.VSCS,  # 4
            river_level_status=RiverLevelStatus.DANGER,  # 4
        )
        result = classifier.classify(data)
        assert result.urgency == 4


# =============================================================================
# Phase Escalation
# =============================================================================


class TestPhaseEscalation:
    def test_active_response_adds_one(self, classifier: UrgencyClassifier):
        """active_response phase should add +1 to base urgency."""
        data_pre = DisasterData(
            disaster_type=IndiaDisasterType.MONSOON_FLOOD,
            imd_color_code=IMDColorCode.ORANGE,
        )
        data_active = DisasterData(
            disaster_type=IndiaDisasterType.MONSOON_FLOOD,
            imd_color_code=IMDColorCode.ORANGE,
            phase=DisasterPhase.ACTIVE_RESPONSE,
        )
        result_pre = classifier.classify(data_pre)
        result_active = classifier.classify(data_active)
        assert result_active.urgency == min(result_pre.urgency + 1, 5)

    def test_phase_escalation_capped_at_5(self, classifier: UrgencyClassifier):
        """Phase escalation should not push urgency above 5."""
        data = DisasterData(
            disaster_type=IndiaDisasterType.CYCLONE,
            imd_color_code=IMDColorCode.RED,  # already 5
            phase=DisasterPhase.ACTIVE_RESPONSE,
        )
        result = classifier.classify(data)
        assert result.urgency == 5

    def test_pre_event_no_escalation(self, classifier: UrgencyClassifier):
        data = DisasterData(
            disaster_type=IndiaDisasterType.MONSOON_FLOOD,
            imd_color_code=IMDColorCode.YELLOW,
            phase=DisasterPhase.PRE_EVENT,
        )
        result = classifier.classify(data)
        assert result.urgency == 2

    def test_recovery_no_escalation(self, classifier: UrgencyClassifier):
        data = DisasterData(
            disaster_type=IndiaDisasterType.MONSOON_FLOOD,
            imd_color_code=IMDColorCode.YELLOW,
            phase=DisasterPhase.RECOVERY,
        )
        result = classifier.classify(data)
        assert result.urgency == 2


# =============================================================================
# Population Factor
# =============================================================================


class TestPopulationFactor:
    def test_high_population_adds_one(self, classifier: UrgencyClassifier):
        data_low = DisasterData(
            disaster_type=IndiaDisasterType.MONSOON_FLOOD,
            imd_color_code=IMDColorCode.ORANGE,
            affected_population=500_000,
        )
        data_high = DisasterData(
            disaster_type=IndiaDisasterType.MONSOON_FLOOD,
            imd_color_code=IMDColorCode.ORANGE,
            affected_population=2_000_000,
        )
        result_low = classifier.classify(data_low)
        result_high = classifier.classify(data_high)
        assert result_high.urgency == min(result_low.urgency + 1, 5)

    def test_population_capped_at_5(self, classifier: UrgencyClassifier):
        data = DisasterData(
            disaster_type=IndiaDisasterType.CYCLONE,
            imd_color_code=IMDColorCode.RED,
            affected_population=5_000_000,
        )
        result = classifier.classify(data)
        assert result.urgency == 5

    def test_no_population_no_bonus(self, classifier: UrgencyClassifier):
        data = DisasterData(
            disaster_type=IndiaDisasterType.MONSOON_FLOOD,
            imd_color_code=IMDColorCode.ORANGE,
        )
        result = classifier.classify(data)
        # No population data → no bonus
        assert "population" not in result.raw_scores


# =============================================================================
# Urgency → LLMTier Mapping
# =============================================================================


class TestTierMapping:
    @pytest.mark.parametrize(
        "urgency, expected_tier",
        [
            (1, LLMTier.ROUTINE),
            (2, LLMTier.ROUTINE),
            (3, LLMTier.STANDARD),
            (4, LLMTier.CRITICAL),
            (5, LLMTier.CRITICAL),
        ],
    )
    def test_urgency_to_tier(
        self, classifier: UrgencyClassifier, urgency: int, expected_tier: LLMTier
    ):
        assert classifier.urgency_to_tier(urgency) == expected_tier

    def test_classify_includes_correct_tier(self, classifier: UrgencyClassifier):
        data = DisasterData(
            disaster_type=IndiaDisasterType.CYCLONE,
            imd_color_code=IMDColorCode.RED,
        )
        result = classifier.classify(data)
        assert result.tier == LLMTier.CRITICAL

    def test_routine_tier_for_low_urgency(self, classifier: UrgencyClassifier):
        data = DisasterData(
            disaster_type=IndiaDisasterType.DROUGHT,
        )
        result = classifier.classify(data)
        assert result.tier == LLMTier.ROUTINE


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    def test_no_signals_uses_disaster_type_default(self, classifier: UrgencyClassifier):
        """When no IMD/earthquake/cyclone/river signals, use disaster type base."""
        data = DisasterData(disaster_type=IndiaDisasterType.CYCLONE)
        result = classifier.classify(data)
        assert result.urgency >= 1
        assert result.urgency <= 5
        assert len(result.factors) > 0

    def test_result_factors_are_populated(self, classifier: UrgencyClassifier):
        data = DisasterData(
            disaster_type=IndiaDisasterType.CYCLONE,
            imd_color_code=IMDColorCode.RED,
            cyclone_class=IMDCycloneClass.ESCS,
        )
        result = classifier.classify(data)
        assert len(result.factors) >= 2
        assert any("imd" in f.lower() or "red" in f.lower() for f in result.factors)

    def test_result_is_urgency_result_model(self, classifier: UrgencyClassifier):
        data = DisasterData(disaster_type=IndiaDisasterType.EARTHQUAKE)
        result = classifier.classify(data)
        assert isinstance(result, UrgencyResult)


# =============================================================================
# Pydantic Validation
# =============================================================================


class TestValidation:
    def test_urgency_result_rejects_urgency_below_1(self):
        with pytest.raises(ValidationError):
            UrgencyResult(
                urgency=0,
                tier=LLMTier.ROUTINE,
                factors=["test"],
                raw_scores={"test": 0},
            )

    def test_urgency_result_rejects_urgency_above_5(self):
        with pytest.raises(ValidationError):
            UrgencyResult(
                urgency=6,
                tier=LLMTier.ROUTINE,
                factors=["test"],
                raw_scores={"test": 6},
            )

    def test_disaster_data_requires_disaster_type(self):
        with pytest.raises(ValidationError):
            DisasterData()  # type: ignore[call-arg]

    def test_disaster_data_defaults_phase_to_pre_event(self):
        data = DisasterData(disaster_type=IndiaDisasterType.EARTHQUAKE)
        assert data.phase == DisasterPhase.PRE_EVENT

    def test_disaster_data_accepts_all_optional_none(self):
        data = DisasterData(disaster_type=IndiaDisasterType.HEATWAVE)
        assert data.imd_color_code is None
        assert data.cyclone_class is None
        assert data.earthquake_magnitude is None
        assert data.river_level_status is None
        assert data.affected_population is None
