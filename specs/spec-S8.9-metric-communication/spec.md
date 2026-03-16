# Spec S8.9 — Metric: Communication Appropriateness

**Status**: spec-written
**Depends On**: S8.4 (Evaluation Engine)
**Location**: `src/benchmark/metrics/communication.py`
**Test File**: `tests/unit/test_metric_communication.py`

---

## 1. Purpose

Evaluate how well the CommunityComms agent (and others producing public-facing content) generates crisis communications. This metric assesses multilingual quality, NDMA guideline adherence, audience appropriateness, actionable content, and channel formatting — all critical for effective disaster communication in India's linguistically diverse context.

## 2. Requirements (from FR-011.5)

- **FR-011.5**: Communication Appropriateness — LLM-as-judge (DeepSeek Reasoner) + manual review for Indian language accuracy

## 3. Five Sub-Dimensions

| Sub-Dimension | Weight | What It Measures |
|---------------|--------|------------------|
| Language Match | 0.25 | Correct language for affected state (Hindi for UP, Odia for Odisha, etc.) |
| NDMA Adherence | 0.25 | Follows NDMA communication guidelines and state SDMA protocols |
| Audience Fit | 0.20 | Appropriate tone/complexity for target audience (first responder vs public vs vulnerable) |
| Actionable Content | 0.20 | Includes shelter locations, helpline numbers, evacuation routes |
| Channel Format | 0.10 | Properly formatted for target channel (WhatsApp, SMS, media briefing) |

## 4. Scoring

Each sub-dimension is scored 1.0-5.0:
- **5.0** — Excellent: all criteria met, exceeds expectations
- **4.0** — Good: most criteria met, minor gaps
- **3.0** — Adequate: minimum requirements met
- **2.0** — Below expectations: significant gaps
- **1.0** — Inadequate: criteria not met

Final score = weighted sum of sub-dimensions (1.0-5.0 range).

## 5. Ground Truth Expectations

From `GroundTruthDecisions.agent_expectations["community_comms"]`:
- `key_observations` contains expected communication requirements as key=value pairs:
  - `expected_languages=hindi,odia` — languages that should be used
  - `expected_audiences=public,first_responders` — target audiences
  - `expected_channels=whatsapp,sms` — output channels
  - `expected_helplines=1070,9711077372` — helplines to include
  - `ndma_guidelines=NDMA-CYC-01,NDMA-FLD-03` — NDMA references to follow
- `expected_actions` lists actions like "Generate bilingual alert", "Include shelter locations"

## 6. Agent Decision Format

From `evaluation_run.agent_decisions` for `community_comms` agent:
```python
{
    "agent_id": "community_comms",
    "communications": [
        {
            "language": "hindi",
            "audience": "public",
            "channel": "whatsapp",
            "content": "...",
            "helplines_included": ["1070", "9711077372"],
            "shelter_info": True,
            "evacuation_routes": True,
        }
    ],
    "languages_used": ["hindi", "odia", "english"],
    "audiences_addressed": ["public", "first_responders"],
    "channels_formatted": ["whatsapp", "sms"],
    "ndma_references": ["NDMA-CYC-01"],
}
```

## 7. Implementation Approach

Pure computation — no LLM calls in the metric itself (LLM-as-judge evaluation is handled by the EvaluationEngine in S8.4). This metric does deterministic scoring based on:
1. Language coverage check (set intersection)
2. NDMA reference inclusion check
3. Audience coverage check
4. Actionable content presence check (helplines, shelters, routes)
5. Channel format coverage check

## 8. TDD Notes

### Red Phase (Tests First)
1. Models: `CommunicationEntry`, `SubDimensionScore`, `CommunicationAppropriatenessResult`
2. Extraction: `extract_communication_expectations`, `extract_communications_from_decisions`
3. Sub-dimension scoring: `score_language_match`, `score_ndma_adherence`, `score_audience_fit`, `score_actionable_content`, `score_channel_format`
4. Composite: `compute_communication_score`
5. Full metric: `CommunicationAppropriatenessMetric.compute()`
6. Edge cases: empty decisions, empty ground truth, missing fields

### Green Phase
Implement minimum code to pass each test.

### Refactor Phase
Clean up, run ruff, ensure consistency with other metrics.

## 9. Outputs

- `CommunicationAppropriatenessResult` with per-sub-dimension breakdown
- Score 1.0-5.0 for integration with aggregate DRS (S8.10)

## 10. Connections

- **Upstream**: S8.4 (Evaluation Engine provides scenario + run data)
- **Downstream**: S8.10 (Aggregate DRS uses this as one of 5 dimensions)
- **Related Agent**: S7.6 (CommunityComms agent produces the communications being evaluated)
