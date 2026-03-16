"""Tests for Plan Adapter (S9.1) — PlanAdapter.

Tests cover: plan adaptation with LLM, delta computation, tier selection,
validation, and graceful degradation when LLM fails.
All LLM calls are mocked — no real calls.
"""

from unittest.mock import AsyncMock

import pytest

from src.caching.plan_adapter import AdaptationResult, PlanAdapter, ScenarioDelta
from src.caching.plan_cache import CacheMatchTier
from src.routing.llm_router import LLMResponse, LLMRouter
from src.shared.config import CrisisSettings
from src.shared.errors import AllProvidersFailedError

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def settings() -> CrisisSettings:
    return CrisisSettings(
        CHROMA_HOST="localhost",
        CHROMA_PORT=8100,
        OLLAMA_HOST="http://localhost:11434",
        OLLAMA_EMBED_MODEL="nomic-embed-text",
        _env_file=None,
    )


@pytest.fixture
def mock_router() -> AsyncMock:
    router = AsyncMock(spec=LLMRouter)
    router.call = AsyncMock(return_value=LLMResponse(
        content="Adapted plan: Deploy 3 NDRF battalions to Ganjam instead of Puri",
        provider="Qwen Flash",
        model="qwen3.5-flash",
        input_tokens=500,
        output_tokens=200,
        cost_usd=0.0001,
        latency_s=1.2,
        tier="routine",
    ))
    return router


@pytest.fixture
def adapter(settings, mock_router) -> PlanAdapter:
    return PlanAdapter(router=mock_router, settings=settings)


# =============================================================================
# AdaptationResult Model
# =============================================================================


class TestAdaptationResult:
    def test_adaptation_result_creation(self):
        result = AdaptationResult(
            original_plan="Original plan text",
            adapted_plan="Adapted plan text",
            delta_summary="Changed districts from Puri to Ganjam",
            llm_tier_used="routine",
            adaptation_confidence=0.88,
        )
        assert result.adapted_plan == "Adapted plan text"
        assert result.llm_tier_used == "routine"


# =============================================================================
# ScenarioDelta Model
# =============================================================================


class TestScenarioDelta:
    def test_delta_creation(self):
        delta = ScenarioDelta(
            geographic_changes=["Puri -> Ganjam"],
            severity_change=None,
            resource_changes=["2 fewer NDRF battalions"],
            temporal_changes=["Night -> Morning"],
        )
        assert len(delta.geographic_changes) == 1
        assert delta.severity_change is None

    def test_delta_has_changes(self):
        delta = ScenarioDelta(
            geographic_changes=["Puri -> Ganjam"],
        )
        assert delta.has_changes() is True

    def test_delta_no_changes(self):
        delta = ScenarioDelta()
        assert delta.has_changes() is False


# =============================================================================
# PlanAdapter.compute_delta
# =============================================================================


class TestComputeDelta:
    def test_geographic_change(self, adapter):
        old_meta = {"affected_states": ["Odisha"], "affected_districts": ["Puri"]}
        new_meta = {"affected_states": ["Tamil Nadu"], "affected_districts": ["Chennai"]}
        delta = adapter.compute_delta(old_meta, new_meta)
        assert len(delta.geographic_changes) > 0

    def test_severity_change(self, adapter):
        old_meta = {"severity": 3}
        new_meta = {"severity": 5}
        delta = adapter.compute_delta(old_meta, new_meta)
        assert delta.severity_change is not None
        assert "3" in delta.severity_change
        assert "5" in delta.severity_change

    def test_no_severity_change(self, adapter):
        old_meta = {"severity": 4}
        new_meta = {"severity": 4}
        delta = adapter.compute_delta(old_meta, new_meta)
        assert delta.severity_change is None

    def test_resource_changes(self, adapter):
        old_meta = {"available_resources": "12 NDRF battalions"}
        new_meta = {"available_resources": "6 NDRF battalions"}
        delta = adapter.compute_delta(old_meta, new_meta)
        assert len(delta.resource_changes) > 0

    def test_temporal_changes(self, adapter):
        old_meta = {"phase": "active_response"}
        new_meta = {"phase": "early_warning"}
        delta = adapter.compute_delta(old_meta, new_meta)
        assert len(delta.temporal_changes) > 0

    def test_multiple_changes(self, adapter):
        old_meta = {
            "affected_states": ["Odisha"],
            "severity": 3,
            "phase": "active_response",
        }
        new_meta = {
            "affected_states": ["Tamil Nadu"],
            "severity": 5,
            "phase": "early_warning",
        }
        delta = adapter.compute_delta(old_meta, new_meta)
        assert delta.has_changes() is True
        assert len(delta.geographic_changes) > 0
        assert delta.severity_change is not None
        assert len(delta.temporal_changes) > 0


