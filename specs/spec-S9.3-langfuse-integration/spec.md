# Spec S9.3: Langfuse Full Integration

**Status**: done

## Overview

**Feature**: Full Langfuse LLM observability integration
**Location**: `src/shared/telemetry.py` (enhanced), integration across LLM Router and BaseAgent
**Depends On**: S2.5 (Telemetry), S7.1 (Base Agent)
**Phase**: 9 — Optimization & Polish

## Problem

The current `LangfuseTracer` in `src/shared/telemetry.py` is a thin wrapper that:
1. Creates a new trace per LLM call in the router (no parent-child hierarchy)
2. Doesn't support spans (sub-operations within a trace)
3. Doesn't track prompt versions
4. Doesn't attribute costs to specific agents
5. Doesn't support session-based grouping (e.g., by scenario run)
6. BaseAgent doesn't create traces for task execution

## Requirements

### R1: Hierarchical Tracing
- Each agent task execution creates a **trace** (top-level)
- Each LLM call within that task creates a **generation** (child of trace)
- Each sub-operation (graph node execution) creates a **span** (child of trace)
- Traces carry `agent_id`, `trace_id`, `disaster_id`, `session_id`

### R2: Session Grouping
- All traces within a benchmark scenario run share a `session_id`
- Sessions can be queried in Langfuse UI to see full scenario execution

### R3: Prompt Versioning
- Agent system prompts are registered as named prompts in Langfuse
- Prompt versions are tracked per agent type
- Changes to system prompts create new versions automatically

### R4: Cost Attribution
- Every generation includes cost breakdown (input cost, output cost, total)
- Costs are tagged by agent_id and tier for per-agent cost analysis
- Langfuse metadata includes provider name and tier

### R5: Enhanced LangfuseTracer API
- `start_trace()` — top-level trace for agent task
- `start_span()` — sub-operation within a trace
- `end_span()` — complete a span with output
- `log_generation()` — log an LLM call as a generation (child of trace/span)
- `register_prompt()` — register/update a named prompt
- `get_prompt()` — retrieve latest prompt version
- `flush()` / `shutdown()` — graceful cleanup

### R6: BaseAgent Integration
- BaseAgent.handle_task() creates a Langfuse trace for the entire task
- BaseAgent.reason() logs each LLM call as a generation under the active trace
- Trace is ended when task completes (success or failure)

### R7: LLM Router Integration
- Router accepts an optional parent trace/span handle
- When provided, generations are nested under the parent
- When not provided, behaves as today (standalone trace or no-op)

### R8: Graceful Degradation
- All Langfuse operations are no-op when Langfuse is unavailable
- No exceptions propagate from tracing code to business logic
- Works in test environments without Langfuse running

## Outcomes

- [ ] Enhanced `LangfuseTracer` with hierarchical trace/span/generation support
- [ ] Prompt versioning via Langfuse prompt management
- [ ] Session grouping for benchmark scenario runs
- [ ] Cost attribution per agent per tier in Langfuse metadata
- [ ] BaseAgent creates traces for task execution, generations for LLM calls
- [ ] LLM Router supports parent trace handles for nested generations
- [ ] All operations degrade gracefully when Langfuse is unavailable
- [ ] >80% test coverage with mocked Langfuse client

## TDD Notes

### Test Strategy
- Mock the `langfuse.Langfuse` client entirely — never hit a real Langfuse server
- Test trace hierarchy: trace → span → generation nesting
- Test graceful degradation: disabled tracer returns None handles, no errors
- Test prompt registration and retrieval
- Test session ID propagation
- Test cost metadata in generations
- Test BaseAgent integration with mocked tracer
- Test LLM Router with parent trace handle

### Key Test Cases
1. `test_start_trace_returns_handle` — enabled tracer returns handle
2. `test_start_trace_disabled_returns_none` — disabled tracer returns None
3. `test_start_span_under_trace` — span created as child of trace
4. `test_log_generation_with_cost` — generation includes cost metadata
5. `test_session_id_propagation` — trace carries session_id
6. `test_prompt_register_and_get` — round-trip prompt versioning
7. `test_graceful_degradation_on_error` — exceptions swallowed
8. `test_base_agent_creates_trace` — handle_task creates trace
9. `test_base_agent_reason_logs_generation` — reason() logs generation
10. `test_router_with_parent_trace` — router nests generation under parent
11. `test_flush_and_shutdown` — cleanup works with and without client
