# Spec S2.5 — Implementation Checklist

## Phase 1: Red (Write Tests)
- [x] Create `tests/unit/test_telemetry.py`
- [x] Test structured logging (get_logger, JSON output, required fields, log level)
- [x] Test Prometheus metrics (all 8 metrics, counter/histogram ops, /metrics endpoint)
- [x] Test Langfuse tracer (init, graceful noop, trace lifecycle, LLM call logging)
- [x] Test hash_content (deterministic, collision-resistant)
- [x] Test setup_telemetry (returns TelemetryContext)
- [x] All tests fail (RED)

## Phase 2: Green (Implement)
- [x] Create `src/shared/telemetry.py`
- [x] Implement structlog configuration + get_logger
- [x] Implement Prometheus metrics (8 module-level singletons)
- [x] Implement setup_metrics_endpoint
- [x] Implement LangfuseTracer with graceful degradation
- [x] Implement hash_content
- [x] Implement setup_telemetry
- [x] All tests pass (GREEN)

## Phase 3: Refactor
- [x] Run ruff check --fix + ruff format
- [x] Verify all tests still pass
- [x] Review for code quality
