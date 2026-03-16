# Spec S2.8: Cost Tracker — Implementation Checklist

## Phase 1: Tests (Red)
- [x] Create `tests/unit/test_cost_tracker.py`
- [x] Test CostRecord creation
- [x] Test CostTracker record + totals
- [x] Test per-provider breakdown
- [x] Test per-tier breakdown
- [x] Test token summary
- [x] Test budget checking (under/warning/exceeded)
- [x] Test full summary dict
- [x] Test reset
- [x] Test empty tracker

## Phase 2: Implementation (Green)
- [x] Create `src/routing/cost_tracker.py`
- [x] Implement BudgetStatus enum
- [x] Implement CostRecord dataclass
- [x] Implement CostTracker class
- [x] All tests pass

## Phase 3: Integration + Refactor
- [x] Wire CostTracker into LLMRouter
- [x] Run ruff, fix any lint issues
- [x] All tests still pass
