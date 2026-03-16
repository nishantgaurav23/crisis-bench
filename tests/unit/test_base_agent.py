"""Tests for BaseAgent — LangGraph state machine + LLM Router + A2A integration.

Tests cover: initialization, abstract enforcement, state machine execution,
LLM reasoning, A2A task handling, health checks, metrics, edge cases.
All external services (Redis, LLM providers) are mocked.
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.base import AgentState, BaseAgent
from src.protocols.a2a.schemas import (
    A2AAgentCard,
    A2AMessage,
    A2AMessageType,
    A2ATask,
    A2ATaskResult,
)
from src.routing.llm_router import LLMResponse, LLMTier
from src.shared.config import CrisisSettings
from src.shared.errors import AgentTimeoutError
from src.shared.models import AgentType, TaskStatus

# =============================================================================
# Test helpers — concrete subclass for testing
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


class ConcreteAgent(BaseAgent):
    """Minimal concrete subclass for testing BaseAgent."""

    def build_graph(self):
        from langgraph.graph import END, StateGraph

        graph = StateGraph(AgentState)

        async def process_node(state: AgentState) -> dict[str, Any]:
            msgs = state.get("messages", [])
            if msgs:
                resp = await self.reason(msgs, trace_id=state.get("trace_id", ""))
                return {
                    "reasoning": resp.content,
                    "confidence": 0.85,
                }
            return {"reasoning": "no messages", "confidence": 0.5}

        graph.add_node("process", process_node)
        graph.set_entry_point("process")
        graph.add_edge("process", END)
        return graph

    def get_system_prompt(self) -> str:
        return "You are a test agent."

    def get_agent_card(self) -> A2AAgentCard:
        return A2AAgentCard(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            name="Test Agent",
            description="A test agent for unit tests",
            capabilities=["testing"],
            llm_tier=self.llm_tier,
        )


class SlowAgent(BaseAgent):
    """Agent that takes too long, for timeout testing."""

    def build_graph(self):
        from langgraph.graph import END, StateGraph

        graph = StateGraph(AgentState)

        async def slow_node(state: AgentState) -> dict[str, Any]:
            await asyncio.sleep(30)  # Way longer than timeout
            return {"reasoning": "done"}

        graph.add_node("slow", slow_node)
        graph.set_entry_point("slow")
        graph.add_edge("slow", END)
        return graph

    def get_system_prompt(self) -> str:
        return "You are slow."

    def get_agent_card(self) -> A2AAgentCard:
        return A2AAgentCard(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            name="Slow Agent",
            description="Slow",
            capabilities=[],
            llm_tier=self.llm_tier,
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
    router.call = AsyncMock(return_value=_make_llm_response())
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
def agent(settings, mock_router, mock_a2a_client, mock_a2a_server):
    a = ConcreteAgent(
        agent_id="test_agent",
        agent_type=AgentType.SITUATION_SENSE,
        llm_tier=LLMTier.ROUTINE,
        settings=settings,
    )
    a._router = mock_router
    a._a2a_client = mock_a2a_client
    a._a2a_server = mock_a2a_server
    return a


def _make_task_message(
    target: str = "test_agent",
    depth: int = 0,
    task_type: str = "analyze",
    payload: dict | None = None,
) -> A2AMessage:
    task = A2ATask(
        source_agent="orchestrator",
        target_agent=target,
        task_type=task_type,
        payload=payload or {"data": "test"},
        priority=3,
        depth=depth,
    )
    return A2AMessage(
        message_type=A2AMessageType.TASK_SEND,
        source_agent="orchestrator",
        target_agent=target,
        payload=task.model_dump(mode="json"),
    )


# =============================================================================
# Test Group 1: Initialization & Abstract Enforcement
# =============================================================================


class TestInitialization:
    def test_base_agent_cannot_be_instantiated(self, settings):
        """BaseAgent is abstract — direct instantiation must fail."""
        with pytest.raises(TypeError, match="abstract"):
            BaseAgent(
                agent_id="x",
                agent_type=AgentType.ORCHESTRATOR,
                llm_tier=LLMTier.CRITICAL,
                settings=settings,
            )

    def test_concrete_subclass_creates(self, settings):
        """A concrete subclass with all abstract methods should instantiate."""
        a = ConcreteAgent(
            agent_id="test",
            agent_type=AgentType.SITUATION_SENSE,
            llm_tier=LLMTier.ROUTINE,
            settings=settings,
        )
        assert a.agent_id == "test"
        assert a.agent_type == AgentType.SITUATION_SENSE
        assert a.llm_tier == LLMTier.ROUTINE

    def test_agent_has_router(self, agent):
        """Agent must have an LLM router."""
        assert agent._router is not None

    def test_agent_has_a2a_client(self, agent):
        """Agent must have an A2A client."""
        assert agent._a2a_client is not None

    def test_agent_has_a2a_server(self, agent):
        """Agent must have an A2A server."""
        assert agent._a2a_server is not None

    def test_agent_default_state(self, agent):
        """Agent should start with zero active tasks."""
        h = agent.health()
        assert h["active_tasks"] == 0


# =============================================================================
# Test Group 2: State Machine
# =============================================================================


class TestStateMachine:
    def test_agent_state_has_expected_keys(self):
        """AgentState TypedDict should support all expected keys."""
        state: AgentState = {
            "task": {},
            "disaster_id": None,
            "trace_id": "abc12345",
            "messages": [],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
        }
        assert state["trace_id"] == "abc12345"
        assert state["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_run_graph_executes(self, agent):
        """run_graph should execute the graph and return final state."""
        initial: AgentState = {
            "task": {},
            "trace_id": "test1234",
            "messages": [{"role": "user", "content": "Hello"}],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
        }
        result = await agent.run_graph(initial)
        assert result["reasoning"] == "test output"
        assert result["confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_run_graph_timeout(self, settings):
        """Graph execution exceeding timeout should raise AgentTimeoutError."""
        slow = SlowAgent(
            agent_id="slow",
            agent_type=AgentType.SITUATION_SENSE,
            llm_tier=LLMTier.ROUTINE,
            settings=_make_settings(AGENT_TIMEOUT_SECONDS=1),
        )
        initial: AgentState = {
            "task": {},
            "trace_id": "slow1234",
            "messages": [],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
        }
        with pytest.raises(AgentTimeoutError):
            await slow.run_graph(initial)


# =============================================================================
# Test Group 3: LLM Reasoning
# =============================================================================


class TestReasoning:
    @pytest.mark.asyncio
    async def test_reason_calls_router(self, agent, mock_router):
        """reason() should delegate to LLMRouter.call()."""
        messages = [{"role": "user", "content": "test"}]
        result = await agent.reason(messages)
        mock_router.call.assert_awaited_once()
        assert result.content == "test output"

    @pytest.mark.asyncio
    async def test_reason_uses_default_tier(self, agent, mock_router):
        """reason() should use the agent's default tier."""
        await agent.reason([{"role": "user", "content": "test"}])
        call_args = mock_router.call.call_args
        assert call_args[0][0] == LLMTier.ROUTINE  # agent's default

    @pytest.mark.asyncio
    async def test_reason_tier_override(self, agent, mock_router):
        """reason() should accept a tier override."""
        await agent.reason(
            [{"role": "user", "content": "urgent"}],
            tier=LLMTier.CRITICAL,
        )
        call_args = mock_router.call.call_args
        assert call_args[0][0] == LLMTier.CRITICAL

    @pytest.mark.asyncio
    async def test_reason_propagates_trace_id(self, agent, mock_router):
        """reason() should pass trace_id to the router."""
        await agent.reason(
            [{"role": "user", "content": "test"}],
            trace_id="abcd1234",
        )
        call_kwargs = mock_router.call.call_args[1]
        assert call_kwargs["trace_id"] == "abcd1234"

    @pytest.mark.asyncio
    async def test_reason_empty_messages_raises(self, agent):
        """reason() with empty messages should raise ValueError."""
        with pytest.raises(ValueError, match="messages"):
            await agent.reason([])


