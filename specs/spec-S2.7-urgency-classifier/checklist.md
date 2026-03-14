# Spec S2.7 — Urgency Classifier Checklist

## Phase 1: Red (Write Failing Tests)
- [x] Create `tests/unit/test_urgency_classifier.py`
- [x] Test IMD color code → urgency mapping (4 colors)
- [x] Test earthquake magnitude → urgency mapping (5 ranges)
- [x] Test IMD cyclone class → urgency mapping (7 classes)
- [x] Test CWC river level → urgency mapping (4 statuses)
- [x] Test disaster type default urgency (10 types)
- [x] Test multi-signal max aggregation
- [x] Test phase escalation (+1 for active_response)
- [x] Test population factor (+1 for >1M)
- [x] Test urgency → LLMTier mapping
- [x] Test edge cases (no signals, boundary values)
- [x] Test Pydantic model validation
- [x] All tests fail (RED)

## Phase 2: Green (Implement)
- [x] Add `IMDColorCode` and `RiverLevelStatus` enums to `src/shared/models.py`
- [x] Create `src/routing/urgency_classifier.py`
- [x] Implement `DisasterData` input model
- [x] Implement `UrgencyResult` output model
- [x] Implement `UrgencyClassifier.classify()`
- [x] Implement `UrgencyClassifier.urgency_to_tier()`
- [x] All tests pass (GREEN) — 59/59

## Phase 3: Refactor
- [x] Run `ruff check` — clean
- [x] Run `ruff format` — clean
- [x] Review code for clarity
- [x] All tests still pass — 535/535 (no regressions)
