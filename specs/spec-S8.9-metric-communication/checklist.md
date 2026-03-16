# Spec S8.9 — Implementation Checklist

## Red Phase (Tests)
- [x] Write model tests (CommunicationEntry, SubDimensionScore, CommunicationAppropriatenessResult)
- [x] Write extraction tests (expectations from ground truth, communications from decisions)
- [x] Write sub-dimension scoring tests (language, NDMA, audience, actionable, channel)
- [x] Write composite score tests
- [x] Write full metric compute tests
- [x] Write edge case tests (empty data, missing fields)
- [x] Confirm all tests fail (Red)

## Green Phase (Implementation)
- [x] Implement Pydantic models
- [x] Implement extraction functions
- [x] Implement sub-dimension scoring functions
- [x] Implement composite score computation
- [x] Implement CommunicationAppropriatenessMetric class
- [x] Confirm all tests pass (Green)

## Refactor Phase
- [x] Run ruff, fix lint issues
- [x] Verify consistency with other metric modules
- [x] Final test run — all pass (44 tests, 278 benchmark tests total)

## Post-Implementation
- [x] Update roadmap.md status to "done"
- [x] Generate explanation.md
