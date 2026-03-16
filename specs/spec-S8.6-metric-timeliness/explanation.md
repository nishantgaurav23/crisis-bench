# Spec S8.6: Decision Timeliness Metric — Explanation

## Why This Spec Exists

In disaster response, **timing is as critical as accuracy**. An evacuation order issued 30 minutes late can mean the difference between life and death. The Decision Timeliness metric quantifies how well agents meet NDMA SOP time windows — the expected decision timelines defined by India's National Disaster Management Authority procedures.

Without this metric, a system could score perfectly on situational accuracy (correct observations) while consistently being too slow to act — a dangerous false positive in benchmark evaluation.

## What It Does

Measures each agent's decision time against its expected time window from ground truth:

- **On time** (within window): Perfect score (5.0)
- **Early** (before window start): Mild penalty — linear decay from 5.0 to 3.0. In disaster response, early warnings are generally preferable to late ones.
- **Late** (after window end): Harsh penalty — exponential decay from 5.0 toward 1.0. The `late_penalty_factor` (default 2.0) controls decay steepness.
- **Missing** (no decision recorded): Worst score (1.0)

The aggregate score is the average across all expected agents.

## How It Works

### Data Flow
```
BenchmarkScenario.ground_truth_decisions.agent_expectations
  → extract_time_windows() → {agent_id: (start, end)}

EvaluationRun.agent_decisions[*].simulated_elapsed_minutes
  → extract_decision_times() → {agent_id: float}

For each agent with a ground truth window:
  score_agent_timeliness(actual, start, end, penalty)
  → (score: 1.0-5.0, status: on_time|early|late|missing)

Average all per-agent scores → DecisionTimelinessResult
```

### Scoring Math
- **Within window**: `score = 5.0`
- **Early by `e` minutes**: `score = 5.0 - 2.0 * min(e / window_size, 1.0)` → clamps to [3.0, 5.0]
- **Late by `l` minutes**: `score = 1.0 + 4.0 * exp(-penalty * l / window_size)` → decays toward 1.0

The asymmetric penalty (early is milder than late) reflects real-world disaster response: premature activation wastes resources but saves lives; late activation risks casualties.

## How It Connects

### Upstream Dependencies
- **S8.1 (models.py)**: Uses `BenchmarkScenario`, `EvaluationRun`, `GroundTruthDecisions`, `AgentExpectation.time_window_minutes`
- **S8.3 (scenario_runner.py)**: Provides `simulated_elapsed_minutes` in agent decision records
- **S8.4 (evaluation_engine.py)**: The engine evaluates `decision_timeliness` as one of 5 dimensions

### Downstream Consumers
- **S8.10 (aggregate.py)**: Feeds into the weighted aggregate Disaster Response Score (DRS)
- **S9.2 (dashboard)**: Per-agent timing breakdown displayed in the metrics panel

### Design Pattern
Follows the same pattern as S8.5 (Situational Accuracy):
- Pure computation — no LLM calls, no external APIs
- Pydantic models for input/output
- Async `compute()` interface for consistency with other metrics
- Graceful handling of missing data

## Interview Talking Points

**Q: Why asymmetric penalties for early vs. late decisions?**
A: In disaster response, the cost of being late is fundamentally higher than being early. A late evacuation order during a cyclone means people are still in harm's way. An early evacuation order means some resource waste and public inconvenience, but lives are preserved. The exponential decay for lateness (vs. linear for earliness) models this real-world asymmetry.

**Q: Why use simulated time instead of wall clock time?**
A: Benchmark scenarios run with time acceleration (e.g., 5x). Using wall clock time would conflate system performance (CPU speed, API latency) with decision quality. `simulated_elapsed_minutes` measures when the agent *would* have decided in a real scenario, independent of hardware.

**Q: How does the `late_penalty_factor` parameter help?**
A: Different disaster types have different time criticality. For earthquakes (immediate response needed), you'd set a high penalty factor (4.0). For slow-onset floods, a lower factor (1.0) is appropriate since the decision window is naturally longer.
