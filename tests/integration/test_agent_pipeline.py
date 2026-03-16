"""Integration tests for the full multi-agent pipeline (S7.9).

Tests the end-to-end flow: SACHET alert → Orchestrator decomposition →
specialist agent execution → synthesis → bilingual briefing → WebSocket update.

All external services (LLM providers, Redis, databases) are mocked.
"""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.base import AgentState, BaseAgent
from src.agents.community_comms import CommunityComms
from src.agents.historical_memory import HistoricalMemory
from src.agents.infra_status import InfraStatus
from src.agents.orchestrator import (
    PHASE_AGENT_MAP,
    OrchestratorAgent,
)
from src.agents.predictive_risk import PredictiveRisk
from src.agents.resource_allocation import ResourceAllocation
from src.agents.situation_sense import SituationSense
from src.api.websocket import ConnectionManager
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
        BUDGET_LIMIT_PER_SCENARIO=0.10,
        _env_file=None,
    )
    defaults.update(overrides)
    return CrisisSettings(**defaults)


def _make_llm_response(content: str = "{}", **kw) -> LLMResponse:
    defaults = dict(
        content=content,
        provider="ollama_local",
        model="qwen2.5:7b",
        input_tokens=10,
        output_tokens=5,
        cost_usd=0.0,
        latency_s=0.05,
        tier="routine",
    )
    defaults.update(kw)
    return LLMResponse(**defaults)


def _make_sachet_alert() -> dict:
    """Realistic SACHET CAP alert for a cyclone approaching Odisha."""
    return {
        "alert_id": "SACHET-2026-CYC-001",
        "sender": "IMD",
        "event": "Cyclone",
        "headline": "VSCS approaching Odisha coast, landfall in 12 hours",
        "severity": "extreme",
        "urgency": "immediate",
        "certainty": "observed",
        "areas": [
            {"district": "Puri", "state": "Odisha"},
            {"district": "Ganjam", "state": "Odisha"},
            {"district": "Khordha", "state": "Odisha"},
        ],
        "effective": "2026-03-16T06:00:00+05:30",
        "expires": "2026-03-17T06:00:00+05:30",
    }


def _make_imd_warning() -> dict:
    """IMD red alert for Odisha coastal districts."""
    return {
        "color_code": "red",
        "district": "Puri",
        "state": "Odisha",
        "warning_type": "cyclone",
        "wind_speed_kt": 90,
        "rainfall_mm": 200,
        "valid_from": "2026-03-16T06:00:00+05:30",
        "valid_to": "2026-03-17T06:00:00+05:30",
    }


def _make_mission_payload() -> dict:
    """Full mission payload as the orchestrator receives it."""
    return {
        "disaster_type": "cyclone",
        "severity": 4,
        "affected_states": ["Odisha"],
        "affected_districts": ["Puri", "Ganjam", "Khordha"],
        "phase": "active_response",
        "description": "VSCS approaching Odisha coast, landfall in 12 hours",
        "sachet_alert": _make_sachet_alert(),
        "imd_data": [_make_imd_warning()],
        "social_media": [
            {"text": "Heavy rain in Puri, roads flooded", "lang": "en"},
            {"text": "पुरी में तूफान आ रहा है", "lang": "hi"},
        ],
    }


def _make_decompose_response() -> LLMResponse:
    """Orchestrator decomposition — returns sub-tasks for all active agents."""
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
            "priority": 1,
            "payload": {"action": "forecast cyclone trajectory"},
        },
        {
            "target_agent": "resource_allocation",
            "task_type": "optimize",
            "priority": 2,
            "payload": {"action": "plan NDRF deployment"},
        },
        {
            "target_agent": "community_comms",
            "task_type": "generate_alerts",
            "priority": 2,
            "payload": {"action": "generate bilingual alerts"},
        },
        {
            "target_agent": "infra_status",
            "task_type": "assess_infra",
            "priority": 2,
            "payload": {"action": "assess infrastructure impact"},
        },
        {
            "target_agent": "historical_memory",
            "task_type": "retrieve_history",
            "priority": 3,
            "payload": {"action": "find similar past cyclones"},
        },
    ]
    return _make_llm_response(
        content=json.dumps({"sub_tasks": sub_tasks}),
        cost_usd=0.001,
        tier="critical",
    )


