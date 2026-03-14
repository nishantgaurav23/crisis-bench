# Spec S2.5 — Telemetry: Explanation

## Why This Spec Exists

Every module in CRISIS-BENCH needs three observability primitives: structured logging (debug/audit), metrics (dashboards/alerts), and LLM call tracing (cost attribution). Without a unified telemetry module, each module would roll its own logging (inconsistent formats), metrics (duplicate registrations), and Langfuse integration (connection boilerplate). S2.5 centralizes this so downstream specs (S2.6 LLM Router, S7.1 Base Agent, S9.3 Langfuse integration, S9.4 Grafana dashboards) import from one place.

## What It Does

`src/shared/telemetry.py` provides:

1. **`get_logger(name, **binds)`** — Returns a structlog bound logger configured for JSON output with auto-injected `timestamp` (ISO 8601 UTC) and `severity`. Callers bind `agent_id` and `trace_id` per-request. This is the only logger factory in the project.

2. **8 Prometheus metrics** (module-level singletons):
   - `crisis_llm_requests_total` — Counter by provider/tier/status
   - `crisis_llm_tokens_total` — Counter by provider/tier/direction
   - `crisis_llm_latency_seconds` — Histogram by provider/tier
   - `crisis_llm_cost_dollars` — Counter by provider/tier
   - `crisis_agent_tasks_total` — Counter by agent_id/status
   - `crisis_agent_task_duration_seconds` — Histogram by agent_id
   - `crisis_cache_operations_total` — Counter by operation (hit/miss/set)
   - `crisis_errors_total` — Counter by error_code/severity

3. **`setup_metrics_endpoint(app)`** — Mounts `/metrics` on FastAPI for Prometheus scraping.

4. **`LangfuseTracer`** — Thin wrapper around Langfuse client. `start_trace()` / `end_trace()` / `log_llm_call()`. Degrades to no-op when Langfuse is unreachable (logs one warning, then silent).

5. **`hash_content(text)`** — Truncated SHA-256 (16 hex chars) for PII protection. Used instead of logging raw LLM responses.

6. **`setup_telemetry(settings)`** — One-call init returning `TelemetryContext(logger, tracer)`.

## How It Works

- **structlog** is configured once (`_configure_structlog()`) with JSON renderer, UTC timestamps, and log-level filtering from `CrisisSettings.LOG_LEVEL`. The `make_filtering_bound_logger` wrapper filters at the structlog level (not stdlib), so DEBUG messages are dropped before serialization when LOG_LEVEL=INFO.

- **Prometheus metrics** are created at module import time (standard pattern for `prometheus_client`). The FastAPI `/metrics` endpoint uses `make_asgi_app()` mounted as a sub-application.

- **Langfuse** connection is attempted in `LangfuseTracer.__init__()`. If it fails (network error, wrong credentials), `enabled` is set to `False` and all methods become no-ops. This is critical because agents must never block on observability failures.

## How It Connects

| Downstream Spec | What It Uses |
|----------------|--------------|
| S2.6 (LLM Router) | `LLM_REQUESTS`, `LLM_TOKENS`, `LLM_LATENCY`, `LLM_COST` counters; `LangfuseTracer.log_llm_call()` |
| S2.8 (Cost Tracker) | `LLM_COST` counter for real-time budget tracking |
| S7.1 (Base Agent) | `get_logger()`, `AGENT_TASKS`, `AGENT_TASK_DURATION`, `LangfuseTracer.start_trace()/end_trace()` |
| S3.1 (API Gateway) | `setup_metrics_endpoint(app)` to expose `/metrics` |
| S9.3 (Langfuse Integration) | Extends `LangfuseTracer` with prompt versioning, cost attribution |
| S9.4 (Grafana Dashboards) | Prometheus scrapes `/metrics` → Grafana queries |

## Interview Q&A

**Q: Why structlog instead of Python's logging module?**
A: structlog produces structured JSON logs — each entry is a JSON object with typed fields. Standard Python logging produces unstructured text strings that are painful to parse. With JSON logs, you can pipe directly to Grafana/Loki for dashboards and search. In production, structured logs are the difference between "grep for errors" and "query for all errors from agent X in the last 5 minutes with trace ID Y."

**Q: Why are Prometheus metrics module-level singletons?**
A: `prometheus_client` requires exactly one instance per metric name in a process. Creating a counter twice with the same name raises `ValueError`. Module-level creation guarantees single registration at import time. Any module that needs to increment a counter just imports it — no initialization ceremony.

**Q: What happens if Langfuse is down?**
A: The `LangfuseTracer` catches the connection exception, sets `enabled = False`, and logs a single warning. All subsequent calls (`start_trace`, `end_trace`, `log_llm_call`) check `enabled` and return immediately. This is the "observability must never break production" principle — tracing is a side-effect, not a critical path dependency.

**Q: Why hash LLM responses instead of logging them?**
A: Two reasons: (1) PII protection — LLM responses may contain user data, location info, or names from crisis reports. Hashing makes the content non-reversible while still allowing deduplication and debugging ("same hash = same response"). (2) Log volume — LLM responses can be thousands of tokens. A 16-char hash reduces log storage by 99%.
