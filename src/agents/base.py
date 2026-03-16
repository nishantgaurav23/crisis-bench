"""BaseAgent — Abstract base class for all CRISIS-BENCH agents.

Every agent is a LangGraph state machine with:
- LLM Router integration (all LLM calls via router.call)
- A2A protocol support (receive tasks, send results)
- Langfuse tracing (every LLM call traced)
- Health checks and Prometheus metrics
- Timeout enforcement and delegation depth guards

Subclasses must implement: build_graph(), get_system_prompt(), get_agent_card().

Usage:
    class MyAgent(BaseAgent):
        def build_graph(self):
            graph = StateGraph(AgentState)
            # ... add nodes and edges ...
            return graph

        def get_system_prompt(self) -> str:
            return "You are a specialist agent."

        def get_agent_card(self) -> A2AAgentCard:
            return A2AAgentCard(...)

    agent = MyAgent("my_agent", AgentType.SITUATION_SENSE, LLMTier.ROUTINE)
    await agent.start()
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, TypedDict

from langgraph.graph import StateGraph

from src.protocols.a2a.client import A2AClient
from src.protocols.a2a.schemas import (
    A2AAgentCard,
    A2AMessage,
    A2AMessageType,
    A2ATask,
    A2ATaskResult,
)
from src.protocols.a2a.server import A2AServer
from src.routing.llm_router import LLMResponse, LLMRouter, LLMTier
from src.shared.config import CrisisSettings, get_settings
from src.shared.errors import AgentTimeoutError
from src.shared.models import AgentType, TaskStatus
from src.shared.telemetry import (
    AGENT_TASK_DURATION,
    AGENT_TASKS,
    get_logger,
)

# =============================================================================
# Agent State
# =============================================================================


class AgentState(TypedDict, total=False):
    """Typed state flowing through the LangGraph state machine."""

    task: dict
    disaster_id: str | None
    trace_id: str
    messages: list[dict[str, str]]
    reasoning: str
    confidence: float
    artifacts: list[dict]
    error: str | None
    iteration: int
    metadata: dict


# =============================================================================
# BaseAgent
# =============================================================================


class BaseAgent(ABC):
    """Abstract base for all CRISIS-BENCH agents.

    Provides LLM routing, A2A communication, Langfuse tracing,
    health checks, and timeout enforcement. Subclasses define
    the LangGraph state machine via build_graph().
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: AgentType,
        llm_tier: LLMTier,
        settings: CrisisSettings | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.llm_tier = llm_tier
        self._settings = settings or get_settings()
        self._logger = get_logger(f"agent.{agent_id}", agent_id=agent_id)

        # LLM Router
        self._router = LLMRouter(self._settings)

        # A2A protocol
        self._a2a_client = A2AClient(agent_id, agent_type)
        self._a2a_server = A2AServer(agent_id)

        # Compiled LangGraph
        self._compiled_graph = None

        # Runtime state
        self._active_tasks = 0
        self._started = False
        self._start_time: float | None = None

    # -----------------------------------------------------------------
    # Abstract methods — subclasses MUST implement
    # -----------------------------------------------------------------

    @abstractmethod
    def build_graph(self) -> StateGraph:
        """Build the LangGraph state machine. Return an uncompiled StateGraph."""

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the agent-specific system prompt."""

    @abstractmethod
    def get_agent_card(self) -> A2AAgentCard:
        """Return the A2A agent card describing capabilities."""

    # -----------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------

    async def start(self) -> None:
        """Initialize A2A, register agent card, compile graph."""
        self._compiled_graph = self.build_graph().compile()
        await self._a2a_client.start()
        await self._a2a_server.register_agent_card(self.get_agent_card())
        self._a2a_client.on_message(A2AMessageType.TASK_SEND, self.handle_task)
        self._started = True
        self._start_time = time.monotonic()
        self._logger.info("agent_started", agent_type=self.agent_type.value)

    async def stop(self) -> None:
        """Graceful shutdown."""
        self._started = False
        await self._a2a_client.stop()
        self._logger.info("agent_stopped")

    # -----------------------------------------------------------------
    # LLM Reasoning
    # -----------------------------------------------------------------

    async def reason(
        self,
        messages: list[dict[str, str]],
        *,
        tier: LLMTier | None = None,
        trace_id: str = "",
        **kwargs: Any,
    ) -> LLMResponse:
        """Route an LLM call through the LLM Router.

        Args:
            messages: OpenAI-format messages.
            tier: Override the agent's default tier.
            trace_id: Trace ID for observability.
            **kwargs: Extra args passed to router.call().

        Returns:
            LLMResponse with content, provider, cost, etc.

        Raises:
            ValueError: If messages is empty.
        """
        if not messages:
            raise ValueError("messages must be non-empty")

        effective_tier = tier or self.llm_tier
        response = await self._router.call(
            effective_tier,
            messages,
            trace_id=trace_id,
            **kwargs,
        )
        self._logger.debug(
            "llm_call_completed",
            provider=response.provider,
            tier=effective_tier.value if isinstance(effective_tier, LLMTier) else effective_tier,
            cost_usd=response.cost_usd,
            trace_id=trace_id,
        )
        return response

    # -----------------------------------------------------------------
    # Graph Execution
    # -----------------------------------------------------------------

    async def run_graph(self, initial_state: AgentState) -> AgentState:
        """Execute the compiled LangGraph with timeout enforcement.

        Raises:
            AgentTimeoutError: If execution exceeds AGENT_TIMEOUT_SECONDS.
        """
        if self._compiled_graph is None:
            self._compiled_graph = self.build_graph().compile()

        timeout = self._settings.AGENT_TIMEOUT_SECONDS
        try:
            result = await asyncio.wait_for(
                self._compiled_graph.ainvoke(initial_state),
                timeout=timeout,
            )
            return result
        except asyncio.TimeoutError:
            raise AgentTimeoutError(
                f"Agent {self.agent_id} exceeded {timeout}s timeout",
                context={"agent_id": self.agent_id, "timeout": timeout},
            )

    # -----------------------------------------------------------------
    # A2A Task Handling
    # -----------------------------------------------------------------

    async def handle_task(self, msg: A2AMessage) -> None:
        """Default handler for incoming A2A tasks.

        Deserializes the task, checks delegation depth, runs the graph,
        and sends back a result (completed or failed).
        """
        trace_id = msg.trace_id

        try:
            task = A2ATask(**msg.payload)
        except Exception as e:
            self._logger.error("invalid_task_payload", error=str(e), trace_id=trace_id)
            await self._a2a_client.send_result(
                A2ATaskResult(
                    task_id=msg.payload.get("id", "00000000-0000-0000-0000-000000000000"),
                    agent_id=self.agent_id,
                    status=TaskStatus.FAILED,
                    error_message=f"Invalid task payload: {e}",
                    trace_id=trace_id,
                )
            )
            return

        # Delegation depth guard
        max_depth = self._settings.AGENT_MAX_DELEGATION_DEPTH
        if task.depth > max_depth:
            self._logger.warning(
                "delegation_depth_exceeded",
                depth=task.depth,
                max_depth=max_depth,
                trace_id=trace_id,
            )
            await self._a2a_client.send_result(
                A2ATaskResult(
                    task_id=task.id,
                    agent_id=self.agent_id,
                    status=TaskStatus.FAILED,
                    error_message=(
                        f"Delegation depth {task.depth} exceeds max {max_depth}"
                    ),
                    trace_id=trace_id,
                )
            )
            return

        # Execute the graph
        self._active_tasks += 1
        AGENT_TASKS.labels(agent_id=self.agent_id, status="in_progress").inc()
        start_time = time.monotonic()

        try:
            initial_state: AgentState = {
                "task": task.payload,
                "disaster_id": str(task.disaster_id) if task.disaster_id else None,
                "trace_id": task.trace_id,
                "messages": [
                    {"role": "system", "content": self.get_system_prompt()},
                    {"role": "user", "content": str(task.payload)},
                ],
                "reasoning": "",
                "confidence": 0.0,
                "artifacts": [],
                "error": None,
                "iteration": 0,
                "metadata": task.metadata,
            }

            result_state = await self.run_graph(initial_state)

            elapsed = time.monotonic() - start_time
            AGENT_TASK_DURATION.labels(agent_id=self.agent_id).observe(elapsed)
            AGENT_TASKS.labels(agent_id=self.agent_id, status="completed").inc()

            await self._a2a_client.send_result(
                A2ATaskResult(
                    task_id=task.id,
                    agent_id=self.agent_id,
                    status=TaskStatus.COMPLETED,
                    confidence=result_state.get("confidence"),
                    trace_id=trace_id,
                )
            )
            self._logger.info(
                "task_completed",
                task_id=str(task.id),
                elapsed_s=round(elapsed, 2),
                confidence=result_state.get("confidence"),
                trace_id=trace_id,
            )

        except Exception as e:
            elapsed = time.monotonic() - start_time
            AGENT_TASK_DURATION.labels(agent_id=self.agent_id).observe(elapsed)
            AGENT_TASKS.labels(agent_id=self.agent_id, status="failed").inc()

            self._logger.error(
                "task_failed",
                task_id=str(task.id),
                error=str(e),
                trace_id=trace_id,
            )
            await self._a2a_client.send_result(
                A2ATaskResult(
                    task_id=task.id,
                    agent_id=self.agent_id,
                    status=TaskStatus.FAILED,
                    error_message=str(e),
                    trace_id=trace_id,
                )
            )

        finally:
            self._active_tasks -= 1

    # -----------------------------------------------------------------
    # Health Check
    # -----------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """Return health check data for monitoring."""
        uptime = time.monotonic() - self._start_time if self._start_time else 0.0
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type.value,
            "llm_tier": self.llm_tier.value,
            "status": "running" if self._started else "stopped",
            "active_tasks": self._active_tasks,
            "uptime_s": round(uptime, 1),
        }
