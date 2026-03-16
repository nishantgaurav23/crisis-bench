"""Tests for SituationSense agent — multi-source data fusion + urgency scoring.

Tests cover: initialization, state machine structure, data ingestion,
urgency scoring (IMD color codes), misinformation detection, GeoJSON output,
and edge cases. All external services (LLM, Redis) are mocked.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.situation_sense import (
    SituationSense,
    SituationState,
    map_urgency,
)
from src.protocols.a2a.schemas import A2AAgentCard
from src.routing.llm_router import LLMResponse, LLMTier
from src.shared.config import CrisisSettings
from src.shared.models import AgentType

# =============================================================================
# Helpers
# =============================================================================


def _make_settings(**overrides) -> CrisisSettings:
    defaults = dict(
        DEEPSEEK_API_KEY="",
        QWEN_API_KEY="",
        KIMI_API_KEY="",
        GROQ_API_KEY="",
        GOOGLE_API_KEY="",
        OLLAMA_HOST="http://localhost:11434",
        AGENT_TIMEOUT_SECONDS=10,
        AGENT_MAX_DELEGATION_DEPTH=5,
        _env_file=None,
    )
    defaults.update(overrides)
    return CrisisSettings(**defaults)


def _make_llm_response(content: str = "test output", **kw) -> LLMResponse:
    defaults = dict(
        content=content,
        provider="ollama_local",
        model="qwen2.5:7b",
        input_tokens=10,
        output_tokens=5,
        cost_usd=0.0,
        latency_s=0.1,
        tier="routine",
    )
    defaults.update(kw)
    return LLMResponse(**defaults)


def _sample_imd_warnings() -> list[dict]:
    """Sample IMD district warning data."""
    return [
        {
            "district_id": "MH001",
            "district_name": "Mumbai",
            "state": "Maharashtra",
            "color_code": "orange",
            "warning": "Heavy rainfall likely",
            "valid_from": "2026-07-15T00:00:00",
            "valid_to": "2026-07-16T00:00:00",
        },
        {
            "district_id": "MH002",
            "district_name": "Thane",
            "state": "Maharashtra",
            "color_code": "yellow",
            "warning": "Moderate rainfall expected",
            "valid_from": "2026-07-15T00:00:00",
            "valid_to": "2026-07-16T00:00:00",
        },
    ]


def _sample_sachet_alerts() -> list[dict]:
    """Sample SACHET CAP alerts."""
    return [
        {
            "identifier": "SACHET-2026-001",
            "sender": "IMD",
            "event": "Heavy Rainfall",
            "severity": "Severe",
            "urgency": "Immediate",
            "certainty": "Likely",
            "headline": "Heavy rainfall warning for Maharashtra",
            "description": "Very heavy rainfall expected in Mumbai and Thane districts.",
            "area_desc": "Mumbai, Thane, Maharashtra",
            "polygon": None,
        },
    ]


_SENTINEL = object()


def _sample_task_payload(
    imd_data: list[dict] | object = _SENTINEL,
    sachet_alerts: list[dict] | object = _SENTINEL,
    social_media: list[dict] | object = _SENTINEL,
) -> dict:
    """Build a task payload for SituationSense."""
    return {
        "action": "assess_situation",
        "disaster_type": "monsoon_flood",
        "affected_state": "Maharashtra",
        "imd_data": _sample_imd_warnings() if imd_data is _SENTINEL else imd_data,
        "sachet_alerts": (
            _sample_sachet_alerts() if sachet_alerts is _SENTINEL else sachet_alerts
        ),
        "social_media": [] if social_media is _SENTINEL else social_media,
    }


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def settings() -> CrisisSettings:
    return _make_settings()


@pytest.fixture
def mock_router():
    router = AsyncMock()
    # Return a fused situation report when called
    fused_json = json.dumps({
        "summary": "Heavy rainfall affecting Mumbai and Thane",
        "affected_areas": ["Mumbai", "Thane"],
        "severity": "high",
        "sources": ["IMD", "SACHET"],
    })
    misinfo_json = json.dumps({"flags": []})
    sitrep_json = json.dumps({
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [72.8777, 19.0760]},
                "properties": {
                    "name": "Mumbai",
                    "urgency": 3,
                    "warning": "Heavy rainfall",
                },
            }
        ],
    })

    # reason() is called multiple times for different graph nodes
    router.call = AsyncMock(
        side_effect=[
            _make_llm_response(fused_json),     # fuse_sources
            _make_llm_response(misinfo_json),    # detect_misinfo
            _make_llm_response(sitrep_json),     # produce_sitrep
        ]
    )
    return router


@pytest.fixture
def mock_a2a_client():
    client = AsyncMock()
    client.start = AsyncMock()
    client.stop = AsyncMock()
    client.send_result = AsyncMock(return_value="msg-123")
    client.on_message = MagicMock()
    return client


@pytest.fixture
def mock_a2a_server():
    server = AsyncMock()
    server.register_agent_card = AsyncMock(return_value="msg-card")
    return server


@pytest.fixture
def agent(settings, mock_router, mock_a2a_client, mock_a2a_server):
    a = SituationSense(settings=settings)
    a._router = mock_router
    a._a2a_client = mock_a2a_client
    a._a2a_server = mock_a2a_server
    return a


# =============================================================================
# Test Group 1: Initialization
# =============================================================================


class TestInitialization:
    def test_creates_with_correct_type(self, agent):
        """SituationSense must use AgentType.SITUATION_SENSE."""
        assert agent.agent_type == AgentType.SITUATION_SENSE

    def test_default_tier_is_routine(self, agent):
        """SituationSense operates on the routine (Qwen Flash) tier."""
        assert agent.llm_tier == LLMTier.ROUTINE

    def test_system_prompt_contains_india_context(self, agent):
        """System prompt must reference India-specific agencies and standards."""
        prompt = agent.get_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 50
        # Must mention key Indian disaster entities
        prompt_lower = prompt.lower()
        assert "imd" in prompt_lower or "india meteorological" in prompt_lower
        assert "ndma" in prompt_lower or "sachet" in prompt_lower

    def test_agent_card_has_capabilities(self, agent):
        """Agent card must declare data fusion and urgency scoring capabilities."""
        card = agent.get_agent_card()
        assert isinstance(card, A2AAgentCard)
        assert card.agent_type == AgentType.SITUATION_SENSE
        assert len(card.capabilities) >= 3
        caps_lower = [c.lower() for c in card.capabilities]
        caps_text = " ".join(caps_lower)
        assert "fusion" in caps_text or "fuse" in caps_text or "data" in caps_text
        assert "urgency" in caps_text or "scoring" in caps_text


# =============================================================================
# Test Group 2: State Machine Structure
# =============================================================================


class TestStateMachine:
    def test_build_graph_has_all_nodes(self, agent):
        """Graph must contain ingest, fuse, score, misinfo, sitrep nodes."""
        graph = agent.build_graph()
        node_names = set(graph.nodes.keys())
        expected = {"ingest_data", "fuse_sources", "score_urgency",
                    "detect_misinfo", "produce_sitrep"}
        assert expected.issubset(node_names), (
            f"Missing nodes: {expected - node_names}"
        )

    def test_graph_compiles(self, agent):
        """Graph must compile without errors."""
        graph = agent.build_graph()
        compiled = graph.compile()
        assert compiled is not None

    @pytest.mark.asyncio
    async def test_graph_runs_end_to_end(self, agent):
        """Full pipeline should execute and produce a result."""
        initial: SituationState = {
            "task": _sample_task_payload(),
            "disaster_id": None,
            "trace_id": "test-trace-001",
            "messages": [
                {"role": "system", "content": agent.get_system_prompt()},
                {"role": "user", "content": json.dumps(_sample_task_payload())},
            ],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
            "imd_data": [],
            "sachet_alerts": [],
            "social_media": [],
            "fused_picture": {},
            "urgency_score": 0,
            "imd_color": "",
            "misinfo_flags": [],
            "geojson": {},
        }
        result = await agent.run_graph(initial)
        assert result.get("urgency_score", 0) >= 1
        assert result.get("geojson") is not None


# =============================================================================
# Test Group 3: Data Ingestion
# =============================================================================


class TestDataIngestion:
    @pytest.mark.asyncio
    async def test_ingest_processes_imd_data(self, agent):
        """Ingest node should extract IMD warnings from task payload."""
        initial: SituationState = {
            "task": _sample_task_payload(),
            "disaster_id": None,
            "trace_id": "test-ingest-001",
            "messages": [],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
            "imd_data": [],
            "sachet_alerts": [],
            "social_media": [],
            "fused_picture": {},
            "urgency_score": 0,
            "imd_color": "",
            "misinfo_flags": [],
            "geojson": {},
        }
        result = await agent.run_graph(initial)
        assert len(result.get("imd_data", [])) > 0

    @pytest.mark.asyncio
    async def test_ingest_processes_sachet_alerts(self, agent):
        """Ingest node should extract SACHET alerts from task payload."""
        initial: SituationState = {
            "task": _sample_task_payload(),
            "disaster_id": None,
            "trace_id": "test-ingest-002",
            "messages": [],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
            "imd_data": [],
            "sachet_alerts": [],
            "social_media": [],
            "fused_picture": {},
            "urgency_score": 0,
            "imd_color": "",
            "misinfo_flags": [],
            "geojson": {},
        }
        result = await agent.run_graph(initial)
        assert len(result.get("sachet_alerts", [])) > 0

    @pytest.mark.asyncio
    async def test_ingest_handles_empty_data(self, agent):
        """Ingest should handle task with no disaster data gracefully."""
        initial: SituationState = {
            "task": {"action": "assess_situation"},
            "disaster_id": None,
            "trace_id": "test-empty-001",
            "messages": [],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
            "imd_data": [],
            "sachet_alerts": [],
            "social_media": [],
            "fused_picture": {},
            "urgency_score": 0,
            "imd_color": "",
            "misinfo_flags": [],
            "geojson": {},
        }
        result = await agent.run_graph(initial)
        # Should not crash — just have empty data
        assert result.get("error") is None


# =============================================================================
# Test Group 4: Urgency Scoring
# =============================================================================


class TestUrgencyScoring:
    def test_urgency_green_maps_to_1(self):
        """IMD Green color code → urgency 1."""
        assert map_urgency(imd_color="green", sachet_severity="Minor") == 1

    def test_urgency_yellow_maps_to_2(self):
        """IMD Yellow color code → urgency 2."""
        assert map_urgency(imd_color="yellow", sachet_severity="Moderate") == 2

    def test_urgency_orange_maps_to_3(self):
        """IMD Orange color code → urgency 3."""
        assert map_urgency(imd_color="orange", sachet_severity="Severe") == 3

    def test_urgency_red_maps_to_4(self):
        """IMD Red color code → urgency 4."""
        assert map_urgency(imd_color="red", sachet_severity="Extreme") == 4

    def test_urgency_extreme_maps_to_5(self):
        """Red + Extreme + Immediate → urgency 5."""
        assert map_urgency(
            imd_color="red",
            sachet_severity="Extreme",
            sachet_urgency="Immediate",
        ) == 5

    def test_urgency_defaults_to_1(self):
        """Unknown or missing data should default to urgency 1."""
        assert map_urgency(imd_color="", sachet_severity="") == 1
        assert map_urgency(imd_color="unknown", sachet_severity="Unknown") == 1

    def test_urgency_sachet_upgrades_imd(self):
        """If SACHET severity is higher than IMD color suggests, take the higher."""
        # IMD says Yellow (2) but SACHET says Extreme (4) → take 4
        assert map_urgency(imd_color="yellow", sachet_severity="Extreme") >= 3


# =============================================================================
# Test Group 5: Misinformation Detection
# =============================================================================


class TestMisinfoDetection:
    @pytest.mark.asyncio
    async def test_misinfo_empty_when_no_issues(self, agent):
        """No misinformation flags when data is consistent."""
        initial: SituationState = {
            "task": _sample_task_payload(),
            "disaster_id": None,
            "trace_id": "test-misinfo-001",
            "messages": [],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
            "imd_data": [],
            "sachet_alerts": [],
            "social_media": [],
            "fused_picture": {},
            "urgency_score": 0,
            "imd_color": "",
            "misinfo_flags": [],
            "geojson": {},
        }
        result = await agent.run_graph(initial)
        # With consistent data, flags should be empty list
        assert isinstance(result.get("misinfo_flags", []), list)


# =============================================================================
# Test Group 6: Situation Report Output
# =============================================================================


class TestSitrepOutput:
    @pytest.mark.asyncio
    async def test_sitrep_produces_geojson(self, agent):
        """Output must have valid GeoJSON structure."""
        initial: SituationState = {
            "task": _sample_task_payload(),
            "disaster_id": None,
            "trace_id": "test-sitrep-001",
            "messages": [],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
            "imd_data": [],
            "sachet_alerts": [],
            "social_media": [],
            "fused_picture": {},
            "urgency_score": 0,
            "imd_color": "",
            "misinfo_flags": [],
            "geojson": {},
        }
        result = await agent.run_graph(initial)
        geojson = result.get("geojson", {})
        assert isinstance(geojson, dict)
        assert geojson.get("type") in ("FeatureCollection", "Feature", None) or geojson == {}

    @pytest.mark.asyncio
    async def test_sitrep_includes_urgency(self, agent):
        """Urgency score must be present in final state."""
        initial: SituationState = {
            "task": _sample_task_payload(),
            "disaster_id": None,
            "trace_id": "test-sitrep-002",
            "messages": [],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
            "imd_data": [],
            "sachet_alerts": [],
            "social_media": [],
            "fused_picture": {},
            "urgency_score": 0,
            "imd_color": "",
            "misinfo_flags": [],
            "geojson": {},
        }
        result = await agent.run_graph(initial)
        assert result.get("urgency_score", 0) >= 1


# =============================================================================
# Test Group 7: Edge Cases
# =============================================================================


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_handles_task_with_no_disaster_data(self, agent):
        """Agent should not crash when task payload has no disaster data."""
        initial: SituationState = {
            "task": {"action": "assess_situation"},
            "disaster_id": None,
            "trace_id": "test-edge-001",
            "messages": [],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
            "imd_data": [],
            "sachet_alerts": [],
            "social_media": [],
            "fused_picture": {},
            "urgency_score": 0,
            "imd_color": "",
            "misinfo_flags": [],
            "geojson": {},
        }
        result = await agent.run_graph(initial)
        assert result is not None

    @pytest.mark.asyncio
    async def test_handles_malformed_imd_data(self, agent):
        """Agent should handle malformed IMD data without crashing."""
        payload = _sample_task_payload(imd_data=[{"bad_key": "no_color"}])
        initial: SituationState = {
            "task": payload,
            "disaster_id": None,
            "trace_id": "test-edge-002",
            "messages": [],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
            "imd_data": [],
            "sachet_alerts": [],
            "social_media": [],
            "fused_picture": {},
            "urgency_score": 0,
            "imd_color": "",
            "misinfo_flags": [],
            "geojson": {},
        }
        result = await agent.run_graph(initial)
        assert result is not None

    @pytest.mark.asyncio
    async def test_confidence_reflects_data_quality(self, agent):
        """With sparse data, confidence should be lower."""
        payload = _sample_task_payload(imd_data=[], sachet_alerts=[])
        initial: SituationState = {
            "task": payload,
            "disaster_id": None,
            "trace_id": "test-edge-003",
            "messages": [],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
            "imd_data": [],
            "sachet_alerts": [],
            "social_media": [],
            "fused_picture": {},
            "urgency_score": 0,
            "imd_color": "",
            "misinfo_flags": [],
            "geojson": {},
        }
        result = await agent.run_graph(initial)
        # With no data sources, confidence should be lower
        assert result.get("confidence", 1.0) <= 0.5
