"""Plan Adapter — LLM-powered adaptation of cached plans to new scenarios.

Given a cached plan and a new scenario, computes the delta between old and new
parameters, then uses an LLM to adapt the plan. Uses cheaper LLM tiers for
higher-similarity matches (routine for HIGH, standard for MEDIUM).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.caching.plan_cache import CacheMatchTier
from src.routing.llm_router import LLMRouter
from src.shared.config import CrisisSettings, get_settings
from src.shared.telemetry import get_logger

logger = get_logger("plan_adapter")

MIN_CONFIDENCE_THRESHOLD = 0.3


# =============================================================================
# Data Models
# =============================================================================


class ScenarioDelta(BaseModel):
    """Differences between the old (cached) scenario and the new scenario."""

    geographic_changes: list[str] = Field(default_factory=list)
    severity_change: str | None = None
    resource_changes: list[str] = Field(default_factory=list)
    temporal_changes: list[str] = Field(default_factory=list)

    def has_changes(self) -> bool:
        return bool(
            self.geographic_changes
            or self.severity_change
            or self.resource_changes
            or self.temporal_changes
        )

    def summary(self) -> str:
        parts: list[str] = []
        if self.geographic_changes:
            parts.append(f"Geographic: {', '.join(self.geographic_changes)}")
        if self.severity_change:
            parts.append(f"Severity: {self.severity_change}")
        if self.resource_changes:
            parts.append(f"Resources: {', '.join(self.resource_changes)}")
        if self.temporal_changes:
            parts.append(f"Temporal: {', '.join(self.temporal_changes)}")
        return "; ".join(parts) if parts else "No significant changes"


class AdaptationResult(BaseModel):
    original_plan: str
    adapted_plan: str
    delta_summary: str
    llm_tier_used: str
    adaptation_confidence: float = Field(..., ge=0.0, le=1.0)


# =============================================================================
# PlanAdapter
# =============================================================================


class PlanAdapter:
    """Adapts cached plans to new scenario parameters via LLM."""

    def __init__(
        self,
        router: LLMRouter | None = None,
        settings: CrisisSettings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._router = router or LLMRouter(self._settings)

    def compute_delta(
        self,
        old_metadata: dict[str, Any],
        new_metadata: dict[str, Any],
    ) -> ScenarioDelta:
        """Compare old and new scenario metadata to identify differences."""
        geographic: list[str] = []
        severity_change: str | None = None
        resource: list[str] = []
        temporal: list[str] = []

        # Geographic changes
        old_states = old_metadata.get("affected_states", [])
        new_states = new_metadata.get("affected_states", [])
        if old_states != new_states:
            geographic.append(f"States: {old_states} -> {new_states}")

        old_districts = old_metadata.get("affected_districts", [])
        new_districts = new_metadata.get("affected_districts", [])
        if old_districts != new_districts:
            geographic.append(f"Districts: {old_districts} -> {new_districts}")

        # Severity changes
        old_sev = old_metadata.get("severity")
        new_sev = new_metadata.get("severity")
        if old_sev is not None and new_sev is not None and old_sev != new_sev:
            severity_change = f"{old_sev} -> {new_sev}"

        # Resource changes
        old_res = old_metadata.get("available_resources")
        new_res = new_metadata.get("available_resources")
        if old_res and new_res and old_res != new_res:
            resource.append(f"Resources: {old_res} -> {new_res}")

        # Temporal / phase changes
        old_phase = old_metadata.get("phase")
        new_phase = new_metadata.get("phase")
        if old_phase and new_phase and old_phase != new_phase:
            temporal.append(f"Phase: {old_phase} -> {new_phase}")

        old_time = old_metadata.get("time_of_day")
        new_time = new_metadata.get("time_of_day")
        if old_time and new_time and old_time != new_time:
            temporal.append(f"Time: {old_time} -> {new_time}")

        return ScenarioDelta(
            geographic_changes=geographic,
            severity_change=severity_change,
            resource_changes=resource,
            temporal_changes=temporal,
        )

    async def adapt_plan(
        self,
        cached_plan: str,
        new_scenario_description: str,
        match_tier: CacheMatchTier,
        old_metadata: dict[str, Any],
        new_metadata: dict[str, Any],
        *,
        trace_id: str = "",
    ) -> AdaptationResult:
        """Adapt a cached plan to a new scenario using LLM.

        Uses routine tier for HIGH similarity, standard tier for MEDIUM.
        """
        tier = "routine" if match_tier == CacheMatchTier.HIGH else "standard"
        delta = self.compute_delta(old_metadata, new_metadata)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a disaster response plan adapter. Given an existing plan "
                    "and the differences between the old and new scenario, adapt the plan "
                    "to fit the new scenario. Preserve the plan structure and NDMA SOP "
                    "format. Only modify sections affected by the changes."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"## Existing Plan\n{cached_plan}\n\n"
                    f"## New Scenario\n{new_scenario_description}\n\n"
                    f"## Key Differences\n{delta.summary()}\n\n"
                    f"## Old Scenario Metadata\n{old_metadata}\n\n"
                    f"## New Scenario Metadata\n{new_metadata}\n\n"
                    "Adapt the existing plan for the new scenario. "
                    "Output the full adapted plan."
                ),
            },
        ]

        response = await self._router.call(tier, messages, trace_id=trace_id)

        # Confidence based on match tier
        confidence = 0.9 if match_tier == CacheMatchTier.HIGH else 0.7

        logger.info(
            "plan_adapted",
            tier=tier,
            delta=delta.summary(),
            confidence=confidence,
            trace_id=trace_id,
        )

        return AdaptationResult(
            original_plan=cached_plan,
            adapted_plan=response.content,
            delta_summary=delta.summary(),
            llm_tier_used=tier,
            adaptation_confidence=confidence,
        )

    def validate_adaptation(self, result: AdaptationResult) -> bool:
        """Check that the adapted plan is non-empty and has reasonable confidence."""
        if not result.adapted_plan or not result.adapted_plan.strip():
            return False
        if result.adaptation_confidence < MIN_CONFIDENCE_THRESHOLD:
            return False
        return True


__all__ = [
    "AdaptationResult",
    "PlanAdapter",
    "ScenarioDelta",
]
