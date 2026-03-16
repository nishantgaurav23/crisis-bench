# Spec S8.9 — Explanation: Communication Appropriateness Metric

## Why This Spec Exists

India has 22 scheduled languages and a population that communicates across vastly different channels (WhatsApp is dominant in urban/semi-urban areas, SMS in rural). During a disaster, a technically accurate evacuation plan in English is useless if the affected population in Odisha speaks Odia. This metric evaluates whether the CommunityComms agent produces crisis communications that are linguistically appropriate, follow NDMA guidelines, reach the right audiences, include actionable information, and are formatted for the correct channels.

Without this metric, the benchmark would score a system that generates English-only, generic, non-actionable alerts the same as one that generates multilingual, helpline-inclusive, shelter-aware communications — a critical gap in evaluating real-world disaster response effectiveness.

## What It Does

Scores agent communications across **5 weighted sub-dimensions**:

| Sub-Dimension | Weight | Evaluation Method |
|---------------|--------|-------------------|
| **Language Match** | 25% | Set intersection: expected languages (from ground truth) vs. languages actually produced |
| **NDMA Adherence** | 25% | Set intersection: expected NDMA guideline references vs. references in agent output |
| **Audience Fit** | 20% | Set intersection: expected audiences (public, first_responders, vulnerable) vs. audiences addressed |
| **Actionable Content** | 20% | Presence check: helpline numbers, shelter info, evacuation routes across all communications |
| **Channel Format** | 10% | Set intersection: expected channels (whatsapp, sms, media_briefing) vs. channels formatted |

Each sub-dimension maps coverage (0.0-1.0) to score (1.0-5.0) linearly. The composite is the weighted sum.

## How It Works

### Data Flow
```
BenchmarkScenario.ground_truth_decisions
    → extract_communication_expectations()
    → {expected_languages, expected_audiences, expected_channels, expected_helplines, ndma_guidelines}

EvaluationRun.agent_decisions (community_comms)
    → extract_communications_from_decisions()
    → (List[CommunicationEntry], meta dict)

5x sub-dimension scoring functions
    → SubDimensionScore per dimension

compute_communication_score()
    → weighted composite (1.0-5.0)
```

### Ground Truth Format
Expectations are encoded as key=value pairs in `agent_expectations["community_comms"].key_observations`:
- `expected_languages=hindi,odia`
- `expected_audiences=public,first_responders`
- `expected_channels=whatsapp,sms`
- `expected_helplines=1070,9711077372`
- `ndma_guidelines=NDMA-CYC-01,NDMA-FLD-03`

### Edge Cases
- Empty ground truth → neutral score (3.0) for all sub-dimensions
- Empty agent decisions → minimum score (1.0) for all sub-dimensions
- Missing `communications` field → scored on metadata only (languages_used, etc.)
- Extra languages/channels beyond expected → no penalty (coverage can only be 0-1)

## How It Connects

- **Upstream**: S8.4 (Evaluation Engine) provides `BenchmarkScenario` and `EvaluationRun` objects
- **Downstream**: S8.10 (Aggregate DRS) will use this as the `communication_appropriateness` dimension (weight 0.20)
- **Agent under evaluation**: S7.6 (CommunityComms) — this metric directly evaluates its output quality
- **Related requirements**: FR-005.1 (multilingual alerts), FR-005.2 (audience adaptation), FR-005.4 (Indian channel formatting), FR-005.5 (NDMA guidelines), FR-005.6 (actionable instructions)
- **Follows the same pattern** as S8.5 (Situational Accuracy), S8.6 (Decision Timeliness), S8.7 (Resource Efficiency) — Pydantic models + extraction + scoring + metric class with `async compute()`

## Interview Q&A

**Q: Why score communication as a separate dimension instead of including it in overall accuracy?**
A: Accuracy measures "did the system detect the right things?" Communication measures "did the system tell the right people in the right language through the right channels?" A system could have perfect situational awareness but generate English-only alerts for a Tamil-speaking population — that's a communication failure, not an accuracy failure. Separating dimensions prevents one from masking the other.

**Q: Why is Language Match weighted 25% — the highest along with NDMA adherence?**
A: In India, language is literally life-or-death during disasters. 26% of India's population doesn't speak Hindi. If a cyclone hits Odisha and you only generate Hindi alerts, you miss the majority of the affected population. The 2013 Phailin cyclone evacuation succeeded partly because alerts were in Odia. Language match and NDMA adherence are equally critical.

**Q: Why not use an LLM to judge communication quality?**
A: We use deterministic scoring (set intersection, presence checks) for reproducibility and zero cost. LLM-as-judge for communication quality would cost ~$0.50 per evaluation (DeepSeek Reasoner) and introduce non-determinism. The Evaluation Engine (S8.4) already handles LLM-as-judge scoring at a higher level. This metric provides the fast, deterministic component.
