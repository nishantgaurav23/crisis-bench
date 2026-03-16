"""InfraStatus agent — infrastructure tracking, cascading failures, restoration (S7.7).

Tracks infrastructure health via Neo4j graph queries, predicts cascading failures,
estimates restoration timelines, and applies NDMA priority restoration framework.

Runs on the **routine** tier (Qwen Flash, $0.04/M tokens).

LangGraph nodes:
    ingest_data -> query_infra_graph -> assess_damage -> predict_cascading
    -> estimate_restoration -> produce_report

Usage::

    agent = InfraStatus()
    await agent.start()
"""

from __future__ import annotations

import json
from typing import Any

from langgraph.graph import END, StateGraph

from src.agents.base import AgentState, BaseAgent
from src.data.ingest.infra_graph import CascadeResult, InfraGraphManager
from src.protocols.a2a.schemas import A2AAgentCard
from src.routing.llm_router import LLMTier
from src.shared.models import AgentType
from src.shared.telemetry import get_logger

logger = get_logger("agent.infra_status")

# =============================================================================
# NDMA Priority Restoration Framework
# =============================================================================

RESTORATION_PRIORITY: dict[str, int] = {
    "Hospital": 1,         # Life-critical
    "WaterTreatment": 2,   # Public health
    "TelecomTower": 3,     # Communication
    "PowerGrid": 4,        # Infrastructure backbone
    "Road": 5,             # Access routes
    "Shelter": 6,          # Temporary housing
}

_DEFAULT_PRIORITY = 99

# =============================================================================
# Restoration Timeline Estimates (hours)
# =============================================================================

_RESTORATION_HOURS: dict[str, dict[str, tuple[float, float]]] = {
    "Hospital": {"minor": (2, 4), "moderate": (8, 12), "severe": (24, 48)},
    "WaterTreatment": {"minor": (4, 8), "moderate": (12, 24), "severe": (48, 72)},
    "TelecomTower": {"minor": (2, 6), "moderate": (8, 16), "severe": (24, 48)},
    "PowerGrid": {"minor": (4, 12), "moderate": (24, 48), "severe": (72, 168)},
    "Road": {"minor": (6, 12), "moderate": (24, 72), "severe": (72, 336)},
    "Shelter": {"minor": (2, 4), "moderate": (6, 12), "severe": (24, 48)},
}

_DEFAULT_RESTORATION = {"minor": (4, 8), "moderate": (12, 24), "severe": (48, 96)}


def estimate_restoration_hours(
    infra_type: str, damage_level: str
) -> tuple[float, float]:
    """Estimate restoration time range (low_hours, high_hours).

    Based on NDRF/SDRF deployment patterns and historical data.
    Unknown types/severities get reasonable defaults.
    """
    type_map = _RESTORATION_HOURS.get(infra_type, _DEFAULT_RESTORATION)
    return type_map.get(damage_level, type_map.get("moderate", (12, 24)))


def get_priority_ordered(nodes: list[dict]) -> list[dict]:
    """Sort infrastructure nodes by NDMA priority framework.

    Hospitals first (1), then water treatment (2), telecom (3),
    power (4), roads (5), shelters (6), unknown last.
    """
    return sorted(
        nodes,
        key=lambda n: RESTORATION_PRIORITY.get(n.get("label", ""), _DEFAULT_PRIORITY),
    )


# =============================================================================
# InfraStatus State
# =============================================================================


class InfraStatusState(AgentState):
    """Extended state for InfraStatus agent."""

    infrastructure_data: list[dict]
    damage_assessment: dict
    cascading_failures: list[dict]
    restoration_plan: list[dict]
    affected_state: str
    affected_districts: list[str]


# =============================================================================
# InfraStatus Agent
# =============================================================================