# =============================================================================
# Test Group 4: A2A Integration
# =============================================================================


class TestA2AIntegration:
    @pytest.mark.asyncio
    async def test_start_registers_card(self, agent, mock_a2a_server, mock_a2a_client):
        """start() should register the agent card and start listening."""
        await agent.start()
        mock_a2a_server.register_agent_card.assert_awaited_once()
        mock_a2a_client.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_registers_task_handler(self, agent, mock_a2a_client):
        """start() should register a handler for TASK_SEND messages."""
        await agent.start()
        mock_a2a_client.on_message.assert_called()
        call_args = mock_a2a_client.on_message.call_args_list
        types_registered = [c[0][0] for c in call_args]
        assert A2AMessageType.TASK_SEND in types_registered

    @pytest.mark.asyncio
    async def test_handle_task_sends_result(self, agent, mock_a2a_client):
        """handle_task should process task and send back a result."""
        msg = _make_task_message()
        await agent.handle_task(msg)
        mock_a2a_client.send_result.assert_awaited_once()
        result_arg = mock_a2a_client.send_result.call_args[0][0]
        assert isinstance(result_arg, A2ATaskResult)
        assert result_arg.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_handle_task_rejects_deep_delegation(self, agent, mock_a2a_client):
        """Tasks at max depth should be rejected with FAILED status."""
        # Build a raw payload with depth > max (bypasses A2ATask Pydantic validation
        # since the message payload is a dict parsed inside handle_task)
        task = A2ATask(
            source_agent="orchestrator",
            target_agent="test_agent",
            task_type="analyze",
            payload={"data": "test"},
            priority=3,
            depth=5,  # max allowed by schema
        )
        payload = task.model_dump(mode="json")
        payload["depth"] = 6  # exceed the max in raw dict

        msg = A2AMessage(
            message_type=A2AMessageType.TASK_SEND,
            source_agent="orchestrator",
            target_agent="test_agent",
            payload=payload,
        )
        await agent.handle_task(msg)
        mock_a2a_client.send_result.assert_awaited_once()
        result_arg = mock_a2a_client.send_result.call_args[0][0]
        # Should fail at either Pydantic validation or depth check
        assert result_arg.status == TaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_handle_task_sends_failure_on_error(self, agent, mock_router, mock_a2a_client):
        """If graph execution fails, handle_task should send FAILED result."""
        mock_router.call.side_effect = RuntimeError("LLM down")
        msg = _make_task_message()
        await agent.handle_task(msg)
        mock_a2a_client.send_result.assert_awaited_once()
        result_arg = mock_a2a_client.send_result.call_args[0][0]
        assert result_arg.status == TaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_stop_shuts_down(self, agent, mock_a2a_client):
        """stop() should call client.stop()."""
        await agent.start()
        await agent.stop()
        mock_a2a_client.stop.assert_awaited_once()


