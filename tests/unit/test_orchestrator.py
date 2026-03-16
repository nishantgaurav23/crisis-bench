"""Tests for OrchestratorAgent — mission decomposition, delegation, synthesis.

Tests cover: initialization, mission decomposition, phase-based activation,
A2A delegation, result collection with timeouts, budget management,
synthesis with confidence-gated escalation, health checks.
All external services (Redis, LLM providers) are mocked.
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.base import AgentState
from src.agents.orchestrator import (
    PHASE_AGENT_MAP,
    OrchestratorAgent,
)
from src.protocols.a2a.schemas import (
    A2AAgentCard,
    A2ATask,
    A2ATaskResult,
)
from src.routing.llm_router import LLMResponse, LLMTier
from src.shared.config import CrisisSettings
from src.shared.models import AgentType, DisasterPhase, TaskStatus

# =============================================================================
# Test helpers
# =============================================================================


def _make_settings(**overrides) -> CrisisSettings:
    defaults = dict(
        DEEPSEEK_API_KEY="",
        QWEN_API_KEY="",
        KIMI_API_KEY="",
        GROQ_API_KEY="",
        GOOGLE_API_KEY="",
        OLLAMA_HOST="http://localhost:11434",
        AGENT_TIMEOUT_SECONDS=5,
        AGENT_MAX_DELEGATION_DEPTH=5,
        BUDGET_LIMIT_PER_SCENARIO=0.05,
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
        tier="critical",
    )
    defaults.update(kw)
    return LLMResponse(**defaults)


def _make_decompose_response() -> LLMResponse:
    """LLM response for mission decomposition — returns JSON with sub-tasks."""
    sub_tasks = [
        {
            "target_agent": "situation_sense",
            "task_type": "fuse_data",
            "priority": 1,
            "payload": {"action": "fuse IMD + SACHET data"},
        },
        {
            "target_agent": "predictive_risk",
            "task_type": "forecast",
            "priority": 2,
            "payload": {"action": "forecast cyclone trajectory"},
        },
        {
            "target_agent": "resource_allocation",
            "task_type": "optimize",
            "priority": 2,
            "payload": {"action": "plan NDRF deployment"},
        },
    ]
    return _make_llm_response(
        content=json.dumps({"sub_tasks": sub_tasks}),
        cost_usd=0.001,
    )


def _make_synthesis_response(confidence: float = 0.85) -> LLMResponse:
    """LLM response for result synthesis."""
    briefing = {
        "situation_summary": "Category 4 cyclone approaching Odisha coast",
        "risk_assessment": "High risk of storm surge in coastal districts",
        "resource_plan": "Deploy 4 NDRF battalions to Puri, Ganjam",
        "communication_directives": "Issue red alert in Odia and English",
        "confidence": confidence,
    }
    return _make_llm_response(
        content=json.dumps(briefing),
        cost_usd=0.002,
    )


def _make_mission_payload() -> dict:
    return {
        "disaster_type": "cyclone",
        "severity": 4,
        "affected_states": ["Odisha"],
        "affected_districts": ["Puri", "Ganjam"],
        "phase": "active_response",
        "description": "VSCS approaching Odisha coast, landfall in 12 hours",
    }


def _make_task_result(
    task_id: uuid.UUID,
    agent_id: str,
    status: TaskStatus = TaskStatus.COMPLETED,
    confidence: float = 0.9,
) -> A2ATaskResult:
    return A2ATaskResult(
        task_id=task_id,
        agent_id=agent_id,
        status=status,
        confidence=confidence,
        trace_id=uuid.uuid4().hex[:8],
    )


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def settings() -> CrisisSettings:
    return _make_settings()


@pytest.fixture
def mock_router():
    router = AsyncMock()
    router.call = AsyncMock(return_value=_make_decompose_response())
    router.get_provider_status = MagicMock(return_value={})
    return router


@pytest.fixture
def mock_a2a_client():
    client = AsyncMock()
    client.start = AsyncMock()
    client.stop = AsyncMock()
    client.send_result = AsyncMock(return_value="msg-123")
    client.send_update = AsyncMock(return_value="msg-456")
    client.send_agent_card = AsyncMock(return_value="msg-789")
    client.on_message = MagicMock()
    return client


@pytest.fixture
def mock_a2a_server():
    server = AsyncMock()
    server.register_agent_card = AsyncMock(return_value="msg-card")
    server.send_task = AsyncMock(return_value="msg-task")
    server.send_result = AsyncMock(return_value="msg-result")
    return server


@pytest.fixture
def orchestrator(settings, mock_router, mock_a2a_client, mock_a2a_server):
    agent = OrchestratorAgent(settings=settings)
    agent._router = mock_router
    agent._a2a_client = mock_a2a_client
    agent._a2a_server = mock_a2a_server
    return agent


# =============================================================================
# Test Group 1: Initialization
# =============================================================================


class TestInitialization:
    def test_orchestrator_creates(self, settings):
        agent = OrchestratorAgent(settings=settings)
        assert agent.agent_id == "orchestrator"
        assert agent.agent_type == AgentType.ORCHESTRATOR
        assert agent.llm_tier == LLMTier.CRITICAL

    def test_orchestrator_system_prompt(self, orchestrator):
        prompt = orchestrator.get_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "orchestrator" in prompt.lower() or "coordinator" in prompt.lower()

    def test_orchestrator_agent_card(self, orchestrator):
        card = orchestrator.get_agent_card()
        assert isinstance(card, A2AAgentCard)
        assert card.agent_id == "orchestrator"
        assert card.agent_type == AgentType.ORCHESTRATOR
        assert card.llm_tier == LLMTier.CRITICAL
        assert "decomposition" in card.capabilities or "orchestration" in card.capabilities

    def test_orchestrator_builds_graph(self, orchestrator):
        graph = orchestrator.build_graph()
        assert graph is not None


# =============================================================================
# Test Group 2: Phase-Based Agent Activation
# =============================================================================


class TestPhaseActivation:
    def test_pre_event_agents(self):
        agents = PHASE_AGENT_MAP[DisasterPhase.PRE_EVENT]
        assert AgentType.SITUATION_SENSE in agents
        assert AgentType.PREDICTIVE_RISK in agents
        assert AgentType.HISTORICAL_MEMORY in agents
        assert AgentType.RESOURCE_ALLOCATION not in agents

    def test_active_response_all_agents(self):
        agents = PHASE_AGENT_MAP[DisasterPhase.ACTIVE_RESPONSE]
        expected = {
            AgentType.SITUATION_SENSE,
            AgentType.PREDICTIVE_RISK,
            AgentType.RESOURCE_ALLOCATION,
            AgentType.COMMUNITY_COMMS,
            AgentType.INFRA_STATUS,
            AgentType.HISTORICAL_MEMORY,
        }
        assert expected == set(agents)

    def test_recovery_agents(self):
        agents = PHASE_AGENT_MAP[DisasterPhase.RECOVERY]
        assert AgentType.RESOURCE_ALLOCATION in agents
        assert AgentType.COMMUNITY_COMMS in agents
        assert AgentType.INFRA_STATUS in agents
        assert AgentType.HISTORICAL_MEMORY in agents
        assert AgentType.SITUATION_SENSE not in agents

    def test_post_event_historical_only(self):
        agents = PHASE_AGENT_MAP[DisasterPhase.POST_EVENT]
        assert agents == [AgentType.HISTORICAL_MEMORY]

    def test_get_active_agents_filters_by_phase(self, orchestrator):
        active = orchestrator.get_active_agents(DisasterPhase.PRE_EVENT)
        agent_types = [a for a in active]
        assert AgentType.RESOURCE_ALLOCATION not in agent_types
        assert AgentType.SITUATION_SENSE in agent_types


# =============================================================================
# Test Group 3: Mission Decomposition
# =============================================================================


class TestMissionDecomposition:
    @pytest.mark.asyncio
    async def test_decompose_calls_llm(self, orchestrator, mock_router):
        mock_router.call = AsyncMock(return_value=_make_decompose_response())
        result = await orchestrator.decompose_mission(
            _make_mission_payload(),
            phase=DisasterPhase.ACTIVE_RESPONSE,
            trace_id="abc12345",
        )
        mock_router.call.assert_awaited()
        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_decompose_returns_valid_sub_tasks(self, orchestrator, mock_router):
        mock_router.call = AsyncMock(return_value=_make_decompose_response())
        result = await orchestrator.decompose_mission(
            _make_mission_payload(),
            phase=DisasterPhase.ACTIVE_RESPONSE,
            trace_id="abc12345",
        )
        for task in result:
            assert "target_agent" in task
            assert "task_type" in task
            assert "priority" in task
            assert "payload" in task

    @pytest.mark.asyncio
    async def test_decompose_filters_by_phase(self, orchestrator, mock_router):
        """Sub-tasks for inactive agents should be filtered out."""
        # Include resource_allocation which is NOT in pre_event
        sub_tasks = [
            {
                "target_agent": "situation_sense",
                "task_type": "fuse_data",
                "priority": 1,
                "payload": {},
            },
            {
                "target_agent": "resource_allocation",
                "task_type": "optimize",
                "priority": 2,
                "payload": {},
            },
        ]
        mock_router.call = AsyncMock(
            return_value=_make_llm_response(
                content=json.dumps({"sub_tasks": sub_tasks}),
            )
        )
        result = await orchestrator.decompose_mission(
            _make_mission_payload(),
            phase=DisasterPhase.PRE_EVENT,
            trace_id="abc12345",
        )
        target_agents = [t["target_agent"] for t in result]
        assert "situation_sense" in target_agents
        assert "resource_allocation" not in target_agents

    @pytest.mark.asyncio
    async def test_decompose_handles_invalid_json(self, orchestrator, mock_router):
        mock_router.call = AsyncMock(
            return_value=_make_llm_response(content="not valid json")
        )
        result = await orchestrator.decompose_mission(
            _make_mission_payload(),
            phase=DisasterPhase.ACTIVE_RESPONSE,
            trace_id="abc12345",
        )
        # Should return empty list on parse failure, not crash
        assert result == []


# =============================================================================
# Test Group 4: Task Delegation
# =============================================================================


class TestDelegation:
    @pytest.mark.asyncio
    async def test_delegate_sends_tasks(self, orchestrator, mock_a2a_server):
        sub_tasks = [
            {
                "target_agent": "situation_sense",
                "task_type": "fuse_data",
                "priority": 1,
                "payload": {"action": "fuse data"},
            },
        ]
        task_ids = await orchestrator.delegate_tasks(
            sub_tasks,
            disaster_id=uuid.uuid4(),
            parent_depth=0,
            trace_id="abc12345",
        )
        mock_a2a_server.send_task.assert_awaited()
        assert len(task_ids) == 1

    @pytest.mark.asyncio
    async def test_delegate_increments_depth(self, orchestrator, mock_a2a_server):
        sub_tasks = [
            {
                "target_agent": "predictive_risk",
                "task_type": "forecast",
                "priority": 2,
                "payload": {},
            },
        ]
        await orchestrator.delegate_tasks(
            sub_tasks,
            disaster_id=uuid.uuid4(),
            parent_depth=2,
            trace_id="abc12345",
        )
        call_args = mock_a2a_server.send_task.call_args[0][0]
        assert isinstance(call_args, A2ATask)
        assert call_args.depth == 3  # parent_depth + 1

    @pytest.mark.asyncio
    async def test_delegate_multiple_tasks(self, orchestrator, mock_a2a_server):
        sub_tasks = [
            {"target_agent": "situation_sense", "task_type": "fuse", "priority": 1, "payload": {}},
            {"target_agent": "predictive_risk", "task_type": "forecast", "priority": 2, "payload": {}},
            {"target_agent": "resource_allocation", "task_type": "optimize", "priority": 2, "payload": {}},
        ]
        task_ids = await orchestrator.delegate_tasks(
            sub_tasks,
            disaster_id=uuid.uuid4(),
            parent_depth=0,
            trace_id="abc12345",
        )
        assert len(task_ids) == 3
        assert mock_a2a_server.send_task.await_count == 3


# =============================================================================
# Test Group 5: Result Collection
# =============================================================================


class TestResultCollection:
    @pytest.mark.asyncio
    async def test_collect_all_results(self, orchestrator):
        task_ids = [uuid.uuid4(), uuid.uuid4()]
        results = {
            task_ids[0]: _make_task_result(task_ids[0], "situation_sense"),
            task_ids[1]: _make_task_result(task_ids[1], "predictive_risk"),
        }
        # Simulate instant result availability
        collected = await orchestrator.collect_results(
            task_ids,
            results=results,
            timeout=5.0,
        )
        assert len(collected) == 2
        assert all(r.status == TaskStatus.COMPLETED for r in collected.values())

    @pytest.mark.asyncio
    async def test_collect_with_timeout_marks_failed(self, orchestrator):
        task_ids = [uuid.uuid4(), uuid.uuid4()]
        # Only provide one result — the other should time out
        results = {
            task_ids[0]: _make_task_result(task_ids[0], "situation_sense"),
        }
        collected = await orchestrator.collect_results(
            task_ids,
            results=results,
            timeout=0.1,  # Very short timeout
        )
        assert len(collected) == 2
        # One completed, one timed out
        statuses = {r.status for r in collected.values()}
        assert TaskStatus.COMPLETED in statuses
        assert TaskStatus.FAILED in statuses

    @pytest.mark.asyncio
    async def test_collect_empty_tasks(self, orchestrator):
        collected = await orchestrator.collect_results([], results={}, timeout=1.0)
        assert collected == {}


# =============================================================================
# Test Group 6: Budget Management
# =============================================================================


class TestBudgetManagement:
    def test_initial_budget_zero(self, orchestrator):
        assert orchestrator.budget_used == 0.0

    def test_track_cost(self, orchestrator):
        orchestrator.track_cost(0.01)
        assert orchestrator.budget_used == pytest.approx(0.01)
        orchestrator.track_cost(0.02)
        assert orchestrator.budget_used == pytest.approx(0.03)

    def test_budget_exceeded(self, orchestrator):
        assert not orchestrator.is_budget_exceeded()
        orchestrator.track_cost(0.06)  # exceeds $0.05 default
        assert orchestrator.is_budget_exceeded()

    def test_budget_at_boundary(self, orchestrator):
        orchestrator.track_cost(0.05)
        assert orchestrator.is_budget_exceeded()

    def test_reset_budget(self, orchestrator):
        orchestrator.track_cost(0.03)
        orchestrator.reset_budget()
        assert orchestrator.budget_used == 0.0
        assert not orchestrator.is_budget_exceeded()


# =============================================================================
# Test Group 7: Synthesis
# =============================================================================


class TestSynthesis:
    @pytest.mark.asyncio
    async def test_synthesize_calls_llm(self, orchestrator, mock_router):
        mock_router.call = AsyncMock(return_value=_make_synthesis_response())
        task_id = uuid.uuid4()
        agent_results = {
            task_id: _make_task_result(task_id, "situation_sense", confidence=0.9),
        }
        result = await orchestrator.synthesize_results(
            agent_results,
            mission=_make_mission_payload(),
            trace_id="abc12345",
        )
        mock_router.call.assert_awaited()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_synthesize_includes_confidence(self, orchestrator, mock_router):
        mock_router.call = AsyncMock(return_value=_make_synthesis_response(confidence=0.85))
        task_id = uuid.uuid4()
        agent_results = {
            task_id: _make_task_result(task_id, "situation_sense", confidence=0.9),
        }
        result = await orchestrator.synthesize_results(
            agent_results,
            mission=_make_mission_payload(),
            trace_id="abc12345",
        )
        assert "confidence" in result
        assert result["confidence"] >= 0.0

    @pytest.mark.asyncio
    async def test_synthesize_escalation_low_confidence(self, orchestrator, mock_router):
        mock_router.call = AsyncMock(return_value=_make_synthesis_response(confidence=0.5))
        task_id = uuid.uuid4()
        agent_results = {
            task_id: _make_task_result(task_id, "situation_sense", confidence=0.4),
        }
        result = await orchestrator.synthesize_results(
            agent_results,
            mission=_make_mission_payload(),
            trace_id="abc12345",
        )
        assert result.get("needs_escalation") is True

    @pytest.mark.asyncio
    async def test_synthesize_no_escalation_high_confidence(self, orchestrator, mock_router):
        mock_router.call = AsyncMock(return_value=_make_synthesis_response(confidence=0.9))
        task_id = uuid.uuid4()
        agent_results = {
            task_id: _make_task_result(task_id, "situation_sense", confidence=0.9),
        }
        result = await orchestrator.synthesize_results(
            agent_results,
            mission=_make_mission_payload(),
            trace_id="abc12345",
        )
        assert result.get("needs_escalation") is False

    @pytest.mark.asyncio
    async def test_synthesize_handles_invalid_json(self, orchestrator, mock_router):
        mock_router.call = AsyncMock(
            return_value=_make_llm_response(content="not valid json")
        )
        task_id = uuid.uuid4()
        agent_results = {
            task_id: _make_task_result(task_id, "situation_sense"),
        }
        result = await orchestrator.synthesize_results(
            agent_results,
            mission=_make_mission_payload(),
            trace_id="abc12345",
        )
        # Should return a fallback briefing, not crash
        assert isinstance(result, dict)
        assert "error" in result or "situation_summary" in result


# =============================================================================
# Test Group 8: Health Check
# =============================================================================


class TestHealthCheck:
    def test_health_includes_budget(self, orchestrator):
        orchestrator.track_cost(0.01)
        h = orchestrator.health()
        assert "budget_used_usd" in h
        assert "budget_limit_usd" in h
        assert h["budget_used_usd"] == pytest.approx(0.01)

    def test_health_includes_budget_exceeded(self, orchestrator):
        orchestrator.track_cost(0.06)
        h = orchestrator.health()
        assert h["budget_exceeded"] is True

    def test_health_inherits_base_fields(self, orchestrator):
        h = orchestrator.health()
        assert h["agent_id"] == "orchestrator"
        assert h["agent_type"] == "orchestrator"
        assert h["llm_tier"] == "critical"


# =============================================================================
# Test Group 9: Full Graph Execution
# =============================================================================


class TestGraphExecution:
    @pytest.mark.asyncio
    async def test_graph_runs_end_to_end(self, orchestrator, mock_router, mock_a2a_server):
        """Full graph execution: parse → decompose → delegate → collect → synthesize."""
        # First call: decompose, second call: synthesize
        mock_router.call = AsyncMock(
            side_effect=[
                _make_decompose_response(),
                _make_synthesis_response(),
            ]
        )

        initial: AgentState = {
            "task": _make_mission_payload(),
            "disaster_id": str(uuid.uuid4()),
            "trace_id": "e2e12345",
            "messages": [
                {"role": "system", "content": "You are the orchestrator."},
                {"role": "user", "content": json.dumps(_make_mission_payload())},
            ],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
        }

        result = await orchestrator.run_graph(initial)
        assert result.get("confidence", 0) > 0
        assert result.get("error") is None or result["error"] == ""
