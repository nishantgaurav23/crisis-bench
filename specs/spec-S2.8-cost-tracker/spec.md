# Spec S2.8: Per-Provider Cost Tracker

**Status**: done
**Phase**: 2 — Shared Infrastructure
**Depends On**: S2.6 (LLM Router) ✅ done
**Location**: `src/routing/cost_tracker.py`

---

## 1. Overview

Track per-provider LLM costs (tokens, USD, latency) with budget alerts and reporting. The CostTracker is a lightweight in-memory tracker that the LLM Router feeds after every call. It provides real-time budget monitoring and per-provider/tier breakdowns.

### Why This Matters

- **Interview**: Demonstrates cost governance in multi-provider LLM architectures — a critical production concern.
- **Project**: Without cost tracking, the $3-8/month budget is unenforceable. Budget alerts prevent runaway costs during benchmark runs.

---

## 2. Requirements

### 2.1 CostRecord (dataclass)
- Fields: `provider`, `tier`, `model`, `input_tokens`, `output_tokens`, `cost_usd`, `latency_s`, `timestamp`
- Immutable after creation

### 2.2 CostTracker (class)
- Thread-safe in-memory tracker
- `record(response: LLMResponse)` — log a completed LLM call
- `get_total_cost()` → float — total USD spent
- `get_cost_by_provider()` → dict[str, float] — cost per provider
- `get_cost_by_tier()` → dict[str, float] — cost per tier
- `get_token_summary()` → dict with total input/output tokens
- `get_summary()` → dict with full breakdown (providers, tiers, totals, records count)
- `check_budget(limit: float)` → BudgetStatus (under/warning/exceeded)
- `reset()` — clear all records
- Budget thresholds: warning at 80%, exceeded at 100%

### 2.3 BudgetStatus (enum)
- `UNDER_BUDGET`, `WARNING`, `EXCEEDED`

### 2.4 Integration with LLMRouter
- LLMRouter accepts an optional `CostTracker` in constructor
- After each successful call, router records the response in the tracker
- Router exposes `get_cost_summary()` that delegates to tracker

---

## 3. Outcomes / Acceptance Criteria

1. CostTracker correctly accumulates costs from multiple LLMResponse objects
2. Per-provider and per-tier breakdowns are accurate
3. Budget checking returns correct status at various thresholds
4. Token summaries include both input and output counts
5. Reset clears all data
6. Thread-safe for concurrent recording
7. All tests pass, ruff clean

---

## 4. TDD Notes

### Test File
`tests/unit/test_cost_tracker.py`

### Test Cases
1. Record single call, verify totals
2. Record multiple calls to different providers, verify per-provider breakdown
3. Record calls to different tiers, verify per-tier breakdown
4. Budget under/warning/exceeded thresholds
5. Token summary accuracy
6. Full summary dict structure
7. Reset clears everything
8. Empty tracker returns zeroes
