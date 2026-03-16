"""Tests for S9.3 — Langfuse Full Integration.

Tests the enhanced LangfuseTracer with hierarchical tracing,
prompt versioning, session grouping, cost attribution, and
integration with BaseAgent and LLM Router.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.shared.config import CrisisSettings
from src.shared.telemetry import LangfuseTracer

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_settings() -> CrisisSettings:
    """CrisisSettings with defaults (no real Langfuse)."""
    return CrisisSettings(
        LANGFUSE_HOST="http://localhost:4000",
        LANGFUSE_SECRET="test-secret",
        LANGFUSE_SALT="test-salt",
    )


@pytest.fixture
def mock_langfuse_client() -> MagicMock:
    """A fully mocked Langfuse client."""
    client = MagicMock()
    # trace() returns a mock trace handle
    mock_trace = MagicMock()
    mock_trace.span.return_value = MagicMock()
    mock_trace.generation.return_value = MagicMock()
    client.trace.return_value = mock_trace
    # Prompt management
    mock_prompt = MagicMock()
    mock_prompt.prompt = "You are a disaster response agent."
    mock_prompt.version = 1
    client.get_prompt.return_value = mock_prompt
    client.create_prompt.return_value = mock_prompt
    client.flush.return_value = None
    return client


@pytest.fixture
def enabled_tracer(mock_settings: CrisisSettings, mock_langfuse_client: MagicMock) -> LangfuseTracer:
    """A LangfuseTracer with a mocked client (enabled)."""
    with patch("src.shared.telemetry.Langfuse", return_value=mock_langfuse_client):
        tracer = LangfuseTracer(mock_settings)
    assert tracer.enabled
    return tracer


@pytest.fixture
def disabled_tracer(mock_settings: CrisisSettings) -> LangfuseTracer:
    """A LangfuseTracer that's disabled (Langfuse unavailable)."""
    with patch("src.shared.telemetry.Langfuse", side_effect=ImportError("no langfuse")):
        tracer = LangfuseTracer(mock_settings)
    assert not tracer.enabled
    return tracer


# =============================================================================
# Test: Enhanced LangfuseTracer API
# =============================================================================


class TestStartTrace:
    """Test trace creation."""

    def test_start_trace_returns_handle(self, enabled_tracer: LangfuseTracer) -> None:
        handle = enabled_tracer.start_trace(
            name="test_task",
            agent_id="orchestrator",
            trace_id="tr-001",
        )
        assert handle is not None

    def test_start_trace_disabled_returns_none(self, disabled_tracer: LangfuseTracer) -> None:
        handle = disabled_tracer.start_trace(
            name="test_task",
            agent_id="orchestrator",
            trace_id="tr-001",
        )
        assert handle is None

    def test_start_trace_with_session_id(
        self, enabled_tracer: LangfuseTracer, mock_langfuse_client: MagicMock
    ) -> None:
        """Trace carries session_id for benchmark scenario grouping."""
        enabled_tracer.start_trace(
            name="scenario_run",
            agent_id="orchestrator",
            trace_id="tr-002",
            session_id="scenario-cyclone-001",
        )
        call_kwargs = mock_langfuse_client.trace.call_args
        # session_id should be passed to the Langfuse trace call
        assert call_kwargs is not None
        # Check keyword argument or positional
        kwargs = call_kwargs.kwargs if call_kwargs.kwargs else {}
        assert kwargs.get("session_id") == "scenario-cyclone-001"

    def test_start_trace_includes_metadata(
        self, enabled_tracer: LangfuseTracer, mock_langfuse_client: MagicMock
    ) -> None:
        enabled_tracer.start_trace(
            name="task",
            agent_id="situation_sense",
            trace_id="tr-003",
            metadata={"disaster_id": "d-123"},
        )
        call_kwargs = mock_langfuse_client.trace.call_args.kwargs
        meta = call_kwargs.get("metadata", {})
        assert meta.get("agent_id") == "situation_sense"
        assert meta.get("disaster_id") == "d-123"


