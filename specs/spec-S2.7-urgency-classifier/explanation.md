# Spec S2.7 — Urgency Classifier: Explanation

## Why This Spec Exists

The LLM Router (S2.6) routes calls to different providers based on a "tier" (critical, standard, routine). But who decides which tier to use? Without the Urgency Classifier, every agent would need to manually pick a tier — duplicating logic and risking inconsistency. The classifier is the bridge between raw disaster signals and the router's tier system.

**FR-002.5**: "Assign urgency scores (1-5) based on IMD warning color codes (Green/Yellow/Orange/Red)."

## What It Does

Takes disaster data (IMD warnings, earthquake magnitude, cyclone class, river levels, population, disaster phase) and produces:
1. **Urgency score (1-5)** — the maximum of all signal scores, plus bonuses for active_response phase and high population
2. **LLM tier** — maps urgency to critical/standard/routine
3. **Factors list** — human-readable explanation of what drove the score
4. **Raw scores** — individual signal scores before aggregation

### Signal Mapping Summary

| Signal | Values → Urgency |
|--------|-----------------|
| IMD color | Green=1, Yellow=2, Orange=3, Red=5 |
| Earthquake (M) | <4.0=1, 4-4.9=2, 5-5.9=3, 6-6.9=4, ≥7.0=5 |
| Cyclone (IMD) | D/DD=2, CS=3, SCS/VSCS=4, ESCS/SuCS=5 |
| River level | Normal=1, Warning=3, Danger=4, Extreme=5 |
| Disaster type | Base urgency per type (1-4) |

## How It Works

1. Score each available signal independently
2. Take the **maximum** score across all signals
3. Add +1 if population > 1M (capped at 5)
4. Add +1 if phase is `active_response` (capped at 5)
5. Map final urgency to LLM tier: 1-2→routine, 3→standard, 4-5→critical

**Key design choice**: Rule-based, not LLM-based. Using an LLM to classify urgency would be circular — you need to know the urgency to pick the LLM tier to classify urgency.

## How It Connects

- **Upstream**: Receives `DisasterData` from agents (especially SituationSense S7.3, which will feed IMD/SACHET data)
- **Downstream**: Produces `UrgencyResult` with `tier` field that feeds into `LLMRouter.call(tier, messages)` (S2.6)
- **Models**: Adds `IMDColorCode` and `RiverLevelStatus` enums to `src/shared/models.py` (S2.1)
- **Future consumers**: Orchestrator (S7.2) will use this to decide which tier to request when delegating tasks

## Interview Talking Points

**Q: Why is this rule-based instead of ML-based?**
A: Three reasons: (1) It would be circular — you need urgency to pick the model, but you need the model to compute urgency. (2) The mapping is well-defined by Indian standards (IMD color codes, seismic scales) — there's no ambiguity to resolve with ML. (3) It's a ~50μs function call vs ~500ms LLM call. For a system processing real-time alerts, deterministic sub-millisecond classification is essential.

**Q: Why max-of-signals instead of weighted average?**
A: Safety principle — if ANY signal says "critical," the system should treat it as critical. A weighted average could mask a Red IMD alert if other signals are low. In disaster response, false negatives (underestimating urgency) are far more costly than false positives (over-using expensive LLM tiers).
