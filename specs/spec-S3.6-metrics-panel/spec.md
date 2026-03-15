# Spec S3.6 — MetricsPanel Component

## Overview

A React dashboard component that displays LLM token usage, cost tracking per provider, a budget gauge, and latency statistics. Uses mock data initially (real cost tracker data comes from S2.8 later).

## Depends On

- **S3.3** (Next.js dashboard setup) — project scaffold, Tailwind CSS, Jest config

## Location

- `dashboard/src/components/MetricsPanel.tsx`
- `dashboard/src/__tests__/components/MetricsPanel.test.tsx`

## Requirements

### R1: Provider Cost Breakdown
- Display per-provider cost data (DeepSeek Reasoner, DeepSeek Chat, Qwen Flash, Groq, Ollama)
- Show provider name, total cost ($), token count (input + output), and request count
- Color-code providers by tier (critical=red, standard=yellow, routine=green, free=blue)

### R2: Token Usage Summary
- Display total tokens used (input + output separately)
- Show token breakdown by tier (critical, standard, routine, free)
- Format large numbers with K/M suffixes (e.g., 1,234,567 → 1.23M)

### R3: Budget Gauge
- Circular or bar gauge showing current spend vs. monthly budget
- Budget threshold from props (default $8/month per design)
- Color transitions: green (<50%), yellow (50-80%), red (>80%)
- Display remaining budget amount

### R4: Latency Statistics
- Show average, P50, P95, P99 latency per provider
- Color-code: green (<1s), yellow (1-3s), red (>3s)

### R5: Mock Data
- Export MOCK_METRICS constant with realistic data for all providers
- Component works with no props (uses mock data by default)
- Accept optional `metrics` prop to override mock data

### R6: Component API
- Props: `metrics?`, `budget?` (number, default 8.0), `className?`, `onProviderClick?`
- All sub-sections use `data-testid` attributes for testing
- Responsive: stacks on mobile, grid on desktop

## Data Types (add to types/index.ts)

```typescript
export interface ProviderMetrics {
  provider: string;
  tier: string;
  total_cost: number;
  input_tokens: number;
  output_tokens: number;
  requests: number;
  avg_latency_ms: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
}

export interface MetricsSummary {
  providers: ProviderMetrics[];
  total_cost: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_requests: number;
  period_start: string;
  period_end: string;
}
```

## Outcomes

1. Component renders with mock data when no props given
2. All 5 providers displayed with correct tier colors
3. Budget gauge changes color at correct thresholds
4. Large token numbers formatted with K/M suffixes
5. Latency values color-coded by severity
6. All tests pass, TypeScript clean, no lint errors

## TDD Notes

### Test First (Red Phase)
- Test component renders container with testid
- Test all providers displayed from mock data
- Test token formatting utility (formatTokens)
- Test budget gauge color thresholds
- Test latency color coding
- Test custom props override mock data
- Test onProviderClick callback
- Test className passthrough
- Test responsive layout testids exist
