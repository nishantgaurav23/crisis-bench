# Spec S4.1: A2A Message Schemas — Implementation Checklist

## Red Phase (Tests First)
- [x] Create `tests/unit/test_a2a_schemas.py`
- [x] Write all 20 test cases (all must fail initially)
- [x] Verify tests fail with ImportError or similar

## Green Phase (Implementation)
- [x] Create `src/protocols/a2a/schemas.py`
- [x] Implement `A2AMessageType` enum
- [x] Implement `A2AArtifact` model
- [x] Implement `A2ATask` model
- [x] Implement `A2ATaskResult` model
- [x] Implement `A2AAgentCard` model
- [x] Implement `A2AMessage` envelope with `to_redis_dict()` / `from_redis_dict()`
- [x] All 21 tests pass

## Refactor Phase
- [x] Run `ruff check --fix`
- [x] Verify `__all__` exports
- [x] Verify all models have `ConfigDict(from_attributes=True)`
- [x] All tests still pass after refactor

## Verification
- [x] No external API dependencies
- [x] No hardcoded secrets
- [x] Reuses S2.1 enums (AgentType, TaskStatus, LLMTier)
- [x] Reuses S2.4 error pattern (trace_id)
