"""SituationSense agent — multi-source data fusion + urgency scoring (S7.3).

Fuses IMD weather warnings, SACHET CAP alerts, and social media data into
a unified situational picture with urgency scoring aligned to IMD color codes.

Runs on the **routine** tier (Qwen Flash, $0.04/M tokens) for text analysis.

LangGraph nodes:
    ingest_data -> fuse_sources -> score_urgency -> detect_misinfo -> produce_sitrep

Usage::

    agent = SituationSense()
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

logger = get_logger("agent.situation_sense")

# =============================================================================
# Urgency Mapping
# =============================================================================

_IMD_COLOR_SCORES: dict[str, int] = {
    "green": 1,
    "yellow": 2,
    "orange": 3,
    "red": 4,
}

_SACHET_SEVERITY_SCORES: dict[str, int] = {
    "minor": 1,
    "moderate": 2,
    "severe": 3,
    "extreme": 4,
    "unknown": 1,
}


def map_urgency(
    *,
    imd_color: str = "",
    sachet_severity: str = "",
    sachet_urgency: str = "",
) -> int:
    """Map IMD color code + SACHET severity to urgency score 1-5.

    Rules:
        - Base score from IMD color code (green=1, yellow=2, orange=3, red=4)
        - SACHET severity can upgrade the score
        - Red + Extreme + Immediate = 5
        - Unknown/missing defaults to 1
    """
    imd_score = _IMD_COLOR_SCORES.get(imd_color.lower().strip(), 0)
    sachet_score = _SACHET_SEVERITY_SCORES.get(sachet_severity.lower().strip(), 0)

    base = max(imd_score, sachet_score)
    if base == 0:
        return 1

    # Escalate to 5 if both IMD Red and SACHET Extreme + Immediate
    if (
        imd_color.lower().strip() == "red"
        and sachet_severity.lower().strip() == "extreme"
        and sachet_urgency.lower().strip() == "immediate"
    ):
        return 5

    return base


# =============================================================================
# Situation State
# =============================================================================


class SituationState(AgentState):
    """Extended state for SituationSense agent."""

    imd_data: list[dict]
    sachet_alerts: list[dict]
    social_media: list[dict]
    fused_picture: dict
    urgency_score: int
    imd_color: str
    misinfo_flags: list[dict]
    geojson: dict


# =============================================================================
# SituationSense Agent
# =============================================================================


class SituationSense(BaseAgent):
    """Multi-source data fusion agent for situational awareness.

    Fuses IMD weather warnings, SACHET CAP alerts, and social media
    into a GeoJSON situation report with urgency scoring.
    """

    def __init__(self, *, settings=None) -> None:
        from src.shared.config import get_settings

        super().__init__(
            agent_id="situation_sense",
            agent_type=AgentType.SITUATION_SENSE,
            llm_tier=LLMTier.ROUTINE,
            settings=settings or get_settings(),
        )

    def get_system_prompt(self) -> str:
        return (
            "You are the SituationSense agent for India's CRISIS-BENCH disaster "
            "response system. Your role is to fuse multi-source data into a unified "
            "situational picture.\n\n"
            "Data sources you analyze:\n"
            "- IMD (India Meteorological Department) district warnings with color codes "
            "(Green/Yellow/Orange/Red)\n"
            "- NDMA SACHET CAP alerts from 7 national agencies + 36 state authorities\n"
            "- Social media posts (Hindi/English/regional languages)\n"
            "- Satellite imagery analysis results\n\n"
            "Your outputs:\n"
            "1. Fused situational picture merging all sources\n"
            "2. Urgency score (1-5) aligned with IMD warning levels\n"
            "3. Misinformation flags for contradictory or suspicious reports\n"
            "4. GeoJSON situation report with affected areas\n\n"
            "Always prioritize official sources (IMD, NDMA, CWC) over social media. "
            "Flag any contradictions between official and unofficial sources. "
            "Output structured JSON when asked."
        )

    def get_agent_card(self) -> A2AAgentCard:
        return A2AAgentCard(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            name="SituationSense",
            description=(
                "Multi-source data fusion agent: IMD weather, SACHET alerts, "
                "social media, satellite imagery → unified situation report"
            ),
            capabilities=[
                "multi_source_data_fusion",
                "urgency_scoring",
                "misinformation_detection",
                "geojson_situation_reports",
                "imd_color_code_mapping",
            ],
            llm_tier=self.llm_tier,
        )

    def build_graph(self) -> StateGraph:
        graph = StateGraph(SituationState)

        graph.add_node("ingest_data", self._ingest_data)
        graph.add_node("fuse_sources", self._fuse_sources)
        graph.add_node("score_urgency", self._score_urgency)
        graph.add_node("detect_misinfo", self._detect_misinfo)
        graph.add_node("produce_sitrep", self._produce_sitrep)

        graph.set_entry_point("ingest_data")
        graph.add_edge("ingest_data", "fuse_sources")
        graph.add_edge("fuse_sources", "score_urgency")
        graph.add_edge("score_urgency", "detect_misinfo")
        graph.add_edge("detect_misinfo", "produce_sitrep")
        graph.add_edge("produce_sitrep", END)

        return graph

    # -----------------------------------------------------------------
    # Graph Nodes
    # -----------------------------------------------------------------

    async def _ingest_data(self, state: SituationState) -> dict[str, Any]:
        """Extract IMD + SACHET + social media data from task payload."""
        task = state.get("task", {})
        imd_data = task.get("imd_data", [])
        sachet_alerts = task.get("sachet_alerts", [])
        social_media = task.get("social_media", [])

        # Determine highest IMD color code from warnings
        imd_color = self._extract_highest_imd_color(imd_data)

        source_count = sum([
            1 if imd_data else 0,
            1 if sachet_alerts else 0,
            1 if social_media else 0,
        ])

        logger.info(
            "data_ingested",
            imd_count=len(imd_data),
            sachet_count=len(sachet_alerts),
            social_count=len(social_media),
            imd_color=imd_color,
            trace_id=state.get("trace_id", ""),
        )

        return {
            "imd_data": imd_data,
            "sachet_alerts": sachet_alerts,
            "social_media": social_media,
            "imd_color": imd_color,
            "metadata": {**state.get("metadata", {}), "source_count": source_count},
        }

    async def _fuse_sources(self, state: SituationState) -> dict[str, Any]:
        """Use LLM to merge multiple data streams into coherent picture."""
        imd_data = state.get("imd_data", [])
        sachet_alerts = state.get("sachet_alerts", [])
        social_media = state.get("social_media", [])

        if not imd_data and not sachet_alerts and not social_media:
            return {
                "fused_picture": {"summary": "No data available", "sources": []},
                "reasoning": "No data sources provided for fusion",
                "confidence": 0.2,
            }

        prompt = (
            "Fuse the following disaster data sources into a unified situational picture. "
            "Output ONLY valid JSON with keys: summary, affected_areas, severity, sources.\n\n"
            f"IMD Warnings: {json.dumps(imd_data[:5])}\n\n"
            f"SACHET Alerts: {json.dumps(sachet_alerts[:5])}\n\n"
            f"Social Media: {json.dumps(social_media[:10])}\n"
        )

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        resp = await self.reason(messages, trace_id=state.get("trace_id", ""))

        try:
            fused = json.loads(resp.content)
        except (json.JSONDecodeError, TypeError):
            fused = {"summary": resp.content, "sources": ["llm_raw"]}

        # Confidence based on number of data sources
        source_count = state.get("metadata", {}).get("source_count", 0)
        confidence = min(0.9, 0.3 + source_count * 0.2)

        return {
            "fused_picture": fused,
            "reasoning": resp.content,
            "confidence": confidence,
        }

    async def _score_urgency(self, state: SituationState) -> dict[str, Any]:
        """Assign urgency score from IMD color + SACHET severity."""
        imd_color = state.get("imd_color", "")
        sachet_alerts = state.get("sachet_alerts", [])

        # Get highest SACHET severity and urgency
        sachet_severity = ""
        sachet_urgency = ""
        for alert in sachet_alerts:
            sev = alert.get("severity", "")
            urg = alert.get("urgency", "")
            if sev:
                s_score = _SACHET_SEVERITY_SCORES.get(sev.lower(), 0)
                cur_score = _SACHET_SEVERITY_SCORES.get(sachet_severity.lower(), 0)
                if s_score > cur_score:
                    sachet_severity = sev
                    sachet_urgency = urg

        urgency = map_urgency(
            imd_color=imd_color,
            sachet_severity=sachet_severity,
            sachet_urgency=sachet_urgency,
        )

        logger.info(
            "urgency_scored",
            imd_color=imd_color,
            sachet_severity=sachet_severity,
            urgency_score=urgency,
            trace_id=state.get("trace_id", ""),
        )

        return {"urgency_score": urgency}

    async def _detect_misinfo(self, state: SituationState) -> dict[str, Any]:
        """Use LLM to detect misinformation and contradictions."""
        fused = state.get("fused_picture", {})
        social_media = state.get("social_media", [])

        if not social_media:
            return {"misinfo_flags": []}

        prompt = (
            "Analyze the following social media posts against the official situation data. "
            "Identify any misinformation, contradictions, or suspicious claims. "
            "Output ONLY valid JSON with key 'flags' containing a list of objects "
            "with keys: claim, source, reason, severity.\n\n"
            f"Official situation: {json.dumps(fused)}\n\n"
            f"Social media posts: {json.dumps(social_media[:10])}\n"
        )

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        resp = await self.reason(messages, trace_id=state.get("trace_id", ""))

        try:
            result = json.loads(resp.content)
            flags = result.get("flags", [])
        except (json.JSONDecodeError, TypeError):
            flags = []

        return {"misinfo_flags": flags}

    async def _produce_sitrep(self, state: SituationState) -> dict[str, Any]:
        """Generate GeoJSON situation report."""
        fused = state.get("fused_picture", {})
        urgency = state.get("urgency_score", 1)
        imd_data = state.get("imd_data", [])
        sachet_alerts = state.get("sachet_alerts", [])
        misinfo_flags = state.get("misinfo_flags", [])

        if not fused.get("summary") or fused.get("summary") == "No data available":
            return {
                "geojson": {},
                "artifacts": [{
                    "type": "situation_report",
                    "urgency": urgency,
                    "data": fused,
                }],
            }

        prompt = (
            "Generate a GeoJSON FeatureCollection for the current disaster situation. "
            "Each Feature should represent an affected area with properties including "
            "name, urgency, warning type, and source. "
            "Output ONLY valid GeoJSON.\n\n"
            f"Situation: {json.dumps(fused)}\n"
            f"Urgency: {urgency}\n"
            f"IMD Data: {json.dumps(imd_data[:3])}\n"
            f"SACHET Alerts: {json.dumps(sachet_alerts[:3])}\n"
        )

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        resp = await self.reason(messages, trace_id=state.get("trace_id", ""))

        try:
            geojson = json.loads(resp.content)
        except (json.JSONDecodeError, TypeError):
            geojson = {
                "type": "FeatureCollection",
                "features": [],
            }

        return {
            "geojson": geojson,
            "artifacts": [{
                "type": "situation_report",
                "urgency": urgency,
                "geojson": geojson,
                "misinfo_flags": misinfo_flags,
                "data": fused,
            }],
        }

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    @staticmethod
    def _extract_highest_imd_color(imd_data: list[dict]) -> str:
        """Extract the highest IMD warning color code from a list of warnings."""
        priority = {"red": 4, "orange": 3, "yellow": 2, "green": 1}
        highest = ""
        highest_score = 0
        for item in imd_data:
            color = item.get("color_code", "").lower().strip()
            score = priority.get(color, 0)
            if score > highest_score:
                highest = color
                highest_score = score
        return highest


__all__ = ["SituationSense", "SituationState", "map_urgency"]
