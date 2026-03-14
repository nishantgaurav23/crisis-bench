"""Urgency Classifier — maps disaster data to urgency (1-5) and LLM tier.

Rule-based classifier that converts disaster signals (IMD warnings, earthquake
magnitude, cyclone class, river levels) into an urgency score which determines
the LLM Router tier. Pure function — no I/O, no LLM calls.

Usage:
    from src.routing.urgency_classifier import UrgencyClassifier, DisasterData

    classifier = UrgencyClassifier()
    data = DisasterData(disaster_type=IndiaDisasterType.CYCLONE, imd_color_code=IMDColorCode.RED)
    result = classifier.classify(data)
    # result.urgency == 5, result.tier == LLMTier.CRITICAL
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.shared.models import (
    DisasterPhase,
    IMDColorCode,
    IMDCycloneClass,
    IndiaDisasterType,
    LLMTier,
    RiverLevelStatus,
)

# =============================================================================
# Data Models
# =============================================================================


class DisasterData(BaseModel):
    """Input data for urgency classification."""

    model_config = ConfigDict(from_attributes=True)

    disaster_type: IndiaDisasterType
    phase: DisasterPhase = DisasterPhase.PRE_EVENT
    imd_color_code: IMDColorCode | None = None
    cyclone_class: IMDCycloneClass | None = None
    earthquake_magnitude: float | None = None
    river_level_status: RiverLevelStatus | None = None
    affected_population: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class UrgencyResult(BaseModel):
    """Output of urgency classification."""

    model_config = ConfigDict(from_attributes=True)

    urgency: int = Field(..., ge=1, le=5)
    tier: LLMTier
    factors: list[str]
    raw_scores: dict[str, int]


# =============================================================================
# Mapping Tables
# =============================================================================

_IMD_COLOR_URGENCY: dict[IMDColorCode, int] = {
    IMDColorCode.GREEN: 1,
    IMDColorCode.YELLOW: 2,
    IMDColorCode.ORANGE: 3,
    IMDColorCode.RED: 5,
}

_EARTHQUAKE_THRESHOLDS: list[tuple[float, int]] = [
    (7.0, 5),
    (6.0, 4),
    (5.0, 3),
    (4.0, 2),
    (0.0, 1),
]

_CYCLONE_URGENCY: dict[IMDCycloneClass, int] = {
    IMDCycloneClass.D: 2,
    IMDCycloneClass.DD: 2,
    IMDCycloneClass.CS: 3,
    IMDCycloneClass.SCS: 4,
    IMDCycloneClass.VSCS: 4,
    IMDCycloneClass.ESCS: 5,
    IMDCycloneClass.SuCS: 5,
}

_RIVER_LEVEL_URGENCY: dict[RiverLevelStatus, int] = {
    RiverLevelStatus.NORMAL: 1,
    RiverLevelStatus.WARNING: 3,
    RiverLevelStatus.DANGER: 4,
    RiverLevelStatus.EXTREME_DANGER: 5,
}

_DISASTER_TYPE_BASE: dict[IndiaDisasterType, int] = {
    IndiaDisasterType.MONSOON_FLOOD: 2,
    IndiaDisasterType.CYCLONE: 3,
    IndiaDisasterType.EARTHQUAKE: 3,
    IndiaDisasterType.TSUNAMI: 4,
    IndiaDisasterType.HEATWAVE: 2,
    IndiaDisasterType.LANDSLIDE: 3,
    IndiaDisasterType.URBAN_WATERLOGGING: 1,
    IndiaDisasterType.INDUSTRIAL_ACCIDENT: 3,
    IndiaDisasterType.DROUGHT: 1,
    IndiaDisasterType.GLACIAL_LAKE_OUTBURST: 4,
}

_TIER_MAP: dict[int, LLMTier] = {
    1: LLMTier.ROUTINE,
    2: LLMTier.ROUTINE,
    3: LLMTier.STANDARD,
    4: LLMTier.CRITICAL,
    5: LLMTier.CRITICAL,
}

_POPULATION_THRESHOLD = 1_000_000


# =============================================================================
# Classifier
# =============================================================================


class UrgencyClassifier:
    """Classifies disaster urgency (1-5) and maps to LLM tier."""

    def classify(self, data: DisasterData) -> UrgencyResult:
        """Classify urgency from disaster data. Pure function, no I/O."""
        raw_scores: dict[str, int] = {}
        factors: list[str] = []

        # Disaster type base
        base = _DISASTER_TYPE_BASE.get(data.disaster_type, 2)
        raw_scores["disaster_type"] = base
        factors.append(f"Disaster type {data.disaster_type.value}: base urgency {base}")

        # IMD color code
        if data.imd_color_code is not None:
            score = _IMD_COLOR_URGENCY[data.imd_color_code]
            raw_scores["imd_color"] = score
            factors.append(f"IMD {data.imd_color_code.value} alert: urgency {score}")

        # Earthquake magnitude
        if data.earthquake_magnitude is not None:
            score = self._earthquake_urgency(data.earthquake_magnitude)
            raw_scores["earthquake"] = score
            factors.append(f"Earthquake M{data.earthquake_magnitude}: urgency {score}")

        # Cyclone classification
        if data.cyclone_class is not None:
            score = _CYCLONE_URGENCY[data.cyclone_class]
            raw_scores["cyclone"] = score
            factors.append(f"Cyclone {data.cyclone_class.value}: urgency {score}")

        # River level
        if data.river_level_status is not None:
            score = _RIVER_LEVEL_URGENCY[data.river_level_status]
            raw_scores["river_level"] = score
            factors.append(f"River level {data.river_level_status.value}: urgency {score}")

        # Max of all signals
        urgency = max(raw_scores.values())

        # Population factor
        if (
            data.affected_population is not None
            and data.affected_population > _POPULATION_THRESHOLD
        ):
            raw_scores["population"] = 1
            factors.append(f"High population ({data.affected_population:,}): +1 urgency")
            urgency = min(urgency + 1, 5)

        # Phase escalation
        if data.phase == DisasterPhase.ACTIVE_RESPONSE:
            factors.append("Active response phase: +1 urgency")
            urgency = min(urgency + 1, 5)

        tier = self.urgency_to_tier(urgency)

        return UrgencyResult(
            urgency=urgency,
            tier=tier,
            factors=factors,
            raw_scores=raw_scores,
        )

    def urgency_to_tier(self, urgency: int) -> LLMTier:
        """Map urgency score (1-5) to LLM routing tier."""
        return _TIER_MAP.get(urgency, LLMTier.STANDARD)

    @staticmethod
    def _earthquake_urgency(magnitude: float) -> int:
        for threshold, score in _EARTHQUAKE_THRESHOLDS:
            if magnitude >= threshold:
                return score
        return 1
