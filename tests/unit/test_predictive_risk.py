"""Tests for PredictiveRisk agent — forecasting, cascading failures, risk maps.

Tests cover: initialization, state machine structure, cyclone classification,
cascading failure chains, historical retrieval (RAG), multi-horizon forecasting,
risk map generation, and edge cases. All external services mocked.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.predictive_risk import (
    PredictiveRisk,
    PredictiveRiskState,
    classify_cyclone,
    get_cascade_chain,
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
        tier="standard",
    )
    defaults.update(kw)
    return LLMResponse(**defaults)


def _sample_weather_data() -> list[dict]:
    """Sample IMD weather observations for testing."""
    return [
        {
            "station": "Mumbai",
            "state": "Maharashtra",
            "latitude": 19.076,
            "longitude": 72.878,
            "rainfall_mm": 185.0,
            "wind_speed_kt": 55,
            "temperature_c": 27.5,
            "observation_time": "2026-07-15T06:00:00",
            "imd_color": "red",
        },
        {
            "station": "Thane",
            "state": "Maharashtra",
            "latitude": 19.218,
            "longitude": 72.978,
            "rainfall_mm": 120.0,
            "wind_speed_kt": 40,
            "temperature_c": 28.0,
            "observation_time": "2026-07-15T06:00:00",
            "imd_color": "orange",
        },
    ]


def _sample_cyclone_data() -> dict:
    """Sample cyclone tracking data."""
    return {
        "name": "Cyclone Biparjoy",
        "current_classification": "VSCS",
        "wind_speed_kt": 75,
        "central_pressure_hpa": 972,
        "latitude": 18.5,
        "longitude": 70.2,
        "movement_direction": "NNE",
        "movement_speed_kmh": 15,
        "landfall_expected": True,
        "landfall_location": "Gujarat coast",
    }


def _sample_task_payload(
    weather_data=None,
    cyclone_data=None,
    disaster_type="monsoon_flood",
    affected_state="Maharashtra",
) -> dict:
    return {
        "action": "predict_risk",
        "disaster_type": disaster_type,
        "affected_state": affected_state,
        "affected_districts": ["Mumbai", "Thane", "Raigad"],
        "weather_data": weather_data or _sample_weather_data(),
        "cyclone_data": cyclone_data,
    }


def _make_initial_state(agent, task_payload=None) -> PredictiveRiskState:
    """Build a full initial state for graph execution."""
    payload = task_payload or _sample_task_payload()
    return {
        "task": payload,
        "disaster_id": None,
        "trace_id": "test-trace-001",
        "messages": [
            {"role": "system", "content": agent.get_system_prompt()},
            {"role": "user", "content": json.dumps(payload)},
        ],
        "reasoning": "",
        "confidence": 0.0,
        "artifacts": [],
        "error": None,
        "iteration": 0,
        "metadata": {},
        "weather_data": [],
        "historical_analogies": [],
        "forecast": {},
        "cascading_failures": [],
        "risk_map": {},
        "cyclone_tracking": {},
        "time_horizons": [],
    }


# =============================================================================
# Mock ChromaDB responses
# =============================================================================


def _mock_similarity_results():
    """Create mock SimilarityResult objects."""
    from src.data.ingest.embeddings import SimilarityResult

    return [
        SimilarityResult(
            text="Cyclone Phailin (2013) made landfall in Odisha as VSCS with 115kt winds. "
            "Caused storm surge of 3.5m, flooding in 14 districts.",
            score=0.87,
            metadata={"event": "Cyclone Phailin", "year": 2013, "state": "Odisha"},
            document_id="hist_001",
        ),
        SimilarityResult(
            text="Mumbai floods (2005) — 944mm rainfall in 24h. Cascading failures: "
            "power grid → telecom → water treatment. 1094 deaths.",
            score=0.82,
            metadata={"event": "Mumbai Floods", "year": 2005, "state": "Maharashtra"},
            document_id="hist_002",
        ),
    ]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def settings() -> CrisisSettings:
    return _make_settings()


@pytest.fixture
def mock_router():
    router = AsyncMock()
    forecast_json = json.dumps({
        "disaster_type": "monsoon_flood",
        "time_horizons": {
            "1h": {"risk_level": "high", "rainfall_forecast_mm": 50},
            "6h": {"risk_level": "critical", "rainfall_forecast_mm": 200},
            "24h": {"risk_level": "critical", "rainfall_forecast_mm": 450},
            "72h": {"risk_level": "high", "rainfall_forecast_mm": 600},
        },
        "cyclone_progression": None,
        "confidence": 0.75,
    })
    cascading_json = json.dumps({
        "chains": [
            {
                "trigger": "Heavy rainfall (>200mm/24h)",
                "sequence": [
                    {"event": "Urban flooding", "probability": 0.9, "eta_hours": 2},
                    {"event": "Power grid failure", "probability": 0.7, "eta_hours": 4},
                    {"event": "Telecom backup exhaustion", "probability": 0.6, "eta_hours": 8},
                    {"event": "Water treatment disruption", "probability": 0.5, "eta_hours": 12},
                ],
            }
        ]
    })
    risk_map_json = json.dumps({
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [72.878, 19.076]},
                "properties": {
                    "name": "Mumbai",
                    "risk_level": "critical",
                    "population_at_risk": 2500000,
                    "vulnerability_index": 0.78,
                },
            }
        ],
    })

    router.call = AsyncMock(
        side_effect=[
            _make_llm_response(forecast_json),     # forecast_risk
            _make_llm_response(cascading_json),     # predict_cascading
            _make_llm_response(risk_map_json),      # generate_risk_map
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
def mock_embedding_pipeline():
    pipeline = AsyncMock()
    pipeline.query_similar = AsyncMock(return_value=_mock_similarity_results())
    return pipeline


@pytest.fixture
def agent(settings, mock_router, mock_a2a_client, mock_a2a_server, mock_embedding_pipeline):
    a = PredictiveRisk(settings=settings)
    a._router = mock_router
    a._a2a_client = mock_a2a_client
    a._a2a_server = mock_a2a_server
    a._embedding_pipeline = mock_embedding_pipeline
    return a


# =============================================================================
# Test Group 1: Initialization
# =============================================================================


class TestInitialization:
    def test_creates_with_correct_type(self, agent):
        """PredictiveRisk must use AgentType.PREDICTIVE_RISK."""
        assert agent.agent_type == AgentType.PREDICTIVE_RISK

    def test_default_tier_is_standard(self, agent):
        """PredictiveRisk operates on the standard (DeepSeek Chat) tier."""
        assert agent.llm_tier == LLMTier.STANDARD

    def test_system_prompt_contains_india_context(self, agent):
        """System prompt must reference India-specific agencies and standards."""
        prompt = agent.get_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 50
        prompt_lower = prompt.lower()
        assert "imd" in prompt_lower or "india meteorological" in prompt_lower
        assert "forecast" in prompt_lower or "predict" in prompt_lower

    def test_system_prompt_mentions_cyclone_classification(self, agent):
        """System prompt should reference IMD cyclone classification scale."""
        prompt = agent.get_system_prompt().lower()
        assert "cyclone" in prompt
        assert "vscs" in prompt or "classification" in prompt

    def test_agent_card_has_capabilities(self, agent):
        """Agent card must declare forecasting and risk capabilities."""
        card = agent.get_agent_card()
        assert isinstance(card, A2AAgentCard)
        assert card.agent_type == AgentType.PREDICTIVE_RISK
        assert len(card.capabilities) >= 3
        caps_text = " ".join(card.capabilities).lower()
        assert "forecast" in caps_text
        assert "cascading" in caps_text or "cascade" in caps_text
        assert "risk" in caps_text


# =============================================================================
# Test Group 2: State Machine Structure
# =============================================================================


class TestStateMachine:
    def test_build_graph_has_all_nodes(self, agent):
        """Graph must contain all 6 required nodes."""
        graph = agent.build_graph()
        node_names = set(graph.nodes.keys())
        expected = {
            "ingest_data",
            "retrieve_historical",
            "forecast_risk",
            "predict_cascading",
            "generate_risk_map",
            "produce_report",
        }
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
        initial = _make_initial_state(agent)
        result = await agent.run_graph(initial)
        assert result.get("forecast") is not None
        assert result.get("risk_map") is not None
        assert result.get("confidence", 0) > 0


# =============================================================================
# Test Group 3: Cyclone Classification
# =============================================================================


class TestCycloneClassification:
    def test_depression(self):
        """17-27 kt → Depression (D)."""
        assert classify_cyclone(17) == "D"
        assert classify_cyclone(27) == "D"

    def test_deep_depression(self):
        """28-33 kt → Deep Depression (DD)."""
        assert classify_cyclone(28) == "DD"
        assert classify_cyclone(33) == "DD"

    def test_cyclonic_storm(self):
        """34-47 kt → Cyclonic Storm (CS)."""
        assert classify_cyclone(34) == "CS"
        assert classify_cyclone(47) == "CS"

    def test_severe_cyclonic_storm(self):
        """48-63 kt → Severe Cyclonic Storm (SCS)."""
        assert classify_cyclone(48) == "SCS"
        assert classify_cyclone(63) == "SCS"

    def test_very_severe(self):
        """64-89 kt → Very Severe Cyclonic Storm (VSCS)."""
        assert classify_cyclone(64) == "VSCS"
        assert classify_cyclone(89) == "VSCS"

    def test_extremely_severe(self):
        """90-119 kt → Extremely Severe (ESCS)."""
        assert classify_cyclone(90) == "ESCS"
        assert classify_cyclone(119) == "ESCS"

    def test_super_cyclonic(self):
        """>=120 kt → Super Cyclonic Storm (SuCS)."""
        assert classify_cyclone(120) == "SuCS"
        assert classify_cyclone(180) == "SuCS"

    def test_below_depression(self):
        """Below 17 kt → Low (not classified as cyclone)."""
        assert classify_cyclone(10) == "LOW"
        assert classify_cyclone(0) == "LOW"

    def test_boundary_values(self):
        """Test exact boundary between categories."""
        assert classify_cyclone(27) == "D"
        assert classify_cyclone(28) == "DD"
        assert classify_cyclone(33) == "DD"
        assert classify_cyclone(34) == "CS"
        assert classify_cyclone(63) == "SCS"
        assert classify_cyclone(64) == "VSCS"
        assert classify_cyclone(89) == "VSCS"
        assert classify_cyclone(90) == "ESCS"
        assert classify_cyclone(119) == "ESCS"
        assert classify_cyclone(120) == "SuCS"


# =============================================================================
# Test Group 4: Cascading Failure Chains
# =============================================================================


class TestCascadingFailureChains:
    def test_cyclone_chain(self):
        """Cyclone should produce India-specific cascade chain."""
        chain = get_cascade_chain("cyclone")
        assert len(chain) >= 3
        # Should include storm surge and infrastructure failures
        chain_text = " ".join(chain).lower()
        assert "storm surge" in chain_text or "surge" in chain_text
        assert "flood" in chain_text or "flooding" in chain_text

    def test_flood_chain(self):
        """Flood should produce cascading chain."""
        chain = get_cascade_chain("flood")
        assert len(chain) >= 2
        chain_text = " ".join(chain).lower()
        assert "power" in chain_text or "infrastructure" in chain_text

    def test_monsoon_flood_chain(self):
        """Monsoon flood should produce cascade."""
        chain = get_cascade_chain("monsoon_flood")
        assert len(chain) >= 2

    def test_earthquake_chain(self):
        """Earthquake should produce cascade chain."""
        chain = get_cascade_chain("earthquake")
        assert len(chain) >= 2

    def test_unknown_disaster_returns_generic(self):
        """Unknown disaster type should return a generic chain."""
        chain = get_cascade_chain("unknown_disaster")
        assert isinstance(chain, list)
        assert len(chain) >= 1


# =============================================================================
# Test Group 5: Historical Retrieval (RAG)
# =============================================================================


class TestHistoricalRetrieval:
    @pytest.mark.asyncio
    async def test_retrieves_historical_analogies(self, agent):
        """Agent should retrieve historical analogies from ChromaDB."""
        initial = _make_initial_state(agent)
        result = await agent.run_graph(initial)
        analogies = result.get("historical_analogies", [])
        assert len(analogies) >= 1

    @pytest.mark.asyncio
    async def test_graceful_degradation_no_chromadb(self, agent, mock_embedding_pipeline):
        """If ChromaDB fails, agent should continue with empty analogies."""
        mock_embedding_pipeline.query_similar.side_effect = Exception("ChromaDB down")
        initial = _make_initial_state(agent)
        result = await agent.run_graph(initial)
        # Should not crash — just have empty analogies
        assert result.get("error") is None
        assert isinstance(result.get("historical_analogies", []), list)


# =============================================================================
# Test Group 6: Multi-Horizon Forecasting
# =============================================================================


class TestForecasting:
    @pytest.mark.asyncio
    async def test_forecast_has_time_horizons(self, agent):
        """Forecast should include 1h, 6h, 24h, 72h windows."""
        initial = _make_initial_state(agent)
        result = await agent.run_graph(initial)
        forecast = result.get("forecast", {})
        time_horizons = forecast.get("time_horizons", {})
        assert "1h" in time_horizons
        assert "6h" in time_horizons
        assert "24h" in time_horizons
        assert "72h" in time_horizons

    @pytest.mark.asyncio
    async def test_forecast_includes_risk_levels(self, agent):
        """Each time horizon should have a risk level."""
        initial = _make_initial_state(agent)
        result = await agent.run_graph(initial)
        forecast = result.get("forecast", {})
        for horizon in forecast.get("time_horizons", {}).values():
            assert "risk_level" in horizon

    @pytest.mark.asyncio
    async def test_cyclone_tracking_with_cyclone_data(self, agent, mock_router):
        """When cyclone data is present, cyclone tracking should be populated."""
        forecast_json = json.dumps({
            "disaster_type": "cyclone",
            "time_horizons": {
                "1h": {"risk_level": "critical", "rainfall_forecast_mm": 80},
                "6h": {"risk_level": "critical", "rainfall_forecast_mm": 300},
                "24h": {"risk_level": "critical", "rainfall_forecast_mm": 500},
                "72h": {"risk_level": "high", "rainfall_forecast_mm": 650},
            },
            "cyclone_progression": ["VSCS", "ESCS", "ESCS", "SCS"],
            "confidence": 0.7,
        })
        cascading_json = json.dumps({"chains": []})
        risk_map_json = json.dumps({"type": "FeatureCollection", "features": []})
        mock_router.call = AsyncMock(side_effect=[
            _make_llm_response(forecast_json),
            _make_llm_response(cascading_json),
            _make_llm_response(risk_map_json),
        ])

        payload = _sample_task_payload(
            disaster_type="cyclone",
            cyclone_data=_sample_cyclone_data(),
        )
        initial = _make_initial_state(agent, payload)
        result = await agent.run_graph(initial)
        tracking = result.get("cyclone_tracking", {})
        assert tracking.get("current_classification") is not None


# =============================================================================
# Test Group 7: Risk Map Generation
# =============================================================================


class TestRiskMapGeneration:
    @pytest.mark.asyncio
    async def test_risk_map_is_geojson(self, agent):
        """Risk map output must be a valid GeoJSON structure."""
        initial = _make_initial_state(agent)
        result = await agent.run_graph(initial)
        risk_map = result.get("risk_map", {})
        assert isinstance(risk_map, dict)
        assert risk_map.get("type") in ("FeatureCollection", "Feature", None) or risk_map == {}

    @pytest.mark.asyncio
    async def test_risk_map_features_have_risk_level(self, agent):
        """Each feature in risk map should have risk_level property."""
        initial = _make_initial_state(agent)
        result = await agent.run_graph(initial)
        risk_map = result.get("risk_map", {})
        features = risk_map.get("features", [])
        if features:
            for f in features:
                props = f.get("properties", {})
                assert "risk_level" in props


# =============================================================================
# Test Group 8: Edge Cases
# =============================================================================


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_handles_empty_weather_data(self, agent, mock_router):
        """Agent should handle empty weather data gracefully."""
        forecast_json = json.dumps({
            "disaster_type": "unknown",
            "time_horizons": {
                "1h": {"risk_level": "low", "rainfall_forecast_mm": 0},
                "6h": {"risk_level": "low", "rainfall_forecast_mm": 0},
                "24h": {"risk_level": "low", "rainfall_forecast_mm": 0},
                "72h": {"risk_level": "low", "rainfall_forecast_mm": 0},
            },
            "cyclone_progression": None,
            "confidence": 0.3,
        })
        cascading_json = json.dumps({"chains": []})
        risk_map_json = json.dumps({"type": "FeatureCollection", "features": []})
        mock_router.call = AsyncMock(side_effect=[
            _make_llm_response(forecast_json),
            _make_llm_response(cascading_json),
            _make_llm_response(risk_map_json),
        ])

        payload = _sample_task_payload(weather_data=[])
        initial = _make_initial_state(agent, payload)
        result = await agent.run_graph(initial)
        assert result is not None
        assert result.get("error") is None

    @pytest.mark.asyncio
    async def test_handles_malformed_llm_response(self, agent, mock_router):
        """Agent should handle non-JSON LLM responses gracefully."""
        mock_router.call = AsyncMock(side_effect=[
            _make_llm_response("This is not valid JSON"),
            _make_llm_response("Also not JSON"),
            _make_llm_response("Still not JSON"),
        ])
        initial = _make_initial_state(agent)
        result = await agent.run_graph(initial)
        # Should not crash
        assert result is not None

    @pytest.mark.asyncio
    async def test_confidence_varies_with_data_quality(self, agent, mock_router):
        """With sparse data, confidence should be lower."""
        forecast_json = json.dumps({
            "disaster_type": "unknown",
            "time_horizons": {
                "1h": {"risk_level": "low", "rainfall_forecast_mm": 0},
                "6h": {"risk_level": "low", "rainfall_forecast_mm": 0},
                "24h": {"risk_level": "low", "rainfall_forecast_mm": 0},
                "72h": {"risk_level": "low", "rainfall_forecast_mm": 0},
            },
            "confidence": 0.2,
        })
        cascading_json = json.dumps({"chains": []})
        risk_map_json = json.dumps({"type": "FeatureCollection", "features": []})
        mock_router.call = AsyncMock(side_effect=[
            _make_llm_response(forecast_json),
            _make_llm_response(cascading_json),
            _make_llm_response(risk_map_json),
        ])

        # Empty pipeline results too
        agent._embedding_pipeline.query_similar = AsyncMock(return_value=[])

        payload = _sample_task_payload(weather_data=[])
        initial = _make_initial_state(agent, payload)
        result = await agent.run_graph(initial)
        # With no data, confidence should be low
        assert result.get("confidence", 1.0) <= 0.5

    @pytest.mark.asyncio
    async def test_artifacts_contain_report(self, agent):
        """Final artifacts should contain a predictive risk report."""
        initial = _make_initial_state(agent)
        result = await agent.run_graph(initial)
        artifacts = result.get("artifacts", [])
        assert len(artifacts) >= 1
        report = artifacts[0]
        assert report.get("type") == "predictive_risk_report"
