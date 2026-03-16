# Spec S8.3 — Scenario Runner Checklist

## Phase 1: Red (Write Failing Tests)
- [x] Write SimulatedClock tests (start, elapsed, acceleration, pause/resume, wait_until)
- [x] Write EventDispatcher tests (schedule, dispatch order, inject, counts)
- [x] Write AgentDecisionCollector tests (record, totals, to_evaluation_data)
- [x] Write ScenarioRunner tests (status transitions, run, pause, resume, abort, inject, error handling)
- [x] Verify all tests FAIL (no implementation yet)

## Phase 2: Green (Implement Minimum Code)
- [x] Implement RunStatus enum
- [x] Implement SimulatedClock
- [x] Implement EventDispatcher
- [x] Implement AgentDecisionCollector
- [x] Implement ScenarioRunner
- [x] All tests pass (33/33)

## Phase 3: Refactor
- [x] Run ruff, fix any lint issues
- [x] Verify all tests still pass (33/33)
- [x] Verify existing S8.1/S8.2 tests still pass (62/62)
- [x] Update roadmap.md status to done
