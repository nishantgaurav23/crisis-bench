# S8.1 Implementation Checklist

## Phase 1: Tests (Red)
- [x] Write model validation tests for ScenarioEvent, AgentExpectation, GroundTruthDecisions
- [x] Write model validation tests for DimensionCriteria, EvaluationRubric (weight sum validation)
- [x] Write serialization round-trip tests
- [x] Write CRUD tests for scenarios (mock asyncpg)
- [x] Write CRUD tests for evaluation runs (mock asyncpg)
- [x] Verify all tests fail (Red)

## Phase 2: Implementation (Green)
- [x] Implement typed sub-models (ScenarioEvent, AgentExpectation, GroundTruthDecisions, DimensionCriteria, EvaluationRubric)
- [x] Implement BenchmarkScenario with typed fields + to_db_row/from_db_row
- [x] Implement EvaluationRun with enhanced fields
- [x] Implement scenario CRUD functions
- [x] Implement evaluation run CRUD functions
- [x] All tests pass (Green) — 34/34

## Phase 3: Refactor
- [x] Run ruff, fix any lint issues
- [x] Verify all tests still pass — 34/34
- [x] Update __init__.py exports
