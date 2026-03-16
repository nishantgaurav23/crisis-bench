"""Tests for CommunityComms agent — multilingual alert generation (S7.6).

Tests cover: initialization, state machine structure, language selection,
message generation, channel formatting, misinformation countering, and
edge cases. All external services (LLM, Redis) are mocked.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.community_comms import (
    STATE_LANGUAGES,
    CommunityComms,
    CommunityCommsState,
    format_sms,
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


def _sample_alert_payload(
    *,
    disaster_type: str = "cyclone",
    severity: int = 4,
    affected_state: str = "Odisha",
    rumors: list | None = None,
) -> dict:
    """Build a task payload for CommunityComms."""
    payload = {
        "action": "generate_alerts",
        "disaster_type": disaster_type,
        "severity": severity,
        "affected_state": affected_state,
        "affected_districts": ["Puri", "Ganjam", "Khordha"],
        "instructions": {
            "shelter_name": "Puri Govt. School No. 5",
            "shelter_location": "Near Jagannath Temple, Puri",
            "evacuation_route": "NH-316 towards Bhubaneswar",
        },
        "situation_summary": "Severe cyclone approaching Odisha coast.",
    }
    if rumors is not None:
        payload["rumors"] = rumors
    return payload


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def settings() -> CrisisSettings:
    return _make_settings()


@pytest.fixture
def mock_router():
    router = AsyncMock()

    # generate_messages: audience-adapted messages
    messages_json = json.dumps({
        "first_responder": (
            "CYCLONE WARNING: Category 4 cyclone approaching Puri coast. "
            "Deploy SAR teams to Puri, Ganjam. Coordinate with NDRF 9711077372."
        ),
        "general_public": (
            "Cyclone alert for Puri, Ganjam, Khordha. Move to nearest shelter immediately. "
            "Shelter: Puri Govt. School No. 5, Near Jagannath Temple. "
            "Helpline: 1070. NDRF: 9711077372."
        ),
        "vulnerable": (
            "DANGER: Big storm coming. Go to school shelter near temple NOW. "
            "Call 1070 for help."
        ),
    })

    # translate: translated messages
    translated_json = json.dumps({
        "odia": "ବାତ୍ୟା ସତର୍କ ବାର୍ତ୍ତା: ପୁରୀ, ଗଞ୍ଜାମ, ଖୋର୍ଦ୍ଧାରେ ବାତ୍ୟା ସତର୍କ।",
        "hindi": "चक्रवात चेतावनी: पुरी, गंजाम, खोर्धा में चक्रवात चेतावनी।",
    })

    # counter_misinfo
    counter_json = json.dumps({
        "counters": [
            {
                "rumor": "The cyclone has weakened",
                "counter": "As per IMD bulletin at 14:00 IST, the cyclone maintains "
                "Category 4 strength. Do NOT return to coastal areas.",
                "source": "IMD Cyclone Bulletin #47",
            }
        ]
    })

    router.call = AsyncMock(
        side_effect=[
            _make_llm_response(messages_json),    # generate_messages
            _make_llm_response(translated_json),   # translation call
            _make_llm_response(counter_json),      # counter_misinfo
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
    a = CommunityComms(settings=settings)
    a._router = mock_router
    a._a2a_client = mock_a2a_client
    a._a2a_server = mock_a2a_server
    return a


def _make_initial_state(agent, payload=None) -> CommunityCommsState:
    """Build initial state for running the graph."""
    if payload is None:
        payload = _sample_alert_payload()
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
        "alert_info": {},
        "target_languages": [],
        "audience_messages": {},
        "channel_formats": {},
        "counter_messages": [],
    }


# =============================================================================
# Test Group 1: Initialization
# =============================================================================


class TestInitialization:
    def test_creates_with_correct_type(self, agent):
        """CommunityComms must use AgentType.COMMUNITY_COMMS."""
        assert agent.agent_type == AgentType.COMMUNITY_COMMS

    def test_default_tier_is_routine(self, agent):
        """CommunityComms operates on the routine (Qwen Flash) tier."""
        assert agent.llm_tier == LLMTier.ROUTINE

    def test_system_prompt_contains_multilingual_context(self, agent):
        """System prompt must reference multilingual capability and Indian languages."""
        prompt = agent.get_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 50
        prompt_lower = prompt.lower()
        assert "multilingual" in prompt_lower or "language" in prompt_lower
        assert "ndma" in prompt_lower or "ndrf" in prompt_lower

    def test_agent_card_has_capabilities(self, agent):
        """Agent card must declare multilingual and channel formatting capabilities."""
        card = agent.get_agent_card()
        assert isinstance(card, A2AAgentCard)
        assert card.agent_type == AgentType.COMMUNITY_COMMS
        assert len(card.capabilities) >= 3
        caps_text = " ".join(c.lower() for c in card.capabilities)
        assert "multilingual" in caps_text or "language" in caps_text or "translation" in caps_text
        assert "channel" in caps_text or "format" in caps_text or "whatsapp" in caps_text


# =============================================================================
# Test Group 2: State Machine Structure
# =============================================================================


class TestStateMachine:
    def test_build_graph_has_all_nodes(self, agent):
        """Graph must contain parse, select_languages, generate, format, counter nodes."""
        graph = agent.build_graph()
        node_names = set(graph.nodes.keys())
        expected = {
            "parse_alert", "select_languages", "generate_messages",
            "format_channels", "counter_misinfo",
        }
        assert expected.issubset(node_names), f"Missing nodes: {expected - node_names}"

    def test_graph_compiles(self, agent):
        """Graph must compile without errors."""
        graph = agent.build_graph()
        compiled = graph.compile()
        assert compiled is not None

    @pytest.mark.asyncio
    async def test_graph_runs_end_to_end(self, agent):
        """Full pipeline should execute and produce a result."""
        payload = _sample_alert_payload(rumors=[{"text": "The cyclone has weakened"}])
        initial = _make_initial_state(agent, payload)
        result = await agent.run_graph(initial)
        assert result.get("channel_formats") is not None
        assert result.get("target_languages") is not None


# =============================================================================
# Test Group 3: Language Selection
# =============================================================================


class TestLanguageSelection:
    def test_state_languages_covers_major_states(self):
        """STATE_LANGUAGES must map all major Indian states to languages."""
        assert "Odisha" in STATE_LANGUAGES
        assert "Maharashtra" in STATE_LANGUAGES
        assert "Tamil Nadu" in STATE_LANGUAGES
        assert "West Bengal" in STATE_LANGUAGES
        assert "Kerala" in STATE_LANGUAGES
        assert "Gujarat" in STATE_LANGUAGES
        assert "Karnataka" in STATE_LANGUAGES
        assert "Andhra Pradesh" in STATE_LANGUAGES
        assert "Telangana" in STATE_LANGUAGES

    def test_odisha_includes_odia_and_hindi(self):
        """Odisha should map to Odia + Hindi."""
        langs = STATE_LANGUAGES["Odisha"]
        assert "odia" in langs
        assert "hindi" in langs

    def test_tamilnadu_includes_tamil_and_hindi(self):
        """Tamil Nadu should map to Tamil + Hindi."""
        langs = STATE_LANGUAGES["Tamil Nadu"]
        assert "tamil" in langs
        assert "hindi" in langs

    def test_hindi_always_included(self):
        """Hindi should be present for every state (pan-India language)."""
        for state, langs in STATE_LANGUAGES.items():
            assert "hindi" in langs, f"Hindi missing for {state}"

    @pytest.mark.asyncio
    async def test_language_selection_for_odisha(self, agent):
        """Selecting languages for Odisha should include odia + hindi."""
        initial = _make_initial_state(agent)
        result = await agent.run_graph(initial)
        langs = result.get("target_languages", [])
        assert "odia" in langs
        assert "hindi" in langs


# =============================================================================
# Test Group 4: Message Generation
# =============================================================================


class TestMessageGeneration:
    @pytest.mark.asyncio
    async def test_generates_audience_messages(self, agent):
        """Must produce messages for 3 audience types."""
        initial = _make_initial_state(agent)
        result = await agent.run_graph(initial)
        audience_msgs = result.get("audience_messages", {})
        assert isinstance(audience_msgs, dict)
        # Should have at least first_responder and general_public
        assert len(audience_msgs) >= 2

    @pytest.mark.asyncio
    async def test_messages_include_helpline_numbers(self, agent):
        """Public-facing messages must include NDRF helpline and state helpline."""
        initial = _make_initial_state(agent)
        result = await agent.run_graph(initial)
        audience_msgs = result.get("audience_messages", {})
        # Check general_public message includes helpline info
        public_msg = audience_msgs.get("general_public", "")
        assert "9711077372" in public_msg or "1070" in public_msg


# =============================================================================
# Test Group 5: Channel Formatting
# =============================================================================


class TestChannelFormatting:
    @pytest.mark.asyncio
    async def test_formats_for_four_channels(self, agent):
        """Must produce formatted output for whatsapp, sms, social_media, media_briefing."""
        initial = _make_initial_state(agent)
        result = await agent.run_graph(initial)
        channels = result.get("channel_formats", {})
        assert isinstance(channels, dict)
        expected_channels = {"whatsapp", "sms", "social_media", "media_briefing"}
        assert expected_channels.issubset(set(channels.keys())), (
            f"Missing channels: {expected_channels - set(channels.keys())}"
        )

    def test_sms_format_respects_char_limit(self):
        """SMS format must be <= 160 characters."""
        long_msg = "A" * 200
        result = format_sms(long_msg)
        assert len(result) <= 160

    def test_sms_format_preserves_short_messages(self):
        """SMS format should not truncate short messages."""
        short_msg = "Cyclone alert. Go to shelter."
        result = format_sms(short_msg)
        assert result == short_msg

    def test_sms_truncation_adds_ellipsis(self):
        """Truncated SMS should end with '...' to indicate truncation."""
        long_msg = "A" * 200
        result = format_sms(long_msg)
        assert result.endswith("...")


# =============================================================================
# Test Group 6: Misinformation Countering
# =============================================================================


class TestMisinfoCountering:
    @pytest.mark.asyncio
    async def test_counter_messages_when_rumors_present(self, agent):
        """Should generate counter-messages when rumors are in the payload."""
        payload = _sample_alert_payload(
            rumors=[{"text": "The cyclone has weakened"}]
        )
        initial = _make_initial_state(agent, payload)
        result = await agent.run_graph(initial)
        counters = result.get("counter_messages", [])
        assert isinstance(counters, list)
        assert len(counters) >= 1

    @pytest.mark.asyncio
    async def test_no_counter_messages_when_no_rumors(self, agent, mock_router):
        """Should return empty list when no rumors in payload."""
        # Reset side_effect for no-rumors case (only 2 LLM calls needed)
        messages_json = json.dumps({
            "first_responder": "Deploy teams.",
            "general_public": "Go to shelter. Call 1070.",
            "vulnerable": "Go to shelter NOW.",
        })
        translated_json = json.dumps({"hindi": "आश्रय में जाएं। 1070 पर कॉल करें।"})
        mock_router.call = AsyncMock(
            side_effect=[
                _make_llm_response(messages_json),
                _make_llm_response(translated_json),
            ]
        )

        payload = _sample_alert_payload()  # No rumors
        initial = _make_initial_state(agent, payload)
        result = await agent.run_graph(initial)
        counters = result.get("counter_messages", [])
        assert counters == []


# =============================================================================
# Test Group 7: Edge Cases
# =============================================================================


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_handles_empty_payload(self, agent, mock_router):
        """Agent should not crash with empty task payload."""
        mock_router.call = AsyncMock(
            side_effect=[
                _make_llm_response(json.dumps({
                    "first_responder": "No alert.",
                    "general_public": "No alert.",
                    "vulnerable": "No alert.",
                })),
                _make_llm_response(json.dumps({"hindi": "कोई चेतावनी नहीं।"})),
            ]
        )
        initial = _make_initial_state(agent, {"action": "generate_alerts"})
        result = await agent.run_graph(initial)
        assert result is not None

    @pytest.mark.asyncio
    async def test_handles_unknown_state(self, agent, mock_router):
        """Unknown state should default to Hindi only."""
        mock_router.call = AsyncMock(
            side_effect=[
                _make_llm_response(json.dumps({
                    "first_responder": "Deploy teams.",
                    "general_public": "Go to shelter. Call 1070.",
                    "vulnerable": "Go to shelter NOW.",
                })),
                _make_llm_response(json.dumps({"hindi": "आश्रय में जाएं।"})),
            ]
        )
        payload = _sample_alert_payload(affected_state="UnknownLand")
        initial = _make_initial_state(agent, payload)
        result = await agent.run_graph(initial)
        langs = result.get("target_languages", [])
        assert "hindi" in langs

    @pytest.mark.asyncio
    async def test_confidence_reflects_data_completeness(self, agent):
        """With full data, confidence should be higher."""
        payload = _sample_alert_payload(
            rumors=[{"text": "The cyclone has weakened"}]
        )
        initial = _make_initial_state(agent, payload)
        result = await agent.run_graph(initial)
        assert result.get("confidence", 0.0) >= 0.5
