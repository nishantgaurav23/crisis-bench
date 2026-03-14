# Spec S2.4: Implementation Checklist

## Phase 1: Red (Write Failing Tests)
- [x] Create `tests/unit/test_errors.py`
- [x] Write all 17 test cases from spec TDD notes (33 tests total)
- [x] Confirm all tests FAIL (no implementation yet)

## Phase 2: Green (Implement)
- [x] Create `src/shared/errors.py`
- [x] Implement `CrisisError` base class with trace_id, error_code, severity, http_status, to_dict
- [x] Implement `AgentError` hierarchy (AgentTimeoutError, AgentDelegationError, AgentLoopError)
- [x] Implement `RouterError` hierarchy (AllProvidersFailedError, RateLimitError, BudgetExceededError)
- [x] Implement `DataError` hierarchy (DatabaseConnectionError, RedisConnectionError, VectorStoreError, GraphDBError)
- [x] Implement `ProtocolError` hierarchy (A2AError, MCPError)
- [x] Implement `ExternalAPIError` + `APIRateLimitError`
- [x] Implement `CrisisValidationError`
- [x] Implement `BenchmarkError`
- [x] All tests PASS

## Phase 3: Refactor
- [x] Run ruff lint — zero violations
- [x] Verify >80% code coverage (100% achieved)
- [x] Update `__all__` exports
- [x] Verify all error codes are unique

## Phase 4: Verify + Explain
- [x] Run `/verify-spec S2.4`
- [x] Run `/explain-spec S2.4`
- [x] Update roadmap.md status → done