class TestSpans:
    """Test span creation within traces."""

    def test_start_span_under_trace(self, enabled_tracer: LangfuseTracer) -> None:
        trace_handle = enabled_tracer.start_trace(name="task", agent_id="agent1")
        span_handle = enabled_tracer.start_span(
            trace_handle=trace_handle,
            name="graph_node:analyze",
        )
        assert span_handle is not None

    def test_start_span_disabled_returns_none(self, disabled_tracer: LangfuseTracer) -> None:
        span_handle = disabled_tracer.start_span(
            trace_handle=None,
            name="graph_node:analyze",
        )
        assert span_handle is None

    def test_end_span_with_output(self, enabled_tracer: LangfuseTracer) -> None:
        trace_handle = enabled_tracer.start_trace(name="task", agent_id="agent1")
        span_handle = enabled_tracer.start_span(
            trace_handle=trace_handle,
            name="graph_node:analyze",
        )
        # Should not raise
        enabled_tracer.end_span(span_handle, output="analysis complete")

    def test_end_span_none_handle(self, disabled_tracer: LangfuseTracer) -> None:
        # Should be no-op, not raise
        disabled_tracer.end_span(None, output="nope")


class TestLogGeneration:
    """Test LLM generation logging."""

    def test_log_generation_with_cost(self, enabled_tracer: LangfuseTracer) -> None:
        trace_handle = enabled_tracer.start_trace(name="task", agent_id="agent1")
        # Should not raise
        enabled_tracer.log_generation(
            parent_handle=trace_handle,
            name="llm:deepseek-chat",
            model="deepseek-chat",
            messages=[{"role": "user", "content": "hello"}],
            response="world",
            tokens_in=10,
            tokens_out=5,
            cost=0.001,
            latency_s=0.5,
            metadata={"tier": "standard", "provider": "DeepSeek Chat"},
        )

    def test_log_generation_disabled(self, disabled_tracer: LangfuseTracer) -> None:
        # Should be no-op
        disabled_tracer.log_generation(
            parent_handle=None,
            name="llm:deepseek-chat",
            model="deepseek-chat",
            messages=[],
            response="",
            tokens_in=0,
            tokens_out=0,
            cost=0.0,
            latency_s=0.0,
        )

    def test_log_generation_under_span(self, enabled_tracer: LangfuseTracer) -> None:
        trace_handle = enabled_tracer.start_trace(name="task", agent_id="agent1")
        span_handle = enabled_tracer.start_span(trace_handle=trace_handle, name="reasoning")
        # Generation nested under span
        enabled_tracer.log_generation(
            parent_handle=span_handle,
            name="llm:qwen-flash",
            model="qwen-plus",
            messages=[{"role": "user", "content": "classify"}],
            response="category: flood",
            tokens_in=8,
            tokens_out=3,
            cost=0.0001,
            latency_s=0.2,
        )


class TestPromptVersioning:
    """Test prompt registration and retrieval."""

    def test_register_prompt(
        self, enabled_tracer: LangfuseTracer, mock_langfuse_client: MagicMock
    ) -> None:
        result = enabled_tracer.register_prompt(
            name="orchestrator_system",
            prompt="You are the disaster response orchestrator.",
            labels=["production"],
        )
        assert result is not None
        mock_langfuse_client.create_prompt.assert_called_once()

    def test_register_prompt_disabled(self, disabled_tracer: LangfuseTracer) -> None:
        result = disabled_tracer.register_prompt(
            name="orchestrator_system",
            prompt="You are the disaster response orchestrator.",
        )
        assert result is None

    def test_get_prompt(
        self, enabled_tracer: LangfuseTracer, mock_langfuse_client: MagicMock
    ) -> None:
        result = enabled_tracer.get_prompt(name="orchestrator_system")
        assert result is not None
        assert result.prompt == "You are a disaster response agent."
        mock_langfuse_client.get_prompt.assert_called_once()

    def test_get_prompt_disabled(self, disabled_tracer: LangfuseTracer) -> None:
        result = disabled_tracer.get_prompt(name="orchestrator_system")
        assert result is None


class TestEndTrace:
    """Test trace completion."""

    def test_end_trace_success(self, enabled_tracer: LangfuseTracer) -> None:
        handle = enabled_tracer.start_trace(name="task", agent_id="agent1")
        # Should not raise
        enabled_tracer.end_trace(handle, output="done", status="ok")

    def test_end_trace_failure(self, enabled_tracer: LangfuseTracer) -> None:
        handle = enabled_tracer.start_trace(name="task", agent_id="agent1")
        enabled_tracer.end_trace(handle, output="error occurred", status="error")

    def test_end_trace_none_handle(self, disabled_tracer: LangfuseTracer) -> None:
        # No-op
        disabled_tracer.end_trace(None, output="nope", status="ok")