def _make_synthesis_response(confidence: float = 0.85) -> LLMResponse:
    """Orchestrator synthesis — bilingual briefing."""
    briefing = {
        "situation_summary": (
            "Category 4 cyclone (VSCS) approaching Odisha coast. "
            "Landfall expected in Puri district within 12 hours. "
            "Wind speed 90kt, expected rainfall 200mm."
        ),
        "risk_assessment": (
            "High risk of storm surge in Puri and Ganjam coastal areas. "
            "Infrastructure failure expected in power grid and telecom."
        ),
        "resource_plan": (
            "Deploy 4 NDRF battalions to Puri and Ganjam. "
            "Pre-position relief at Khordha. Open 15 shelters."
        ),
        "communication_directives": (
            "Issue red alert in Odia and English via SMS, WhatsApp. "
            "Activate NDRF helpline 9711077372."
        ),
        "confidence": confidence,
    }
    return _make_llm_response(
        content=json.dumps(briefing),
        cost_usd=0.002,
        tier="critical",
    )


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


def _mock_agent(agent: BaseAgent) -> None:
    """Replace A2A client/server and LLM router with mocks on any agent."""
    agent._router = AsyncMock()
    agent._router.call = AsyncMock(return_value=_make_llm_response())
    agent._a2a_client = AsyncMock()
    agent._a2a_client.start = AsyncMock()
    agent._a2a_client.stop = AsyncMock()
    agent._a2a_client.send_result = AsyncMock()
    agent._a2a_client.on_message = MagicMock()
    agent._a2a_server = AsyncMock()
    agent._a2a_server.register_agent_card = AsyncMock()
    agent._a2a_server.send_task = AsyncMock()


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def settings() -> CrisisSettings:
    return _make_settings()


@pytest.fixture
def orchestrator(settings):
    agent = OrchestratorAgent(settings=settings)
    _mock_agent(agent)
    return agent


@pytest.fixture
def all_agents(settings):
    """Create all 7 agents with mocked dependencies."""
    agents = {}

    orch = OrchestratorAgent(settings=settings)
    _mock_agent(orch)
    agents["orchestrator"] = orch

    ss = SituationSense(settings=settings)
    _mock_agent(ss)
    agents["situation_sense"] = ss

    pr = PredictiveRisk(settings=settings)
    _mock_agent(pr)
    # Mock the embedding pipeline that PredictiveRisk uses
    pr._embedding_pipeline = MagicMock()
    pr._embedding_pipeline.query = AsyncMock(return_value=[])
    agents["predictive_risk"] = pr

    ra = ResourceAllocation(settings=settings)
    _mock_agent(ra)
    agents["resource_allocation"] = ra

    cc = CommunityComms(settings=settings)
    _mock_agent(cc)
    agents["community_comms"] = cc

    infra = InfraStatus(settings=settings)
    _mock_agent(infra)
    # Mock the infra graph manager
    infra._graph_manager = MagicMock()
    infra._graph_manager.get_downstream_affected = AsyncMock(return_value=[])
    agents["infra_status"] = infra

    hm = HistoricalMemory(settings=settings)
    _mock_agent(hm)
    # Mock the embedding pipeline
    hm._embedding_pipeline = MagicMock()
    hm._embedding_pipeline.query = AsyncMock(return_value=[])
    agents["historical_memory"] = hm

    return agents


@pytest.fixture
def ws_manager():
    return ConnectionManager()


# =============================================================================
# Test Group 1: Full Pipeline Smoke Test (O1)
# =============================================================================


