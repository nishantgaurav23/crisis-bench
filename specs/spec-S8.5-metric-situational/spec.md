# Spec S8.5 — Metric: Situational Accuracy

**Status**: spec-written
**Depends On**: S8.4 (Evaluation Engine)
**Location**: `src/benchmark/metrics/situational.py`
**Test File**: `tests/unit/test_metric_situational.py`

---

## 1. Purpose

Implements the **Situational Accuracy** evaluation metric — the first of 5 benchmark dimensions. This metric measures how accurately agents identify and report crisis observations against ground truth data from IMD/CWC bulletins.

It computes precision, recall, and F1 scores by comparing agent-reported observations against expected key observations from ground truth.

---

## 2. Requirements (FR-011.1)

> **Situational Accuracy** — precision/recall/F1 against IMD/CWC actual bulletin timelines

### Functional

1. Extract observations from agent decisions (key observations, event detections, data fusions)
2. Compare against ground truth `agent_expectations[*].key_observations`
3. Use fuzzy/semantic matching (not just exact string match) via configurable similarity threshold
4. Compute:
   - **Precision**: fraction of agent observations that match ground truth
   - **Recall**: fraction of ground truth observations found by agents
   - **F1**: harmonic mean of precision and recall
5. Optionally use LLM-as-judge for nuanced observation matching
6. Produce a 1.0–5.0 score suitable for the evaluation engine's DimensionScore
7. Return detailed breakdown per agent

### Non-Functional

- Pure computation (no DB or network calls) for core precision/recall/F1
- LLM-based matching is optional (falls back to keyword overlap)
- Must handle empty observations gracefully (score = 1.0)
- All functions async-compatible

---

## 3. Data Flow

```
BenchmarkScenario.ground_truth_decisions.agent_expectations[agent].key_observations
  → expected observations (list[str])

EvaluationRun.agent_decisions[*].reasoning + observations
  → actual observations (list[str])

Compare expected vs actual → precision, recall, F1 → map to 1.0-5.0 score
```

---

## 4. API

```python
class SituationalAccuracyMetric:
    """Computes situational accuracy as precision/recall/F1."""

    def __init__(self, similarity_threshold: float = 0.5, router: Any = None):
        ...

    async def compute(
        self,
        scenario: BenchmarkScenario,
        evaluation_run: EvaluationRun,
    ) -> SituationalAccuracyResult:
        ...

class SituationalAccuracyResult(BaseModel):
    precision: float  # 0.0-1.0
    recall: float     # 0.0-1.0
    f1: float         # 0.0-1.0
    score: float      # 1.0-5.0 (mapped from F1)
    matched_observations: list[ObservationMatch]
    unmatched_expected: list[str]
    unmatched_actual: list[str]
    per_agent_scores: dict[str, AgentAccuracyScore]

class ObservationMatch(BaseModel):
    expected: str
    actual: str
    similarity: float  # 0.0-1.0

class AgentAccuracyScore(BaseModel):
    agent_id: str
    precision: float
    recall: float
    f1: float
    matched: int
    expected_total: int
    actual_total: int
```

---

## 5. Scoring Mapping

F1 → Score (1.0-5.0):
- F1 >= 0.9 → 5.0
- F1 >= 0.7 → 4.0
- F1 >= 0.5 → 3.0
- F1 >= 0.3 → 2.0
- F1 < 0.3 → 1.0

Linear interpolation within each band.

---

## 6. Matching Strategy

### Keyword Overlap (default, no LLM needed)
- Tokenize both strings (lowercase, strip punctuation)
- Compute Jaccard similarity = |intersection| / |union|
- Match if similarity >= threshold (default 0.5)

### LLM-based (optional, if router provided)
- Ask LLM: "Do these two observations describe the same crisis event? Return similarity 0.0-1.0"
- Used for nuanced matching (e.g., "cyclone approaching coast" vs "severe storm nearing shore")

---

## 7. TDD Plan

### Red Phase — Tests to write first:

1. **ObservationMatch model** — valid construction, similarity bounds
2. **AgentAccuracyScore model** — valid construction, F1 computation
3. **SituationalAccuracyResult model** — all fields populated
4. **keyword_similarity** — exact match = 1.0, partial overlap, no overlap = 0.0
5. **extract_observations_from_decisions** — extracts from agent_decisions
6. **extract_expected_observations** — extracts from ground_truth
7. **match_observations** — matches with threshold, handles duplicates
8. **compute precision/recall/F1** — known inputs, known outputs
9. **f1_to_score mapping** — each band boundary
10. **Full compute()** — scenario + run → SituationalAccuracyResult
11. **Empty observations** — graceful degradation (score = 1.0)
12. **Per-agent breakdown** — correct per-agent scores

### Green Phase — Implement:
- `keyword_similarity(a, b) -> float`
- `extract_observations_from_decisions(decisions) -> dict[str, list[str]]`
- `extract_expected_observations(ground_truth) -> dict[str, list[str]]`
- `match_observations(expected, actual, threshold) -> MatchResult`
- `f1_to_score(f1) -> float`
- `SituationalAccuracyMetric.compute(scenario, run) -> SituationalAccuracyResult`

---

## 8. Outcomes

- [ ] `src/benchmark/metrics/situational.py` exists with all functions
- [ ] `tests/unit/test_metric_situational.py` — all tests pass
- [ ] Precision/recall/F1 correctly computed
- [ ] F1 → 1.0-5.0 score mapping verified at boundaries
- [ ] Graceful handling of empty data
- [ ] No external API calls in core computation
- [ ] ruff lint clean
