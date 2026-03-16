"""OrchestratorAgent — Master coordinator for CRISIS-BENCH multi-agent system.

Receives high-level disaster missions, decomposes into sub-tasks via LLM,
delegates to specialist agents via A2A, collects results with timeout,
synthesizes bilingual briefings, and manages per-scenario LLM budget.

Uses CRITICAL tier (DeepSeek Reasoner) for decomposition and synthesis.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from langgraph.graph import END, StateGraph

from src.agents.base import AgentState, BaseAgent
from src.protocols.a2a.schemas import (
    A2AAgentCard,
    A2ATask,
    A2ATaskResult,
)
from src.routing.llm_router import LLMTier
from src.shared.config import CrisisSettings
from src.shared.models import AgentType, DisasterPhase, TaskStatus
from src.shared.telemetry import get_logger

logger = get_logger("agent.orchestrator")

# =============================================================================
# Phase-to-Agent mapping
# =============================================================================

PHASE_AGENT_MAP: dict[DisasterPhase, list[AgentType]] = {
    DisasterPhase.PRE_EVENT: [
        AgentType.SITUATION_SENSE,
        AgentType.PREDICTIVE_RISK,
        AgentType.HISTORICAL_MEMORY,
    ],
    DisasterPhase.ACTIVE_RESPONSE: [
        AgentType.SITUATION_SENSE,
        AgentType.PREDICTIVE_RISK,
        AgentType.RESOURCE_ALLOCATION,
        AgentType.COMMUNITY_COMMS,
        AgentType.INFRA_STATUS,
        AgentType.HISTORICAL_MEMORY,
    ],
    DisasterPhase.RECOVERY: [
        AgentType.RESOURCE_ALLOCATION,
        AgentType.COMMUNITY_COMMS,
        AgentType.INFRA_STATUS,
        AgentType.HISTORICAL_MEMORY,
    ],
    DisasterPhase.POST_EVENT: [
        AgentType.HISTORICAL_MEMORY,
    ],
}

# Map agent type enum values to agent IDs used in A2A
_AGENT_TYPE_TO_ID: dict[str, str] = {
    AgentType.SITUATION_SENSE.value: "situation_sense",
    AgentType.PREDICTIVE_RISK.value: "predictive_risk",
    AgentType.RESOURCE_ALLOCATION.value: "resource_allocation",
    AgentType.COMMUNITY_COMMS.value: "community_comms",
    AgentType.INFRA_STATUS.value: "infra_status",
    AgentType.HISTORICAL_MEMORY.value: "historical_memory",
}

# Confidence threshold for escalation
ESCALATION_THRESHOLD = 0.7


# =============================================================================
# Orchestrator State (extends AgentState)
# =============================================================================


class OrchestratorState(AgentState, total=False):
    """Extended state for orchestrator graph."""

    sub_tasks: list[dict]
    pending_task_ids: list[str]
    agent_results: dict[str, dict]
    budget_used: float
    budget_exceeded: bool
    needs_escalation: bool
    phase: str
    mission: dict


# =============================================================================
# OrchestratorAgent
# =============================================================================


class OrchestratorAgent(BaseAgent):
    """Master coordinator agent for disaster response.

    Decomposes missions, delegates to specialist agents, collects results,
    synthesizes briefings, and manages LLM budget.
    """

    def __init__(self, settings: CrisisSettings | None = None) -> None:
        super().__init__(
            agent_id="orchestrator",
            agent_type=AgentType.ORCHESTRATOR,
            llm_tier=LLMTier.CRITICAL,
            settings=settings,
        )
        self._budget_used: float = 0.0

    # -----------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------

    @property
    def budget_used(self) -> float:
        return self._budget_used

    @property
    def budget_limit(self) -> float:
        return self._settings.BUDGET_LIMIT_PER_SCENARIO

    # -----------------------------------------------------------------
    # Budget management
    # -----------------------------------------------------------------

    def track_cost(self, cost_usd: float) -> None:
        """Add cost to the running total for the current scenario."""
        self._budget_used += cost_usd

    def is_budget_exceeded(self) -> bool:
        """Check if the per-scenario budget ceiling has been reached."""
        return self._budget_used >= self._settings.BUDGET_LIMIT_PER_SCENARIO

    def reset_budget(self) -> None:
        """Reset budget tracking for a new scenario."""
        self._budget_used = 0.0

    # -----------------------------------------------------------------
    # Phase-based agent activation
    # -----------------------------------------------------------------

    def get_active_agents(self, phase: DisasterPhase) -> list[AgentType]:
        """Return agent types that should be active for the given disaster phase."""
        return PHASE_AGENT_MAP.get(phase, PHASE_AGENT_MAP[DisasterPhase.ACTIVE_RESPONSE])

    # -----------------------------------------------------------------
    # Mission decomposition
    # -----------------------------------------------------------------

    async def decompose_mission(
        self,
        mission: dict[str, Any],
        *,
        phase: DisasterPhase,
        trace_id: str,
    ) -> list[dict[str, Any]]:
        """Use LLM to decompose a mission into sub-tasks for specialist agents.

        Returns a list of sub-task dicts with keys:
        target_agent, task_type, priority, payload.
        Filters out sub-tasks targeting agents not active for the current phase.
        """
        active_agents = self.get_active_agents(phase)
        active_ids = {_AGENT_TYPE_TO_ID.get(a.value, a.value) for a in active_agents}

        prompt = (
            "You are the Orchestrator for a disaster response system. "
            "Decompose the following disaster mission into sub-tasks for specialist agents.\n\n"
            f"Mission: {json.dumps(mission)}\n\n"
            f"Available agents: {list(active_ids)}\n\n"
            "Respond with JSON: {\"sub_tasks\": [{\"target_agent\": str, "
            "\"task_type\": str, \"priority\": int (1=highest), \"payload\": dict}]}"
        )

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        response = await self.reason(messages, trace_id=trace_id)
        self.track_cost(response.cost_usd)

        try:
            parsed = json.loads(response.content)
            sub_tasks = parsed.get("sub_tasks", [])
        except (json.JSONDecodeError, KeyError):
            logger.error("decompose_parse_failed", trace_id=trace_id)
            return []

        # Filter by active agents
        filtered = [t for t in sub_tasks if t.get("target_agent") in active_ids]
        return filtered

    # -----------------------------------------------------------------
    # Task delegation
    # -----------------------------------------------------------------

    async def delegate_tasks(
        self,
        sub_tasks: list[dict[str, Any]],
        *,
        disaster_id: uuid.UUID | None = None,
        parent_depth: int = 0,
        trace_id: str,
    ) -> list[uuid.UUID]:
        """Send sub-tasks to specialist agents via A2A. Returns list of task IDs."""
        task_ids: list[uuid.UUID] = []

        for sub in sub_tasks:
            task = A2ATask(
                source_agent=self.agent_id,
                target_agent=sub["target_agent"],
                disaster_id=disaster_id,
                task_type=sub["task_type"],
                priority=sub.get("priority", 3),
                payload=sub.get("payload", {}),
                depth=parent_depth + 1,
                trace_id=trace_id,
            )
            await self._a2a_server.send_task(task)
            task_ids.append(task.id)

        logger.info(
            "tasks_delegated",
            count=len(task_ids),
            trace_id=trace_id,
        )
        return task_ids

    # -----------------------------------------------------------------
    # Result collection
    # -----------------------------------------------------------------

    async def collect_results(
        self,
        task_ids: list[uuid.UUID],
        *,
        results: dict[uuid.UUID, A2ATaskResult],
        timeout: float,
    ) -> dict[uuid.UUID, A2ATaskResult]:
        """Collect results for delegated tasks, marking missing ones as failed on timeout.

        Args:
            task_ids: List of expected task IDs.
            results: Pre-populated results dict (from A2A callbacks or direct injection).
            timeout: Maximum seconds to wait for outstanding results.

        Returns:
            Dict mapping task_id → A2ATaskResult for all tasks.
        """
        if not task_ids:
            return {}

        collected: dict[uuid.UUID, A2ATaskResult] = {}

        # Copy already-available results
        for tid in task_ids:
            if tid in results:
                collected[tid] = results[tid]

        # Wait for remaining results
        if len(collected) < len(task_ids):
            remaining = [tid for tid in task_ids if tid not in collected]
            try:
                await asyncio.wait_for(
                    self._wait_for_results(remaining, results, collected),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                # Mark timed-out tasks as failed
                for tid in remaining:
                    if tid not in collected:
                        collected[tid] = A2ATaskResult(
                            task_id=tid,
                            agent_id="unknown",
                            status=TaskStatus.FAILED,
                            error_message=f"Timed out after {timeout}s",
                            trace_id=uuid.uuid4().hex[:8],
                        )
                        logger.warning(
                            "task_timeout",
                            task_id=str(tid),
                            timeout_s=timeout,
                        )

        return collected

    async def _wait_for_results(
        self,
        remaining: list[uuid.UUID],
        results: dict[uuid.UUID, A2ATaskResult],
        collected: dict[uuid.UUID, A2ATaskResult],
    ) -> None:
        """Poll for remaining results until all are collected."""
        while remaining:
            await asyncio.sleep(0.01)
            for tid in list(remaining):
                if tid in results:
                    collected[tid] = results[tid]
                    remaining.remove(tid)

    # -----------------------------------------------------------------
    # Synthesis
    # -----------------------------------------------------------------

    async def synthesize_results(
        self,
        agent_results: dict[uuid.UUID, A2ATaskResult],
        *,
        mission: dict[str, Any],
        trace_id: str,
    ) -> dict[str, Any]:
        """Synthesize agent results into a structured briefing.

        Returns a dict with situation_summary, risk_assessment, resource_plan,
        communication_directives, confidence, and needs_escalation.
        """
        # Calculate aggregate confidence from agent results
        confidences = [
            r.confidence for r in agent_results.values()
            if r.confidence is not None and r.status == TaskStatus.COMPLETED
        ]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Build synthesis prompt
        results_summary = []
        for tid, result in agent_results.items():
            results_summary.append({
                "agent": result.agent_id,
                "status": result.status.value,
                "confidence": result.confidence,
            })

        prompt = (
            "Synthesize the following agent results into a disaster response briefing.\n\n"
            f"Mission: {json.dumps(mission)}\n\n"
            f"Agent Results: {json.dumps(results_summary)}\n\n"
            "Respond with JSON: {\"situation_summary\": str, \"risk_assessment\": str, "
            "\"resource_plan\": str, \"communication_directives\": str, "
            f"\"confidence\": float (agent avg: {avg_confidence:.2f})}}"
        )

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        response = await self.reason(messages, trace_id=trace_id)
        self.track_cost(response.cost_usd)

        try:
            briefing = json.loads(response.content)
        except (json.JSONDecodeError, KeyError):
            logger.error("synthesis_parse_failed", trace_id=trace_id)
            briefing = {
                "error": "Failed to parse synthesis response",
                "situation_summary": "Synthesis failed — raw results available",
                "confidence": avg_confidence,
            }

        # Confidence-gated escalation
        final_confidence = briefing.get("confidence", avg_confidence)
        if isinstance(final_confidence, str):
            try:
                final_confidence = float(final_confidence)
            except ValueError:
                final_confidence = avg_confidence

        needs_escalation = final_confidence < ESCALATION_THRESHOLD
        briefing["needs_escalation"] = needs_escalation
        briefing["confidence"] = final_confidence

        if needs_escalation:
            logger.warning(
                "escalation_needed",
                confidence=final_confidence,
                threshold=ESCALATION_THRESHOLD,
                trace_id=trace_id,
            )

        return briefing

    # -----------------------------------------------------------------
    # Health check (extends BaseAgent.health)
    # -----------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """Return health check including budget info."""
        base = super().health()
        base["budget_used_usd"] = round(self._budget_used, 6)
        base["budget_limit_usd"] = self.budget_limit
        base["budget_exceeded"] = self.is_budget_exceeded()
        return base

    # -----------------------------------------------------------------
    # Abstract method implementations
    # -----------------------------------------------------------------

    def get_system_prompt(self) -> str:
        return (
            "You are the Orchestrator for CRISIS-BENCH, an India-specific multi-agent "
            "disaster response coordination system. Your role is to:\n"
            "1. Decompose disaster missions into sub-tasks for specialist agents\n"
            "2. Coordinate situation assessment, risk prediction, resource allocation, "
            "communication, infrastructure tracking, and historical analysis\n"
            "3. Synthesize agent outputs into actionable bilingual briefings\n"
            "4. Manage response priorities based on disaster phase and severity\n\n"
            "Always respond with valid JSON when asked. Be concise and actionable.\n\n"
            "NDMA Standard Operating Procedures:\n"
            "Follow NDMA's National Disaster Management Plan (NDMP) 2019 coordination "
            "structure: NCMC (National Crisis Management Committee) → NDMA → State SDMA → "
            "District DDMA → Block/Taluka. Activate IRS (Incident Response System) with "
            "clear IC (Incident Commander) designation. Budget tracking: average NDRF "
            "deployment costs Rs 2-5 crore per battalion per week. Mission phases: "
            "Warning → Evacuation → Search & Rescue → Relief → Early Recovery. Ensure "
            "all 7 specialist agents are activated within 15 minutes of alert."
        )

    def get_agent_card(self) -> A2AAgentCard:
        return A2AAgentCard(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            name="Orchestrator",
            description="Master coordinator for multi-agent disaster response",
            capabilities=[
                "decomposition",
                "orchestration",
                "synthesis",
                "budget_management",
                "escalation",
            ],
            llm_tier=self.llm_tier,
        )

    def build_graph(self) -> StateGraph:
        """Build the orchestrator LangGraph state machine.

        Flow: parse_mission → decompose → delegate → collect → synthesize
        """
        graph = StateGraph(OrchestratorState)

        async def parse_mission(state: OrchestratorState) -> dict[str, Any]:
            """Extract disaster info from the task payload."""
            task = state.get("task", {})
            phase_str = task.get("phase", "active_response")
            # Validate phase string (fallback to active_response)
            try:
                DisasterPhase(phase_str)
            except ValueError:
                phase_str = DisasterPhase.ACTIVE_RESPONSE.value

            return {
                "phase": phase_str,
                "mission": task,
                "metadata": {**state.get("metadata", {}), "phase": phase_str},
            }

        async def decompose(state: OrchestratorState) -> dict[str, Any]:
            """Decompose mission into sub-tasks via LLM."""
            mission = state.get("mission", state.get("task", {}))
            phase_str = state.get("phase", "active_response")
            trace_id = state.get("trace_id", "")

            try:
                phase = DisasterPhase(phase_str)
            except ValueError:
                phase = DisasterPhase.ACTIVE_RESPONSE

            sub_tasks = await self.decompose_mission(
                mission, phase=phase, trace_id=trace_id
            )
            return {"sub_tasks": sub_tasks}

        async def delegate(state: OrchestratorState) -> dict[str, Any]:
            """Send sub-tasks to specialist agents."""
            sub_tasks = state.get("sub_tasks", [])
            trace_id = state.get("trace_id", "")
            disaster_id_str = state.get("disaster_id")
            disaster_id = uuid.UUID(disaster_id_str) if disaster_id_str else None

            task_ids = await self.delegate_tasks(
                sub_tasks,
                disaster_id=disaster_id,
                parent_depth=state.get("iteration", 0),
                trace_id=trace_id,
            )
            return {
                "pending_task_ids": [str(tid) for tid in task_ids],
            }

        async def collect(state: OrchestratorState) -> dict[str, Any]:
            """Collect results from specialist agents."""
            pending_ids = state.get("pending_task_ids", [])
            task_ids = [uuid.UUID(tid) for tid in pending_ids]
            timeout = float(self._settings.AGENT_TIMEOUT_SECONDS)

            # In a real system, results come from A2A callbacks.
            # For the graph, we collect with timeout (results dict is empty
            # since real results would arrive asynchronously).
            # Use a short timeout (1s) to avoid blocking the graph.
            collected = await self.collect_results(
                task_ids, results={}, timeout=min(timeout, 1.0)
            )

            agent_results = {}
            for tid, result in collected.items():
                agent_results[str(tid)] = {
                    "agent_id": result.agent_id,
                    "status": result.status.value,
                    "confidence": result.confidence,
                }

            return {"agent_results": agent_results}

        async def synthesize(state: OrchestratorState) -> dict[str, Any]:
            """Synthesize results into a briefing."""
            mission = state.get("mission", state.get("task", {}))
            trace_id = state.get("trace_id", "")
            raw_results = state.get("agent_results", {})

            # Convert back to A2ATaskResult objects for synthesize_results
            result_objs: dict[uuid.UUID, A2ATaskResult] = {}
            for tid_str, info in raw_results.items():
                tid = uuid.UUID(tid_str) if isinstance(tid_str, str) and len(tid_str) == 36 else uuid.uuid4()
                result_objs[tid] = A2ATaskResult(
                    task_id=tid,
                    agent_id=info.get("agent_id", "unknown"),
                    status=TaskStatus(info.get("status", "failed")),
                    confidence=info.get("confidence"),
                    trace_id=trace_id if len(trace_id) == 8 else uuid.uuid4().hex[:8],
                )

            briefing = await self.synthesize_results(
                result_objs, mission=mission, trace_id=trace_id
            )

            return {
                "reasoning": json.dumps(briefing),
                "confidence": briefing.get("confidence", 0.0),
                "artifacts": [briefing],
                "error": None,
            }

        graph.add_node("parse_mission", parse_mission)
        graph.add_node("decompose", decompose)
        graph.add_node("delegate", delegate)
        graph.add_node("collect", collect)
        graph.add_node("synthesize", synthesize)

        graph.set_entry_point("parse_mission")
        graph.add_edge("parse_mission", "decompose")
        graph.add_edge("decompose", "delegate")
        graph.add_edge("delegate", "collect")
        graph.add_edge("collect", "synthesize")
        graph.add_edge("synthesize", END)

        return graph
