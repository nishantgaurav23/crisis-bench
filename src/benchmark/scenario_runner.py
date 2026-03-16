"""Scenario runner with simulated clock for CRISIS-BENCH (spec S8.3).

Replays a BenchmarkScenario's event sequence against the multi-agent system
using a simulated clock with configurable acceleration. Collects agent
decisions and produces an EvaluationRun record for downstream evaluation.

Key design: the runner uses a *simulated clock* so that a 72-hour disaster
scenario can be replayed in minutes. Events fire at their time_offset_minutes
relative to simulated start, with configurable time acceleration (default 5x).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from enum import Enum
from typing import Any, Awaitable, Callable

from src.benchmark.models import (
    BenchmarkScenario,
    EvaluationRun,
    ScenarioEvent,
)
from src.shared.telemetry import get_logger

logger = get_logger("benchmark.scenario_runner")


# =============================================================================
# RunStatus
# =============================================================================


class RunStatus(str, Enum):
    """Lifecycle status of a scenario run."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAILED = "failed"


# =============================================================================
# SimulatedClock
# =============================================================================


class SimulatedClock:
    """Async simulated clock with configurable acceleration.

    Acceleration controls how fast simulated time passes relative to real time.
    An acceleration of 5.0 means 1 real second = 5 simulated seconds, i.e.
    1 simulated minute takes 12 real seconds.

    An acceleration of 1000.0 means 1 real second = ~16.67 simulated minutes.
    """

    def __init__(
        self,
        acceleration: float = 5.0,
        start_offset_minutes: int = 0,
    ) -> None:
        self._acceleration = max(acceleration, 0.01)
        self._start_offset_minutes = start_offset_minutes
        self._accumulated_minutes: float = float(start_offset_minutes)
        self._last_real_time: float | None = None
        self._running = False
        self._stopped = False

    @property
    def elapsed_minutes(self) -> float:
        """Simulated minutes elapsed since start (including offset)."""
        if self._running and self._last_real_time is not None:
            real_delta = time.monotonic() - self._last_real_time
            return self._accumulated_minutes + (real_delta * self._acceleration / 60.0)
        return self._accumulated_minutes

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Start the simulated clock."""
        self._last_real_time = time.monotonic()
        self._running = True
        self._stopped = False

    async def pause(self) -> None:
        """Pause the clock, freezing elapsed time."""
        if self._running and self._last_real_time is not None:
            real_delta = time.monotonic() - self._last_real_time
            self._accumulated_minutes += real_delta * self._acceleration / 60.0
        self._running = False
        self._last_real_time = None

    async def resume(self) -> None:
        """Resume a paused clock."""
        self._last_real_time = time.monotonic()
        self._running = True

    async def stop(self) -> None:
        """Stop the clock permanently."""
        if self._running and self._last_real_time is not None:
            real_delta = time.monotonic() - self._last_real_time
            self._accumulated_minutes += real_delta * self._acceleration / 60.0
        self._running = False
        self._last_real_time = None
        self._stopped = True

    async def wait_until(self, target_minutes: float) -> None:
        """Sleep until simulated clock reaches target_minutes.

        Returns immediately if already past the target or if the clock
        has been stopped.
        """
        while self.elapsed_minutes < target_minutes:
            if self._stopped or not self._running:
                break
            remaining_sim = target_minutes - self.elapsed_minutes
            # Convert simulated minutes to real seconds
            real_seconds = remaining_sim * 60.0 / self._acceleration
            sleep_time = min(real_seconds, 0.05)  # poll at most every 50ms
            if sleep_time <= 0:
                break
            await asyncio.sleep(sleep_time)


# =============================================================================
# EventDispatcher
# =============================================================================


class EventDispatcher:
    """Dispatches ScenarioEvents at their scheduled simulated times.

    Events are sorted by time_offset_minutes and dispatched in order.
    Supports mid-run injection of ad-hoc events.
    """

    def __init__(self, clock: SimulatedClock) -> None:
        self._clock = clock
        self._pending: list[ScenarioEvent] = []
        self._dispatched_count: int = 0
        self._abort = False

    async def schedule(self, events: list[ScenarioEvent]) -> None:
        """Schedule all events, sorted by time_offset_minutes."""
        self._pending = sorted(events, key=lambda e: e.time_offset_minutes)

    async def inject(self, event: ScenarioEvent) -> None:
        """Inject an ad-hoc event into the pending queue at the correct position.

        Uses insertion sort to maintain time ordering.
        """
        # Find the right position
        idx = 0
        for i, e in enumerate(self._pending):
            if e.time_offset_minutes > event.time_offset_minutes:
                break
            idx = i + 1
        else:
            idx = len(self._pending)
        self._pending.insert(idx, event)

    async def run(
        self,
        callback: Callable[[ScenarioEvent], Awaitable[None]],
    ) -> None:
        """Dispatch events in order, waiting for each event's simulated time.

        Calls callback for each event at its scheduled time.
        """
        while self._pending and not self._abort:
            event = self._pending.pop(0)
            await self._clock.wait_until(float(event.time_offset_minutes))
            if self._abort:
                # Put event back if aborted during wait
                self._pending.insert(0, event)
                break
            await callback(event)
            self._dispatched_count += 1

    def abort(self) -> None:
        """Signal the dispatcher to stop processing."""
        self._abort = True

    @property
    def dispatched_count(self) -> int:
        return self._dispatched_count

    @property
    def pending_count(self) -> int:
        return len(self._pending)


# =============================================================================
# AgentDecisionCollector
# =============================================================================


class AgentDecisionCollector:
    """Collects agent decisions during a benchmark run.

    Each decision is timestamped with the simulated clock and includes
    the agent ID, decision payload, and optional trace ID.
    """

    def __init__(self, clock: SimulatedClock) -> None:
        self._clock = clock
        self._decisions: list[dict[str, Any]] = []

    def record(
        self,
        agent_id: str,
        decision: dict[str, Any],
        trace_id: str = "",
    ) -> None:
        """Record a decision with the current simulated timestamp."""
        entry = {
            "agent_id": agent_id,
            "simulated_elapsed_minutes": self._clock.elapsed_minutes,
            "trace_id": trace_id,
            **decision,
        }
        self._decisions.append(entry)

    @property
    def decisions(self) -> list[dict[str, Any]]:
        return list(self._decisions)

    @property
    def total_tokens(self) -> int:
        """Sum of all tokens across decisions."""
        return sum(d.get("tokens", 0) for d in self._decisions)

    @property
    def total_cost_usd(self) -> float:
        """Sum of all cost_usd across decisions."""
        return sum(d.get("cost_usd", 0.0) for d in self._decisions)

    def to_evaluation_data(self) -> dict[str, Any]:
        """Return data suitable for populating an EvaluationRun."""
        return {
            "agent_decisions": self.decisions,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
        }


# =============================================================================
# ScenarioRunner
# =============================================================================


class ScenarioRunner:
    """Runs a BenchmarkScenario against the agent system with simulated clock.

    Orchestrates: load scenario -> start clock -> dispatch events ->
    collect results -> produce EvaluationRun.
    """

    def __init__(
        self,
        scenario: BenchmarkScenario,
        orchestrator: Any,
        acceleration: float = 5.0,
    ) -> None:
        self._scenario = scenario
        self._orchestrator = orchestrator
        self._acceleration = acceleration
        self._clock = SimulatedClock(acceleration=acceleration)
        self._dispatcher = EventDispatcher(self._clock)
        self._collector = AgentDecisionCollector(self._clock)
        self._status = RunStatus.PENDING
        self._errors: list[str] = []
        self._start_real_time: float | None = None

    @property
    def status(self) -> RunStatus:
        return self._status

    @property
    def clock(self) -> SimulatedClock:
        return self._clock

    @property
    def collector(self) -> AgentDecisionCollector:
        return self._collector

    async def run(self) -> EvaluationRun:
        """Execute the full scenario and return an EvaluationRun.

        1. Reset orchestrator budget
        2. Start clock
        3. Schedule and dispatch events
        4. Collect agent results
        5. Build EvaluationRun
        """
        self._status = RunStatus.RUNNING
        self._start_real_time = time.monotonic()
        self._orchestrator.reset_budget()

        try:
            # Schedule events
            await self._dispatcher.schedule(list(self._scenario.event_sequence))

            # Start clock
            await self._clock.start()

            # Dispatch events, calling orchestrator for each
            await self._dispatcher.run(self._handle_event)

            # Wait briefly for any final processing
            await asyncio.sleep(0.01)

            if self._status == RunStatus.RUNNING:
                self._status = RunStatus.COMPLETED

        except Exception as exc:
            self._status = RunStatus.FAILED
            self._errors.append(str(exc))
            logger.error(
                "scenario_run_failed",
                scenario_id=str(self._scenario.id),
                error=str(exc),
            )
        finally:
            await self._clock.stop()

        return self._build_evaluation_run()

    async def pause(self) -> None:
        """Pause the running scenario."""
        if self._status == RunStatus.RUNNING:
            self._status = RunStatus.PAUSED
            await self._clock.pause()

    async def resume(self) -> None:
        """Resume a paused scenario."""
        if self._status == RunStatus.PAUSED:
            self._status = RunStatus.RUNNING
            await self._clock.resume()

    async def abort(self) -> None:
        """Abort the scenario run."""
        self._status = RunStatus.ABORTED
        self._dispatcher.abort()
        await self._clock.stop()

    async def inject_event(self, event: ScenarioEvent) -> None:
        """Inject an event during a running scenario."""
        await self._dispatcher.inject(event)

    async def _handle_event(self, event: ScenarioEvent) -> None:
        """Handle a single dispatched event by sending it to the orchestrator."""
        if self._status not in (RunStatus.RUNNING,):
            return

        trace_id = uuid.uuid4().hex[:8]
        mission = {
            "event_type": event.event_type,
            "phase": event.phase.value,
            "description": event.description,
            "time_offset_minutes": event.time_offset_minutes,
            **event.data_payload,
        }

        initial_state = {
            "task": mission,
            "disaster_id": str(self._scenario.id),
            "trace_id": trace_id,
            "messages": [],
            "reasoning": "",
            "confidence": 0.0,
            "artifacts": [],
            "error": None,
            "iteration": 0,
            "metadata": {"benchmark_run": True},
        }

        try:
            result = await self._orchestrator.run_graph(initial_state)
            self._collector.record(
                agent_id="orchestrator",
                decision={
                    "event_type": event.event_type,
                    "confidence": result.get("confidence", 0.0),
                    "reasoning": result.get("reasoning", ""),
                    "artifacts": result.get("artifacts", []),
                },
                trace_id=trace_id,
            )
        except Exception as exc:
            error_msg = f"Event {event.event_type} at t+{event.time_offset_minutes}m: {exc}"
            self._errors.append(error_msg)
            self._status = RunStatus.FAILED
            self._dispatcher.abort()
            logger.error(
                "event_handling_failed",
                event_type=event.event_type,
                error=str(exc),
            )

    def _build_evaluation_run(self) -> EvaluationRun:
        """Build an EvaluationRun from collected data."""
        duration = (
            time.monotonic() - self._start_real_time
            if self._start_real_time
            else 0.0
        )
        eval_data = self._collector.to_evaluation_data()

        return EvaluationRun(
            scenario_id=self._scenario.id,
            agent_config={
                "acceleration": self._acceleration,
                "orchestrator_id": self._orchestrator.agent_id,
            },
            agent_decisions=eval_data["agent_decisions"],
            total_tokens=eval_data["total_tokens"],
            total_cost_usd=eval_data["total_cost_usd"],
            duration_seconds=round(duration, 3),
            error_log=self._errors,
        )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "AgentDecisionCollector",
    "EventDispatcher",
    "RunStatus",
    "ScenarioRunner",
    "SimulatedClock",
]
