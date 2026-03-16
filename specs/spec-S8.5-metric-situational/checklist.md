# Spec S8.5 — Implementation Checklist

## Red Phase (Tests First)
- [ ] Write ObservationMatch model tests
- [ ] Write AgentAccuracyScore model tests
- [ ] Write SituationalAccuracyResult model tests
- [ ] Write keyword_similarity tests
- [ ] Write extract_observations_from_decisions tests
- [ ] Write extract_expected_observations tests
- [ ] Write match_observations tests
- [ ] Write precision/recall/F1 computation tests
- [ ] Write f1_to_score mapping tests
- [ ] Write full compute() integration tests
- [ ] Write empty observation graceful degradation tests
- [ ] Write per-agent breakdown tests
- [ ] Verify all tests FAIL (no implementation yet)

## Green Phase (Implementation)
- [ ] Implement Pydantic models (ObservationMatch, AgentAccuracyScore, SituationalAccuracyResult)
- [ ] Implement keyword_similarity()
- [ ] Implement extract_observations_from_decisions()
- [ ] Implement extract_expected_observations()
- [ ] Implement match_observations()
- [ ] Implement f1_to_score()
- [ ] Implement SituationalAccuracyMetric.compute()
- [ ] All tests pass

## Refactor Phase
- [ ] ruff lint clean
- [ ] No unused imports
- [ ] All exports in __all__
