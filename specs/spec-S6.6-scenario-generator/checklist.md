# S6.6 Implementation Checklist

## Phase 1: Red (Write Failing Tests)
- [x] Create `tests/unit/test_scenario_gen.py`
- [x] Write test for scenario template structure
- [x] Write test for distribution counts
- [x] Write test for valid scenario output
- [x] Write test for event sequence ordering
- [x] Write test for language distribution
- [x] Write test for ground truth retrieval
- [x] Write test for evaluation rubric completeness
- [x] Write test for LLM failure fallback
- [x] Write test for affected states validation
- [x] Write test for complexity-severity mapping
- [x] All tests fail (Red)

## Phase 2: Green (Implement)
- [x] Define `ScenarioGenerationError` in scenario_gen.py
- [x] Define `ScenarioTemplate` data model
- [x] Define `SCENARIO_TEMPLATES` for 7 disaster types
- [x] Define `SCENARIO_DISTRIBUTION` counts
- [x] Implement `ScenarioGenerator.__init__()`
- [x] Implement `ScenarioGenerator._select_geography()`
- [x] Implement `ScenarioGenerator._build_fallback_events()`
- [x] Implement `ScenarioGenerator._build_fallback_rubric()`
- [x] Implement `ScenarioGenerator._retrieve_ground_truth()`
- [x] Implement `ScenarioGenerator.generate_scenario()`
- [x] Implement `ScenarioGenerator.generate_batch()`
- [x] All tests pass (Green) — 30/30

## Phase 3: Refactor
- [x] Run ruff, fix any issues
- [x] All tests still pass — 30/30
- [x] Update roadmap status
