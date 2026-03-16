# Spec S8.5 — Explanation: Metric: Situational Accuracy

## Why This Spec Exists

The benchmark system (Phase 8) needs 5 evaluation dimensions to score agent performance. Situational Accuracy is dimension 1 of 5 — it measures how well agents identify and report crisis observations compared to ground truth from IMD/CWC bulletins. Without this, we can't quantify whether agents are accurately reading the crisis situation.

## What It Does

Computes **precision/recall/F1** by comparing agent-reported observations against expected observations from ground truth:

- **Precision**: What fraction of agent observations are correct? (false alarm rate)
- **Recall**: What fraction of ground truth events did agents detect? (miss rate)
- **F1**: Harmonic mean — balances precision and recall into one score
- **Score**: Maps F1 (0.0–1.0) to a 1.0–5.0 score via linear interpolation across 5 bands

### Key Components

| Function | Purpose |
|----------|---------|
| `keyword_similarity(a, b)` | Jaccard similarity on tokenized strings |
| `extract_expected_observations(gt)` | Pull per-agent observations from ground truth |
| `extract_observations_from_decisions(decisions)` | Pull observations from agent decision records |
| `match_observations(expected, actual, threshold)` | Greedy best-first bipartite matching |
| `compute_precision_recall_f1(matched, expected, actual)` | Standard IR metrics |
| `f1_to_score(f1)` | F1 → 1.0-5.0 mapping with interpolation |
| `SituationalAccuracyMetric.compute()` | Full pipeline: extract → match → score |

### Scoring Bands

| F1 Range | Score Range |
|----------|-------------|
| 0.9–1.0 | 5.0 (Excellent) |
| 0.7–0.9 | 4.0–5.0 (Good) |
| 0.5–0.7 | 3.0–4.0 (Adequate) |
| 0.3–0.5 | 2.0–3.0 (Below expectations) |
| 0.0–0.3 | 1.0–2.0 (Inadequate) |

## How It Works

1. **Extract** expected observations from `scenario.ground_truth_decisions.agent_expectations[agent].key_observations`
2. **Extract** actual observations from `evaluation_run.agent_decisions[*].observations` (fallback to `reasoning`)
3. **Match** using greedy best-first: compute all pairwise Jaccard similarities, take the highest-similarity pair above threshold, remove both, repeat
4. **Compute** precision = matched/actual_total, recall = matched/expected_total, F1 = harmonic mean
5. **Map** F1 to 1.0–5.0 score via linear interpolation
6. **Per-agent** breakdown computed independently for each agent

### Design Decisions

- **Keyword Jaccard** (not cosine/embedding similarity): No dependency on Ollama or any embedding model. Pure computation, fast, deterministic. Good enough for comparing crisis observations that share domain vocabulary.
- **Greedy best-first matching** (not optimal bipartite): Simpler, O(n² log n) vs O(n³). For small observation lists (5-20 items), the difference is negligible.
- **LLM-based matching reserved**: The `router` parameter is accepted but not used yet. When S8.9 (Communication Appropriateness) needs LLM-as-judge, we can extend matching here too.

## Connections

- **Depends on**: S8.4 (Evaluation Engine) — uses same `BenchmarkScenario` and `EvaluationRun` models
- **Used by**: S8.10 (Aggregate DRS) — this score feeds into the weighted DRS computation
- **Parallel to**: S8.6 (Timeliness), S8.7 (Resource), S8.8 (Coordination), S8.9 (Communication) — all 5 metrics follow the same pattern

## Interview Q&A

**Q: Why precision/recall/F1 instead of just accuracy?**
A: In crisis detection, false negatives (missing a real cyclone) and false positives (false evacuation order) have very different costs. Accuracy treats them equally. Precision measures "of what we reported, how much was real?" (false alarm rate). Recall measures "of what was real, how much did we detect?" (miss rate). F1 balances both. In disaster response, recall is arguably more important (missing a real threat is worse than a false alarm), but we use balanced F1 as the baseline — the aggregate DRS can weight this dimension higher.

**Q: Why Jaccard similarity instead of cosine similarity with embeddings?**
A: (1) Zero dependencies — no embedding model needed. (2) Deterministic — same input always gives same output. (3) For crisis observations that share domain vocabulary ("cyclone", "Odisha", "coast", "flood"), keyword overlap is highly effective. (4) Speed — O(n) tokenization + set operations vs. O(n×768) embedding computation. Trade-off: Jaccard misses semantic similarity ("storm approaching shore" vs "cyclone nearing coast"), but the 0.5 threshold is tunable.

**Q: What is greedy best-first bipartite matching?**
A: Given N expected and M actual observations, we want to find the best pairing. Optimal bipartite matching (Hungarian algorithm) is O(n³). We use greedy: compute all N×M similarity scores, pick the highest pair, remove both from candidates, repeat. This is O(n² log n) and gives results within ~5% of optimal for our small observation lists. It also prevents double-counting (one actual can match at most one expected).
