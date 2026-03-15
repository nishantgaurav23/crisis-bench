# S3.1 — FastAPI Gateway

**Status**: spec-written
**Depends On**: S1.3 (config), S2.1 (domain models), S2.4 (error handling)
**Location**: `src/api/main.py`, `src/api/routes/`

---

## Overview

FastAPI application serving as the API gateway for CRISIS-BENCH. Provides health checks, disaster CRUD, agent status endpoints, and structured error responses using the CrisisError hierarchy. CORS enabled for dashboard (localhost:3000).

## Requirements

### R1: Application Factory
- `create_app()` function returning a FastAPI instance
- CORS middleware allowing `localhost:3000` (dashboard) and configurable origins
- Exception handlers for `CrisisError` hierarchy → structured JSON responses
- Lifespan context manager for startup/shutdown hooks (no-op initially, ready for DB pool)

### R2: Health Endpoint
- `GET /health` → `{"status": "ok", "version": "0.1.0", "environment": "development"}`
- Returns 200 when healthy
- Reads environment from `CrisisSettings`

### R3: Disaster CRUD Routes
- `POST /api/v1/disasters` — create disaster (accepts `Disaster` model)
- `GET /api/v1/disasters` — list disasters (in-memory store for now)
- `GET /api/v1/disasters/{disaster_id}` — get single disaster
- `DELETE /api/v1/disasters/{disaster_id}` — delete disaster
- All responses use Pydantic models from `src/shared/models.py`
- 404 for missing disasters using `CrisisValidationError`

### R4: Agent Status Routes
- `GET /api/v1/agents` — list all 7 agent cards (static for now)
- `GET /api/v1/agents/{agent_type}` — get single agent card
- Returns `AgentCard` models from `src/shared/models.py`

### R5: Structured Error Responses
- Global exception handler catches `CrisisError` subclasses
- Returns JSON: `{"error_code", "message", "trace_id", "severity", "context"}`
- HTTP status from `CrisisError.http_status`
- Unhandled exceptions → 500 with generic message

## Files

| File | Purpose |
|------|---------|
| `src/api/main.py` | App factory, CORS, exception handlers, lifespan |
| `src/api/routes/health.py` | Health check endpoint |
| `src/api/routes/disasters.py` | Disaster CRUD (in-memory store) |
| `src/api/routes/agents.py` | Agent status endpoints |
| `tests/unit/test_api_gateway.py` | All tests |

## TDD Notes

### Red Phase — Tests to Write First
1. `test_health_returns_ok` — GET /health returns 200 + expected JSON
2. `test_create_disaster` — POST /api/v1/disasters with valid payload → 201
3. `test_list_disasters` — GET /api/v1/disasters → 200 + list
4. `test_get_disaster` — GET /api/v1/disasters/{id} → 200
5. `test_get_disaster_not_found` — GET /api/v1/disasters/{bad_id} → 404 + error JSON
6. `test_delete_disaster` — DELETE /api/v1/disasters/{id} → 204
7. `test_list_agents` — GET /api/v1/agents → 200 + 7 agents
8. `test_get_agent` — GET /api/v1/agents/{type} → 200
9. `test_get_agent_not_found` — GET /api/v1/agents/invalid → 404
10. `test_crisis_error_handler` — CrisisError → structured JSON + correct HTTP status
11. `test_cors_headers` — CORS headers present for allowed origin
12. `test_create_disaster_invalid` — invalid payload → 422

## Outcomes

- [ ] `GET /health` returns 200 with status/version/environment
- [ ] Disaster CRUD works with in-memory store
- [ ] Agent status endpoints return all 7 agent cards
- [ ] CrisisError exceptions produce structured JSON responses
- [ ] CORS allows dashboard origin
- [ ] All tests pass, ruff clean
