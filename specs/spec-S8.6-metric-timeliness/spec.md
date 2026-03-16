# Spec S8.6: Metric — Decision Timeliness

**Status**: done

**Phase**: 8 (Benchmark System)
**Depends On**: S8.4 (Evaluation Engine)
**Location**: `src/benchmark/metrics/timeliness.py`
**Test File**: `tests/unit/test_metric_timeliness.py`

---

## Overview

Implements the **Decision Timeliness** metric for CRISIS-BENCH. Measures how quickly agents make decisions relative to NDMA SOP time windows defined in ground truth. Each agent has an expected `time_window_minutes: (min, max)` — the metric scores how well actual decision times fall within these windows.

## Key Concepts

### NDMA SOP Time Windows
Each agent in `GroundTruthDecisions.agent_expectations` has a `time_window_minutes: tuple[int, int]` field. This represents the expected time range (in simulated minutes) within which the agent should produce its decision. For example, `(0, 15)` means the agent should respond within 0-15 simulated minutes.

### Scoring Logic
For each agent decision:
1. Extract `simulated_elapsed_minutes` from the agent decision record
2. Compare against the ground truth `time_window_minutes` for that agent
3. Score based on position relative to the window:
   - **Within window**: 5.0 (perfect)
   - **Early** (before window start): Linear decay from 5.0 to 3.0 based on how early
   - **Late** (after window end): Exponential decay from 5.0 toward 1.0 based on how late (lateness is worse than earliness in disaster response)
   - **Missing decision**: 1.0 (no decision = worst timeliness)

### Aggregate Scoring
- Per-agent scores are averaged to get the overall timeliness score
- The score maps to the standard 1.0-5.0 range
- Agents without ground truth time windows are excluded from scoring

## Models

### `AgentTimeliness` (Pydantic)
- `agent_id: str`
- `expected_window: tuple[int, int]` — from ground truth
- `actual_minutes: float | None` — from agent decision
- `score: float` (1.0-5.0)
- `status: str` — "on_time", "early", "late", "missing"

### `DecisionTimelinessResult` (Pydantic)
- `per_agent: dict[str, AgentTimeliness]`
- `score: float` (1.0-5.0) — average of per-agent scores
- `on_time_count: int`
- `early_count: int`
- `late_count: int`
- `missing_count: int`

## Class

### `DecisionTimelinessMetric`
- `__init__(self, late_penalty_factor: float = 2.0)` — controls how harshly lateness is penalized
- `async compute(scenario, evaluation_run) -> DecisionTimelinessResult`

## Outcomes

1. Pure computation — no LLM calls, no external APIs
2. Uses `simulated_elapsed_minutes` from agent decisions (set by ScenarioRunner S8.3)
3. Maps to 1.0-5.0 score range consistent with other metrics
4. Handles missing decisions, missing time windows, empty inputs gracefully
5. Late decisions penalized more heavily than early ones (disaster response context)

## TDD Notes

### Red Phase — Tests to Write First
1. **Models**: Validate `AgentTimeliness` and `DecisionTimelinessResult` bounds
2. **On-time scoring**: Decision within window → score 5.0
3. **Early scoring**: Decision before window start → score between 3.0-5.0
4. **Late scoring**: Decision after window end → score decays toward 1.0
5. **Missing decision**: Agent expected but no decision → score 1.0
6. **Full compute**: End-to-end with scenario + evaluation run
7. **Edge cases**: Empty decisions, no ground truth windows, all agents missing
8. **Aggregate**: Multiple agents averaged correctly
9. **Penalty factor**: Higher penalty = harsher late scoring
