# Spec S8.10 — Aggregate Disaster Response Score (DRS)

**Status**: done

## Overview
Computes the aggregate Disaster Response Score by combining the 5 individual metric scores (S8.5-S8.9) using configurable weights. Supports pass@k reliability measurement for statistical robustness.

## Depends On
- S8.5 (Situational Accuracy metric)
- S8.6 (Decision Timeliness metric)
- S8.7 (Resource Efficiency metric)
- S8.8 (Coordination Quality metric)
- S8.9 (Communication Appropriateness metric)

## Location
`src/benchmark/metrics/aggregate.py`

## Outcomes
1. `DimensionWeight` model — per-dimension weight configuration with validation (sum=1.0)
2. `AggregateDRSResult` model — full breakdown with per-dimension scores, weighted composite, normalized DRS (0.0-1.0), and pass@k stats
3. `AggregateDRSMetric` class — orchestrates all 5 metrics, computes weighted aggregate
4. `pass_at_k()` function — computes pass@k reliability from multiple runs (best score, mean, std dev)
5. Default weights from `EvaluationRubric` (each 0.20) with override support
6. DRS normalized to 0.0-1.0 scale: `DRS = weighted_sum / 5.0` (scores are 1-5, weights sum to 1.0)

## Key Design Decisions
- Reuses existing metric classes (S8.5-S8.9) — calls their `compute()` methods
- Weights default to equal (0.20 each) but can be overridden via `EvaluationRubric` or custom dict
- pass@k: given k evaluation results, computes `best`, `mean`, `std_dev`, and `pass_rate` (fraction scoring above a threshold)
- DRS range: 0.0 (worst) to 1.0 (best), matching EvaluationEngine convention

## TDD Notes
- Test weight validation (must sum to 1.0 within tolerance)
- Test DRS computation with known scores
- Test pass@k with edge cases (k=1, all same, empty)
- Test integration with all 5 metric result types
- Test default vs custom weights
- Test DRS normalization bounds (always 0.0-1.0)
