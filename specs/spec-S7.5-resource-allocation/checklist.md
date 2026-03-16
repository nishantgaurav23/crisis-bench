# S7.5 ResourceAllocation Agent — Implementation Checklist

## Phase 1: Red (Write Failing Tests)
- [x] Write test_resource_allocation.py with all 18 test cases
- [x] Verify all tests fail (Red)

## Phase 2: Green (Implement)
- [x] Implement haversine_distance utility
- [x] Implement greedy_allocate fallback heuristic
- [x] Implement OR-Tools optimize_allocation function
- [x] Implement ResourceAllocationState TypedDict
- [x] Implement ResourceAllocation agent class (extends BaseAgent)
- [x] Implement assess_demand graph node
- [x] Implement inventory_resources graph node
- [x] Implement optimize_allocation graph node
- [x] Implement format_plan graph node
- [x] Wire up LangGraph state machine
- [x] Verify all tests pass (Green)

## Phase 3: Refactor
- [x] Run ruff lint + fix
- [x] Review code for clarity
- [x] Verify all tests still pass

## Phase 4: Verify
- [x] All 18 tests pass
- [x] ruff clean
- [x] No hardcoded secrets
- [x] All LLM calls via router
- [x] OR-Tools used (free, Apache 2.0)
