# Spec S8.7: Resource Efficiency Metric — Explanation

## Why This Spec Exists

In disaster response, resource allocation is life-or-death. The ResourceAllocation agent (S7.5) uses OR-Tools to optimize NDRF/SDRF battalion deployment, shelter assignments, and supply routing. But how do we measure if the agent's LLM-guided decisions are actually *good*?

This metric quantifies the "optimality gap" — the difference between what the agent decided and what a pure mathematical optimizer (OR-Tools) would produce. It answers: "How much worse is the agent's allocation compared to the mathematical optimum?"

## What It Does

Evaluates agent resource allocation decisions across 4 components:

1. **Utilization Ratio** (weight 0.20) — What fraction of available resources did the agent deploy? Under-utilization means resources sit idle while people need help.

2. **Coverage Score** (weight 0.30) — What fraction of displaced population is covered by the allocation? This is the most important component — uncovered demand means unprotected people.

3. **Optimality Gap** (weight 0.35) — `(agent_distance - optimal_distance) / optimal_distance`. How much extra travel distance did the agent's routing add compared to the OR-Tools solution? This directly maps to response time.

4. **Waste Ratio** (weight 0.15) — Resources allocated but demand not covered. High waste indicates misallocation (sending battalions to the wrong districts).

Each component maps to a 1.0-5.0 sub-score. The composite score is a weighted sum.

## How It Works

### Data Flow

```
EvaluationRun.agent_decisions  →  extract_allocations_from_decisions()
    ↓                                    ↓
allocations list + stats          AllocationEntry models + summary stats
                                         ↓
BenchmarkScenario.ground_truth  →  extract_optimal_baseline()
    ↓                                    ↓
OR-Tools baseline values          optimal_total_distance_km, coverage_pct, utilization_pct
                                         ↓
                              compute_utilization_ratio()
                              compute_coverage_score()
                              compute_optimality_gap()
                              compute_waste_ratio()
                                         ↓
                              compute_composite_score()
                                         ↓
                              ResourceEfficiencyResult (score 1.0-5.0)
```

### Gap-to-Score Mapping

| Optimality Gap | Score Range |
|---------------|-------------|
| 0.00 - 0.05  | 5.0 (excellent — within 5% of optimal) |
| 0.05 - 0.15  | 4.0 - 5.0 (good) |
| 0.15 - 0.30  | 3.0 - 4.0 (adequate) |
| 0.30 - 0.50  | 2.0 - 3.0 (below expectations) |
| 0.50+        | 1.0 - 2.0 (inadequate) |

### Ground Truth Format

OR-Tools baseline values are stored in `ground_truth_decisions.agent_expectations["resource_allocation"].key_observations` as `key=value` strings:
- `optimal_total_distance_km=120.5`
- `optimal_coverage_pct=0.95`
- `optimal_utilization_pct=0.85`

### Graceful Degradation

- Missing resource_allocation agent decisions → score defaults based on zero utilization/coverage
- Missing ground truth → optimality gap estimated from coverage + utilization
- Missing allocations field → stats still extracted from top-level decision fields
- Zero demand/available → returns 0.0 ratios, not division errors

## How It Connects

### Upstream Dependencies
- **S8.4 Evaluation Engine** — Provides the EvaluationRun and BenchmarkScenario models that this metric consumes
- **S8.1 Scenario Models** — AllocationEntry parsing from agent_decisions follows the patterns set by scenario models

### Downstream Dependents
- **S8.10 Aggregate DRS** — This metric's score feeds into the weighted aggregate Disaster Response Score (resource_efficiency dimension, weight 0.20)
- **S8.11 Self-Evolving Generator** — Resource efficiency scores identify which allocation scenarios need more challenging variants

### Sibling Metrics
- **S8.5 Situational Accuracy** — Same pattern (pure computation, no LLM calls)
- **S8.6 Decision Timeliness** — Measures time; this measures allocation quality
- **S8.8 Coordination Quality** — Measures inter-agent sharing; this measures single-agent output quality
- **S8.9 Communication Appropriateness** — Measures message quality; this measures resource decisions

### Agent Connection
- **S7.5 ResourceAllocation Agent** — This metric directly evaluates that agent's output quality against its own OR-Tools solver's optimal solution

## Interview Q&A

**Q: Why measure optimality gap instead of just checking if the allocation "looks right"?**
A: Qualitative assessment ("looks right") is subjective and non-reproducible. The optimality gap is a precise, quantitative measure — it tells you exactly how much worse the agent is compared to the mathematical optimum. A gap of 0.10 means the agent's solution costs 10% more (in distance/time) than the optimal. This is actionable: you can track improvement over model iterations and set concrete thresholds (e.g., "must be within 15% of optimal to pass").

**Q: Why use 4 components instead of just optimality gap alone?**
A: Optimality gap only measures routing efficiency (total distance). But resource allocation has other failure modes: (1) deploying too few resources (low utilization), (2) not covering all affected people (low coverage), (3) sending resources to wrong places (high waste despite high utilization). A single gap number can't capture all four. The weighted composite gives a holistic view of allocation quality.

**Q: Why is coverage weighted highest (0.30)?**
A: In disaster response, uncovered demand = unprotected lives. You can have perfect routing efficiency (gap = 0) but if you only cover 30% of displaced people, the allocation is a failure. Coverage is the most directly life-critical component.
