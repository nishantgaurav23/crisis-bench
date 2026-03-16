# Spec S9.2 — Dashboard Full Data Integration

**Status**: spec-written
**Phase**: 9 (Optimization & Polish)
**Depends On**: S3.4-S3.7 (dashboard components), S7.9 (agent integration), S8.4 (evaluation engine)
**Location**: `dashboard/src/`, `src/api/routes/`

---

## 1. Overview

Wire the existing dashboard components (GeoMap, AgentFlow, MetricsPanel, Timeline) to live backend data via REST API endpoints and WebSocket real-time events. Add new API routes for benchmark results and metrics, a scenario replay UI, and evaluation result display. Replace all mock/hardcoded data with real data from the agent system and benchmark engine.

---

## 2. Outcomes

| # | Outcome | Measurable |
|---|---------|------------|
| O1 | GeoMap renders live disasters from API + real-time updates via WebSocket | Map shows markers from `GET /api/v1/disasters` and updates on `disaster.created`/`disaster.updated` events |
| O2 | AgentFlow shows live agent status with real-time WebSocket updates | Agent cards update status/last_active on `agent.status` events |
| O3 | MetricsPanel displays real cost/token data from API | Panel fetches from `GET /api/v1/metrics/summary` and updates on `metrics.update` events |
| O4 | Timeline shows real events from WebSocket stream | Timeline appends events from all WebSocket channels (disasters, agents, metrics) |
| O5 | Benchmark API endpoints serve scenario and evaluation data | `GET /api/v1/benchmark/scenarios`, `GET /api/v1/benchmark/runs/{id}` return real data |
| O6 | Scenario replay UI allows selecting and viewing benchmark scenarios | New `ScenarioReplay` component shows scenario details, event timeline, evaluation scores |
| O7 | Evaluation results displayed with per-dimension DRS breakdown | `EvaluationDetail` component shows 5-dimension radar chart + justifications |

---

## 3. API Endpoints (New)

### 3.1 Benchmark Routes (`src/api/routes/benchmark.py`)

```
GET  /api/v1/benchmark/scenarios              → List scenarios (filterable by category, complexity)
GET  /api/v1/benchmark/scenarios/{id}         → Scenario detail with event sequence
GET  /api/v1/benchmark/runs                   → List evaluation runs (filterable by scenario_id)
GET  /api/v1/benchmark/runs/{id}              → Evaluation run detail with dimension scores
```

### 3.2 Metrics Route (`src/api/routes/metrics.py`)

```
GET  /api/v1/metrics/summary                  → Current cost/token/latency summary by provider
```

### 3.3 Agent Decisions Route (extend `src/api/routes/agents.py`)

```
GET  /api/v1/agents/{agent_type}/decisions    → Recent decisions from a specific agent
```

---

## 4. WebSocket Integration

### 4.1 Backend → Dashboard Event Flow

The WebSocket manager (`src/api/websocket.py`) already supports `broadcast()`. This spec wires it to real sources:

| Event Type | Source | Payload |
|-----------|--------|---------|
| `disaster.created` | `POST /api/v1/disasters` handler | Full `Disaster` dict |
| `disaster.updated` | Future: agent decision triggers update | Updated fields |
| `agent.status` | Agent `start()`/`stop()`/`handle_task()` lifecycle | `{agent_type, status, current_task, last_active}` |
| `agent.decision` | Agent `run_graph()` completion | `{agent_type, decision_type, confidence, reasoning, cost_usd, latency_ms}` |
| `metrics.update` | LLM Router after each call | `{total_cost, total_tokens, provider_breakdown[]}` |

### 4.2 Dashboard WebSocket Hook (`dashboard/src/hooks/useCrisisWebSocket.ts`)

React hook that:
- Connects on mount, disconnects on unmount
- Subscribes to all channels
- Dispatches events to the appropriate state handlers
- Reconnects automatically on disconnect

---

## 5. Dashboard Components (Modifications)

### 5.1 GeoMap — Live Data

- On mount: fetch `GET /api/v1/disasters` to populate initial markers
- On `disaster.created`: add new marker with animation
- On `disaster.updated`: update existing marker severity/phase

