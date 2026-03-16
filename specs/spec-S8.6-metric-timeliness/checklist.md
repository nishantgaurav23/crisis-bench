# Spec S8.6: Implementation Checklist

## Red Phase (Tests First)
- [x] Write `AgentTimeliness` and `DecisionTimelinessResult` model tests
- [x] Write on-time scoring test (within window → 5.0)
- [x] Write early scoring test (before window → 3.0-5.0)
- [x] Write late scoring test (after window → decay toward 1.0)
- [x] Write missing decision test (→ 1.0)
- [x] Write full compute test (scenario + run → result)
- [x] Write edge case tests (empty inputs)
- [x] Write aggregate scoring test (multiple agents)
- [x] Write penalty factor test
- [x] Verify all tests FAIL (Red)

## Green Phase (Implementation)
- [x] Implement `AgentTimeliness` model
- [x] Implement `DecisionTimelinessResult` model
- [x] Implement `score_agent_timeliness()` helper
- [x] Implement `extract_decision_times()` helper
- [x] Implement `DecisionTimelinessMetric` class
- [x] All tests pass (Green)

## Refactor Phase
- [x] Run ruff, fix any lint issues
- [x] Ensure all tests still pass
- [x] Verify no hardcoded secrets or paid API calls

## Verification
- [x] `pytest tests/unit/test_metric_timeliness.py -v` passes (29/29)
- [x] `ruff check src/benchmark/metrics/timeliness.py` clean
- [x] No external API calls in metric code