class TestGracefulDegradation:
    """Test that errors in tracing never leak to business logic."""

    def test_trace_exception_swallowed(self, enabled_tracer: LangfuseTracer) -> None:
        """If Langfuse client.trace() raises, start_trace returns None."""
        enabled_tracer._client.trace.side_effect = RuntimeError("connection refused")
        handle = enabled_tracer.start_trace(name="task", agent_id="agent1")
        assert handle is None

    def test_span_exception_swallowed(self, enabled_tracer: LangfuseTracer) -> None:
        """If span creation fails, returns None."""
        trace_handle = MagicMock()
        trace_handle.span.side_effect = RuntimeError("oops")
        handle = enabled_tracer.start_span(trace_handle=trace_handle, name="node")
        assert handle is None

    def test_generation_exception_swallowed(self, enabled_tracer: LangfuseTracer) -> None:
        """If generation logging fails, no exception propagates."""
        parent = MagicMock()
        parent.generation.side_effect = RuntimeError("network error")
        # Should not raise
        enabled_tracer.log_generation(
            parent_handle=parent,
            name="llm:test",
            model="test",
            messages=[],
            response="",
            tokens_in=0,
            tokens_out=0,
            cost=0.0,
            latency_s=0.0,
        )

    def test_flush_exception_swallowed(self, enabled_tracer: LangfuseTracer) -> None:
        enabled_tracer._client.flush.side_effect = RuntimeError("flush failed")
        # Should not raise
        enabled_tracer.shutdown()

    def test_prompt_register_exception_swallowed(self, enabled_tracer: LangfuseTracer) -> None:
        enabled_tracer._client.create_prompt.side_effect = RuntimeError("fail")
        result = enabled_tracer.register_prompt(name="test", prompt="test prompt")
        assert result is None

    def test_prompt_get_exception_swallowed(self, enabled_tracer: LangfuseTracer) -> None:
        enabled_tracer._client.get_prompt.side_effect = RuntimeError("fail")
        result = enabled_tracer.get_prompt(name="test")
        assert result is None


class TestFlushAndShutdown:
    """Test cleanup operations."""

    def test_shutdown_flushes_client(
        self, enabled_tracer: LangfuseTracer, mock_langfuse_client: MagicMock
    ) -> None:
        enabled_tracer.shutdown()
        mock_langfuse_client.flush.assert_called_once()

    def test_shutdown_disabled_no_error(self, disabled_tracer: LangfuseTracer) -> None:
        # Should not raise
        disabled_tracer.shutdown()


# =============================================================================
# Test: BaseAgent Integration
# =============================================================================


