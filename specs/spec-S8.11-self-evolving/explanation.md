# Spec S8.11: Self-Evolving Benchmark Generator — Explanation

## Why This Spec Exists

Static benchmarks lose validity when LLMs memorize their training data. If a model has seen CRISIS-BENCH scenarios during pre-training, its evaluation scores become meaningless — it's reciting answers, not demonstrating disaster response capability. S8.11 solves this with three mechanisms:

1. **Perturbation operations** create hard-to-memorize scenario variants
2. **Contamination detection** flags scenarios where scores jump suspiciously
3. **Historical generation** creates new scenarios from real Indian disasters

This implements requirements FR-010.1 through FR-010.5.

## What It Does

### Perturbation Operations (5 types, from COLING 2025 framework)

| Operation | Function | What Changes | Example |
|-----------|----------|-------------|---------|
| Geographic Swap | `perturb_geographic_swap()` | States, language | Odisha cyclone → Tamil Nadu cyclone |
| Temporal Shift | `perturb_temporal_shift()` | Season, time of day | October daytime → April midnight |
| Resource Constraint | `perturb_resource_constraint()` | NDRF battalions, shelters (−30-50%) | 10 battalions → 5 battalions |
| Cascading Injection | `perturb_cascading_injection()` | Adds secondary disaster | Flood + earthquake aftershock |
| Communication Degradation | `perturb_communication_degradation()` | Marks telecom as failed | Mobile/internet down in affected area |

Each operation uses `_clone_scenario()` which deep-copies the scenario with a new UUID, resets version to 1, and sets `source="perturbation"`.

### Contamination Detection

`detect_contamination()` analyzes evaluation run history per scenario:
- Needs ≥3 evaluation runs to analyze (avoids false positives)
- Computes mean + std dev of historical aggregate_drs scores
- Flags if latest score exceeds mean + 2σ (z-score threshold)
- Ignores jumps where the model config changed (expected improvement)
- Returns a set of flagged scenario IDs for regeneration

### Self-Evolving Generator

`SelfEvolvingGenerator` orchestrates the full evolution cycle:
1. Fetches existing scenarios from `ScenarioManager`
2. Applies random perturbation operations to create variants
3. Generates new scenarios from `HISTORICAL_CONTEXTS` (real Indian disasters)
4. Returns all newly created `BenchmarkScenario` objects

## How It Connects

```
S6.6 (ScenarioGenerator) ──→ S8.11 (SelfEvolvingGenerator)
                               ├── perturb_* functions
                               ├── detect_contamination()
                               └── evolve_benchmark()
S8.2 (ScenarioManager)  ──→ provides existing scenarios for perturbation
S8.4 (EvaluationEngine)  ──→ provides EvaluationRun data for contamination detection
S8.1 (Models)            ──→ BenchmarkScenario, EvaluationRun types
```

**Upstream dependencies:**
- `S8.2` — ScenarioManager for listing/searching existing scenarios
- `S6.6` — ScenarioGenerator for LLM-powered scenario creation

**Downstream consumers:**
- Benchmark runner uses evolved scenarios for evaluation
- Evaluation engine scores the new variants
- Dashboard can show contamination flags

## Interview Q&A

**Q: Why perturbation instead of generating entirely new scenarios?**
A: Perturbation preserves the core challenge of a scenario while changing surface features. A model that memorized "Cyclone Fani hits Odisha" will fail on "Cyclone Fani hits Tamil Nadu" because it memorized the geography, not the disaster response logic. Perturbation tests generalization, not memorization.

**Q: Why z-score for contamination instead of simpler percentage thresholds?**
A: Z-score accounts for score variance. A scenario with high-variance scores (0.4, 0.8, 0.5, 0.7) needs a bigger jump to be suspicious than one with stable scores (0.60, 0.61, 0.59, 0.60). A flat 15% threshold would miss contamination in high-variance scenarios and false-flag in low-variance ones.

**Q: How many runs do you need for reliable contamination detection?**
A: We require ≥3 runs minimum. With fewer data points, the standard deviation is unreliable and we'd get too many false positives. In practice, 5+ runs gives much better signal.
