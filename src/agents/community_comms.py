"""CommunityComms agent — multilingual emergency alert generation (S7.6).

Generates multilingual alerts for 9 Indian languages, adapts messaging for
different audiences (first responders, public, vulnerable), formats for
Indian communication channels (WhatsApp, SMS, social media, media briefing),
and generates misinformation counter-messaging.

Runs on the **routine** tier (Qwen Flash, $0.04/M tokens).

LangGraph nodes:
    parse_alert -> select_languages -> generate_messages -> format_channels -> counter_misinfo

Usage::

    agent = CommunityComms()
    await agent.start()
"""

from __future__ import annotations

import json
from typing import Any

from langgraph.graph import END, StateGraph

from src.agents.base import AgentState, BaseAgent
from src.protocols.a2a.schemas import A2AAgentCard
from src.routing.llm_router import LLMTier
from src.shared.models import AgentType
from src.shared.telemetry import get_logger

logger = get_logger("agent.community_comms")

# =============================================================================
# Constants
# =============================================================================

_NDRF_HELPLINE = "9711077372"
_STATE_HELPLINE = "1070"
_SMS_CHAR_LIMIT = 160

# State → primary languages. Hindi is always included (pan-India).
STATE_LANGUAGES: dict[str, list[str]] = {
    # Eastern India
    "Odisha": ["odia", "hindi"],
    "West Bengal": ["bengali", "hindi"],
    "Jharkhand": ["hindi"],
    "Bihar": ["hindi"],
    "Sikkim": ["hindi"],
    "Assam": ["bengali", "hindi"],
    "Meghalaya": ["hindi"],
    "Tripura": ["bengali", "hindi"],
    "Mizoram": ["hindi"],
    "Manipur": ["hindi"],
    "Nagaland": ["hindi"],
    "Arunachal Pradesh": ["hindi"],
    # Western India
    "Maharashtra": ["marathi", "hindi"],
    "Gujarat": ["gujarati", "hindi"],
    "Goa": ["marathi", "hindi"],
    "Rajasthan": ["hindi"],
    # Southern India
    "Tamil Nadu": ["tamil", "hindi"],
    "Kerala": ["malayalam", "hindi"],
    "Karnataka": ["kannada", "hindi"],
    "Andhra Pradesh": ["telugu", "hindi"],
    "Telangana": ["telugu", "hindi"],
    "Puducherry": ["tamil", "hindi"],
    "Lakshadweep": ["malayalam", "hindi"],
    # Northern India
    "Uttar Pradesh": ["hindi"],
    "Madhya Pradesh": ["hindi"],
    "Chhattisgarh": ["hindi"],
    "Uttarakhand": ["hindi"],
    "Himachal Pradesh": ["hindi"],
    "Haryana": ["hindi"],
    "Punjab": ["hindi"],
    "Delhi": ["hindi"],
    "Chandigarh": ["hindi"],
    "Jammu and Kashmir": ["hindi"],
    "Ladakh": ["hindi"],
    # Island territories
    "Andaman and Nicobar Islands": ["hindi"],
    "Dadra and Nagar Haveli and Daman and Diu": ["gujarati", "hindi"],
}


# =============================================================================
# SMS Formatter
# =============================================================================


def format_sms(message: str) -> str:
    """Truncate a message to fit SMS 160-char limit.

    If the message exceeds 160 characters, truncate and append '...'.
    """
    if len(message) <= _SMS_CHAR_LIMIT:
        return message
    return message[: _SMS_CHAR_LIMIT - 3] + "..."


# =============================================================================
# Community Comms State
# =============================================================================


class CommunityCommsState(AgentState, total=False):
    """Extended state for CommunityComms agent."""

    alert_info: dict
    target_languages: list[str]
    audience_messages: dict[str, str]
    channel_formats: dict[str, str]
    counter_messages: list[dict]


# =============================================================================
# CommunityComms Agent
# =============================================================================