class TestPipelineSmoke:
    """Validate the full SACHET → briefing pipeline end-to-end."""

    @pytest.mark.asyncio
    async def test_orchestrator_full_graph(self, orchestrator):
        """Orchestrator graph runs: parse → decompose → delegate → collect → synthesize."""
        orchestrator._router.call = AsyncMock(
            side_effect=[
                _make_decompose_response(),
                _make_synthesis_response(),
            ]
        )

        initial: AgentState = {
            "task": _make_mission_payload(),
            "disaster_id": str(uuid.uuid4()),
            "trace_id": "a0000001",
            "messages": [],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
        }

        result = await orchestrator.run_graph(initial)

        assert result.get("error") is None
        assert result.get("confidence", 0) > 0
        assert len(result.get("artifacts", [])) > 0

    @pytest.mark.asyncio
    async def test_pipeline_produces_briefing_with_all_sections(self, orchestrator):
        """Synthesized briefing has all required sections."""
        orchestrator._router.call = AsyncMock(
            side_effect=[
                _make_decompose_response(),
                _make_synthesis_response(),
            ]
        )

        initial: AgentState = {
            "task": _make_mission_payload(),
            "disaster_id": str(uuid.uuid4()),
            "trace_id": "a0000002",
            "messages": [],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
        }

        result = await orchestrator.run_graph(initial)
        briefing = result.get("artifacts", [{}])[0]

        assert "situation_summary" in briefing
        assert "risk_assessment" in briefing
        assert "resource_plan" in briefing
        assert "communication_directives" in briefing
        assert "confidence" in briefing

    @pytest.mark.asyncio
    async def test_pipeline_tracks_budget(self, orchestrator):
        """Budget is tracked across decomposition + synthesis LLM calls."""
        orchestrator._router.call = AsyncMock(
            side_effect=[
                _make_decompose_response(),  # cost_usd=0.001
                _make_synthesis_response(),  # cost_usd=0.002
            ]
        )

        initial: AgentState = {
            "task": _make_mission_payload(),
            "disaster_id": str(uuid.uuid4()),
            "trace_id": "a0000003",
            "messages": [],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
        }

        await orchestrator.run_graph(initial)

        assert orchestrator.budget_used == pytest.approx(0.003)


# =============================================================================
# Test Group 2: Phase-Based Agent Activation (O2)
# =============================================================================


class TestPhaseActivation:
    """Verify that the orchestrator activates correct agents per disaster phase."""

    def test_pre_event_excludes_resource_and_comms(self):
        agents = PHASE_AGENT_MAP[DisasterPhase.PRE_EVENT]
        assert AgentType.SITUATION_SENSE in agents
        assert AgentType.PREDICTIVE_RISK in agents
        assert AgentType.HISTORICAL_MEMORY in agents
        assert AgentType.RESOURCE_ALLOCATION not in agents
        assert AgentType.COMMUNITY_COMMS not in agents

    def test_active_response_includes_all_six(self):
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

    def test_recovery_excludes_situation_and_predictive(self):
        agents = PHASE_AGENT_MAP[DisasterPhase.RECOVERY]
        assert AgentType.SITUATION_SENSE not in agents
        assert AgentType.PREDICTIVE_RISK not in agents
        assert AgentType.RESOURCE_ALLOCATION in agents
        assert AgentType.INFRA_STATUS in agents

    @pytest.mark.asyncio
    async def test_decompose_filters_pre_event(self, orchestrator):
        """Sub-tasks for inactive agents are filtered out in PRE_EVENT phase."""
        all_agents_response = _make_decompose_response()  # has all 6 agents
        orchestrator._router.call = AsyncMock(return_value=all_agents_response)

        result = await orchestrator.decompose_mission(
            _make_mission_payload(),
            phase=DisasterPhase.PRE_EVENT,
            trace_id="aa000001",
        )

        target_agents = {t["target_agent"] for t in result}
        assert "resource_allocation" not in target_agents
        assert "community_comms" not in target_agents
        # These should remain
        assert "situation_sense" in target_agents
        assert "predictive_risk" in target_agents
        assert "historical_memory" in target_agents

    @pytest.mark.asyncio
    async def test_decompose_keeps_all_in_active_response(self, orchestrator):
        """All 6 specialist agents are kept in ACTIVE_RESPONSE phase."""
        orchestrator._router.call = AsyncMock(return_value=_make_decompose_response())

        result = await orchestrator.decompose_mission(
            _make_mission_payload(),
            phase=DisasterPhase.ACTIVE_RESPONSE,
            trace_id="aa000002",
        )

        target_agents = {t["target_agent"] for t in result}
        assert len(target_agents) == 6