# =============================================================================
# PlanAdapter.adapt_plan — tier selection
# =============================================================================


class TestAdaptPlan:
    async def test_high_similarity_uses_routine_tier(self, adapter, mock_router):
        await adapter.adapt_plan(
            cached_plan="Original plan",
            new_scenario_description="Similar cyclone in Odisha",
            match_tier=CacheMatchTier.HIGH,
            old_metadata={"affected_states": ["Odisha"]},
            new_metadata={"affected_states": ["Odisha"]},
        )
        call_args = mock_router.call.call_args
        assert call_args[0][0] == "routine"

    async def test_medium_similarity_uses_standard_tier(self, adapter, mock_router):
        await adapter.adapt_plan(
            cached_plan="Original plan",
            new_scenario_description="Different flood scenario",
            match_tier=CacheMatchTier.MEDIUM,
            old_metadata={"affected_states": ["Odisha"]},
            new_metadata={"affected_states": ["Bihar"]},
        )
        call_args = mock_router.call.call_args
        assert call_args[0][0] == "standard"

    async def test_adapt_returns_adaptation_result(self, adapter, mock_router):
        result = await adapter.adapt_plan(
            cached_plan="Deploy 4 NDRF battalions to Puri",
            new_scenario_description="Cyclone in Ganjam",
            match_tier=CacheMatchTier.HIGH,
            old_metadata={"affected_districts": ["Puri"]},
            new_metadata={"affected_districts": ["Ganjam"]},
        )
        assert isinstance(result, AdaptationResult)
        assert result.original_plan == "Deploy 4 NDRF battalions to Puri"
        assert len(result.adapted_plan) > 0
        assert result.adaptation_confidence > 0.0

    async def test_adapt_includes_delta_in_prompt(self, adapter, mock_router):
        await adapter.adapt_plan(
            cached_plan="Plan for Odisha",
            new_scenario_description="Cyclone in Tamil Nadu",
            match_tier=CacheMatchTier.MEDIUM,
            old_metadata={"affected_states": ["Odisha"]},
            new_metadata={"affected_states": ["Tamil Nadu"]},
        )
        call_args = mock_router.call.call_args
        messages = call_args[0][1]
        # The prompt should mention the delta
        prompt_text = " ".join(m["content"] for m in messages)
        assert "Odisha" in prompt_text or "Tamil Nadu" in prompt_text


# =============================================================================
# PlanAdapter.validate_adaptation
# =============================================================================


class TestValidateAdaptation:
    def test_valid_adaptation(self, adapter):
        result = AdaptationResult(
            original_plan="Original plan",
            adapted_plan="Adapted plan with NDRF deployment to Chennai",
            delta_summary="Changed location",
            llm_tier_used="routine",
            adaptation_confidence=0.85,
        )
        assert adapter.validate_adaptation(result) is True

    def test_empty_adaptation_invalid(self, adapter):
        result = AdaptationResult(
            original_plan="Original plan",
            adapted_plan="",
            delta_summary="Changed location",
            llm_tier_used="routine",
            adaptation_confidence=0.85,
        )
        assert adapter.validate_adaptation(result) is False

    def test_low_confidence_invalid(self, adapter):
        result = AdaptationResult(
            original_plan="Original plan",
            adapted_plan="Some adapted text",
            delta_summary="Changed location",
            llm_tier_used="routine",
            adaptation_confidence=0.2,
        )
        assert adapter.validate_adaptation(result) is False


# =============================================================================
# Graceful degradation
# =============================================================================


class TestAdapterGracefulDegradation:
    async def test_llm_failure_raises(self, adapter, mock_router):
        mock_router.call.side_effect = AllProvidersFailedError(
            "All providers failed", context={"tier": "routine"}
        )
        with pytest.raises(AllProvidersFailedError):
            await adapter.adapt_plan(
                cached_plan="Plan text",
                new_scenario_description="Scenario",
                match_tier=CacheMatchTier.HIGH,
                old_metadata={},
                new_metadata={},
            )
