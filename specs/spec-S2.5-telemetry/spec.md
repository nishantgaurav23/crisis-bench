# Spec S2.5 — Telemetry (structlog + Prometheus + Langfuse)

**Status**: spec-written
**Depends On**: S1.3 (Environment config)
**Location**: `src/shared/telemetry.py`
**Phase**: 2 (Shared Infrastructure)

---

## 1. Purpose

Provide a unified telemetry module that every other module imports for:
1. **Structured JSON logging** via `structlog` — required fields: `timestamp`, `agent_id`, `trace_id`, `severity`, `message`
2. **Prometheus metrics** — counters, histograms, gauges for `tokens_per_agent`, `cost_per_provider`, `latency`, `cache_hit_rate`, etc.
3. **Langfuse trace stubs** — thin wrappers so agents can start/end traces without importing Langfuse directly; graceful no-op when Langfuse is unavailable

## 2. Requirements

### FR-1: Structured Logging
- Configure `structlog` to output JSON in all environments
- Auto-bind `timestamp` (ISO 8601 UTC), `severity` (log level name)
- Provide `get_logger(name, **initial_binds)` factory that returns a bound logger
- Callers bind `agent_id` and `trace_id` per-request
- Never log PII or full LLM responses — log content hashes instead
- Respect `LOG_LEVEL` from `CrisisSettings`

### FR-2: Prometheus Metrics
- Expose the following metrics via `prometheus_client`:
  - `crisis_llm_requests_total` (Counter) — labels: `provider`, `tier`, `status`
  - `crisis_llm_tokens_total` (Counter) — labels: `provider`, `tier`, `direction` (input/output)
  - `crisis_llm_latency_seconds` (Histogram) — labels: `provider`, `tier`
  - `crisis_llm_cost_dollars` (Counter) — labels: `provider`, `tier`
  - `crisis_agent_tasks_total` (Counter) — labels: `agent_id`, `status`
  - `crisis_agent_task_duration_seconds` (Histogram) — labels: `agent_id`
  - `crisis_cache_operations_total` (Counter) — labels: `operation` (hit/miss/set)
  - `crisis_errors_total` (Counter) — labels: `error_code`, `severity`
- Provide a `setup_metrics_endpoint(app: FastAPI)` function to mount `/metrics`
- All metrics are module-level singletons (created once, reused)

### FR-3: Langfuse Trace Stubs
- `LangfuseTracer` class that wraps `langfuse.Langfuse`
- `start_trace(name, agent_id, trace_id, metadata)` → returns a trace/span handle
- `end_trace(handle, output, status)` → completes the trace
- `log_llm_call(handle, model, messages, response, tokens, cost, latency)` → logs a generation
- If Langfuse is unreachable, all methods become no-ops (log a warning once, then silence)
- Uses `LANGFUSE_HOST` from `CrisisSettings`

### FR-4: Convenience Functions
- `setup_telemetry(settings: CrisisSettings)` — one-call init for structlog + Prometheus + Langfuse
- Returns a `TelemetryContext` dataclass with `logger`, `metrics` (namespace object), `tracer`

## 3. Non-Functional Requirements

- NFR-1: Zero external network calls in tests (Langfuse mocked)
- NFR-2: All functions are sync (logging/metrics don't need async)
- NFR-3: No PII in logs — use `hash_content(text) -> str` helper
- NFR-4: Module import must not fail even if Prometheus/Langfuse unavailable

## 4. API Surface

```python
# Logging
def get_logger(name: str, **initial_binds: Any) -> structlog.BoundLogger: ...

# Metrics (module-level singletons)
LLM_REQUESTS: Counter
LLM_TOKENS: Counter
LLM_LATENCY: Histogram
LLM_COST: Counter
AGENT_TASKS: Counter
AGENT_TASK_DURATION: Histogram
CACHE_OPS: Counter
ERRORS: Counter

def setup_metrics_endpoint(app: "FastAPI") -> None: ...

# Langfuse
class LangfuseTracer:
    def __init__(self, settings: CrisisSettings) -> None: ...
    def start_trace(self, name: str, *, agent_id: str = "", trace_id: str = "",
                    metadata: dict | None = None) -> TraceHandle: ...
    def end_trace(self, handle: TraceHandle, *, output: str = "",
                  status: str = "ok") -> None: ...
    def log_llm_call(self, handle: TraceHandle, *, model: str, messages: list,
                     response: str, tokens_in: int, tokens_out: int,
                     cost: float, latency_s: float) -> None: ...
    def shutdown(self) -> None: ...

# Content hashing (PII protection)
def hash_content(text: str) -> str: ...

# One-call setup
@dataclass
class TelemetryContext:
    logger: structlog.BoundLogger
    tracer: LangfuseTracer

def setup_telemetry(settings: CrisisSettings) -> TelemetryContext: ...
```

## 5. TDD Notes

### Red Phase — Tests to Write First
1. `test_get_logger_returns_bound_logger` — verify structlog logger with JSON output
2. `test_get_logger_binds_initial_context` — verify agent_id, trace_id bind
3. `test_logger_respects_log_level` — DEBUG vs INFO filtering
4. `test_logger_outputs_json_with_required_fields` — timestamp, severity, message present
5. `test_prometheus_metrics_exist` — all 8 metrics importable and correct types
6. `test_prometheus_counter_increment` — counter labels work
7. `test_prometheus_histogram_observe` — histogram records values
8. `test_setup_metrics_endpoint` — mounts `/metrics` on FastAPI app
9. `test_langfuse_tracer_init_success` — connects when Langfuse available (mocked)
10. `test_langfuse_tracer_graceful_noop` — no crash when Langfuse unreachable
11. `test_langfuse_start_end_trace` — trace lifecycle (mocked)
12. `test_langfuse_log_llm_call` — generation logged (mocked)
13. `test_hash_content_deterministic` — same input → same hash
14. `test_hash_content_different_inputs` — different inputs → different hashes
15. `test_setup_telemetry_returns_context` — full integration of all subsystems

### Green Phase
- Implement `src/shared/telemetry.py` to pass all tests

### Refactor Phase
- Run `ruff check --fix` + `ruff format`
- Ensure all tests still pass

## 6. Outcomes

- [ ] `src/shared/telemetry.py` exists with all public API
- [ ] 15+ tests passing in `tests/unit/test_telemetry.py`
- [ ] `ruff check` clean
- [ ] Prometheus metrics accessible via FastAPI `/metrics` endpoint
- [ ] Langfuse tracer degrades gracefully when unavailable
- [ ] No PII leakage — `hash_content` used for sensitive data
