# Spec S2.4: CrisisError Exception Hierarchy

**Status**: done
**Location**: `src/shared/errors.py`
**Depends On**: None
**Consumed By**: S2.5 (telemetry), S2.6 (LLM Router), S3.1 (API gateway), S4.1 (A2A schemas), all agents

---

## 1. Overview

A custom exception hierarchy rooted at `CrisisError` that provides:
- Typed error categories for every subsystem (agents, LLM router, data layer, protocols, benchmark)
- Automatic trace ID generation for distributed tracing
- Structured error context (agent_id, provider, tier, etc.) for logging
- HTTP status code mapping for API error responses
- Severity classification for error-handling decisions

This is a foundational module — every other module catches or raises these errors.

---

## 2. Exception Hierarchy

```
CrisisError (base)
├── AgentError
│   ├── AgentTimeoutError          # Agent exceeded AGENT_TIMEOUT_SECONDS (120s)
│   ├── AgentDelegationError       # Delegation depth exceeded or target unavailable
│   └── AgentLoopError             # Loop detection triggered (120s cycle)
├── RouterError
│   ├── AllProvidersFailedError    # All providers in fallback chain exhausted
│   ├── RateLimitError             # Provider rate limit hit
│   └── BudgetExceededError        # Per-scenario budget ceiling breached
├── DataError
│   ├── DatabaseConnectionError    # PostgreSQL/PostGIS connection failure
│   ├── RedisConnectionError       # Redis connection failure
│   ├── VectorStoreError           # ChromaDB operation failure
│   └── GraphDBError               # Neo4j operation failure
├── ProtocolError
│   ├── A2AError                   # A2A message serialization/delivery failure
│   └── MCPError                   # MCP server/tool invocation failure
├── ExternalAPIError               # External API (IMD, SACHET, USGS, etc.) failure
│   └── APIRateLimitError          # External API rate limit
├── ValidationError                # Data validation failure (distinct from Pydantic's)
└── BenchmarkError                 # Benchmark runner/evaluation errors
```

---

## 3. Requirements

### 3.1 Base CrisisError
- Must accept `message: str` and optional `context: dict[str, Any]`
- Must auto-generate a `trace_id` (UUID4 hex, 8 chars) if not provided in context
- Must expose `trace_id`, `error_code`, `severity`, `http_status` as properties
- Must implement `to_dict()` returning structured error data for JSON logging
- Must be serializable to JSON (no non-serializable objects in context)

### 3.2 Error Codes
- Each error class has a unique string code: e.g., `"AGENT_TIMEOUT"`, `"ALL_PROVIDERS_FAILED"`
- Codes are UPPER_SNAKE_CASE, prefixed by subsystem

### 3.3 Severity Levels
- `"low"` — recoverable, log and continue (e.g., cache miss)
- `"medium"` — degraded service, fallback available (e.g., single provider failure)
- `"high"` — major failure, requires intervention (e.g., all providers failed)
- `"critical"` — system-level failure (e.g., database down)

### 3.4 HTTP Status Mapping
- Each error maps to an HTTP status code for API responses
- AgentTimeoutError → 504, AllProvidersFailedError → 503, BudgetExceededError → 429, etc.

### 3.5 Context
- Context dict can carry arbitrary metadata: `agent_id`, `provider`, `tier`, `disaster_id`, etc.
- `trace_id` is always present in context (auto-generated if missing)

---

## 4. Outcomes

1. `src/shared/errors.py` exists with the full hierarchy
2. Every error class has a unique `error_code` and default `severity`/`http_status`
3. `CrisisError.to_dict()` returns a dict with keys: `error_code`, `message`, `trace_id`, `severity`, `context`
4. All error classes are importable from `src.shared.errors`
5. >80% test coverage

---

## 5. TDD Notes

### Tests to write FIRST (Red phase):
1. `test_crisis_error_base` — CrisisError has message, trace_id, error_code, severity, http_status
2. `test_crisis_error_auto_trace_id` — trace_id auto-generated if not provided
3. `test_crisis_error_custom_trace_id` — trace_id from context is used if provided
4. `test_crisis_error_to_dict` — to_dict returns correct structure
5. `test_crisis_error_context` — arbitrary context is preserved
6. `test_agent_error_hierarchy` — AgentError, AgentTimeoutError, etc. are CrisisError subclasses
7. `test_router_error_hierarchy` — RouterError and subclasses
8. `test_data_error_hierarchy` — DataError and subclasses
9. `test_protocol_error_hierarchy` — ProtocolError and subclasses
10. `test_external_api_error` — ExternalAPIError and APIRateLimitError
11. `test_validation_error` — CrisisValidationError (named to avoid collision with Pydantic)
12. `test_benchmark_error` — BenchmarkError
13. `test_error_codes_unique` — all error classes have unique error_code values
14. `test_http_status_mapping` — each error has appropriate HTTP status
15. `test_severity_values` — each error has valid severity level
16. `test_inheritance_catch` — catching CrisisError catches all subclasses
17. `test_str_repr` — str(error) includes trace_id and message

---

## 6. Interview Q&A

**Q: Why a custom exception hierarchy instead of using Python's built-in exceptions?**
A: Built-in exceptions (`RuntimeError`, `ValueError`, `TimeoutError`) lack domain context. When a `TimeoutError` fires at 3am, you don't know if it's a database timeout, an LLM provider timeout, or an agent loop. `AgentTimeoutError` vs `DatabaseConnectionError` tells you exactly what failed and which team/runbook to engage. The hierarchy also enables granular error handling: `except RouterError` catches all LLM routing issues without catching database errors.

**Q: Why auto-generate trace IDs in the error itself?**
A: In a multi-agent system, errors propagate across agent boundaries via A2A messages. Without trace IDs, correlating "Agent B failed" with "Agent A sent a bad request" requires timestamp matching across logs — fragile and slow. With trace IDs baked into every error, you grep one ID and see the entire failure chain. We use 8-char hex (4 bytes) because full UUIDs are noisy in logs while 8 chars give 4 billion unique values — more than enough for debugging sessions.

**Q: Why separate severity from HTTP status?**
A: They serve different purposes. Severity drives operational decisions (page oncall for `critical`, auto-retry for `low`). HTTP status drives API client behavior (retry on 503, don't retry on 400). A `RateLimitError` is `medium` severity (we have fallbacks) but maps to 429 (client should back off). A `DatabaseConnectionError` is `critical` severity (system is degraded) and maps to 503 (service unavailable). Collapsing them would lose information.
