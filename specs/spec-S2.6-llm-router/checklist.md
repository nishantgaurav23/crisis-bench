# S2.6 LLM Router — Implementation Checklist

## Phase 1: Red (Write Tests)
- [x] Create `tests/unit/test_llm_router.py`
- [x] Test LLMRouter initialization from CrisisSettings
- [x] Test tier routing to correct primary provider
- [x] Test automatic failover on provider failure
- [x] Test AllProvidersFailedError when chain exhausted
- [x] Test sliding-window rate limiter
- [x] Test circuit breaker state transitions
- [x] Test cost calculation
- [x] Test Prometheus metrics emission
- [x] Test empty API key providers skipped (except Ollama)
- [x] Test timeout handling
- [x] Test LLMResponse dataclass
- [x] Test LLMTier enum
- [x] Verify all tests FAIL (no implementation yet)

## Phase 2: Green (Implement)
- [x] Implement LLMProvider dataclass
- [x] Implement LLMResponse dataclass
- [x] Implement LLMTier enum
- [x] Implement SlidingWindowRateLimiter
- [x] Implement CircuitBreaker
- [x] Implement LLMRouter.__init__ (provider setup from settings)
- [x] Implement LLMRouter.call() with failover chain
- [x] Implement LLMRouter.get_provider_status()
- [x] Implement Prometheus metrics integration
- [x] Implement structlog logging
- [x] Implement optional Langfuse tracing
- [x] All tests pass (40/40)

## Phase 3: Refactor
- [x] Run ruff — fix lint issues (3 fixed)
- [x] Review for code clarity
- [x] Ensure all tests still pass (476/476 full suite)
