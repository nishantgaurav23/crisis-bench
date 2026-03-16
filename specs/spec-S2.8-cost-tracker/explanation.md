# Spec S2.8: Cost Tracker — Explanation

## Why This Spec Exists

The CRISIS-BENCH system routes LLM calls across 8 providers at different price points ($0–$2.18/M tokens). Without cost tracking, the $3–8/month budget is unenforceable — a benchmark run could silently spend $50 on DeepSeek Reasoner calls. The CostTracker provides real-time visibility into spending by provider and tier, with budget alerts at 80% (warning) and 100% (exceeded).

## What It Does

1. **`CostRecord`** — An immutable dataclass capturing a single LLM call's cost fingerprint: provider, tier, model, input/output tokens, cost in USD, latency, and timestamp. Created from the existing `LLMResponse` via `CostRecord.from_response()`.

2. **`CostTracker`** — A thread-safe in-memory tracker that accumulates `CostRecord`s. Provides:
   - `get_total_cost()` — total USD spent
   - `get_cost_by_provider()` — breakdown per provider (DeepSeek Chat, Qwen Flash, etc.)
   - `get_cost_by_tier()` — breakdown per tier (critical, standard, routine, vision)
   - `get_token_summary()` — total input/output/combined tokens
   - `get_summary()` — full dict with all the above
   - `check_budget(limit)` — returns `BudgetStatus` enum (UNDER_BUDGET / WARNING / EXCEEDED)
   - `reset()` — clears all records

3. **`BudgetStatus`** — Enum with three states. Warning triggers at 80% of the budget limit.

4. **LLMRouter integration** — The router accepts an optional `CostTracker` in its constructor. After each successful LLM call, it records the response automatically. `router.get_cost_summary()` delegates to the tracker.

## How It Works

The CostTracker uses a simple append-only list protected by a `threading.Lock`. Each `record()` call creates an immutable `CostRecord` from the `LLMResponse` and appends it. Aggregation methods iterate the list under the lock to compute sums. This is O(n) per query but perfectly adequate for the expected volume (~100–1000 calls per benchmark run).

**Key design decisions:**
- **Immutable records**: `CostRecord` is `frozen=True` — once created, it cannot be modified. This prevents accidental mutation and makes thread safety simpler.
- **No persistence**: Costs are in-memory only. For cross-session tracking, the Prometheus `LLM_COST` counter (already in S2.5) provides durable metrics. The CostTracker is for real-time budget enforcement within a single run.
- **Loose coupling to LLMRouter**: The tracker is passed as `Any` to avoid circular imports (CostTracker imports LLMResponse from llm_router). The router just calls `.record()` — no type import needed.
- **80% warning threshold**: Based on common budget alert practices. Gives the operator time to react before costs hit the limit.

## How It Connects

| Upstream | Provides |
|----------|----------|
| S2.6 (LLM Router) | `LLMResponse` objects that get recorded |

| Downstream Spec | Uses |
|----------------|------|
| S7.2 (Orchestrator) | Budget management — checks budget before delegating to agents |
| S3.6 (Metrics Panel) | Dashboard displays cost breakdown per provider/tier |
| S9.4 (Grafana Dashboards) | Budget alert thresholds visualized |
| S8.3 (Scenario Runner) | Per-scenario budget enforcement via `BUDGET_LIMIT_PER_SCENARIO` |

## Interview Talking Points

**Q: Why an in-memory tracker instead of a database table?**
A: The CostTracker serves a different purpose than the Prometheus `LLM_COST` counter. Prometheus gives you durable, time-series metrics for dashboards and alerting over days/weeks. The in-memory tracker gives you instant, per-run budget enforcement — "has this benchmark run exceeded $0.05?" — without a database round-trip on every LLM call. Both exist and complement each other.

**Q: How do you handle the circular import between cost_tracker and llm_router?**
A: The CostTracker imports `LLMResponse` from `llm_router` (it needs the type for `CostRecord.from_response()`). The LLMRouter accepts the tracker as `Any` — no import of `cost_tracker` needed. This breaks the cycle while maintaining type safety in the tracker module. At runtime, the router just calls `.record()` — duck typing.

**Q: Why thread-safe with a Lock instead of asyncio?**
A: The CostTracker is a synchronous data structure — it doesn't do I/O. The `threading.Lock` protects against concurrent access from multiple asyncio tasks running in the same event loop (which share the same thread but can interleave at await points) or from background threads. It's the simplest correct approach.
