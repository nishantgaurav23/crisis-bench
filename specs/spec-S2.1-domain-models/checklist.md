# Spec S2.1 Implementation Checklist

## Red Phase — Tests First
- [x] Write `tests/unit/test_domain_models.py`
- [x] Test all enums (IndiaDisasterType, DisasterPhase, Severity, AgentType, LLMTier, TaskStatus, IMDCycloneClass, AlertChannel)
- [x] Test GeoPoint validation (valid coords, invalid coords)
- [x] Test core domain models (State, District, Disaster, IMDObservation, CWCRiverLevel)
- [x] Test agent models (AgentCard, AgentDecision, TaskRequest, TaskResult)
- [x] Test resource models (Resource, Shelter, NDRFBattalion)
- [x] Test alert models (Alert, SACHETAlert)
- [x] Test benchmark models (BenchmarkScenario, EvaluationRun, EvaluationMetrics)
- [x] Test LLM router models (LLMRequest, LLMResponse)
- [x] Test JSON serialization round-trip
- [x] Test from_attributes=True
- [x] All tests FAIL (red)

## Green Phase — Implementation
- [x] Implement all enums in `src/shared/models.py`
- [x] Implement GeoPoint + GeoPolygon
- [x] Implement core domain models
- [x] Implement agent models
- [x] Implement resource models
- [x] Implement alert models
- [x] Implement benchmark models
- [x] Implement LLM router models
- [x] All tests PASS (green)

## Refactor Phase
- [x] Run ruff — lint clean
- [x] Add `__all__` exports
- [x] Verify no unnecessary complexity
- [x] All tests still pass