# =============================================================================
# Test Group 3: Agent Task Flow (O3)
# =============================================================================


class TestAgentTaskFlow:
    """Validate task delegation and result collection."""

    @pytest.mark.asyncio
    async def test_delegate_sends_to_all_agents(self, orchestrator):
        """Orchestrator sends A2ATask to each specialist."""
        sub_tasks = json.loads(_make_decompose_response().content)["sub_tasks"]

        task_ids = await orchestrator.delegate_tasks(
            sub_tasks,
            disaster_id=uuid.uuid4(),
            parent_depth=0,
            trace_id="ff000001",
        )

        assert len(task_ids) == 6
        assert orchestrator._a2a_server.send_task.await_count == 6

    @pytest.mark.asyncio
    async def test_delegate_increments_depth(self, orchestrator):
        """Delegation depth increases by 1."""
        sub_tasks = [
            {
                "target_agent": "situation_sense",
                "task_type": "fuse_data",
                "priority": 1,
                "payload": {},
            },
        ]
        await orchestrator.delegate_tasks(
            sub_tasks,
            disaster_id=uuid.uuid4(),
            parent_depth=2,
            trace_id="ff000002",
        )

        sent_task = orchestrator._a2a_server.send_task.call_args[0][0]
        assert isinstance(sent_task, A2ATask)
        assert sent_task.depth == 3

    @pytest.mark.asyncio
    async def test_collect_with_all_results(self, orchestrator):
        """All results collected when available immediately."""
        task_ids = [uuid.uuid4() for _ in range(3)]
        results = {
            tid: _make_task_result(tid, f"agent_{i}")
            for i, tid in enumerate(task_ids)
        }

        collected = await orchestrator.collect_results(
            task_ids, results=results, timeout=2.0
        )

        assert len(collected) == 3
        assert all(r.status == TaskStatus.COMPLETED for r in collected.values())

    @pytest.mark.asyncio
    async def test_collect_timeout_produces_failed(self, orchestrator):
        """Missing results become FAILED after timeout."""
        task_ids = [uuid.uuid4(), uuid.uuid4()]
        results = {
            task_ids[0]: _make_task_result(task_ids[0], "situation_sense"),
        }

        collected = await orchestrator.collect_results(
            task_ids, results=results, timeout=0.1
        )

        assert len(collected) == 2
        statuses = {r.status for r in collected.values()}
        assert TaskStatus.COMPLETED in statuses
        assert TaskStatus.FAILED in statuses


# =============================================================================
# Test Group 4: Synthesis and Briefing (O4)
# =============================================================================


