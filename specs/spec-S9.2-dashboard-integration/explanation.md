# Spec S9.2 — Dashboard Full Data Integration: Explanation

## Why This Spec Exists

The dashboard components (GeoMap, AgentFlow, MetricsPanel, Timeline) were built in Phase 3 with mock data to enable visual development feedback. The agent system (Phase 7) and benchmark engine (Phase 8) now produce real data — but the dashboard can't see it. This spec bridges that gap by:
1. Creating API endpoints for benchmark data and metrics
2. Wiring WebSocket broadcasts to real backend events
3. Connecting all dashboard components to live data sources
4. Adding scenario replay and evaluation result display

## What It Does

### Backend (Python/FastAPI)

**New API routes:**
- `GET /api/v1/benchmark/scenarios` — list benchmark scenarios with category/complexity filtering
- `GET /api/v1/benchmark/scenarios/{id}` — scenario detail
- `GET /api/v1/benchmark/runs` — list evaluation runs with scenario filter
- `GET /api/v1/benchmark/runs/{id}` — evaluation run detail with DRS scores
- `GET /api/v1/metrics/summary` — cost/token/latency summary by LLM provider
- `GET /api/v1/agents/{type}/decisions` — recent decisions from a specific agent

**WebSocket wiring:**
- Disaster creation now broadcasts `disaster.created` event to all connected WebSocket clients via the existing `ConnectionManager.broadcast()` infrastructure

### Frontend (Next.js/TypeScript)

**New hook:** `useCrisisWebSocket` — manages WebSocket lifecycle, dispatches incoming events to React state for disasters, agent status, metrics, and timeline

**New components:**
- `ScenarioReplay` — dropdown to browse benchmark scenarios, view event counts, and select evaluation runs
- `EvaluationDetail` — displays 5-dimension DRS scores as bar charts with color coding, plus run metadata (tokens, cost, duration)

**Updated main page:** wires all components to live data — GeoMap shows real disasters, AgentFlow merges WebSocket status updates, MetricsPanel fetches from API, Timeline streams real-time events

## How It Works

### Data Flow: API → Dashboard

```
Backend                          Dashboard
┌───────────┐                    ┌────────────────┐
│ FastAPI    │ ──GET /disasters→  │ useCrisisWS    │
│ routes     │ ──GET /agents──→  │ hook fetches    │
│            │ ──GET /metrics─→  │ initial data    │
│            │ ──GET /benchmark→ │ on mount        │
└───────────┘                    └────────────────┘
```

### Data Flow: WebSocket → Dashboard

```
Agent System                     Dashboard
┌───────────┐                    ┌────────────────┐
│ disaster   │ ──ws:disaster.──→ │ handleMessage() │
│ create API │   created         │ updates state:  │
│            │                   │ - disasters[]   │
│ agent      │ ──ws:agent.───→  │ - agents Map    │
│ lifecycle  │   status          │ - metrics       │
│            │                   │ - timeline[]    │
│ LLM Router │ ──ws:metrics.──→ │                 │
│            │   update          │                 │
└───────────┘                    └────────────────┘
```

### State Merging Pattern

The hook maintains separate state for WebSocket updates and API-fetched data. The main page merges them:
- `agents`: API fetch provides the full AgentCard list; WebSocket `agent.status` events provide `{status, last_active}` patches that are merged per-agent
- `metrics`: API fetch provides the initial MetricsSummary; WebSocket `metrics.update` events overlay new values
- `disasters`: API fetch provides the initial list; WebSocket `disaster.created` events append new entries

## How It Connects to the Rest of the Project

| Connection | Direction | Details |
|-----------|-----------|---------|
| **S3.1 API Gateway** | extends | New routers registered in `src/api/main.py` alongside existing health/disasters/agents |
| **S3.2 WebSocket** | uses | Disaster creation now calls `manager.broadcast()` from S3.2's ConnectionManager |
| **S3.4-S3.7 Components** | updates | GeoMap, AgentFlow, MetricsPanel, Timeline now receive live data instead of mock data |
| **S7.1-S7.9 Agent System** | reads | Agent decisions are queryable via `/agents/{type}/decisions`; status updates arrive via WebSocket |
| **S8.1-S8.4 Benchmark** | reads | Scenarios and evaluation runs are queryable via `/benchmark/scenarios` and `/benchmark/runs` |
| **S2.6 LLM Router** | reads (future) | Metrics endpoint currently returns defaults; will connect to CostTracker (S2.8) when implemented |
| **S9.1 Plan Caching** | prepared | Dashboard infrastructure ready to display cache hit rates when S9.1 is implemented |

## Interview Q&A

**Q: How does the dashboard handle real-time updates without polling?**
A: WebSocket push — the backend broadcasts events (`disaster.created`, `agent.status`, `metrics.update`) to all connected clients. The `useCrisisWebSocket` React hook maintains the WebSocket lifecycle (connect, reconnect with exponential backoff, cleanup on unmount) and dispatches events to React state via a `handleMessage` callback. No polling needed — updates arrive in <50ms.

**Q: Why merge WebSocket updates with API-fetched data instead of relying solely on WebSocket?**
A: Two reasons: (1) **Cold start** — when the dashboard first loads, it needs the current state (existing disasters, agent cards, cost totals), not just future events. The API provides that snapshot. (2) **Reliability** — WebSocket connections can drop; when the client reconnects, it re-fetches the full state to avoid missing events during the gap.

**Q: Why use a React hook instead of a global state manager (Redux, Zustand)?**
A: For a single-page dashboard with 4-5 data streams, a custom hook is the simplest solution. It encapsulates WebSocket lifecycle, provides typed state, and integrates with React's `useEffect` cleanup. A global store would add indirection for no benefit — we have one consumer (the main page) and one producer (the WebSocket). If the dashboard grows to multiple pages sharing state, Zustand would be the natural evolution.

**Q: How do you display benchmark evaluation results?**
A: The `EvaluationDetail` component shows a 5-dimension bar chart for the DRS sub-scores (Situational Accuracy, Decision Timeliness, Resource Efficiency, Coordination Quality, Communication). Each bar is color-coded by dimension and scaled to 1-5. The aggregate DRS (0-1 normalized) is prominently displayed with green/yellow/red coloring based on thresholds. This gives a quick visual assessment of agent performance while allowing drill-down into individual dimensions.
