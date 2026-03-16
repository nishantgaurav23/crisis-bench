"""Agent status endpoints."""

from typing import Any

from fastapi import APIRouter

from src.shared.errors import CrisisValidationError
from src.shared.models import AgentCard, AgentType, LLMTier

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

# In-memory decision store — keyed by agent_type
_agent_decisions: dict[str, list[dict[str, Any]]] = {}

# Static agent registry — will be replaced by live agent status in later specs
_AGENT_CARDS: dict[str, AgentCard] = {
    AgentType.ORCHESTRATOR: AgentCard(
        agent_id="orchestrator-01",
        agent_type=AgentType.ORCHESTRATOR,
        name="Orchestrator",
        description="Mission decomposition, agent activation, synthesis",
        capabilities=["task_decomposition", "agent_routing", "synthesis"],
        llm_tier=LLMTier.CRITICAL,
    ),
    AgentType.SITUATION_SENSE: AgentCard(
        agent_id="situation-sense-01",
        agent_type=AgentType.SITUATION_SENSE,
        name="SituationSense",
        description="Multi-source data fusion and situational awareness",
        capabilities=["data_fusion", "urgency_scoring", "misinformation_detection"],
        llm_tier=LLMTier.ROUTINE,
    ),
    AgentType.PREDICTIVE_RISK: AgentCard(
        agent_id="predictive-risk-01",
        agent_type=AgentType.PREDICTIVE_RISK,
        name="PredictiveRisk",
        description="Forecasting and cascading failure analysis",
        capabilities=["forecasting", "risk_mapping", "historical_analogies"],
        llm_tier=LLMTier.STANDARD,
    ),
    AgentType.RESOURCE_ALLOCATION: AgentCard(
        agent_id="resource-allocation-01",
        agent_type=AgentType.RESOURCE_ALLOCATION,
        name="ResourceAllocation",
        description="Constrained optimization for NDRF/SDRF deployment",
        capabilities=["optimization", "shelter_matching", "supply_routing"],
        llm_tier=LLMTier.STANDARD,
    ),
    AgentType.COMMUNITY_COMMS: AgentCard(
        agent_id="community-comms-01",
        agent_type=AgentType.COMMUNITY_COMMS,
        name="CommunityComms",
        description="Multilingual emergency alerts and communication",
        capabilities=["translation", "alert_generation", "misinformation_countering"],
        llm_tier=LLMTier.ROUTINE,
    ),
    AgentType.INFRA_STATUS: AgentCard(
        agent_id="infra-status-01",
        agent_type=AgentType.INFRA_STATUS,
        name="InfraStatus",
        description="Infrastructure tracking and cascading failure prediction",
        capabilities=["infra_tracking", "dependency_analysis", "restoration_timeline"],
        llm_tier=LLMTier.ROUTINE,
    ),
    AgentType.HISTORICAL_MEMORY: AgentCard(
        agent_id="historical-memory-01",
        agent_type=AgentType.HISTORICAL_MEMORY,
        name="HistoricalMemory",
        description="RAG over NDMA docs and historical disaster retrieval",
        capabilities=["rag_retrieval", "historical_search", "knowledge_ingestion"],
        llm_tier=LLMTier.STANDARD,
    ),
}


@router.get("", response_model=list[AgentCard])
async def list_agents():
    """List all 7 agent cards."""
    return list(_AGENT_CARDS.values())


@router.get("/{agent_type}", response_model=AgentCard)
async def get_agent(agent_type: str):
    """Get a single agent card by type."""
    card = _AGENT_CARDS.get(agent_type)
    if card is None:
        raise CrisisValidationError(
            f"Agent type '{agent_type}' not found",
            context={"agent_type": agent_type},
        )
    return card


@router.get("/{agent_type}/decisions")
async def list_agent_decisions(agent_type: str) -> list[dict[str, Any]]:
    """List recent decisions from a specific agent."""
    if agent_type not in _AGENT_CARDS:
        raise CrisisValidationError(
            f"Agent type '{agent_type}' not found",
            context={"agent_type": agent_type},
        )
    return _agent_decisions.get(agent_type, [])
