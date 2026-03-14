# Spec S2.4: CrisisError Exception Hierarchy — Explanation

## Why This Spec Exists

Every subsystem in CRISIS-BENCH (agents, LLM router, data layer, protocols, benchmark) needs a consistent way to signal failures with enough context for debugging. Python's built-in exceptions (`RuntimeError`, `TimeoutError`) lack domain context — when a `TimeoutError` fires, you don't know if it's a database timeout, LLM provider timeout, or agent loop. This spec creates typed exceptions that tell you exactly what failed, how severe it is, and how to trace the failure across agent boundaries.

## What It Does

Defines a 21-class exception hierarchy rooted at `CrisisError`:

- **CrisisError** — base class with auto-generated 8-char hex trace IDs, structured context dicts, error codes, severity levels (low/medium/high/critical), and HTTP status mapping
- **AgentError** subtree — timeout (504), delegation failure (502), loop detection (508)
- **RouterError** subtree — all providers failed (503), rate limit (429), budget exceeded (429)
- **DataError** subtree — PostgreSQL (503), Redis (503), ChromaDB (503), Neo4j (503)
- **ProtocolError** subtree — A2A (502), MCP (502)
- **ExternalAPIError** subtree — generic API failure (502), rate limit (429)
- **CrisisValidationError** — data validation (422), named to avoid collision with Pydantic
- **BenchmarkError** — benchmark runner/evaluation failures (500)

Every error has:
- `error_code` — unique UPPER_SNAKE_CASE identifier (e.g., `AGENT_TIMEOUT`)
- `severity` — operational severity for alerting decisions
- `http_status` — HTTP status code for API responses
- `trace_id` — 8-char hex for distributed tracing
- `to_dict()` — structured JSON for logging

## How It Works

1. Error is raised: `raise AgentTimeoutError("agent timed out", context={"agent_id": "orchestrator"})`
2. `CrisisError.__init__` auto-generates a trace_id (or uses one from context), stores context
3. `str(err)` produces: `[a1b2c3d4] AGENT_TIMEOUT: agent timed out`
4. `err.to_dict()` returns: `{"error_code": "AGENT_TIMEOUT", "message": "...", "trace_id": "a1b2c3d4", "severity": "high", "context": {"agent_id": "orchestrator", "trace_id": "a1b2c3d4"}}`
5. API gateway catches `CrisisError`, uses `err.http_status` for response code, `err.to_dict()` for body
6. Telemetry (S2.5) uses `err.to_dict()` for structured JSON logging

## How It Connects

- **S2.5 (Telemetry)** — structlog uses `to_dict()` for structured error logging
- **S2.6 (LLM Router)** — raises `AllProvidersFailedError`, `RateLimitError`, `BudgetExceededError`
- **S3.1 (API Gateway)** — catches `CrisisError`, maps `http_status` to HTTP responses
- **S4.1 (A2A Schemas)** — raises `A2AError` for message failures
- **S4.4 (MCP Base)** — raises `MCPError` for tool failures
- **S7.x (All Agents)** — raise/catch `AgentError` subtree
- **S8.x (Benchmark)** — raises `BenchmarkError`

## Files

| File | Purpose |
|------|---------|
| `src/shared/errors.py` | 21-class exception hierarchy (99 statements, 100% coverage) |
| `tests/unit/test_errors.py` | 33 tests covering all classes, uniqueness, inheritance, serialization |