class TestSynthesis:
    """Validate briefing generation and escalation logic."""

    @pytest.mark.asyncio
    async def test_synthesize_produces_structured_briefing(self, orchestrator):
        """Synthesis returns a dict with all required briefing sections."""
        orchestrator._router.call = AsyncMock(
            return_value=_make_synthesis_response(confidence=0.85)
        )

        task_id = uuid.uuid4()
        agent_results = {
            task_id: _make_task_result(task_id, "situation_sense", confidence=0.9),
        }

        briefing = await orchestrator.synthesize_results(
            agent_results,
            mission=_make_mission_payload(),
            trace_id="bb000001",
        )

        assert "situation_summary" in briefing
        assert "risk_assessment" in briefing
        assert "resource_plan" in briefing
        assert "confidence" in briefing

    @pytest.mark.asyncio
    async def test_low_confidence_triggers_escalation(self, orchestrator):
        """Confidence < 0.7 sets needs_escalation = True."""
        orchestrator._router.call = AsyncMock(
            return_value=_make_synthesis_response(confidence=0.5)
        )

        task_id = uuid.uuid4()
        agent_results = {
            task_id: _make_task_result(task_id, "situation_sense", confidence=0.4),
        }

        briefing = await orchestrator.synthesize_results(
            agent_results,
            mission=_make_mission_payload(),
            trace_id="bb000002",
        )

        assert briefing["needs_escalation"] is True

    @pytest.mark.asyncio
    async def test_high_confidence_no_escalation(self, orchestrator):
        """Confidence >= 0.7 sets needs_escalation = False."""
        orchestrator._router.call = AsyncMock(
            return_value=_make_synthesis_response(confidence=0.9)
        )

        task_id = uuid.uuid4()
        agent_results = {
            task_id: _make_task_result(task_id, "situation_sense", confidence=0.9),
        }

        briefing = await orchestrator.synthesize_results(
            agent_results,
            mission=_make_mission_payload(),
            trace_id="bb000003",
        )

        assert briefing["needs_escalation"] is False

    @pytest.mark.asyncio
    async def test_synthesis_with_multiple_agent_results(self, orchestrator):
        """Synthesis handles results from all 6 specialist agents."""
        orchestrator._router.call = AsyncMock(
            return_value=_make_synthesis_response(confidence=0.88)
        )

        agent_ids = [
            "situation_sense", "predictive_risk", "resource_allocation",
            "community_comms", "infra_status", "historical_memory",
        ]
        agent_results = {}
        for aid in agent_ids:
            tid = uuid.uuid4()
            agent_results[tid] = _make_task_result(tid, aid, confidence=0.85)

        briefing = await orchestrator.synthesize_results(
            agent_results,
            mission=_make_mission_payload(),
            trace_id="bb000004",
        )

        assert briefing["confidence"] == pytest.approx(0.88)
        assert briefing["needs_escalation"] is False


# =============================================================================
# Test Group 5: WebSocket Dashboard Integration (O5)
# =============================================================================


class TestWebSocketIntegration:
    """Validate WebSocket broadcasting of agent events."""

    @pytest.mark.asyncio
    async def test_broadcast_agent_event(self, ws_manager):
        """Agent events are broadcast to clients on the 'agents' channel."""
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await ws_manager.connect(ws, channels={"agents"})

        await ws_manager.broadcast(
            "agent.status_update",
            {"agent_id": "orchestrator", "status": "running"},
            trace_id="cc000001",
        )

        ws.send_json.assert_awaited_once()
        msg = ws.send_json.call_args[0][0]
        assert msg["type"] == "agent.status_update"
        assert msg["data"]["agent_id"] == "orchestrator"

    @pytest.mark.asyncio
    async def test_broadcast_disaster_event(self, ws_manager):
        """Disaster events go to 'disasters' channel."""
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await ws_manager.connect(ws, channels={"disasters"})

        await ws_manager.broadcast(
            "disaster.new_alert",
            {"disaster_type": "cyclone", "severity": 4},
            trace_id="cc000002",
        )

        ws.send_json.assert_awaited_once()
        msg = ws.send_json.call_args[0][0]
        assert msg["type"] == "disaster.new_alert"

    @pytest.mark.asyncio
    async def test_channel_filtering(self, ws_manager):
        """Client subscribed to 'agents' does NOT receive 'disasters' events."""
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await ws_manager.connect(ws, channels={"agents"})

        await ws_manager.broadcast(
            "disaster.new_alert",
            {"disaster_type": "cyclone"},
            trace_id="cc000003",
        )

        ws.send_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_multiple_clients(self, ws_manager):
        """Multiple clients receive the same broadcast."""
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()

        await ws_manager.connect(ws1, channels={"agents"})
        await ws_manager.connect(ws2, channels={"agents"})

        await ws_manager.broadcast(
            "agent.task_completed",
            {"agent_id": "situation_sense", "task_id": "t001"},
            trace_id="cc000004",
        )

        ws1.send_json.assert_awaited_once()
        ws2.send_json.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_removes_client(self, ws_manager):
        """Disconnected client no longer receives broadcasts."""
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        client_id = await ws_manager.connect(ws, channels={"agents"})
        await ws_manager.disconnect(client_id)

        await ws_manager.broadcast(
            "agent.status_update",
            {"agent_id": "orchestrator"},
            trace_id="cc000005",
        )

        ws.send_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_metrics_event_routing(self, ws_manager):
        """Metrics events go to 'metrics' channel."""
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await ws_manager.connect(ws, channels={"metrics"})

        await ws_manager.broadcast(
            "metrics.cost_update",
            {"total_cost_usd": 0.003, "provider": "ollama_local"},
            trace_id="cc000006",
        )

        ws.send_json.assert_awaited_once()
        msg = ws.send_json.call_args[0][0]
        assert msg["data"]["total_cost_usd"] == 0.003