class CommunityComms(BaseAgent):
    """Multilingual emergency alert generation agent.

    Generates alerts in 9 Indian languages, adapts for audiences,
    formats for channels, and counters misinformation.
    """

    def __init__(self, *, settings=None) -> None:
        from src.shared.config import get_settings

        super().__init__(
            agent_id="community_comms",
            agent_type=AgentType.COMMUNITY_COMMS,
            llm_tier=LLMTier.ROUTINE,
            settings=settings or get_settings(),
        )

    def get_system_prompt(self) -> str:
        return (
            "You are the CommunityComms agent for India's CRISIS-BENCH disaster "
            "response system. Your role is to generate multilingual emergency alerts "
            "for affected communities across India.\n\n"
            "Capabilities:\n"
            "- Generate alerts in 9 Indian languages: Hindi, Bengali, Tamil, Telugu, "
            "Odia, Marathi, Gujarati, Kannada, Malayalam\n"
            "- Adapt messaging for audiences: first responders (technical/English), "
            "general public (simple/local language), vulnerable populations (simple "
            "directives)\n"
            "- Follow NDMA/NDRF communication guidelines\n"
            "- Include actionable instructions: shelter locations, helpline numbers "
            f"(NDRF: {_NDRF_HELPLINE}, State: {_STATE_HELPLINE}), evacuation routes\n"
            "- Generate misinformation counter-messaging with official source citations\n\n"
            "Rules:\n"
            "- Always include helpline numbers in public-facing messages\n"
            "- Use simple language for general public and vulnerable groups\n"
            "- First responder messages should be technical and in English\n"
            "- Always cite official sources (IMD, NDMA, CWC) when countering rumors\n"
            "- Output structured JSON when asked."
        )

    def get_agent_card(self) -> A2AAgentCard:
        return A2AAgentCard(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            name="CommunityComms",
            description=(
                "Multilingual emergency alert generation: 9 Indian languages, "
                "audience adaptation, WhatsApp/SMS/social formatting, "
                "misinformation countering"
            ),
            capabilities=[
                "multilingual_alerts",
                "audience_adaptation",
                "channel_formatting",
                "misinformation_countering",
                "bhashini_tts_stub",
            ],
            llm_tier=self.llm_tier,
        )

    def build_graph(self) -> StateGraph:
        graph = StateGraph(CommunityCommsState)

        graph.add_node("parse_alert", self._parse_alert)
        graph.add_node("select_languages", self._select_languages)
        graph.add_node("generate_messages", self._generate_messages)
        graph.add_node("format_channels", self._format_channels)
        graph.add_node("counter_misinfo", self._counter_misinfo)

        graph.set_entry_point("parse_alert")
        graph.add_edge("parse_alert", "select_languages")
        graph.add_edge("select_languages", "generate_messages")
        graph.add_edge("generate_messages", "format_channels")
        graph.add_edge("format_channels", "counter_misinfo")
        graph.add_edge("counter_misinfo", END)

        return graph

    # -----------------------------------------------------------------
    # Graph Nodes
    # -----------------------------------------------------------------

    async def _parse_alert(self, state: CommunityCommsState) -> dict[str, Any]:
        """Extract disaster info from task payload."""
        task = state.get("task", {})

        alert_info = {
            "disaster_type": task.get("disaster_type", "unknown"),
            "severity": task.get("severity", 1),
            "affected_state": task.get("affected_state", ""),
            "affected_districts": task.get("affected_districts", []),
            "situation_summary": task.get("situation_summary", ""),
            "instructions": task.get("instructions", {}),
            "rumors": task.get("rumors", []),
            "helplines": {
                "ndrf": _NDRF_HELPLINE,
                "state": _STATE_HELPLINE,
            },
        }

        logger.info(
            "alert_parsed",
            disaster_type=alert_info["disaster_type"],
            severity=alert_info["severity"],
            affected_state=alert_info["affected_state"],
            districts=len(alert_info["affected_districts"]),
            trace_id=state.get("trace_id", ""),
        )

        return {"alert_info": alert_info}

    async def _select_languages(self, state: CommunityCommsState) -> dict[str, Any]:
        """Determine target languages from affected state."""
        alert_info = state.get("alert_info", {})
        affected_state = alert_info.get("affected_state", "")

        languages = STATE_LANGUAGES.get(affected_state, ["hindi"])

        # Ensure hindi is always present
        if "hindi" not in languages:
            languages = ["hindi"] + languages

        logger.info(
            "languages_selected",
            affected_state=affected_state,
            languages=languages,
            trace_id=state.get("trace_id", ""),
        )

        return {"target_languages": languages}

    async def _generate_messages(self, state: CommunityCommsState) -> dict[str, Any]:
        """Use LLM to generate audience-adapted messages, then translate."""
        alert_info = state.get("alert_info", {})
        target_languages = state.get("target_languages", ["hindi"])
        trace_id = state.get("trace_id", "")

        instructions = alert_info.get("instructions", {})
        shelter_info = ""
        if instructions.get("shelter_name"):
            shelter_info = (
                f"Shelter: {instructions['shelter_name']}"
                + (f", {instructions['shelter_location']}" if instructions.get("shelter_location") else "")
            )
        evac_info = ""
        if instructions.get("evacuation_route"):
            evac_info = f"Evacuation route: {instructions['evacuation_route']}"

        prompt = (
            "Generate emergency alert messages for THREE audience types. "
            "Output ONLY valid JSON with keys: first_responder, general_public, vulnerable.\n\n"
            f"Disaster: {alert_info.get('disaster_type', 'unknown')}\n"
            f"Severity: {alert_info.get('severity', 1)}/5\n"
            f"Affected areas: {', '.join(alert_info.get('affected_districts', []))}, "
            f"{alert_info.get('affected_state', '')}\n"
            f"Situation: {alert_info.get('situation_summary', '')}\n"
            f"{shelter_info}\n{evac_info}\n"
            f"NDRF helpline: {_NDRF_HELPLINE}\nState helpline: {_STATE_HELPLINE}\n\n"
            "Rules:\n"
            "- first_responder: Technical, English, coordinate with NDRF\n"
            "- general_public: Simple language, include shelter + helplines\n"
            "- vulnerable: Very simple directives, include helpline 1070"
        )

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        resp = await self.reason(messages, trace_id=trace_id)

        try:
            audience_msgs = json.loads(resp.content)
        except (json.JSONDecodeError, TypeError):
            audience_msgs = {
                "first_responder": resp.content,
                "general_public": resp.content,
                "vulnerable": resp.content,
            }

        # Translate general_public message into target languages
        non_english_langs = [lang for lang in target_languages if lang != "english"]
        if non_english_langs:
            translate_prompt = (
                "Translate the following emergency alert into the specified Indian languages. "
                "Output ONLY valid JSON with language codes as keys.\n\n"
                f"Message: {audience_msgs.get('general_public', '')}\n\n"
                f"Languages: {', '.join(non_english_langs)}"
            )
            translate_messages = [
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": translate_prompt},
            ]

            translate_resp = await self.reason(translate_messages, trace_id=trace_id)

            try:
                translations = json.loads(translate_resp.content)
                audience_msgs["translations"] = translations
            except (json.JSONDecodeError, TypeError):
                audience_msgs["translations"] = {}

        # Confidence based on data completeness
        has_shelter = bool(instructions.get("shelter_name"))
        has_summary = bool(alert_info.get("situation_summary"))
        confidence = 0.5 + (0.15 if has_shelter else 0) + (0.15 if has_summary else 0)

        return {
            "audience_messages": audience_msgs,
            "reasoning": resp.content,
            "confidence": confidence,
        }

    async def _format_channels(self, state: CommunityCommsState) -> dict[str, Any]:
        """Format messages for different communication channels."""
        audience_msgs = state.get("audience_messages", {})
        alert_info = state.get("alert_info", {})

        public_msg = audience_msgs.get("general_public", "")
        responder_msg = audience_msgs.get("first_responder", "")
        vulnerable_msg = audience_msgs.get("vulnerable", "")

        disaster_type = alert_info.get("disaster_type", "alert").upper()
        districts = ", ".join(alert_info.get("affected_districts", []))

        # WhatsApp: emoji-rich, bullet points
        whatsapp = (
            f"🚨 *{disaster_type} ALERT* 🚨\n\n"
            f"📍 Affected: {districts}\n\n"
            f"{public_msg}\n\n"
            f"📞 NDRF: {_NDRF_HELPLINE}\n"
            f"📞 State Helpline: {_STATE_HELPLINE}\n\n"
            f"_Source: NDMA/IMD Official_"
        )

        # SMS: 160-char limit
        sms = format_sms(
            f"{disaster_type} ALERT: {districts}. {vulnerable_msg} "
            f"Helpline: {_STATE_HELPLINE}"
        )

        # Social media: hashtag-driven
        state_name = alert_info.get("affected_state", "India")
        social_media = (
            f"⚠️ {disaster_type} ALERT — {districts}, {state_name}\n\n"
            f"{public_msg}\n\n"
            f"NDRF: {_NDRF_HELPLINE} | Helpline: {_STATE_HELPLINE}\n"
            f"#DisasterAlert #{state_name.replace(' ', '')} #NDMA #NDRF"
        )

        # Media briefing: formal, structured
        media_briefing = (
            f"MEDIA BRIEFING — {disaster_type} ALERT\n"
            f"{'=' * 40}\n\n"
            f"Affected Area: {districts}, {state_name}\n"
            f"Severity: {alert_info.get('severity', 'N/A')}/5\n\n"
            f"Situation Summary:\n{alert_info.get('situation_summary', 'N/A')}\n\n"
            f"First Responder Advisory:\n{responder_msg}\n\n"
            f"Public Advisory:\n{public_msg}\n\n"
            f"Contact:\n"
            f"  NDRF Helpline: {_NDRF_HELPLINE}\n"
            f"  State Helpline: {_STATE_HELPLINE}\n\n"
            f"Source: NDMA / IMD Official Bulletin"
        )

        channel_formats = {
            "whatsapp": whatsapp,
            "sms": sms,
            "social_media": social_media,
            "media_briefing": media_briefing,
        }

        logger.info(
            "channels_formatted",
            channels=list(channel_formats.keys()),
            sms_length=len(sms),
            trace_id=state.get("trace_id", ""),
        )

        return {"channel_formats": channel_formats}

    async def _counter_misinfo(self, state: CommunityCommsState) -> dict[str, Any]:
        """Generate counter-messages for known rumors."""
        alert_info = state.get("alert_info", {})
        rumors = alert_info.get("rumors", [])
        trace_id = state.get("trace_id", "")

        if not rumors:
            return {
                "counter_messages": [],
                "artifacts": [{
                    "type": "community_alerts",
                    "channel_formats": state.get("channel_formats", {}),
                    "audience_messages": state.get("audience_messages", {}),
                    "target_languages": state.get("target_languages", []),
                    "counter_messages": [],
                }],
            }

        prompt = (
            "Generate counter-messages for the following rumors about a disaster. "
            "Each counter should cite an official source (IMD, NDMA, CWC). "
            "Output ONLY valid JSON with key 'counters' containing a list of objects "
            "with keys: rumor, counter, source.\n\n"
            f"Disaster: {alert_info.get('disaster_type', '')}, "
            f"Severity: {alert_info.get('severity', '')}/5\n"
            f"Situation: {alert_info.get('situation_summary', '')}\n\n"
            f"Rumors:\n{json.dumps(rumors)}"
        )

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        resp = await self.reason(messages, trace_id=trace_id)

        try:
            result = json.loads(resp.content)
            counters = result.get("counters", [])
        except (json.JSONDecodeError, TypeError):
            counters = []

        logger.info(
            "misinfo_countered",
            rumor_count=len(rumors),
            counter_count=len(counters),
            trace_id=trace_id,
        )

        return {
            "counter_messages": counters,
            "artifacts": [{
                "type": "community_alerts",
                "channel_formats": state.get("channel_formats", {}),
                "audience_messages": state.get("audience_messages", {}),
                "target_languages": state.get("target_languages", []),
                "counter_messages": counters,
            }],
        }


__all__ = [
    "CommunityComms",
    "CommunityCommsState",
    "STATE_LANGUAGES",
    "format_sms",
]
