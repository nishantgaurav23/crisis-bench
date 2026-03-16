# Spec S8.3 — Scenario Runner: Explanation

## Why This Spec Exists

The benchmark system needs a way to **replay disaster scenarios against the multi-agent system** in a controlled, repeatable manner. Without a scenario runner, benchmarking would require either:
1. Waiting for real disasters (impractical, unethical)
2. Running scenarios in real-time (a 72-hour cyclone would take 72 hours to benchmark)
3. Feeding events manually (error-prone, non-reproducible)

The Scenario Runner solves all three problems by using a **simulated clock** that compresses time — a 72-hour disaster replays in ~14 minutes at 5x acceleration, or under a minute at 100x.

## What It Does

The runner takes a `BenchmarkScenario` (from S8.1/S8.2) and replays its `event_sequence` against the `OrchestratorAgent` (from S7.2). It consists of four components:

### SimulatedClock
An async clock where 1 simulated minute = `60/acceleration` real seconds. At 5x acceleration, 1 simulated minute = 12 real seconds. Supports pause/resume for debugging and start-offset for resuming mid-scenario.

### EventDispatcher
Schedules `ScenarioEvent`s sorted by `time_offset_minutes`. For each event, it waits until the simulated clock reaches the event's offset, then fires a callback. Supports mid-run injection of ad-hoc events for perturbation testing (S8.11).

### AgentDecisionCollector
Captures every decision the orchestrator makes during the run, tagged with the simulated timestamp. Tracks aggregate metrics (total tokens, total cost) for populating the `EvaluationRun`.

### ScenarioRunner
Orchestrates the full lifecycle:
1. Resets orchestrator budget
2. Starts simulated clock
3. Dispatches events to orchestrator via `run_graph()`
4. Collects decisions
5. Builds `EvaluationRun` with duration, decisions, errors, tokens, cost

Run lifecycle states: `pending → running → completed/aborted/failed`

## How It Works

```
BenchmarkScenario (S8.1)
    │
    ▼
ScenarioRunner.run()
    │
    ├── SimulatedClock.start()
    │
    ├── EventDispatcher.run(callback)
    │       │
    │       ├── wait_until(t=0) → dispatch "sachet_alert"
    │       │       └── OrchestratorAgent.run_graph({mission})
    │       │               └── AgentDecisionCollector.record(result)
    │       │
    │       ├── wait_until(t=10) → dispatch "imd_warning"
    │       │       └── ...
    │       │
    │       └── wait_until(t=30) → dispatch "evacuation_order"
    │               └── ...
    │
    ├── SimulatedClock.stop()
    │
    └── build EvaluationRun
            │
            ▼
        EvaluationRun (→ S8.4 Evaluation Engine)
```

## How It Connects

| Component | Relationship |
|-----------|-------------|
| **S8.1** (Scenario Models) | Consumes `BenchmarkScenario`, produces `EvaluationRun` |
| **S8.2** (Scenario Manager) | Provides scenarios via manager queries |
| **S7.2** (Orchestrator) | Receives events as mission payloads via `run_graph()` |
| **S7.9** (Agent Integration) | Runner exercises the same pipeline tested in integration |
| **S8.4** (Evaluation Engine) | Downstream consumer of `EvaluationRun` for scoring |
| **S8.11** (Self-Evolving) | Uses `inject_event()` for perturbation testing |

## Key Design Decisions

1. **Simulated vs real clock**: Using a simulated clock makes benchmarking practical — 100 scenarios with 72-hour timelines would take 300 days in real-time.

2. **Poll-based wait_until**: Uses `asyncio.sleep()` with 50ms polling intervals. This is simpler than event-based signaling and sufficient since benchmark accuracy doesn't require sub-millisecond precision.

3. **Orchestrator-only dispatch**: Events go to the Orchestrator (not individual agents) because in the real system, all external data flows through the Orchestrator for decomposition. This tests the full pipeline.

4. **Stateless runner**: The runner doesn't persist runs — it returns an `EvaluationRun` and the caller decides whether to persist it via S8.1's CRUD. This keeps the runner focused on execution.

5. **Abort via dispatcher signal**: Abort sets a flag on the dispatcher that causes `wait_until` and the dispatch loop to exit cleanly, rather than using `asyncio.Task.cancel()` which can leave resources in inconsistent states.

## Interview Q&A

**Q: Why use a simulated clock instead of just feeding events as fast as possible?**
A: The simulated clock preserves **temporal relationships** between events. In a real disaster, there's a 10-minute gap between the SACHET alert and the first IMD warning — the agent system might use that gap to pre-position resources. If we feed events instantly, we lose the ability to evaluate whether agents used time windows effectively. The `Decision Timeliness` metric (S8.6) specifically measures whether decisions fell within expected time windows.

**Q: How does the acceleration factor work mathematically?**
A: `acceleration = simulated_time / real_time`. At 5x: 1 real second = 5 simulated seconds. So 1 simulated minute = 60/5 = 12 real seconds. A 72-hour scenario (4320 minutes) at 5x takes 4320 * 12 = 51,840 seconds ≈ 14.4 hours. At 100x, it takes ~43 minutes. In tests we use 10000x so everything is near-instant.

**Q: What happens if the orchestrator is slower than the event spacing?**
A: The runner dispatches events sequentially — it waits for the orchestrator to finish processing one event before waiting for the next event's time offset. If the orchestrator takes longer than the gap between events, subsequent events will be "late" (dispatched after their scheduled time). This is intentional — it tests whether the system can keep up with the event rate, and `Decision Timeliness` scoring captures this latency.

**Q: Why not use `asyncio.Task.cancel()` for abort?**
A: `Task.cancel()` injects `CancelledError` at arbitrary `await` points, which can leave the orchestrator's internal state inconsistent (half-processed messages, unclosed connections). Instead, we set a flag that `wait_until()` checks on each poll cycle, causing a clean exit. The dispatcher stops, the clock stops, and the runner builds a partial `EvaluationRun` with whatever was collected.
