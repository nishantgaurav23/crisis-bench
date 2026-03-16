# Spec S8.3 — Scenario Runner with Simulated Clock

**Status**: done

## Overview

**Location**: `src/benchmark/scenario_runner.py`
**Depends On**: S8.2 (Scenario Manager), S7.9 (Agent Integration)
**Downstream**: S8.4 (Evaluation Engine)

The Scenario Runner takes a `BenchmarkScenario`, replays its event sequence against the multi-agent system using a simulated clock, collects all agent decisions with timestamps, and produces an `EvaluationRun` record. This is the bridge between benchmark scenarios and the evaluation engine.

Key design: the runner uses a **simulated clock** (not wall-clock) so that a 72-hour disaster scenario can be replayed in minutes. Events fire at their `time_offset_minutes` relative to the simulated start, with configurable time acceleration (default 5x).

## Outcomes

1. **SimulatedClock** — async clock with configurable acceleration factor, pause/resume, current time tracking
2. **EventDispatcher** — fires `ScenarioEvent`s at their scheduled simulated time offsets
3. **AgentDecisionCollector** — captures all agent decisions/responses with simulated timestamps
4. **ScenarioRunner** — orchestrates: load scenario → start clock → dispatch events → collect results → produce EvaluationRun
5. **Deterministic replay** — given the same scenario + seed, events fire in identical order
6. **Configurable acceleration** — default 5x (1 simulated minute = 12 real seconds), adjustable 1x-100x
7. **Event injection** — ability to inject ad-hoc events mid-run (for perturbation testing)
8. **Run lifecycle** — start, pause, resume, abort with proper cleanup
9. **EvaluationRun output** — populates duration_seconds, agent_decisions, error_log, total_tokens, total_cost_usd

## Classes

### SimulatedClock

```python
class SimulatedClock:
    """Async simulated clock with configurable acceleration."""

    def __init__(self, acceleration: float = 5.0, start_offset_minutes: int = 0):
        ...

    @property
    def elapsed_minutes(self) -> float:
        """Simulated minutes elapsed since start."""

    @property
    def is_running(self) -> bool: ...

    async def start(self) -> None: ...
    async def pause(self) -> None: ...
    async def resume(self) -> None: ...
    async def stop(self) -> None: ...

    async def wait_until(self, target_minutes: float) -> None:
        """Sleep until simulated clock reaches target_minutes."""
```

### EventDispatcher

```python
class EventDispatcher:
    """Dispatches ScenarioEvents at their scheduled simulated times."""

    def __init__(self, clock: SimulatedClock):
        ...

    async def schedule(self, events: list[ScenarioEvent]) -> None:
        """Schedule all events from a scenario's event_sequence."""

    async def inject(self, event: ScenarioEvent) -> None:
        """Inject an ad-hoc event into the running dispatch queue."""

    async def run(self, callback: Callable[[ScenarioEvent], Awaitable[None]]) -> None:
        """Dispatch events in order, calling callback for each."""

    @property
    def dispatched_count(self) -> int: ...

    @property
    def pending_count(self) -> int: ...
```

### AgentDecisionCollector

```python
class AgentDecisionCollector:
    """Collects agent decisions during a benchmark run."""

    def __init__(self, clock: SimulatedClock):
        ...

    def record(self, agent_id: str, decision: dict, trace_id: str = "") -> None:
        """Record a decision with current simulated timestamp."""

    @property
    def decisions(self) -> list[dict]: ...

    @property
    def total_tokens(self) -> int: ...

    @property
    def total_cost_usd(self) -> float: ...

    def to_evaluation_data(self) -> dict:
        """Return data suitable for populating an EvaluationRun."""
```

### RunStatus (enum)

```python
class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAILED = "failed"
```

### ScenarioRunner

```python
class ScenarioRunner:
    """Runs a BenchmarkScenario against the agent system."""

    def __init__(
        self,
        scenario: BenchmarkScenario,
        orchestrator: OrchestratorAgent,
        acceleration: float = 5.0,
    ):
        ...

    @property
    def status(self) -> RunStatus: ...

    @property
    def clock(self) -> SimulatedClock: ...

    @property
    def collector(self) -> AgentDecisionCollector: ...

    async def run(self) -> EvaluationRun:
        """Execute the full scenario and return an EvaluationRun."""

    async def pause(self) -> None: ...
    async def resume(self) -> None: ...
    async def abort(self) -> None: ...

    async def inject_event(self, event: ScenarioEvent) -> None:
        """Inject an event during a running scenario."""
```

## Event Dispatch Flow

1. ScenarioRunner loads scenario from ScenarioManager
2. SimulatedClock starts at t=0
3. EventDispatcher schedules all events from `scenario.event_sequence`
4. For each event at `time_offset_minutes`:
   - Clock waits until simulated time reaches the offset
   - Event is dispatched to OrchestratorAgent as a mission payload
   - Agent decisions are collected by AgentDecisionCollector
5. After all events dispatched, runner waits for final agent responses
6. Runner builds EvaluationRun with collected data

## TDD Notes

### Test File: `tests/unit/test_scenario_runner.py`

1. **SimulatedClock**:
   - Clock starts at 0, tracks elapsed simulated minutes
   - Acceleration works (5x → 1 real second = 5 simulated minutes... actually 1 simulated minute = 12 real seconds)
   - Pause/resume preserves elapsed time
   - wait_until returns immediately if already past target
   - wait_until actually waits correct real-time duration

2. **EventDispatcher**:
   - Events are dispatched in time_offset_minutes order
   - Callback is invoked for each event
   - inject() adds event to pending queue at correct position
   - dispatched_count and pending_count track correctly

3. **AgentDecisionCollector**:
   - Records decisions with simulated timestamps
   - Tracks total_tokens and total_cost_usd
   - to_evaluation_data() returns properly structured dict

4. **ScenarioRunner**:
   - Status transitions: pending → running → completed
   - run() dispatches all events to orchestrator
   - run() returns EvaluationRun with populated fields
   - Abort mid-run sets status to aborted
   - Pause/resume works correctly
   - inject_event() during run adds to dispatch queue
   - Empty event_sequence still produces valid EvaluationRun (edge case handled by validate_scenario)
   - Error in orchestrator → status=failed, error_log populated

## Non-Goals

- Evaluation scoring (S8.4-S8.9)
- Scenario generation (S6.6, S8.11)
- Persistent run storage (EvaluationRun is returned, caller decides to persist via S8.1 CRUD)
- Real-time dashboard updates during run (S9.2)
