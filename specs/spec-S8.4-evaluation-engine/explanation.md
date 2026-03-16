# Spec S8.4: Evaluation Engine — Explanation

## Why This Spec Exists

The benchmark system needs an automated way to score agent performance across multiple quality dimensions. Manual evaluation of 100 scenarios x 5 dimensions = 500 evaluations is impractical for a solo developer. The evaluation engine uses **LLM-as-judge** — a strong LLM (DeepSeek Reasoner, `critical` tier) evaluates other LLMs' outputs against structured rubrics with 80-90% agreement with human judges.

## What It Does

The `EvaluationEngine` takes an `EvaluationRun` (from `ScenarioRunner` S8.3) plus its `BenchmarkScenario` (with ground truth + rubric), and produces scores across 5 dimensions:

1. **Situational Accuracy** — Did agents correctly identify what's happening? (precision/recall vs IMD/CWC ground truth)
2. **Decision Timeliness** — Were decisions made within NDMA SOP time windows?
3. **Resource Efficiency** — How close to optimal resource allocation (vs OR-Tools baseline)?
4. **Coordination Quality** — Did agents share information effectively?
5. **Communication Appropriateness** — Were alerts multilingual, clear, and NDMA-compliant?

Each dimension is scored 1.0-5.0. The aggregate **Disaster Response Score (DRS)** is a weighted sum normalized to 0.0-1.0.

## How It Works

### Architecture
```
EvaluationRun + BenchmarkScenario
    → build_evaluation_prompt(dimension, scenario, run)
    → LLMRouter.call("critical", messages)
    → parse_score_response(raw, dimension)
    → DimensionScore(score, justification, key_factors)
    → _compute_drs(scores, rubric)
    → EvaluationResult
```

### Key Components

- **`build_evaluation_prompt()`** — Constructs a 2-message prompt (system + user) containing: evaluator instructions, rubric criteria, ground truth expectations, actual agent decisions, and JSON output format specification.

- **`parse_score_response()`** — Robust JSON parser that handles: clean JSON, JSON in markdown code blocks, malformed responses (defaults to score 1.0), and out-of-range scores (clamped to 1.0-5.0).

- **`EvaluationEngine.evaluate()`** — Evaluates all 5 dimensions sequentially, computing scores via LLM calls. Handles per-dimension LLM failures gracefully (failed dimensions get score 1.0, other dimensions still evaluated).

- **`EvaluationEngine.batch_evaluate()`** — Evaluates multiple runs for the same scenario.

- **`_compute_drs()`** — `DRS = sum(score_i * weight_i) / 5.0`. Weights come from the scenario's `EvaluationRubric` and must sum to 1.0.

### Graceful Degradation
- If one dimension's LLM call fails → that dimension scores 1.0, others still evaluated
- If all dimensions fail → all score 1.0, DRS = 0.2
- If scenario has no rubric → default equal-weight rubric (0.20 each) is used

## How It Connects

### Depends On
- **S8.3** (`ScenarioRunner`) — Produces `EvaluationRun` with `agent_decisions`
- **S8.1** (`models.py`) — `BenchmarkScenario`, `EvaluationRun`, `EvaluationRubric`
- **S2.6** (`LLMRouter`) — Routes evaluation LLM calls at `critical` tier

### Required By
- **S8.5-S8.9** — Individual metric modules that extend per-dimension evaluation
- **S8.10** — Aggregate DRS scoring builds on this engine's output
- **S9.2** — Dashboard integration displays evaluation results

## Interview Q&A

**Q: Why evaluate each dimension with a separate LLM call instead of one big call?**
A: (1) Focused prompts produce better scores — the LLM evaluates one thing at a time with specific rubric criteria. (2) If one dimension fails, others still get scored. (3) Each prompt fits comfortably in context window. (4) Individual dimension calls are easier to debug and validate.

**Q: Why clamp scores to 1.0-5.0 instead of rejecting out-of-range values?**
A: LLMs occasionally output scores like 4.7/5 as "4.7" or give 0 or 6. Clamping is more robust than rejecting — we get a usable (if imperfect) score rather than a missing one. The justification text still provides qualitative context.

**Q: How do you prevent the judge LLM from being biased toward certain response styles?**
A: The structured rubric with specific criteria (from `EvaluationRubric`) anchors the evaluation in concrete, measurable factors rather than style preferences. Ground truth expectations provide a factual baseline. The key_factors in the response force the LLM to explain its reasoning, which helps catch superficial scoring.