class TestBaseAgentLangfuseIntegration:
    """Test that BaseAgent creates traces and logs generations."""

    @pytest.fixture
    def mock_tracer(self) -> MagicMock:
        tracer = MagicMock(spec=LangfuseTracer)
        tracer.enabled = True
        mock_handle = MagicMock()
        tracer.start_trace.return_value = mock_handle
        tracer.start_span.return_value = MagicMock()
        return tracer

    @pytest.fixture
    def concrete_agent(self, mock_tracer: MagicMock) -> "BaseAgent":  # noqa: F821
        """Create a minimal concrete BaseAgent subclass for testing."""
        from langgraph.graph import StateGraph

        from src.agents.base import AgentState, BaseAgent
        from src.protocols.a2a.schemas import A2AAgentCard
        from src.routing.llm_router import LLMTier
        from src.shared.models import AgentType

        class TestAgent(BaseAgent):
            def build_graph(self) -> StateGraph:
                graph = StateGraph(AgentState)
                graph.add_node("noop", lambda state: state)
                graph.set_entry_point("noop")
                graph.set_finish_point("noop")
                return graph

            def get_system_prompt(self) -> str:
                return "You are a test agent."

            def get_agent_card(self) -> A2AAgentCard:
                return A2AAgentCard(
                    agent_id="test_agent",
                    name="Test Agent",
                    description="A test agent",
                    capabilities=["test"],
                )

        agent = TestAgent("test_agent", AgentType.SITUATION_SENSE, LLMTier.ROUTINE)
        agent._tracer = mock_tracer
        return agent

    @pytest.mark.asyncio
    async def test_handle_task_creates_trace(
        self, concrete_agent: "BaseAgent", mock_tracer: MagicMock  # noqa: F821
    ) -> None:
        """handle_task should create a Langfuse trace for the full task."""
        from src.protocols.a2a.schemas import A2AMessage, A2AMessageType, A2ATask

        task = A2ATask(
            source_agent="orchestrator",
            target_agent="test_agent",
            task_type="analyze",
            payload={"instruction": "analyze flood"},
            trace_id="ab12cd34",
        )
        msg = A2AMessage(
            message_type=A2AMessageType.TASK_SEND,
            source_agent="orchestrator",
            target_agent="test_agent",
            payload=task.model_dump(mode="json"),
            trace_id="ab12cd34",
        )

        # Mock A2A client and graph
        concrete_agent._a2a_client = AsyncMock()
        concrete_agent._compiled_graph = MagicMock()
        concrete_agent._compiled_graph.ainvoke = AsyncMock(return_value={
            "confidence": 0.9,
            "reasoning": "test",
        })

        await concrete_agent.handle_task(msg)

        # Verify trace was created
        mock_tracer.start_trace.assert_called_once()
        call_kwargs = mock_tracer.start_trace.call_args.kwargs
        assert call_kwargs.get("agent_id") == "test_agent"
        assert call_kwargs.get("trace_id") == "ab12cd34"

        # Verify trace was ended
        mock_tracer.end_trace.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_task_ends_trace_on_failure(
        self, concrete_agent: "BaseAgent", mock_tracer: MagicMock  # noqa: F821
    ) -> None:
        """handle_task should end trace with error status on failure."""
        from src.protocols.a2a.schemas import A2AMessage, A2AMessageType, A2ATask

        task = A2ATask(
            source_agent="orchestrator",
            target_agent="test_agent",
            task_type="analyze",
            payload={"instruction": "analyze"},
            trace_id="ef56ab78",
        )
        msg = A2AMessage(
            message_type=A2AMessageType.TASK_SEND,
            source_agent="orchestrator",
            target_agent="test_agent",
            payload=task.model_dump(mode="json"),
            trace_id="ef56ab78",
        )

        concrete_agent._a2a_client = AsyncMock()
        concrete_agent._compiled_graph = MagicMock()
        concrete_agent._compiled_graph.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))

        await concrete_agent.handle_task(msg)

        # Verify trace ended with error
        mock_tracer.end_trace.assert_called_once()
        end_kwargs = mock_tracer.end_trace.call_args.kwargs
        assert end_kwargs.get("status") == "error"


# =============================================================================
# Test: LLM Router Integration
# =============================================================================


class TestRouterLangfuseIntegration:
    """Test LLM Router passes trace handles through."""

    @pytest.fixture
    def mock_tracer_for_router(self) -> MagicMock:
        tracer = MagicMock(spec=LangfuseTracer)
        tracer.enabled = True
        tracer.start_trace.return_value = MagicMock()
        return tracer

    @pytest.mark.asyncio
    async def test_router_logs_generation_under_parent(
        self, mock_settings: CrisisSettings, mock_tracer_for_router: MagicMock
    ) -> None:
        """When parent_handle is provided, router logs generation under it."""
        from src.routing.llm_router import LLMRouter

        router = LLMRouter(mock_settings, tracer=mock_tracer_for_router)

        # Mock provider call to return a response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "test response"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5

        # Patch the actual provider call
        parent_handle = MagicMock()
        with patch.object(router, "_call_provider") as mock_call:
            mock_call.return_value = MagicMock(
                content="test",
                provider="test",
                model="test",
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.001,
                latency_s=0.5,
                tier="standard",
            )
            await router.call(
                "standard",
                [{"role": "user", "content": "hello"}],
                trace_id="tr-200",
                parent_handle=parent_handle,
            )

        # Verify tracer.log_generation was called with the parent handle
        mock_tracer_for_router.log_generation.assert_called_once()
        gen_kwargs = mock_tracer_for_router.log_generation.call_args.kwargs
        assert gen_kwargs.get("parent_handle") == parent_handle

    @pytest.mark.asyncio
    async def test_router_without_parent_handle_skips_generation(
        self, mock_settings: CrisisSettings, mock_tracer_for_router: MagicMock
    ) -> None:
        """When no parent_handle, router skips Langfuse generation logging."""
        from src.routing.llm_router import LLMRouter

        router = LLMRouter(mock_settings, tracer=mock_tracer_for_router)

        with patch.object(router, "_call_provider") as mock_call:
            mock_call.return_value = MagicMock(
                content="test",
                provider="test",
                model="test",
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.001,
                latency_s=0.5,
                tier="routine",
            )
            await router.call(
                "routine",
                [{"role": "user", "content": "hello"}],
                trace_id="tr-201",
            )

        # Without parent_handle, no generation is logged
        mock_tracer_for_router.log_generation.assert_not_called()
