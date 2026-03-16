# Spec S8.7: Resource Efficiency Metric

**Status**: done

**Phase**: 8 — Benchmark System
**Depends On**: S8.4 (Evaluation Engine)
**Location**: `src/benchmark/metrics/resource.py`
**Tests**: `tests/unit/test_metric_resource.py`

---

## Why This Spec Exists

The Resource Efficiency metric measures how close agent resource allocation decisions are to the OR-Tools mathematical optimum. In a disaster scenario, the ResourceAllocation agent (S7.5) decides how to deploy NDRF/SDRF battalions, assign shelters, and distribute relief supplies across affected districts. This metric quantifies the "optimality gap" — how much worse (or better) the agent's allocation is compared to what a pure optimization solver would produce.

This is critical because:
1. Over-allocation wastes resources needed elsewhere
2. Under-allocation leaves people unprotected
3. Suboptimal routing costs lives (delayed response)

---

## What It Does

Compares agent resource allocation decisions from an `EvaluationRun` against OR-Tools optimal baseline allocations from the scenario's ground truth. Produces a score (1.0-5.0) based on the optimality gap.

### Key Computations

1. **Resource Utilization Ratio** — `allocated / available` per resource type (battalions, shelters, supplies)
2. **Coverage Score** — What fraction of demand (displaced population) is covered by allocations
3. **Optimality Gap** — `(agent_cost - optimal_cost) / optimal_cost` where cost = total travel distance + unmet demand penalty
4. **Waste Score** — Resources allocated but unused or redundantly deployed

### Inputs

From `EvaluationRun.agent_decisions` (decisions by `resource_allocation` agent):
- `allocations`: list of `{resource_type, source, destination, quantity, distance_km}`
- `total_allocated`: int (total resources deployed)
- `total_demand`: int (total displaced population)
- `total_distance_km`: float (total travel distance for all deployments)

From `BenchmarkScenario.ground_truth_decisions.agent_expectations["resource_allocation"]`:
- `expected_actions`: list of expected allocation actions
- `key_observations`: optimal allocation metrics from OR-Tools baseline
  - `optimal_total_distance_km`: float
  - `optimal_coverage_pct`: float
  - `optimal_utilization_pct`: float

### Output: `ResourceEfficiencyResult`

```python
class ResourceEfficiencyResult(BaseModel):
    utilization_ratio: float      # 0.0-1.0, allocated/available
    coverage_score: float         # 0.0-1.0, demand covered
    optimality_gap: float         # 0.0+, lower is better
    waste_ratio: float            # 0.0-1.0, unused/allocated
    component_scores: dict[str, float]  # per-component breakdown
    score: float                  # 1.0-5.0 final score
```

### Scoring (optimality_gap to 1.0-5.0)

| Optimality Gap | Score |
|---------------|-------|
| 0.0 - 0.05   | 5.0   |
| 0.05 - 0.15  | 4.0 - 5.0 (interpolated) |
| 0.15 - 0.30  | 3.0 - 4.0 (interpolated) |
| 0.30 - 0.50  | 2.0 - 3.0 (interpolated) |
| 0.50+        | 1.0 - 2.0 (interpolated) |

---

## TDD Notes

### Test Groups

1. **Models** — Validate all Pydantic models (ResourceAllocation, ResourceEfficiencyResult, AllocationEntry)
2. **Extraction** — Extract allocation data from agent decisions and ground truth
3. **Utilization Ratio** — `allocated / available` computation
4. **Coverage Score** — Demand coverage computation
5. **Optimality Gap** — Gap vs OR-Tools baseline
6. **Waste Ratio** — Unused resource detection
7. **Composite Score** — Weighted combination of components
8. **Gap-to-Score Mapping** — Linear interpolation between bands
9. **Full Compute** — End-to-end `ResourceEfficiencyMetric.compute()`
10. **Graceful Degradation** — Empty data, missing fields, edge cases

### What to Mock

- Nothing — this metric is pure computation (no external APIs, no LLM calls)

---

## Outcomes

- [ ] `ResourceEfficiencyResult` Pydantic model with bounds validation
- [ ] `AllocationEntry` model for individual resource allocations
- [ ] `extract_allocations_from_decisions()` — parse agent decisions
- [ ] `extract_optimal_baseline()` — parse ground truth OR-Tools baseline
- [ ] `compute_utilization_ratio()` — allocated/available ratio
- [ ] `compute_coverage_score()` — demand coverage
- [ ] `compute_optimality_gap()` — gap vs OR-Tools
- [ ] `compute_waste_ratio()` — unused resources
- [ ] `gap_to_score()` — map optimality gap to 1.0-5.0
- [ ] `ResourceEfficiencyMetric.compute()` — full computation
- [ ] All tests pass, ruff clean, >80% coverage
