# S9.1 — Agentic Plan Caching — Explanation

## Why This Spec Exists

When the same type of disaster recurs (e.g., cyclone season in Odisha), the agent system generates very similar response plans each time, spending expensive LLM calls on reasoning that's already been done. Plan caching eliminates this waste by storing completed plans in ChromaDB and retrieving them via similarity search for new but similar scenarios. Instead of ~15 LLM calls for full planning, adaptation requires ~3 calls — a 20-40% latency reduction.

## What It Does

### PlanCache (`src/caching/plan_cache.py`)
- **Stores** agent response plans in ChromaDB's `plan_cache` collection with metadata (disaster type, severity, affected regions, timestamps)
- **Retrieves** similar past plans via cosine similarity search using the existing `EmbeddingPipeline` from S6.1
- **Classifies** matches into tiers: HIGH (≥0.85), MEDIUM (0.70-0.84), MISS (<0.70)
- **Filters** out misses — only returns actionable cache hits
- **Invalidates** stale plans older than a configurable TTL (default 30 days)
- **Tracks** hit/miss statistics for observability

### PlanAdapter (`src/caching/plan_adapter.py`)
- **Computes deltas** between old and new scenarios: geographic, severity, resource, and temporal differences
- **Adapts** cached plans via LLM, using cheaper tiers for closer matches (routine for HIGH, standard for MEDIUM)
- **Validates** adapted plans — rejects empty results or low-confidence adaptations
- Constructs structured prompts that include the delta summary, ensuring the LLM only modifies affected sections

## How It Works

```
New Scenario → query_similar_plans() → [CachedPlan list]
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    │ HIGH (≥0.85)          │ MEDIUM (0.70-0.84)    │ MISS (<0.70)
                    │                       │                       │
                    ▼                       ▼                       ▼
              adapt_plan()           adapt_plan()           Generate from scratch
              (routine tier)         (standard tier)        (full LLM pipeline)
                    │                       │
                    ▼                       ▼
              AdaptationResult       AdaptationResult
              (confidence: 0.9)      (confidence: 0.7)
```

### Key Design Decisions
1. **Composition over inheritance**: PlanCache wraps `EmbeddingPipeline` rather than extending it
2. **Graceful degradation**: If ChromaDB is down, `query_similar_plans()` returns `[]` — the system falls back to full plan generation
3. **Store failures propagate**: `store_plan()` raises on failure because data loss matters — but reads degrade gracefully
4. **Tier-based LLM routing**: HIGH matches use the cheapest LLM tier (routine/Qwen Flash at $0.04/M) since minimal changes are needed

## How It Connects

### Upstream Dependencies
- **S6.1 (ChromaDB + EmbeddingPipeline)**: Provides the `plan_cache` collection, embedding via `nomic-embed-text`, and the `query_similar` / `embed_and_store` API
- **S2.6 (LLM Router)**: PlanAdapter routes adaptation calls through the router's failover chain

### Downstream Consumers
- **S9.2 (Dashboard Integration)**: Can display cache hit rates, similarity scores, and adaptation metrics
- **Orchestrator (S7.2)**: Primary integration point — query cache before expensive decomposition/synthesis LLM calls
- **S9.4 (Grafana Dashboards)**: Cache stats feed into Prometheus metrics

### Data Flow
```
Agent Pipeline (S7.9) ─→ Orchestrator decides plan ─→ PlanCache.store_plan()
                                                           │
New similar scenario ─→ PlanCache.query_similar_plans() ───┘
                              │
                              ▼ (if hit)
                        PlanAdapter.adapt_plan() ─→ Adapted plan returned
```
