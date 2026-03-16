"""Tests for InfraStatus agent — infrastructure tracking, cascading failures, restoration.

Tests cover: initialization, state machine structure, NDMA priority framework,
restoration timeline estimation, Neo4j graph integration, cascading failure
prediction, damage assessment, and edge cases. All external services mocked.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.infra_status import (
    RESTORATION_PRIORITY,
    InfraStatus,
    InfraStatusState,
    estimate_restoration_hours,
    get_priority_ordered,
)
from src.data.ingest.infra_graph import CascadeResult
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


def _sample_task_payload(
    disaster_type="cyclone",
    affected_state="Odisha",
    affected_districts=None,
    reported_damage=None,
) -> dict:
    return {
        "action": "assess_infrastructure",
        "disaster_type": disaster_type,
        "affected_state": affected_state,
        "affected_districts": affected_districts or ["Khordha", "Puri"],
        "reported_damage": reported_damage or [
            {"type": "PowerGrid", "name": "TPCODL Bhubaneswar", "status": "damaged"},
            {"type": "Road", "name": "NH-16 (Kolkata-Chennai)", "status": "damaged"},
        ],
    }


def _sample_infra_nodes() -> list[dict]:
    """Sample infrastructure nodes as returned by InfraGraphManager."""
    return [
        {"name": "TPCODL Bhubaneswar", "label": "PowerGrid", "status": "operational",
         "type": "distribution", "capacity_mw": 400, "state": "Odisha"},
        {"name": "Jio Tower Patia", "label": "TelecomTower", "status": "operational",
         "operator": "Jio", "backup_hours": 8, "state": "Odisha"},
        {"name": "Kuakhai WTP", "label": "WaterTreatment", "status": "operational",
         "capacity_mld": 200, "state": "Odisha"},
        {"name": "Capital Hospital", "label": "Hospital", "status": "operational",
         "beds": 700, "type": "government", "state": "Odisha"},
        {"name": "NH-16 (Kolkata-Chennai)", "label": "Road", "status": "operational",
         "type": "highway", "state": "Odisha"},
        {"name": "Puri Cyclone Shelter 1", "label": "Shelter", "status": "operational",
         "capacity": 600, "type": "cyclone", "state": "Odisha"},
    ]


def _sample_cascade_results() -> list[CascadeResult]:
    """Sample cascading failure results from Neo4j."""
    return [
        CascadeResult(
            affected_node="Jio Tower Patia",
            affected_label="TelecomTower",
            impact_type="power_loss",
            estimated_recovery_hours=0.0,
            path=["Jio Tower Patia", "TPCODL Bhubaneswar"],
        ),
        CascadeResult(
            affected_node="Kuakhai WTP",
            affected_label="WaterTreatment",
            impact_type="power_loss",
            estimated_recovery_hours=0.0,
            path=["Kuakhai WTP", "TPCODL Bhubaneswar"],
        ),
        CascadeResult(
            affected_node="Capital Hospital",
            affected_label="Hospital",
            impact_type="power_loss",
            estimated_recovery_hours=0.0,
            path=["Capital Hospital", "TPCODL Bhubaneswar"],
        ),
    ]


def _make_initial_state(agent, task_payload=None) -> InfraStatusState:
    payload = task_payload or _sample_task_payload()
    return {
        "task": payload,
        "disaster_id": None,
        "trace_id": "test-trace-infra-001",
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
        "infrastructure_data": [],
        "damage_assessment": {},
        "cascading_failures": [],
        "restoration_plan": [],
        "affected_state": "",
        "affected_districts": [],
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
    damage_json = json.dumps({
        "damage_summary": {
            "total_nodes": 6,
            "damaged_nodes": 2,
            "critical_failures": ["TPCODL Bhubaneswar"],
        },
        "per_node": [
            {"name": "TPCODL Bhubaneswar", "label": "PowerGrid",
             "damage_level": "severe", "operational_capacity_pct": 20},
            {"name": "NH-16 (Kolkata-Chennai)", "label": "Road",
             "damage_level": "moderate", "operational_capacity_pct": 50},
        ],
    })
    cascading_json = json.dumps({
        "cascading_timeline": [
            {"time_hours": 0, "event": "Power grid failure at TPCODL Bhubaneswar",
             "affected": "PowerGrid", "probability": 0.95},
            {"time_hours": 4, "event": "Telecom backup exhaustion at Jio Tower Patia",
             "affected": "TelecomTower", "probability": 0.8},
            {"time_hours": 8, "event": "Water treatment disruption at Kuakhai WTP",
             "affected": "WaterTreatment", "probability": 0.7},
            {"time_hours": 12, "event": "Hospital generator strain at Capital Hospital",
             "affected": "Hospital", "probability": 0.5},
        ],
    })
    restoration_json = json.dumps({
        "restoration_estimates": [
            {"name": "Capital Hospital", "label": "Hospital",
             "priority": 1, "estimated_hours": 4, "action": "Deploy generator"},
            {"name": "Kuakhai WTP", "label": "WaterTreatment",
             "priority": 2, "estimated_hours": 12, "action": "Repair pump + power"},
            {"name": "Jio Tower Patia", "label": "TelecomTower",
             "priority": 3, "estimated_hours": 8, "action": "Restore power feed"},
            {"name": "TPCODL Bhubaneswar", "label": "PowerGrid",
             "priority": 4, "estimated_hours": 48, "action": "Repair distribution lines"},
            {"name": "NH-16 (Kolkata-Chennai)", "label": "Road",
             "priority": 5, "estimated_hours": 36, "action": "Clear debris, temp bridge"},
        ],
    })

    router.call = AsyncMock(
        side_effect=[
            _make_llm_response(damage_json),        # assess_damage
            _make_llm_response(cascading_json),      # predict_cascading
            _make_llm_response(restoration_json),    # estimate_restoration
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
def mock_infra_graph():
    graph = AsyncMock()
    graph.connect = AsyncMock()
    graph.health_check = AsyncMock(return_value=True)
    graph.close = AsyncMock()
    graph.get_infrastructure_by_state = AsyncMock(return_value=_sample_infra_nodes())
    graph.get_downstream_impacts = AsyncMock(return_value=_sample_cascade_results())
    graph.simulate_failure = AsyncMock(return_value=_sample_cascade_results())
    graph.get_infrastructure_status_summary = AsyncMock(return_value=[
        {"label": "PowerGrid", "status": "operational", "count": 2},
        {"label": "TelecomTower", "status": "operational", "count": 3},
    ])
    return graph


@pytest.fixture
def agent(settings, mock_router, mock_a2a_client, mock_a2a_server, mock_infra_graph):
    a = InfraStatus(settings=settings)
    a._router = mock_router
    a._a2a_client = mock_a2a_client
    a._a2a_server = mock_a2a_server
    a._infra_graph = mock_infra_graph
    return a


# =============================================================================
# Test Group 1: Initialization
# =============================================================================


class TestInitialization:
    def test_creates_with_correct_type(self, agent):
        """InfraStatus must use AgentType.INFRA_STATUS."""
        assert agent.agent_type == AgentType.INFRA_STATUS

    def test_default_tier_is_routine(self, agent):
        """InfraStatus operates on the routine (Qwen Flash) tier."""
        assert agent.llm_tier == LLMTier.ROUTINE

    def test_system_prompt_contains_infrastructure_context(self, agent):
        """System prompt must reference infrastructure tracking and Neo4j."""
        prompt = agent.get_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 50
        prompt_lower = prompt.lower()
        assert "infrastructure" in prompt_lower
        assert "power" in prompt_lower or "telecom" in prompt_lower
        assert "cascading" in prompt_lower or "cascade" in prompt_lower

    def test_system_prompt_mentions_ndma_priority(self, agent):
        """System prompt should reference NDMA priority restoration framework."""
        prompt = agent.get_system_prompt().lower()
        assert "ndma" in prompt or "priority" in prompt
        assert "hospital" in prompt or "restoration" in prompt

    def test_agent_card_has_capabilities(self, agent):
        """Agent card must declare infrastructure and cascade capabilities."""
        card = agent.get_agent_card()
        assert isinstance(card, A2AAgentCard)
        assert card.agent_type == AgentType.INFRA_STATUS
        assert len(card.capabilities) >= 3
        caps_text = " ".join(card.capabilities).lower()
        assert "infrastructure" in caps_text or "infra" in caps_text
        assert "cascading" in caps_text or "cascade" in caps_text
        assert "restoration" in caps_text


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
            "query_infra_graph",
            "assess_damage",
            "predict_cascading",
            "estimate_restoration",
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
        assert result.get("damage_assessment") is not None
        assert result.get("cascading_failures") is not None
        assert result.get("restoration_plan") is not None
        assert result.get("confidence", 0) > 0


# =============================================================================
# Test Group 3: NDMA Priority Framework
# =============================================================================


class TestNDMAPriority:
    def test_hospital_highest_priority(self):
        """Hospital must be priority 1 (life-critical)."""
        assert RESTORATION_PRIORITY["Hospital"] == 1

    def test_water_treatment_second(self):
        """Water treatment must be priority 2 (public health)."""
        assert RESTORATION_PRIORITY["WaterTreatment"] == 2

    def test_telecom_third(self):
        """Telecom must be priority 3 (communication)."""
        assert RESTORATION_PRIORITY["TelecomTower"] == 3

    def test_power_grid_fourth(self):
        """Power grid must be priority 4 (backbone)."""
        assert RESTORATION_PRIORITY["PowerGrid"] == 4

    def test_road_fifth(self):
        """Road must be priority 5 (access)."""
        assert RESTORATION_PRIORITY["Road"] == 5

    def test_shelter_sixth(self):
        """Shelter must be priority 6 (temporary housing)."""
        assert RESTORATION_PRIORITY["Shelter"] == 6

    def test_priority_ordering_function(self):
        """get_priority_ordered should sort infrastructure by NDMA priority."""
        nodes = [
            {"label": "Road", "name": "NH-16"},
            {"label": "Hospital", "name": "Capital Hospital"},
            {"label": "PowerGrid", "name": "TPCODL"},
            {"label": "WaterTreatment", "name": "Kuakhai WTP"},
            {"label": "TelecomTower", "name": "Jio Tower"},
        ]
        ordered = get_priority_ordered(nodes)
        labels = [n["label"] for n in ordered]
        assert labels == [
            "Hospital", "WaterTreatment", "TelecomTower", "PowerGrid", "Road"
        ]

    def test_unknown_label_gets_lowest_priority(self):
        """Unknown infrastructure types should sort last."""
        nodes = [
            {"label": "Hospital", "name": "A"},
            {"label": "UnknownType", "name": "B"},
        ]
        ordered = get_priority_ordered(nodes)
        assert ordered[0]["label"] == "Hospital"
        assert ordered[1]["label"] == "UnknownType"


# =============================================================================
# Test Group 4: Restoration Time Estimation
# =============================================================================


class TestRestorationEstimation:
    def test_hospital_minor_damage(self):
        """Hospital minor damage should be 2-4 hours."""
        low, high = estimate_restoration_hours("Hospital", "minor")
        assert low >= 2
        assert high <= 4

    def test_hospital_severe_damage(self):
        """Hospital severe damage should be 24-48 hours."""
        low, high = estimate_restoration_hours("Hospital", "severe")
        assert low >= 24
        assert high <= 48

    def test_power_grid_moderate_damage(self):
        """Power grid moderate damage should be 24-48 hours."""
        low, high = estimate_restoration_hours("PowerGrid", "moderate")
        assert low >= 24
        assert high <= 48

    def test_power_grid_severe_damage(self):
        """Power grid severe damage should be 72-168 hours."""
        low, high = estimate_restoration_hours("PowerGrid", "severe")
        assert low >= 72
        assert high <= 168

    def test_telecom_moderate_damage(self):
        """Telecom moderate damage should be 8-16 hours."""
        low, high = estimate_restoration_hours("TelecomTower", "moderate")
        assert low >= 8
        assert high <= 16

    def test_road_severe_damage(self):
        """Road severe damage should be 72-336 hours."""
        low, high = estimate_restoration_hours("Road", "severe")
        assert low >= 72
        assert high <= 336

    def test_unknown_type_returns_default(self):
        """Unknown infrastructure type should return a reasonable default."""
        low, high = estimate_restoration_hours("UnknownType", "moderate")
        assert low > 0
        assert high > low

    def test_unknown_severity_returns_moderate(self):
        """Unknown severity should default to moderate estimate."""
        low, high = estimate_restoration_hours("Hospital", "unknown_severity")
        assert low > 0
        assert high > low


# =============================================================================
# Test Group 5: Neo4j Graph Integration
# =============================================================================


class TestGraphIntegration:
    @pytest.mark.asyncio
    async def test_queries_infrastructure_by_state(self, agent, mock_infra_graph):
        """Agent should query Neo4j for infrastructure in affected state."""
        initial = _make_initial_state(agent)
        await agent.run_graph(initial)
        mock_infra_graph.get_infrastructure_by_state.assert_called_once_with("Odisha")

    @pytest.mark.asyncio
    async def test_simulates_reported_failures(self, agent, mock_infra_graph):
        """Agent should simulate failures for reported damaged nodes."""
        initial = _make_initial_state(agent)
        await agent.run_graph(initial)
        # Should have called simulate_failure for reported damaged nodes
        assert mock_infra_graph.simulate_failure.call_count >= 1

    @pytest.mark.asyncio
    async def test_graceful_degradation_no_neo4j(self, agent, mock_infra_graph, mock_router):
        """If Neo4j fails, agent should continue with empty infrastructure data."""
        mock_infra_graph.get_infrastructure_by_state.side_effect = Exception("Neo4j down")
        mock_infra_graph.simulate_failure.side_effect = Exception("Neo4j down")

        # Need fresh LLM responses since graph fails
        damage_json = json.dumps({
            "damage_summary": {"total_nodes": 0, "damaged_nodes": 0},
            "per_node": [],
        })
        cascading_json = json.dumps({"cascading_timeline": []})
        restoration_json = json.dumps({"restoration_estimates": []})
        mock_router.call = AsyncMock(side_effect=[
            _make_llm_response(damage_json),
            _make_llm_response(cascading_json),
            _make_llm_response(restoration_json),
        ])

        initial = _make_initial_state(agent)
        result = await agent.run_graph(initial)
        assert result is not None
        assert result.get("error") is None


# =============================================================================
# Test Group 6: Cascading Failure Prediction
# =============================================================================


class TestCascadingFailures:
    @pytest.mark.asyncio
    async def test_cascading_failures_populated(self, agent):
        """Cascading failures should be predicted from Neo4j + LLM."""
        initial = _make_initial_state(agent)
        result = await agent.run_graph(initial)
        cascading = result.get("cascading_failures", [])
        assert isinstance(cascading, list)
        assert len(cascading) >= 1

    @pytest.mark.asyncio
    async def test_cascading_includes_timeline(self, agent):
        """Each cascading failure should include time estimate."""
        initial = _make_initial_state(agent)
        result = await agent.run_graph(initial)
        cascading = result.get("cascading_failures", [])
        for event in cascading:
            assert "time_hours" in event or "eta_hours" in event


# =============================================================================
# Test Group 7: Restoration Planning
# =============================================================================


class TestRestorationPlanning:
    @pytest.mark.asyncio
    async def test_restoration_plan_populated(self, agent):
        """Restoration plan should be generated."""
        initial = _make_initial_state(agent)
        result = await agent.run_graph(initial)
        plan = result.get("restoration_plan", [])
        assert isinstance(plan, list)
        assert len(plan) >= 1

    @pytest.mark.asyncio
    async def test_restoration_follows_priority_order(self, agent):
        """Restoration plan should follow NDMA priority framework."""
        initial = _make_initial_state(agent)
        result = await agent.run_graph(initial)
        plan = result.get("restoration_plan", [])
        if len(plan) >= 2:
            priorities = [p.get("priority", 99) for p in plan]
            assert priorities == sorted(priorities), (
                f"Restoration plan not in priority order: {priorities}"
            )


# =============================================================================
# Test Group 8: Report Production
# =============================================================================


class TestReportProduction:
    @pytest.mark.asyncio
    async def test_artifacts_contain_infra_report(self, agent):
        """Final artifacts should contain an infrastructure status report."""
        initial = _make_initial_state(agent)
        result = await agent.run_graph(initial)
        artifacts = result.get("artifacts", [])
        assert len(artifacts) >= 1
        report = artifacts[0]
        assert report.get("type") == "infrastructure_status_report"

    @pytest.mark.asyncio
    async def test_report_has_required_sections(self, agent):
        """Report must include damage, cascading, and restoration sections."""
        initial = _make_initial_state(agent)
        result = await agent.run_graph(initial)
        artifacts = result.get("artifacts", [])
        assert len(artifacts) >= 1
        report = artifacts[0]
        assert "damage_assessment" in report
        assert "cascading_failures" in report
        assert "restoration_plan" in report

    @pytest.mark.asyncio
    async def test_confidence_increases_with_data(self, agent):
        """Confidence should be reasonable when infrastructure data is present."""
        initial = _make_initial_state(agent)
        result = await agent.run_graph(initial)
        confidence = result.get("confidence", 0)
        assert 0.1 < confidence <= 0.95


# =============================================================================
# Test Group 9: Edge Cases
# =============================================================================


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_handles_empty_reported_damage(self, agent, mock_router):
        """Agent should handle no reported damage gracefully."""
        damage_json = json.dumps({
            "damage_summary": {"total_nodes": 6, "damaged_nodes": 0},
            "per_node": [],
        })
        cascading_json = json.dumps({"cascading_timeline": []})
        restoration_json = json.dumps({"restoration_estimates": []})
        mock_router.call = AsyncMock(side_effect=[
            _make_llm_response(damage_json),
            _make_llm_response(cascading_json),
            _make_llm_response(restoration_json),
        ])

        payload = _sample_task_payload(reported_damage=[])
        initial = _make_initial_state(agent, payload)
        result = await agent.run_graph(initial)
        assert result is not None
        assert result.get("error") is None

    @pytest.mark.asyncio
    async def test_handles_malformed_llm_response(self, agent, mock_router):
        """Agent should handle non-JSON LLM responses gracefully."""
        mock_router.call = AsyncMock(side_effect=[
            _make_llm_response("Not valid JSON at all"),
            _make_llm_response("Still not JSON"),
            _make_llm_response("Nope"),
        ])
        initial = _make_initial_state(agent)
        result = await agent.run_graph(initial)
        assert result is not None

    @pytest.mark.asyncio
    async def test_handles_unknown_disaster_type(self, agent, mock_router):
        """Agent should handle unknown disaster types."""
        damage_json = json.dumps({
            "damage_summary": {"total_nodes": 0, "damaged_nodes": 0},
            "per_node": [],
        })
        cascading_json = json.dumps({"cascading_timeline": []})
        restoration_json = json.dumps({"restoration_estimates": []})
        mock_router.call = AsyncMock(side_effect=[
            _make_llm_response(damage_json),
            _make_llm_response(cascading_json),
            _make_llm_response(restoration_json),
        ])

        payload = _sample_task_payload(disaster_type="alien_invasion")
        initial = _make_initial_state(agent, payload)
        result = await agent.run_graph(initial)
        assert result is not None
        assert result.get("error") is None