# =============================================================================
# Test Group 6: Error Resilience (O6)
# =============================================================================


class TestErrorResilience:
    """Validate graceful degradation when agents or LLM calls fail."""

    @pytest.mark.asyncio
    async def test_pipeline_survives_agent_failure(self, orchestrator):
        """Pipeline completes even when synthesis gets partial (failed) results."""
        orchestrator._router.call = AsyncMock(
            side_effect=[
                _make_decompose_response(),
                _make_synthesis_response(confidence=0.6),
            ]
        )

        initial: AgentState = {
            "task": _make_mission_payload(),
            "disaster_id": str(uuid.uuid4()),
            "trace_id": "e0000001",
            "messages": [],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
        }

        # This should complete without exception even though collect will
        # produce FAILED results (since no real agents are responding)
        result = await orchestrator.run_graph(initial)
        assert result is not None
        assert result.get("confidence", 0) > 0

    @pytest.mark.asyncio
    async def test_invalid_json_decompose_returns_empty(self, orchestrator):
        """Invalid JSON from LLM during decompose → empty sub-task list."""
        orchestrator._router.call = AsyncMock(
            return_value=_make_llm_response(content="NOT JSON AT ALL")
        )

        result = await orchestrator.decompose_mission(
            _make_mission_payload(),
            phase=DisasterPhase.ACTIVE_RESPONSE,
            trace_id="e0000002",
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_invalid_json_synthesis_returns_fallback(self, orchestrator):
        """Invalid JSON from LLM during synthesis → fallback briefing."""
        orchestrator._router.call = AsyncMock(
            return_value=_make_llm_response(content="invalid json response")
        )

        task_id = uuid.uuid4()
        agent_results = {
            task_id: _make_task_result(task_id, "situation_sense"),
        }

        briefing = await orchestrator.synthesize_results(
            agent_results,
            mission=_make_mission_payload(),
            trace_id="e0000003",
        )

        assert isinstance(briefing, dict)
        # Should have either error or situation_summary fallback
        assert "error" in briefing or "situation_summary" in briefing

    @pytest.mark.asyncio
    async def test_budget_tracking_after_multiple_calls(self, orchestrator):
        """Budget accumulates correctly across multiple LLM calls."""
        orchestrator._router.call = AsyncMock(
            side_effect=[
                _make_llm_response(cost_usd=0.01),
                _make_llm_response(cost_usd=0.02),
                _make_llm_response(cost_usd=0.03),
            ]
        )

        for _ in range(3):
            resp = await orchestrator.reason(
                [{"role": "user", "content": "test"}],
                trace_id="e0000004",
            )
            orchestrator.track_cost(resp.cost_usd)

        assert orchestrator.budget_used == pytest.approx(0.06)

    @pytest.mark.asyncio
    async def test_empty_results_synthesis(self, orchestrator):
        """Synthesis with no agent results still returns a briefing."""
        orchestrator._router.call = AsyncMock(
            return_value=_make_synthesis_response(confidence=0.3)
        )

        briefing = await orchestrator.synthesize_results(
            {},
            mission=_make_mission_payload(),
            trace_id="e0000005",
        )

        assert isinstance(briefing, dict)
        assert "confidence" in briefing

    @pytest.mark.asyncio
    async def test_websocket_handles_disconnected_client(self, ws_manager):
        """Broadcasting to a client that throws doesn't crash the manager."""
        ws_good = AsyncMock()
        ws_good.accept = AsyncMock()
        ws_good.send_json = AsyncMock()

        ws_bad = AsyncMock()
        ws_bad.accept = AsyncMock()
        ws_bad.send_json = AsyncMock(side_effect=RuntimeError("connection lost"))

        await ws_manager.connect(ws_good, channels={"agents"})
        await ws_manager.connect(ws_bad, channels={"agents"})

        # Should not raise despite ws_bad failing
        await ws_manager.broadcast(
            "agent.status_update",
            {"agent_id": "orchestrator"},
            trace_id="e0000006",
        )

        ws_good.send_json.assert_awaited_once()


# =============================================================================
# Test Group 7: Concurrent Agent Execution (O7)
# =============================================================================


class TestConcurrency:
    """Validate that multiple agents can process tasks concurrently."""

    @pytest.mark.asyncio
    async def test_concurrent_agent_graph_execution(self, all_agents):
        """Multiple agent graphs run concurrently without interference."""
        agents_to_run = ["situation_sense", "predictive_risk", "resource_allocation"]

        # Agent-specific LLM mock responses matching what each graph node expects
        _agent_responses = {
            "situation_sense": [
                # _fuse_sources
                json.dumps({
                    "summary": "Cyclone approaching Odisha",
                    "affected_areas": ["Puri", "Ganjam"],
                    "severity": "extreme",
                    "sources": ["IMD", "SACHET"],
                }),
                # _detect_misinfo
                json.dumps({"flags": []}),
                # _produce_sitrep
                json.dumps({
                    "type": "FeatureCollection",
                    "features": [],
                }),
            ],
            "predictive_risk": [
                # forecast_risk
                json.dumps({
                    "forecast": "Cyclone landfall in 12h",
                    "confidence": 0.8,
                    "trajectory": "NW towards Puri",
                }),
                # predict_cascading
                json.dumps({
                    "cascading_failures": [],
                    "risk_level": "high",
                }),
                # generate_risk_map
                json.dumps({
                    "type": "FeatureCollection",
                    "features": [],
                }),
                # produce_report
                json.dumps({
                    "summary": "High risk cyclone scenario",
                    "confidence": 0.85,
                }),
            ],
            "resource_allocation": [
                # assess_demand
                json.dumps({
                    "demand": [{"district": "Puri", "population": 100000}],
                }),
                # inventory_resources
                json.dumps({
                    "inventory": [{"type": "NDRF", "count": 4}],
                }),
                # optimize_allocation
                json.dumps({
                    "allocation": {"Puri": 2, "Ganjam": 2},
                    "total_cost": 0.0,
                }),
                # format_plan
                json.dumps({
                    "plan": "Deploy 4 NDRF battalions",
                    "confidence": 0.9,
                }),
            ],
        }

        async def run_agent(agent_id: str):
            agent = all_agents[agent_id]
            responses = _agent_responses[agent_id]
            agent._router.call = AsyncMock(
                side_effect=[_make_llm_response(content=c) for c in responses]
            )

            # Build task payload with structured dicts for resource_allocation
            task = _make_mission_payload()
            task["affected_districts"] = [
                {"name": "Puri", "state": "Odisha", "population": 50000,
                 "severity": 4, "lat": 19.81, "lon": 85.83},
                {"name": "Ganjam", "state": "Odisha", "population": 40000,
                 "severity": 3, "lat": 19.38, "lon": 84.97},
            ]
            task["available_resources"] = {
                "ndrf_battalions": [
                    {"name": "1-NDRF", "base_lat": 20.27, "base_lon": 85.84,
                     "strength": 45},
                ],
                "shelters": [
                    {"name": "Puri Stadium", "capacity": 500,
                     "current_occupancy": 0},
                ],
                "relief_kits": 1000,
            }

            initial: AgentState = {
                "task": task,
                "disaster_id": str(uuid.uuid4()),
                "trace_id": uuid.uuid4().hex[:8],
                "messages": [],
                "reasoning": "",
                "confidence": 0.0,
                "artifacts": [],
                "error": None,
                "iteration": 0,
                "metadata": {},
            }
            return await agent.run_graph(initial)

        results = await asyncio.gather(
            *[run_agent(aid) for aid in agents_to_run],
            return_exceptions=True,
        )

        # All should complete (may succeed or fail gracefully)
        assert len(results) == 3
        for r in results:
            assert not isinstance(r, Exception), f"Agent raised: {r}"

    @pytest.mark.asyncio
    async def test_result_attribution(self, orchestrator):
        """Results from different agents are correctly attributed."""
        agent_ids = ["situation_sense", "predictive_risk", "resource_allocation"]
        task_ids = [uuid.uuid4() for _ in agent_ids]

        results = {
            tid: _make_task_result(tid, aid)
            for tid, aid in zip(task_ids, agent_ids)
        }

        collected = await orchestrator.collect_results(
            task_ids, results=results, timeout=2.0
        )

        for tid, aid in zip(task_ids, agent_ids):
            assert collected[tid].agent_id == aid

    @pytest.mark.asyncio
    async def test_concurrent_websocket_broadcasts(self, ws_manager):
        """Multiple concurrent broadcasts don't interfere."""
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await ws_manager.connect(ws, channels={"agents", "disasters", "metrics"})

        await asyncio.gather(
            ws_manager.broadcast("agent.update", {"id": 1}, trace_id="dd000001"),
            ws_manager.broadcast("disaster.alert", {"id": 2}, trace_id="dd000002"),
            ws_manager.broadcast("metrics.cost", {"id": 3}, trace_id="dd000003"),
        )

        assert ws.send_json.await_count == 3


# =============================================================================
# Test Group 8: Individual Agent Initialization (cross-cutting)
# =============================================================================


class TestAgentInitialization:
    """Validate all 7 agents initialize correctly with test settings."""

    def test_all_agents_have_correct_ids(self, all_agents):
        expected_ids = {
            "orchestrator", "situation_sense", "predictive_risk",
            "resource_allocation", "community_comms", "infra_status",
            "historical_memory",
        }
        assert set(all_agents.keys()) == expected_ids

    def test_all_agents_have_system_prompts(self, all_agents):
        for agent_id, agent in all_agents.items():
            prompt = agent.get_system_prompt()
            assert isinstance(prompt, str), f"{agent_id} has no system prompt"
            assert len(prompt) > 50, f"{agent_id} system prompt too short"

    def test_all_agents_have_agent_cards(self, all_agents):
        for agent_id, agent in all_agents.items():
            card = agent.get_agent_card()
            assert isinstance(card, A2AAgentCard), f"{agent_id} bad agent card"
            assert card.agent_id == agent_id
            assert len(card.capabilities) > 0

    def test_all_agents_build_graphs(self, all_agents):
        for agent_id, agent in all_agents.items():
            graph = agent.build_graph()
            assert graph is not None, f"{agent_id} build_graph returned None"

    def test_orchestrator_uses_critical_tier(self, all_agents):
        assert all_agents["orchestrator"].llm_tier == LLMTier.CRITICAL

    def test_situation_sense_uses_routine_tier(self, all_agents):
        assert all_agents["situation_sense"].llm_tier == LLMTier.ROUTINE

    def test_health_check_all_agents(self, all_agents):
        for agent_id, agent in all_agents.items():
            h = agent.health()
            assert h["agent_id"] == agent_id
            assert "status" in h
            assert "active_tasks" in h
