# S8.10 — Aggregate Disaster Response Score (DRS): Explanation

## Why This Spec Exists
The 5 individual metrics (S8.5-S8.9) each evaluate one dimension of disaster response quality. Without an aggregate score, comparing system configurations or model versions requires examining 5 numbers independently. The DRS provides a single 0.0-1.0 score that collapses all dimensions into one comparable number, weighted by importance. The pass@k function adds statistical robustness — running the same scenario k times and measuring consistency.

## What It Does
1. **Orchestrates all 5 metrics** — calls `SituationalAccuracyMetric`, `DecisionTimelinessMetric`, `ResourceEfficiencyMetric`, `CoordinationQualityMetric`, and `CommunicationAppropriatenessMetric` via their `compute()` methods
2. **Weighted combination** — multiplies each dimension's 1.0-5.0 score by its weight (sum=1.0), then normalizes to 0.0-1.0 via `DRS = weighted_sum / 5.0`
3. **Configurable weights** — priority: custom weights > `EvaluationRubric` weights > default equal (0.20 each)
4. **pass@k reliability** — given k DRS scores from repeated runs, computes best, mean, std_dev, and pass_rate (fraction above threshold)
5. **Batch evaluation** — `compute_batch()` runs multiple evaluation runs and returns per-run results

## How It Works
- `validate_weights(weights)` — checks all 5 dimensions present, non-negative, sum to 1.0 (±0.01)
- `compute_weighted_drs(scores, weights)` — pure function, missing dimensions default to 1.0 (worst)
- `pass_at_k(drs_scores, threshold)` — population std_dev, pass_rate = count(score ≥ threshold) / k
- `AggregateDRSMetric` — holds the 5 sub-metric instances, resolves weights from scenario rubric or custom override

## How It Connects
- **Upstream**: Consumes results from S8.5 (situational), S8.6 (timeliness), S8.7 (resource), S8.8 (coordination), S8.9 (communication)
- **Downstream**: Used by S8.11 (self-evolving generator) to score scenarios and detect regression. Used by the evaluation engine (S8.4) which has its own `_compute_drs` for LLM-as-judge scores — this module provides the metric-based equivalent
- **Dashboard**: S9.2 will display the DRS breakdown on the metrics panel
- **CI/CD**: S9.5 will use DRS for benchmark regression detection in GitHub Actions

## Interview Q&A

**Q: Why normalize DRS to 0.0-1.0 instead of keeping the 1.0-5.0 scale?**
A: Normalization enables meaningful comparison across configurations. A DRS of 0.8 means "80% of maximum possible performance." The 1-5 scale is intuitive for individual dimensions (like a Likert scale), but weighted sums of Likert scores aren't immediately interpretable. The 0-1 normalization also matches the convention used in `EvaluationEngine._compute_drs`.

**Q: What is pass@k and why does it matter for benchmarks?**
A: LLM outputs are non-deterministic — the same scenario can produce different agent decisions each run. pass@k measures reliability: run the same scenario k times, compute how often the DRS exceeds a threshold. A system with pass@3 = 100% at threshold 0.6 is more reliable than one with pass@3 = 33%. It's borrowed from code generation benchmarks (HumanEval) where pass@k measures how many attempts it takes to get a correct solution.

**Q: Why use population std_dev instead of sample std_dev?**
A: We compute the std_dev of the actual k runs, not an estimate of a population parameter. When k=3, the difference between dividing by k vs k-1 is significant — and we're describing these specific runs, not inferring about all possible runs.
