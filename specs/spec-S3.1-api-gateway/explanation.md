# S3.1 — FastAPI Gateway: Explanation

## Why This Spec Exists

The API gateway is the single entry point for the CRISIS-BENCH system. Every external client — the Next.js dashboard (S3.3-S3.7), future CLI tools, and the benchmark runner (S8.3) — communicates through this gateway. Without it, agents and data have no external interface.

## What It Does

1. **Health endpoint** (`GET /health`) — returns system status, version, and environment. Used by Docker health checks and monitoring (S9.4).

2. **Disaster CRUD** (`/api/v1/disasters`) — create, list, get, delete disasters using the `Disaster` Pydantic model from S2.1. Currently uses an in-memory store; will be backed by PostgreSQL (S2.2) when the WebSocket spec (S3.2) wires up real data flows.

3. **Agent status** (`/api/v1/agents`) — returns the 7 `AgentCard` models with capabilities and LLM tier assignments. Static registry now; will become live agent status once the agent system (S7.x) is implemented.

4. **Structured error handling** — global exception handler catches all `CrisisError` subclasses (from S2.4) and returns JSON with `error_code`, `message`, `trace_id`, `severity`. This means every error in the system produces consistent, traceable API responses.

5. **CORS** — allows `http://localhost:3000` (the dashboard) to make cross-origin requests.

## How It Works

- **Application factory pattern** — `create_app()` returns a configured FastAPI instance. This pattern enables test isolation (each test gets a fresh app) and supports different configurations for dev/test/prod.

- **Router composition** — three separate routers (`health`, `disasters`, `agents`) are composed into the main app. Each router is independently testable and maps to a logical domain boundary.

- **Lifespan context manager** — `asynccontextmanager` provides startup/shutdown hooks. Currently a no-op, but will initialize database connection pools when S3.2 integrates real persistence.

## How It Connects

| Spec | Relationship |
|------|-------------|
| S1.3 (config) | Reads `ENVIRONMENT` from `CrisisSettings` for health endpoint |
| S2.1 (models) | Uses `Disaster`, `AgentCard`, `AgentType`, `LLMTier` Pydantic models |
| S2.4 (errors) | `CrisisError` exception handler produces structured JSON responses |
| S3.2 (WebSocket) | Will add WebSocket endpoint to this app for real-time dashboard updates |
| S7.x (agents) | Agent status endpoints will become live once agents are implemented |
| S8.3 (benchmark runner) | Will submit scenarios and read results via these API endpoints |

## Interview Talking Points

**Q: Why use an application factory instead of a module-level `app = FastAPI()` object?**
A: The factory pattern (`create_app()`) solves three problems: (1) **test isolation** — each test creates a fresh app with clean state, no cross-test contamination, (2) **configuration flexibility** — you can pass different settings for dev/test/prod, (3) **circular import prevention** — the app is created on demand, not at import time.

**Q: Why an in-memory store instead of PostgreSQL right away?**
A: Vertical slicing — get the API surface working and tested first, then wire up persistence. This lets the dashboard team (Phase 3) start integrating immediately while database integration happens in parallel. The in-memory store also makes tests fast (0.22s for 12 tests) with no Docker dependency.

**Q: How does the CrisisError handler work?**
A: FastAPI's `@app.exception_handler(CrisisError)` catches any exception that inherits from `CrisisError`. Since all our custom exceptions (AgentTimeoutError, RouterError, DataError, etc.) inherit from it, one handler covers them all. Each exception carries its own `http_status`, `error_code`, and `trace_id` — the handler just calls `exc.to_dict()` and returns it as JSON. This is the **Template Method pattern** — the base class defines the structure, subclasses customize the details.
