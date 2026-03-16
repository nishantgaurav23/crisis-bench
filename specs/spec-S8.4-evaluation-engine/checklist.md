# Spec S8.4: Evaluation Engine — Implementation Checklist

## Red Phase (Tests First)
- [x] Write DimensionScore + EvaluationResult model tests
- [x] Write prompt building tests
- [x] Write LLM response parsing tests
- [x] Write single dimension evaluation tests
- [x] Write full evaluation tests
- [x] Write batch evaluation tests
- [x] Write graceful degradation tests
- [x] All tests fail (no implementation yet)

## Green Phase (Implementation)
- [x] Implement DimensionScore + EvaluationResult Pydantic models
- [x] Implement prompt building (system + rubric + ground truth + decisions)
- [x] Implement LLM response parsing with JSON extraction
- [x] Implement EvaluationEngine class with evaluate() method
- [x] Implement per-dimension evaluation with LLMRouter
- [x] Implement aggregate DRS computation
- [x] Implement batch_evaluate() for multiple runs
- [x] Implement graceful degradation on LLM failure
- [x] All tests pass

## Refactor Phase
- [x] Run ruff, fix any lint issues
- [x] Ensure line length <= 100
- [x] Verify all tests still pass
- [x] Update checklist status
