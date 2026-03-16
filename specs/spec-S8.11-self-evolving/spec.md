# Spec S8.11: Self-Evolving Benchmark Generator

**Phase**: 8 — Benchmark System
**Location**: `src/benchmark/self_evolving.py`
**Depends On**: S8.2 (Scenario Manager), S6.6 (Synthetic Scenario Generator)
**Status**: spec-written

---

## Why This Spec Exists

Static benchmarks become stale when LLMs memorize them during training (data contamination). A self-evolving benchmark automatically generates new scenario variants, detects contamination via performance anomaly analysis, and applies perturbation operations (COLING 2025 framework) to create hard-to-memorize variants. This keeps CRISIS-BENCH scores meaningful over time.

---

## Requirements (from FR-010)

| Req | Description |
|-----|-------------|
| FR-010.1 | Auto-generate new scenarios from historical Indian disaster data |
| FR-010.2 | Contamination detection (performance jump > 15% without model changes -> flag) |
| FR-010.3 | Perturbation operations: geographic swap, temporal shift, resource constraint, cascading injection, communication degradation |
| FR-010.4 | Version history for all scenarios (tracked via ScenarioManager.bump_version) |
| FR-010.5 | Generate 10+ new scenarios per quarter |

---

## Outcomes

1. `SelfEvolvingGenerator` class with methods for:
   - `generate_from_historical()` — create scenarios from historical disaster data
   - `detect_contamination()` — analyze evaluation runs for performance anomalies
   - `perturb_scenario()` — apply perturbation operations to existing scenarios
   - `evolve_benchmark()` — orchestrate a full evolution cycle
2. 5 perturbation operations implemented as composable functions
3. Contamination detection using statistical analysis of evaluation run scores
4. All external dependencies (LLM, DB) mocked in tests

---

## Perturbation Operations (COLING 2025)

| Operation | What Changes | Preserves |
|-----------|-------------|-----------|
| Geographic Swap | State, districts, language, demographics | Disaster type, severity, event structure |
| Temporal Shift | Time of day, season | Geography, disaster type |
| Resource Constraint | Available NDRF battalions, shelters (-30-50%) | Scenario structure |
| Cascading Injection | Adds secondary disaster event | Original event sequence |
| Communication Degradation | Marks telecom/internet as failed | Everything else |

---

## Contamination Detection Algorithm

1. For each scenario, collect all evaluation run scores
2. Compute rolling mean + std dev of aggregate_drs over time
3. Flag if latest score > mean + 2*std (>15% jump) AND no model config change
4. Return list of flagged scenario IDs for regeneration

---

## TDD Notes

### Test File: `tests/unit/test_self_evolving.py`

**RED phase tests:**
1. Perturbation: geographic swap changes states/language but preserves category
2. Perturbation: temporal shift changes season but preserves geography
3. Perturbation: resource constraint reduces resources by 30-50%
4. Perturbation: cascading injection adds secondary disaster event
5. Perturbation: communication degradation adds telecom failure
6. Contamination: no flag when scores are stable
7. Contamination: flags scenario with >15% performance jump
8. Contamination: no flag if model config changed
9. Generate from historical: produces valid BenchmarkScenario
10. Evolve benchmark: orchestrates perturbation + generation

---

## Code Standards

- All methods `async def` / `await`
- LLM calls through `LLMRouter.call(tier, messages)` only
- Mock all external services in tests
- Pydantic models for all data structures
- ruff clean (line-length: 100)
