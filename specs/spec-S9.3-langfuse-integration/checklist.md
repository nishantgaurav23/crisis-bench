# S9.3 Langfuse Full Integration — Checklist

## Phase 1: Tests (Red)
- [x] Write tests for enhanced LangfuseTracer API
- [x] Write tests for prompt versioning
- [x] Write tests for session grouping
- [x] Write tests for cost attribution
- [x] Write tests for BaseAgent integration
- [x] Write tests for LLM Router parent trace support
- [x] Write tests for graceful degradation
- [x] Verify all tests FAIL (Red)

## Phase 2: Implementation (Green)
- [x] Enhance LangfuseTracer with span/generation hierarchy
- [x] Add prompt versioning methods
- [x] Add session_id support to traces
- [x] Add cost metadata to generations
- [x] Integrate tracer into BaseAgent.handle_task() and reason()
- [x] Update LLM Router to accept parent trace handle
- [x] Verify all tests PASS (Green)

## Phase 3: Refactor
- [x] Run ruff, fix lint issues
- [x] Review for clean separation of concerns
- [x] Ensure no Langfuse exceptions leak to business logic
- [x] All tests still pass after refactoring
