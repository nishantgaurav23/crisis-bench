# Spec S8.4: Evaluation Engine (LLM-as-Judge)

**Status**: spec-written
**Depends On**: S8.3 (Scenario Runner), S2.6 (LLM Router)
**Location**: `src/benchmark/evaluation_engine.py`
**Tests**: `tests/unit/test_evaluation_engine.py`

---

## 1. Purpose

The Evaluation Engine uses an **LLM-as-judge** pattern to evaluate agent decisions from benchmark scenario runs against ground truth and structured scoring rubrics. It scores across 5 dimensions (situational accuracy, decision timeliness, resource efficiency, coordination quality, communication appropriateness) and produces an aggregate Disaster Response Score (DRS).

This is the core scoring component that all individual metric modules (S8.5-S8.9) and the aggregate DRS (S8.10) depend on.

## 2. Requirements

### Functional
- **EE-01**: Accept an `EvaluationRun` (from ScenarioRunner) and its `BenchmarkScenario` (with ground truth + rubric)
- **EE-02**: Build structured LLM prompts from rubric criteria, ground truth, and agent decisions
- **EE-03**: Route evaluation LLM calls through LLM Router at `critical` tier (DeepSeek Reasoner)
- **EE-04**: Parse structured JSON scores from LLM responses (1.0-5.0 scale per dimension)
- **EE-05**: Compute per-dimension scores with rubric-based prompts
- **EE-06**: Compute aggregate DRS as weighted sum of dimension scores (weights from rubric)
- **EE-07**: Update the `EvaluationRun` record with all scores
- **EE-08**: Handle LLM failures gracefully (retry once, then mark dimension as unevaluated)
- **EE-09**: Support batch evaluation of multiple runs
- **EE-10**: Log all evaluation LLM calls via structured logging

### Non-Functional
- All LLM calls go through `LLMRouter.call()`
- Async throughout
- All external LLM calls mocked in tests
- Pydantic models for evaluation request/response

## 3. Data Flow

```
EvaluationRun (from S8.3 ScenarioRunner)
    + BenchmarkScenario (ground truth + rubric)
    ↓
EvaluationEngine.evaluate()
    ↓
Build prompt per dimension (rubric criteria + ground truth + agent decisions)
    ↓
LLMRouter.call("critical", prompt) for each dimension
    ↓
Parse JSON response → DimensionScore (score 1-5, justification)
    ↓
Compute aggregate DRS = weighted sum / 5.0 (normalized to 0-1)
    ↓
Updated EvaluationRun with all scores
```

## 4. Models

```python
class DimensionScore(BaseModel):
    dimension: str          # e.g., "situational_accuracy"
    score: float            # 1.0-5.0
    justification: str      # LLM explanation
    key_factors: list[str]  # What influenced the score

class EvaluationResult(BaseModel):
    run_id: UUID
    scenario_id: UUID
    dimension_scores: dict[str, DimensionScore]
    aggregate_drs: float    # 0.0-1.0
    total_eval_tokens: int
    total_eval_cost_usd: float
    evaluated_at: datetime
```

## 5. LLM Prompt Strategy

Each dimension gets a separate LLM call with:
1. System prompt: "You are an expert disaster response evaluator..."
2. Rubric criteria for this dimension (from scenario's EvaluationRubric)
3. Ground truth decisions (from scenario's GroundTruthDecisions)
4. Actual agent decisions (from EvaluationRun.agent_decisions)
5. Output format: JSON with score (1-5), justification, key_factors

## 6. TDD Notes

### Test Strategy
- Mock LLMRouter to return predictable JSON responses
- Test prompt building logic independently
- Test JSON parsing with valid/invalid/malformed responses
- Test aggregate DRS computation with known weights
- Test graceful degradation on LLM failure
- Test batch evaluation

### Red Phase Tests
1. `test_dimension_score_model_validation` — Pydantic validation
2. `test_evaluation_result_model` — Full result model
3. `test_build_evaluation_prompt` — Prompt contains rubric, ground truth, decisions
4. `test_parse_llm_score_response` — Valid JSON parsing
5. `test_parse_llm_score_malformed` — Handles malformed JSON gracefully
6. `test_evaluate_single_dimension` — Calls router with correct tier
7. `test_evaluate_all_dimensions` — Evaluates all 5 dimensions
8. `test_aggregate_drs_computation` — Weighted sum correct
9. `test_evaluate_full_run` — End-to-end evaluation
10. `test_llm_failure_graceful_degradation` — Marks failed dimensions
11. `test_batch_evaluate` — Multiple runs
12. `test_evaluate_updates_run_scores` — Scores populated on result