class InfraStatus(BaseAgent):
    """Infrastructure tracking and cascading failure prediction agent.

    Queries Neo4j infrastructure graph, assesses damage, predicts
    cascading failures, and generates priority-ordered restoration plans
    using the NDMA framework.
    """

    def __init__(self, *, settings=None) -> None:
        from src.shared.config import get_settings

        super().__init__(
            agent_id="infra_status",
            agent_type=AgentType.INFRA_STATUS,
            llm_tier=LLMTier.ROUTINE,
            settings=settings or get_settings(),
        )
        self._infra_graph: InfraGraphManager | None = None

    def _get_infra_graph(self) -> InfraGraphManager:
        if self._infra_graph is None:
            self._infra_graph = InfraGraphManager(settings=self._settings)
        return self._infra_graph

    def get_system_prompt(self) -> str:
        return (
            "You are the InfraStatus agent for India's CRISIS-BENCH disaster "
            "response system. Your role is to track infrastructure health and "
            "predict cascading failures.\n\n"
            "Your capabilities:\n"
            "1. Infrastructure tracking: power grids (state DISCOMs), telecom towers, "
            "water treatment plants, hospitals, roads, railways, shelters\n"
            "2. Cascading failure prediction via Neo4j dependency graph: "
            "power grid failure -> telecom backup exhaustion (4-8h) -> "
            "communication blackout -> water treatment failure\n"
            "3. Restoration timeline estimation based on NDRF/SDRF deployment capacity "
            "and historical patterns\n"
            "4. NDMA priority restoration framework: "
            "hospitals > water treatment > telecom > power > roads\n\n"
            "Data sources:\n"
            "- Neo4j infrastructure dependency graph (5 Indian cities)\n"
            "- OpenStreetMap India infrastructure data\n"
            "- ISRO Bhuvan satellite layers\n"
            "- Historical restoration data from NDRF/SDRF deployments\n\n"
            "Always output structured JSON. Include damage levels (minor/moderate/severe), "
            "estimated restoration hours, and priority ordering per NDMA framework."
        )

    def get_agent_card(self) -> A2AAgentCard:
        return A2AAgentCard(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            name="InfraStatus",
            description=(
                "Infrastructure tracking agent: power/telecom/water/hospital status, "
                "cascading failure prediction, NDMA priority restoration planning"
            ),
            capabilities=[
                "infrastructure_tracking",
                "cascading_failure_prediction",
                "restoration_planning",
                "neo4j_graph_analysis",
                "ndma_priority_framework",
            ],
            llm_tier=self.llm_tier,
        )

    def build_graph(self) -> StateGraph:
        graph = StateGraph(InfraStatusState)

        graph.add_node("ingest_data", self._ingest_data)
        graph.add_node("query_infra_graph", self._query_infra_graph)
        graph.add_node("assess_damage", self._assess_damage)
        graph.add_node("predict_cascading", self._predict_cascading)
        graph.add_node("estimate_restoration", self._estimate_restoration)
        graph.add_node("produce_report", self._produce_report)

        graph.set_entry_point("ingest_data")
        graph.add_edge("ingest_data", "query_infra_graph")
        graph.add_edge("query_infra_graph", "assess_damage")
        graph.add_edge("assess_damage", "predict_cascading")
        graph.add_edge("predict_cascading", "estimate_restoration")
        graph.add_edge("estimate_restoration", "produce_report")
        graph.add_edge("produce_report", END)

        return graph

    # -----------------------------------------------------------------
    # Graph Nodes
    # -----------------------------------------------------------------

    async def _ingest_data(self, state: InfraStatusState) -> dict[str, Any]:
        """Extract affected area, disaster type, and reported damage from task."""
        task = state.get("task", {})
        affected_state = task.get("affected_state", "")
        affected_districts = task.get("affected_districts", [])
        disaster_type = task.get("disaster_type", "unknown")
        reported_damage = task.get("reported_damage", [])

        logger.info(
            "data_ingested",
            affected_state=affected_state,
            districts=affected_districts,
            disaster_type=disaster_type,
            reported_damage_count=len(reported_damage),
            trace_id=state.get("trace_id", ""),
        )

        return {
            "affected_state": affected_state,
            "affected_districts": affected_districts,
            "metadata": {
                **state.get("metadata", {}),
                "disaster_type": disaster_type,
                "reported_damage": reported_damage,
            },
        }

    async def _query_infra_graph(self, state: InfraStatusState) -> dict[str, Any]:
        """Query Neo4j for infrastructure in affected area and simulate failures."""
        affected_state = state.get("affected_state", "")
        metadata = state.get("metadata", {})
        reported_damage = metadata.get("reported_damage", [])

        infra_data: list[dict] = []
        cascade_from_graph: list[CascadeResult] = []

        graph = self._get_infra_graph()
        try:
            # Get all infrastructure in the affected state
            infra_data = await graph.get_infrastructure_by_state(affected_state)

            # Simulate failures for reported damaged nodes
            for dmg in reported_damage:
                node_name = dmg.get("name", "")
                if node_name and affected_state:
                    try:
                        results = await graph.simulate_failure(
                            node_name, affected_state
                        )
                        cascade_from_graph.extend(results)
                    except Exception as exc:
                        logger.warning(
                            "simulate_failure_error",
                            node=node_name,
                            error=str(exc),
                            trace_id=state.get("trace_id", ""),
                        )
        except Exception as exc:
            logger.warning(
                "neo4j_query_failed",
                error=str(exc),
                trace_id=state.get("trace_id", ""),
            )

        # Convert CascadeResult to dicts for state
        cascade_dicts = [
            {
                "affected_node": c.affected_node,
                "affected_label": c.affected_label,
                "impact_type": c.impact_type,
                "path": c.path,
            }
            for c in cascade_from_graph
        ]

        logger.info(
            "infra_graph_queried",
            infra_count=len(infra_data),
            cascade_count=len(cascade_dicts),
            trace_id=state.get("trace_id", ""),
        )

        return {
            "infrastructure_data": infra_data,
            "metadata": {
                **metadata,
                "graph_cascades": cascade_dicts,
            },
        }

    async def _assess_damage(self, state: InfraStatusState) -> dict[str, Any]:
        """LLM-based damage assessment combining graph data with disaster context."""
        infra_data = state.get("infrastructure_data", [])
        metadata = state.get("metadata", {})
        disaster_type = metadata.get("disaster_type", "unknown")
        reported_damage = metadata.get("reported_damage", [])
        graph_cascades = metadata.get("graph_cascades", [])

        prompt = (
            "Assess infrastructure damage for this disaster scenario. "
            "Output ONLY valid JSON with keys: damage_summary (total_nodes, "
            "damaged_nodes, critical_failures list), per_node (list of "
            "{name, label, damage_level: minor|moderate|severe, "
            "operational_capacity_pct: 0-100}).\n\n"
            f"Disaster type: {disaster_type}\n"
            f"Affected state: {state.get('affected_state', '')}\n"
            f"Districts: {state.get('affected_districts', [])}\n"
            f"Infrastructure in area ({len(infra_data)} nodes): "
            f"{json.dumps(infra_data[:10])}\n"
            f"Reported damage: {json.dumps(reported_damage)}\n"
            f"Graph cascade analysis: {json.dumps(graph_cascades[:5])}\n"
        )

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        resp = await self.reason(messages, trace_id=state.get("trace_id", ""))

        try:
            assessment = json.loads(resp.content)
        except (json.JSONDecodeError, TypeError):
            assessment = {
                "damage_summary": {
                    "total_nodes": len(infra_data),
                    "damaged_nodes": len(reported_damage),
                    "critical_failures": [],
                },
                "per_node": [],
            }

        return {"damage_assessment": assessment}

    async def _predict_cascading(self, state: InfraStatusState) -> dict[str, Any]:
        """Predict cascading failure timeline via LLM + graph data."""
        damage = state.get("damage_assessment", {})
        metadata = state.get("metadata", {})
        disaster_type = metadata.get("disaster_type", "unknown")
        graph_cascades = metadata.get("graph_cascades", [])
        infra_data = state.get("infrastructure_data", [])

        prompt = (
            "Predict cascading infrastructure failures with timeline. "
            "Output ONLY valid JSON with key 'cascading_timeline' containing "
            "a list of {time_hours, event, affected (label), probability (0-1)}.\n\n"
            "India-specific cascade patterns:\n"
            "- Cyclone: power grid → telecom backup exhaustion (4-8h) → "
            "communication blackout → water treatment failure\n"
            "- Flood: substation inundation → power loss → telecom failure → "
            "road disruption → hospital access cutoff\n"
            "- Earthquake: structural collapse → gas pipeline rupture → "
            "power grid damage → water main breaks\n\n"
            f"Disaster type: {disaster_type}\n"
            f"Damage assessment: {json.dumps(damage)}\n"
            f"Neo4j cascade analysis: {json.dumps(graph_cascades[:5])}\n"
            f"Infrastructure: {json.dumps(infra_data[:5])}\n"
        )

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        resp = await self.reason(messages, trace_id=state.get("trace_id", ""))

        try:
            result = json.loads(resp.content)
            cascading = result.get("cascading_timeline", [])
        except (json.JSONDecodeError, TypeError):
            cascading = []

        return {"cascading_failures": cascading}

    async def _estimate_restoration(self, state: InfraStatusState) -> dict[str, Any]:
        """Estimate restoration timelines using NDMA priority framework + LLM."""
        damage = state.get("damage_assessment", {})
        cascading = state.get("cascading_failures", [])
        infra_data = state.get("infrastructure_data", [])

        prompt = (
            "Generate a priority-ordered restoration plan following NDMA framework: "
            "hospitals (1) > water treatment (2) > telecom (3) > power (4) > roads (5). "
            "Output ONLY valid JSON with key 'restoration_estimates' containing "
            "a list of {name, label, priority (1-6), estimated_hours, action}.\n\n"
            f"Damage assessment: {json.dumps(damage)}\n"
            f"Cascading failures: {json.dumps(cascading[:5])}\n"
            f"Infrastructure: {json.dumps(infra_data[:10])}\n"
        )

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        resp = await self.reason(messages, trace_id=state.get("trace_id", ""))

        try:
            result = json.loads(resp.content)
            plan = result.get("restoration_estimates", [])
        except (json.JSONDecodeError, TypeError):
            plan = []

        # Ensure priority ordering
        plan.sort(key=lambda p: p.get("priority", _DEFAULT_PRIORITY))

        return {"restoration_plan": plan}

    async def _produce_report(self, state: InfraStatusState) -> dict[str, Any]:
        """Compile final infrastructure status report."""
        damage = state.get("damage_assessment", {})
        cascading = state.get("cascading_failures", [])
        restoration = state.get("restoration_plan", [])
        infra_data = state.get("infrastructure_data", [])

        # Confidence based on data quality
        data_score = 0.0
        if infra_data:
            data_score += 0.3
        if damage.get("per_node"):
            data_score += 0.25
        if cascading:
            data_score += 0.2
        if restoration:
            data_score += 0.15
        if state.get("metadata", {}).get("graph_cascades"):
            data_score += 0.1

        confidence = min(0.95, max(0.1, data_score))

        report = {
            "type": "infrastructure_status_report",
            "affected_state": state.get("affected_state", ""),
            "affected_districts": state.get("affected_districts", []),
            "damage_assessment": damage,
            "cascading_failures": cascading,
            "restoration_plan": restoration,
            "infrastructure_summary": {
                "total_nodes": len(infra_data),
                "damaged_count": damage.get("damage_summary", {}).get(
                    "damaged_nodes", 0
                ),
            },
            "confidence": confidence,
        }

        logger.info(
            "report_produced",
            confidence=round(confidence, 2),
            infra_count=len(infra_data),
            cascade_count=len(cascading),
            restoration_count=len(restoration),
            trace_id=state.get("trace_id", ""),
        )

        return {
            "confidence": confidence,
            "artifacts": [report],
            "reasoning": json.dumps(damage),
        }


__all__ = [
    "InfraStatus",
    "InfraStatusState",
    "RESTORATION_PRIORITY",
    "estimate_restoration_hours",
    "get_priority_ordered",
]
