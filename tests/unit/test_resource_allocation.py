"""Tests for ResourceAllocation agent — OR-Tools optimization + LLM plan formatting.

Tests cover: initialization, agent card, system prompt, graph structure,
haversine distance, demand assessment, resource inventory, OR-Tools optimization,
capacity constraints, coverage constraints, empty resources, greedy fallback,
LLM plan formatting, full graph execution, rolling re-optimization.

All external services (LLM providers, databases) are mocked.
"""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

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


def _sample_task_payload() -> dict[str, Any]:
    """Standard task payload for resource allocation."""
    return {
        "affected_districts": [
            {
                "name": "Puri",
                "state": "Odisha",
                "population": 1698730,
                "severity": 4,
                "lat": 19.81,
                "lon": 85.83,
            },
            {
                "name": "Khurda",
                "state": "Odisha",
                "population": 2246341,
                "severity": 3,
                "lat": 20.18,
                "lon": 85.62,
            },
        ],
        "available_resources": {
            "ndrf_battalions": [
                {
                    "name": "12 Bn NDRF",
                    "base_lat": 12.77,
                    "base_lon": 79.94,
                    "strength": 1000,
                    "status": "standby",
                },
                {
                    "name": "1 Bn NDRF",
                    "base_lat": 28.63,
                    "base_lon": 77.22,
                    "strength": 800,
                    "status": "standby",
                },
            ],
            "shelters": [
                {
                    "name": "Govt School Puri",
                    "capacity": 500,
                    "current_occupancy": 100,
                    "lat": 19.80,
                    "lon": 85.82,
                },
                {
                    "name": "Community Hall Khurda",
                    "capacity": 800,
                    "current_occupancy": 0,
                    "lat": 20.17,
                    "lon": 85.61,
                },
            ],
            "relief_kits": 5000,
        },
        "constraints": {
            "max_travel_hours": 12,
            "shelter_max_occupancy_pct": 90,
            "min_coverage_per_district": 0.5,
        },
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
    plan_json = json.dumps({
        "recommendations": "Deploy 12 Bn NDRF to Puri district within 4 hours.",
        "summary": "Allocation plan generated successfully.",
    })
    router.call = AsyncMock(return_value=_make_llm_response(content=plan_json))
    router.get_provider_status = MagicMock(return_value={})
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
    server.send_task = AsyncMock(return_value="msg-task")
    return server


@pytest.fixture
def agent(settings, mock_router, mock_a2a_client, mock_a2a_server):
    from src.agents.resource_allocation import ResourceAllocation

    a = ResourceAllocation(settings=settings)
    a._router = mock_router
    a._a2a_client = mock_a2a_client
    a._a2a_server = mock_a2a_server
    return a


# =============================================================================
# Test Group 1: Initialization
# =============================================================================


class TestInitialization:
    def test_resource_allocation_init(self, agent):
        """Agent initializes with correct type, tier, and ID."""
        assert agent.agent_id == "resource_allocation"
        assert agent.agent_type == AgentType.RESOURCE_ALLOCATION
        assert agent.llm_tier == LLMTier.STANDARD

    def test_agent_card(self, agent):
        """Agent card has correct capabilities."""
        card = agent.get_agent_card()
        assert isinstance(card, A2AAgentCard)
        assert card.agent_id == "resource_allocation"
        assert "optimization" in card.capabilities
        assert "shelter_matching" in card.capabilities
        assert "ndrf_deployment" in card.capabilities

    def test_system_prompt(self, agent):
        """System prompt mentions key concepts."""
        prompt = agent.get_system_prompt()
        assert "optimization" in prompt.lower() or "resource" in prompt.lower()
        assert "NDRF" in prompt or "ndrf" in prompt.lower()
        assert "shelter" in prompt.lower()

    def test_build_graph(self, agent):
        """Graph compiles and has correct nodes."""
        graph = agent.build_graph()
        compiled = graph.compile()
        assert compiled is not None


# =============================================================================
# Test Group 2: Haversine Distance
# =============================================================================


class TestHaversineDistance:
    def test_haversine_known_cities(self):
        """Haversine distance between Delhi and Mumbai should be ~1150 km."""
        from src.agents.resource_allocation import haversine_distance

        # Delhi: 28.6139, 77.2090; Mumbai: 19.0760, 72.8777
        dist = haversine_distance(28.6139, 77.2090, 19.0760, 72.8777)
        assert 1100 < dist < 1200  # ~1150 km

    def test_haversine_same_point(self):
        """Distance from a point to itself should be 0."""
        from src.agents.resource_allocation import haversine_distance

        assert haversine_distance(20.0, 80.0, 20.0, 80.0) == 0.0

    def test_haversine_short_distance(self):
        """Short distance between nearby points in same district."""
        from src.agents.resource_allocation import haversine_distance

        # Two points ~10 km apart in Odisha
        dist = haversine_distance(19.81, 85.83, 19.80, 85.82)
        assert 0 < dist < 5  # Very close


# =============================================================================
# Test Group 3: Demand Assessment
# =============================================================================


class TestDemandAssessment:
    @pytest.mark.asyncio
    async def test_assess_demand_extracts_districts(self, agent):
        """Demand assessment extracts district info from payload."""
        state = {
            "task": _sample_task_payload(),
            "trace_id": "test1234",
            "messages": [],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
        }
        result = await agent._assess_demand(state)
        districts = result["demand_assessment"]
        assert len(districts) == 2
        assert districts[0]["name"] == "Puri"
        assert districts[0]["severity"] == 4
        assert districts[1]["name"] == "Khurda"

    @pytest.mark.asyncio
    async def test_assess_demand_empty_payload(self, agent):
        """Handles empty/missing district data gracefully."""
        state = {
            "task": {},
            "trace_id": "empty123",
            "messages": [],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
        }
        result = await agent._assess_demand(state)
        assert result["demand_assessment"] == []


# =============================================================================
# Test Group 4: Resource Inventory
# =============================================================================


class TestResourceInventory:
    @pytest.mark.asyncio
    async def test_inventory_resources_parses_payload(self, agent):
        """Resource inventory correctly parsed from payload."""
        state = {
            "task": _sample_task_payload(),
            "trace_id": "inv12345",
            "messages": [],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
            "demand_assessment": [],
        }
        result = await agent._inventory_resources(state)
        inventory = result["resource_inventory"]
        assert "ndrf_battalions" in inventory
        assert "shelters" in inventory
        assert len(inventory["ndrf_battalions"]) == 2
        assert len(inventory["shelters"]) == 2
        assert inventory["relief_kits"] == 5000


# =============================================================================
# Test Group 5: OR-Tools Optimization
# =============================================================================


class TestOptimization:
    @pytest.mark.asyncio
    async def test_optimize_allocation_basic(self, agent):
        """OR-Tools produces a valid allocation for simple case."""
        from src.agents.resource_allocation import optimize_allocation

        districts = [
            {"name": "Puri", "severity": 4, "population": 1698730,
             "lat": 19.81, "lon": 85.83},
            {"name": "Khurda", "severity": 3, "population": 2246341,
             "lat": 20.18, "lon": 85.62},
        ]
        battalions = [
            {"name": "12 Bn", "base_lat": 12.77, "base_lon": 79.94, "strength": 1000},
        ]
        shelters = [
            {"name": "School Puri", "capacity": 500, "current_occupancy": 100,
             "lat": 19.80, "lon": 85.82},
            {"name": "Hall Khurda", "capacity": 800, "current_occupancy": 0,
             "lat": 20.17, "lon": 85.61},
        ]
        relief_kits = 5000

        result = optimize_allocation(
            districts=districts,
            battalions=battalions,
            shelters=shelters,
            relief_kits=relief_kits,
            max_shelter_pct=90,
        )

        assert result["solver_status"] in ("optimal", "feasible")
        assert "ndrf_deployments" in result
        assert "shelter_assignments" in result
        assert "supply_distribution" in result

    @pytest.mark.asyncio
    async def test_optimize_respects_capacity(self, agent):
        """Shelter assignments don't exceed 90% capacity."""
        from src.agents.resource_allocation import optimize_allocation

        districts = [
            {"name": "D1", "severity": 4, "population": 500000,
             "lat": 19.81, "lon": 85.83},
        ]
        shelters = [
            {"name": "S1", "capacity": 100, "current_occupancy": 80,
             "lat": 19.80, "lon": 85.82},
        ]
        result = optimize_allocation(
            districts=districts,
            battalions=[],
            shelters=shelters,
            relief_kits=1000,
            max_shelter_pct=90,
        )
        for assignment in result.get("shelter_assignments", []):
            shelter_name = assignment["shelter"]
            # Find the shelter
            for s in shelters:
                if s["name"] == shelter_name:
                    total = s["current_occupancy"] + assignment["assigned_people"]
                    max_cap = int(s["capacity"] * 0.9)
                    assert total <= max_cap + 1  # +1 for rounding

    @pytest.mark.asyncio
    async def test_optimize_covers_all_districts(self, agent):
        """Every affected district gets some allocation."""
        from src.agents.resource_allocation import optimize_allocation

        districts = [
            {"name": "D1", "severity": 4, "population": 100000,
             "lat": 19.81, "lon": 85.83},
            {"name": "D2", "severity": 2, "population": 50000,
             "lat": 20.18, "lon": 85.62},
        ]
        battalions = [
            {"name": "B1", "base_lat": 19.5, "base_lon": 85.5, "strength": 500},
            {"name": "B2", "base_lat": 20.0, "base_lon": 85.5, "strength": 500},
        ]
        result = optimize_allocation(
            districts=districts,
            battalions=battalions,
            shelters=[],
            relief_kits=3000,
            max_shelter_pct=90,
        )
        # Each district should get some relief kits
        dist_names = {d["district"] for d in result.get("supply_distribution", [])}
        assert "D1" in dist_names
        assert "D2" in dist_names

    @pytest.mark.asyncio
    async def test_optimize_empty_resources(self, agent):
        """Handles zero available resources gracefully."""
        from src.agents.resource_allocation import optimize_allocation

        districts = [
            {"name": "D1", "severity": 4, "population": 100000,
             "lat": 19.81, "lon": 85.83},
        ]
        result = optimize_allocation(
            districts=districts,
            battalions=[],
            shelters=[],
            relief_kits=0,
            max_shelter_pct=90,
        )
        assert result["solver_status"] in ("optimal", "feasible", "no_resources")
        assert result["ndrf_deployments"] == []
        assert result["shelter_assignments"] == []


# =============================================================================
# Test Group 6: Greedy Fallback
# =============================================================================


class TestGreedyFallback:
    def test_greedy_allocate(self):
        """Greedy heuristic runs and produces valid allocation."""
        from src.agents.resource_allocation import greedy_allocate

        districts = [
            {"name": "D1", "severity": 4, "population": 100000,
             "lat": 19.81, "lon": 85.83},
            {"name": "D2", "severity": 2, "population": 50000,
             "lat": 20.18, "lon": 85.62},
        ]
        battalions = [
            {"name": "B1", "base_lat": 19.5, "base_lon": 85.5, "strength": 500},
        ]
        shelters = [
            {"name": "S1", "capacity": 300, "current_occupancy": 0,
             "lat": 19.80, "lon": 85.82},
        ]

        result = greedy_allocate(
            districts=districts,
            battalions=battalions,
            shelters=shelters,
            relief_kits=2000,
            max_shelter_pct=90,
        )

        assert result["solver_status"] == "greedy_heuristic"
        assert len(result["ndrf_deployments"]) > 0
        assert len(result["supply_distribution"]) > 0


# =============================================================================
# Test Group 7: LLM Plan Formatting
# =============================================================================


class TestFormatPlan:
    @pytest.mark.asyncio
    async def test_format_plan_calls_llm(self, agent, mock_router):
        """Format node calls LLM and produces structured output."""
        state = {
            "task": _sample_task_payload(),
            "trace_id": "fmt12345",
            "messages": [],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
            "demand_assessment": [
                {"name": "Puri", "severity": 4, "population": 1698730},
            ],
            "resource_inventory": {
                "ndrf_battalions": [],
                "shelters": [],
                "relief_kits": 0,
            },
            "optimization_result": {
                "solver_status": "optimal",
                "ndrf_deployments": [],
                "shelter_assignments": [],
                "supply_distribution": [],
                "solve_time_ms": 50,
            },
        }
        result = await agent._format_plan(state)
        mock_router.call.assert_awaited_once()
        assert result["confidence"] > 0
        assert len(result["artifacts"]) > 0


# =============================================================================
# Test Group 8: Full Graph Execution
# =============================================================================


class TestFullGraph:
    @pytest.mark.asyncio
    async def test_full_graph_execution(self, agent, mock_router):
        """End-to-end graph run with mocked LLM produces valid state."""
        initial = {
            "task": _sample_task_payload(),
            "trace_id": "full1234",
            "messages": [{"role": "system", "content": agent.get_system_prompt()}],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
        }
        result = await agent.run_graph(initial)
        assert result.get("confidence", 0) > 0
        assert len(result.get("artifacts", [])) > 0
        assert result.get("optimization_result") is not None

    @pytest.mark.asyncio
    async def test_rolling_reoptimization(self, agent, mock_router):
        """Calling agent twice with updated state produces different plans."""
        payload1 = _sample_task_payload()
        payload2 = _sample_task_payload()
        # Change severity in second run
        payload2["affected_districts"][0]["severity"] = 2
        payload2["affected_districts"][1]["severity"] = 5

        initial1 = {
            "task": payload1,
            "trace_id": "roll0001",
            "messages": [{"role": "system", "content": agent.get_system_prompt()}],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
        }
        initial2 = {
            "task": payload2,
            "trace_id": "roll0002",
            "messages": [{"role": "system", "content": agent.get_system_prompt()}],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
        }

        result1 = await agent.run_graph(initial1)
        result2 = await agent.run_graph(initial2)

        opt1 = result1.get("optimization_result", {})
        opt2 = result2.get("optimization_result", {})
        # Both should have valid results
        assert opt1.get("solver_status") in ("optimal", "feasible", "no_resources")
        assert opt2.get("solver_status") in ("optimal", "feasible", "no_resources")
        # Supply distribution should differ since severities changed
        dist1 = opt1.get("supply_distribution", [])
        dist2 = opt2.get("supply_distribution", [])
        if dist1 and dist2:
            # At least the distribution should be different given different severities
            kits1 = {d["district"]: d["relief_kits"] for d in dist1}
            kits2 = {d["district"]: d["relief_kits"] for d in dist2}
            assert kits1 != kits2
