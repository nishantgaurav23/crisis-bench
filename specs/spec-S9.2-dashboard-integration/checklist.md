# Spec S9.2 — Dashboard Full Data Integration: Checklist

## Phase A: Backend API Routes (Red → Green → Refactor)

- [x] A1. Write tests for benchmark scenarios route (`test_benchmark_routes.py`)
- [x] A2. Write tests for metrics summary route (`test_metrics_route.py`)
- [x] A3. Write tests for agent decisions route (`test_agent_decisions_route.py`)
- [x] A4. Implement `src/api/routes/benchmark.py` — scenario + run endpoints
- [x] A5. Implement `src/api/routes/metrics.py` — cost/token summary
- [x] A6. Extend `src/api/routes/agents.py` — add decisions endpoint
- [x] A7. Register new routers in `src/api/main.py`
- [x] A8. All backend tests pass, ruff clean

## Phase B: WebSocket Event Wiring (Red → Green → Refactor)

- [x] B1. Write tests for WebSocket broadcast on disaster create (`test_websocket_integration.py`)
- [x] B2. Wire disaster creation to WebSocket broadcast in `disasters.py`
- [x] B3. All WebSocket tests pass

## Phase C: Dashboard Data Integration

- [x] C1. Create `useCrisisWebSocket` React hook
- [x] C2. Add new API client functions to `dashboard/src/lib/api.ts`
- [x] C3. Update GeoMap to fetch live data + respond to WebSocket events
- [x] C4. Update AgentFlow to fetch live data + respond to WebSocket events
- [x] C5. Update MetricsPanel to fetch live data + respond to WebSocket events
- [x] C6. Update Timeline to use WebSocket events (remove mock data)

## Phase D: New Dashboard Components

- [x] D1. Create `ScenarioReplay.tsx` component
- [x] D2. Create `EvaluationDetail.tsx` component
- [x] D3. Update main page (`page.tsx`) to wire all components together

## Phase E: Verification

- [x] E1. All backend tests pass (30/30)
- [x] E2. Ruff lint clean
- [x] E3. Dashboard builds without errors (`npm run build`)
- [x] E4. All outcomes O1-O7 verified