# =============================================================================
# Test Group 5: Health & Metrics
# =============================================================================


class TestHealthAndMetrics:
    def test_health_returns_expected_fields(self, agent):
        """health() should return agent_id, status, active_tasks, uptime."""
        h = agent.health()
        assert "agent_id" in h
        assert "status" in h
        assert "active_tasks" in h
        assert "agent_type" in h
        assert h["agent_id"] == "test_agent"

    @pytest.mark.asyncio
    async def test_health_shows_running_after_start(self, agent):
        """After start(), health status should be 'running'."""
        await agent.start()
        h = agent.health()
        assert h["status"] == "running"

    @pytest.mark.asyncio
    async def test_active_task_count_increments(self, agent, mock_a2a_client):
        """Active task count should increment during task processing."""
        observed_counts = []

        original_run_graph = agent.run_graph

        async def capturing_run_graph(state):
            observed_counts.append(agent.health()["active_tasks"])
            return await original_run_graph(state)

        agent.run_graph = capturing_run_graph
        msg = _make_task_message()
        await agent.handle_task(msg)
        assert any(c >= 1 for c in observed_counts)
        # After completion, count should be back to 0
        assert agent.health()["active_tasks"] == 0


# =============================================================================
# Test Group 6: Edge Cases
# =============================================================================


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_handle_task_missing_payload(self, agent, mock_a2a_client):
        """A message with invalid payload should result in FAILED status."""
        msg = A2AMessage(
            message_type=A2AMessageType.TASK_SEND,
            source_agent="orchestrator",
            target_agent="test_agent",
            payload={},  # Missing required fields for A2ATask
        )
        await agent.handle_task(msg)
        mock_a2a_client.send_result.assert_awaited_once()
        result_arg = mock_a2a_client.send_result.call_args[0][0]
        assert result_arg.status == TaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_run_graph_no_messages(self, agent):
        """Graph should handle empty messages gracefully."""
        state: AgentState = {
            "task": {},
            "trace_id": "nomsg123",
            "messages": [],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {},
        }
        result = await agent.run_graph(state)
        assert result["reasoning"] == "no messages"
        assert result["confidence"] == 0.5

    def test_get_system_prompt_returns_string(self, agent):
        """get_system_prompt must return a non-empty string."""
        prompt = agent.get_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_get_agent_card_returns_card(self, agent):
        """get_agent_card must return an A2AAgentCard."""
        card = agent.get_agent_card()
        assert isinstance(card, A2AAgentCard)
        assert card.agent_id == "test_agent"
        assert card.agent_type == AgentType.SITUATION_SENSE