### 5.2 AgentFlow — Live Status

- On mount: fetch `GET /api/v1/agents` for initial state
- On `agent.status`: update agent card status + `last_active` display
- On `agent.decision`: flash the agent card briefly to indicate activity

### 5.3 MetricsPanel — Live Metrics

- On mount: fetch `GET /api/v1/metrics/summary` for initial data
- On `metrics.update`: update cost gauge + provider breakdown
- Show budget alert when cost > 80% of monthly budget

### 5.4 Timeline — Live Events

- Remove all mock data
- Populate from WebSocket events only (real-time stream)
- Persist last 100 events in React state

### 5.5 New: ScenarioReplay Component (`dashboard/src/components/ScenarioReplay.tsx`)

- Dropdown to select from available scenarios (`GET /api/v1/benchmark/scenarios`)
- Selected scenario shows: category, complexity, affected states, event count
- Event sequence displayed as a vertical timeline with phase badges
- Link to evaluation runs for this scenario

### 5.6 New: EvaluationDetail Component (`dashboard/src/components/EvaluationDetail.tsx`)

- Shows evaluation run results for a selected scenario
- 5-dimension score display (bar chart or radar)
- Per-dimension justification text
- Aggregate DRS score prominently displayed
- Cost and token usage for the run

---

## 6. Dashboard Page Updates

### 6.1 Main Dashboard Page (`dashboard/src/app/page.tsx`)

- Wire all components to the `useCrisisWebSocket` hook
- Pass live data to GeoMap, AgentFlow, MetricsPanel, Timeline
- Add ScenarioReplay and EvaluationDetail sections

---

## 7. Non-Goals

- No scenario execution from dashboard (benchmark runs are CLI-only)
- No agent configuration from dashboard (config is via `.env`)
- No user authentication (single-user local system)
- No persistent storage for WebSocket events (in-memory only)

---

## 8. TDD Notes

### Unit Tests (Backend)

| Test | File | What It Tests |
|------|------|--------------|
| Benchmark routes CRUD | `tests/unit/test_benchmark_routes.py` | Scenario listing, filtering, run detail endpoints |
| Metrics route | `tests/unit/test_metrics_route.py` | Cost/token summary aggregation |
| Agent decisions route | `tests/unit/test_agent_decisions_route.py` | Decision listing with filters |
| WebSocket broadcast on disaster create | `tests/unit/test_websocket_integration.py` | Disaster creation triggers WebSocket event |

### Unit Tests (Frontend)

Frontend tests are out of scope — the dashboard is a visual tool and will be validated by manual inspection + API integration tests.

### Integration Tests

| Test | What It Tests |
|------|--------------|
| API → WebSocket → Dashboard data flow | Create disaster via API, verify WebSocket event emitted with correct payload |
| Benchmark scenario → evaluation run → API | Verify evaluation runs are queryable and return dimension scores |

---

## 9. File Manifest

### New Files
- `src/api/routes/benchmark.py` — Benchmark scenarios + evaluation runs API
- `src/api/routes/metrics.py` — Metrics summary API
- `dashboard/src/hooks/useCrisisWebSocket.ts` — React WebSocket hook
- `dashboard/src/components/ScenarioReplay.tsx` — Scenario replay component
- `dashboard/src/components/EvaluationDetail.tsx` — Evaluation result display
- `tests/unit/test_benchmark_routes.py` — Backend benchmark route tests
- `tests/unit/test_metrics_route.py` — Backend metrics route tests

### Modified Files
- `src/api/main.py` — Register new route routers
- `src/api/routes/agents.py` — Add decisions endpoint
- `src/api/routes/disasters.py` — Broadcast WebSocket on create/update
- `dashboard/src/components/GeoMap.tsx` — Fetch live data + WebSocket updates
- `dashboard/src/components/AgentFlow.tsx` — WebSocket status updates
- `dashboard/src/components/MetricsPanel.tsx` — Live metrics from API
- `dashboard/src/components/Timeline.tsx` — WebSocket event stream
- `dashboard/src/app/page.tsx` — Wire components to live data
- `dashboard/src/lib/api.ts` — Add new API client functions
