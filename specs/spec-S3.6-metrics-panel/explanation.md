# S3.6 MetricsPanel — Explanation

## Why This Spec Exists

The MetricsPanel is the financial observability layer of the dashboard. CRISIS-BENCH operates on a $3-8/month budget using 5 LLM providers across 4 pricing tiers. Without real-time cost visibility, it's easy to accidentally blow the budget with a burst of critical-tier calls to DeepSeek Reasoner ($0.50/M tokens). This component makes cost, token usage, and latency visible at a glance.

## What It Does

1. **Budget Gauge** — Shows current spend vs. monthly budget ($8 default) with color-coded thresholds (green <50%, yellow 50-80%, red >80%)
2. **Token Summary** — Displays total input/output tokens with human-readable formatting (K/M suffixes)
3. **Cost Breakdown** — Per-provider cost with tier color coding (critical=red, standard=yellow, routine=green, free=blue)
4. **Latency Statistics** — Average, P95, P99 latency per provider with severity coloring

## How It Works

- **Component**: `dashboard/src/components/MetricsPanel.tsx` — a "use client" React component
- **Types**: `ProviderMetrics` and `MetricsSummary` added to `dashboard/src/types/index.ts`
- **Mock Data**: `MOCK_METRICS` constant with realistic data for all 5 providers (DeepSeek Reasoner, DeepSeek Chat, Qwen Flash, Groq, Ollama)
- **Utilities**: `formatTokens()`, `getBudgetColor()`, `getLatencyColor()` — all exported and independently testable
- **Props**: `metrics?` (override mock data), `budget?` (default $8), `className?`, `onProviderClick?`

### Key Design Decisions

- Uses mock data by default so the component works standalone before S2.8 (Cost Tracker) is implemented
- Tier color scheme matches `AgentFlow.tsx`'s `TIER_STYLES` for visual consistency
- All sections have `data-testid` attributes for reliable testing
- Utility functions are pure and exported separately for unit testing

## How It Connects

| Connection | Direction | Description |
|-----------|-----------|-------------|
| S3.3 (Dashboard Setup) | depends on | Uses Next.js, Tailwind, Jest config |
| S2.8 (Cost Tracker) | will consume | Real provider metrics will replace mock data |
| S9.2 (Dashboard Integration) | feeds into | Will be wired to live WebSocket data |
| S3.5 (Agent Panel) | sibling | Same dashboard layout, consistent styling |

## Interview Q&A

**Q: Why use mock data instead of waiting for the real cost tracker?**
A: Building the visualization layer early gives us a target interface for the backend. When S2.8 implements the actual cost tracker, we just swap `MOCK_METRICS` for real data — the component API is already defined. This is the "outside-in" development pattern: build the consumer first, then the producer.

**Q: Why export utility functions separately instead of keeping them private?**
A: `formatTokens`, `getBudgetColor`, and `getLatencyColor` are pure functions with well-defined behavior. Exporting them allows direct unit testing without rendering the full component — tests run faster and failures are more precise. These utilities may also be reused by other dashboard components (e.g., Timeline might need `formatTokens`).
