# Spec S9.1 — Agentic Plan Caching

## Overview

ChromaDB-based caching of agent response plans, enabling similarity-based retrieval and LLM-powered adaptation of past plans to new scenarios. Targets >20% latency reduction for recurring disaster patterns.

## Dependencies

| Spec | Feature | Status |
|------|---------|--------|
| S6.1 | ChromaDB + EmbeddingPipeline | done |
| S7.9 | Agent integration test | done |

## Outcomes

1. `src/caching/plan_cache.py` — PlanCache class that stores/retrieves plans from ChromaDB `plan_cache` collection
2. `src/caching/plan_adapter.py` — PlanAdapter class that adapts cached plans to new scenario parameters via LLM
3. >80% test coverage for both modules
4. All tests pass with mocked ChromaDB and LLM

## Functional Requirements

### PlanCache (`plan_cache.py`)

1. **Store plan**: Given a completed plan (text + metadata), embed and store in ChromaDB `plan_cache` collection
   - Metadata: `document_id`, `disaster_type`, `severity`, `affected_states`, `affected_districts`, `phase`, `timestamp`, `scenario_id`, `plan_type`
   - Uses existing `EmbeddingPipeline.embed_and_store()`

2. **Query similar plans**: Given a scenario description, find top-K similar cached plans
   - Uses existing `EmbeddingPipeline.query_similar()`
   - Returns `list[CachedPlan]` with similarity scores

3. **Similarity tiers**:
   - score >= 0.85: HIGH — use cached plan with minimal adaptation
   - 0.70 <= score < 0.85: MEDIUM — use cached plan with significant adaptation
   - score < 0.70: LOW — generate fresh plan (cache miss)

4. **Cache hit/miss classification**: `classify_match(score: float) -> CacheMatchTier`

5. **Plan invalidation**: Remove stale plans older than configurable TTL (default 30 days)

6. **Cache statistics**: Track hit/miss counts, average similarity scores

### PlanAdapter (`plan_adapter.py`)

1. **Adapt plan**: Given a cached plan + new scenario parameters, generate an adapted plan via LLM
   - Uses `routine` tier LLM (cheap) for HIGH similarity adaptations
   - Uses `standard` tier LLM for MEDIUM similarity adaptations
   - Prompt: "Given this existing plan for [old scenario], adapt it for [new scenario]. Key differences: [delta]"

2. **Compute delta**: Compare old plan metadata with new scenario to identify differences
   - Geographic changes (different districts/states)
   - Severity changes (upgraded/downgraded)
   - Resource changes (different available resources)
   - Temporal changes (different time of day/season)

3. **Validate adaptation**: Ensure adapted plan still references valid locations and resources

## Data Models

```python
class CacheMatchTier(str, Enum):
    HIGH = "high"       # >= 0.85
    MEDIUM = "medium"   # 0.70 - 0.84
    MISS = "miss"       # < 0.70

class CachedPlan(BaseModel):
    plan_text: str
    similarity_score: float
    match_tier: CacheMatchTier
    metadata: dict[str, Any]
    document_id: str

class PlanCacheStats(BaseModel):
    total_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_similarity: float = 0.0
    hit_rate: float = 0.0

class AdaptationResult(BaseModel):
    original_plan: str
    adapted_plan: str
    delta_summary: str
    llm_tier_used: str
    adaptation_confidence: float
```

## Integration Points

- PlanCache uses `EmbeddingPipeline` from S6.1 (composition, not inheritance)
- PlanAdapter uses `LLMRouter` from S2.6 for adaptation calls
- Orchestrator (S7.2) can optionally integrate PlanCache before decomposition/synthesis
- Graceful degradation: if ChromaDB is down, skip cache and proceed normally

## TDD Notes

### Test file: `tests/unit/test_plan_cache.py`

1. `test_store_plan` — stores a plan and verifies embed_and_store was called with correct collection/metadata
2. `test_query_similar_high_match` — returns CachedPlan with HIGH tier for score >= 0.85
3. `test_query_similar_medium_match` — returns CachedPlan with MEDIUM tier for 0.70-0.84
4. `test_query_similar_miss` — returns empty list for score < 0.70
5. `test_classify_match_tiers` — boundary testing for tier classification
6. `test_invalidate_stale_plans` — removes plans older than TTL
7. `test_cache_stats_tracking` — hit/miss counts update correctly
8. `test_graceful_degradation_chromadb_down` — returns empty results when ChromaDB fails

### Test file: `tests/unit/test_plan_adapter.py`

1. `test_adapt_plan_high_similarity` — uses routine tier LLM
2. `test_adapt_plan_medium_similarity` — uses standard tier LLM
3. `test_compute_delta_geographic` — detects geographic differences
4. `test_compute_delta_severity` — detects severity changes
5. `test_compute_delta_multiple` — detects multiple simultaneous differences
6. `test_validate_adaptation` — checks adapted plan has required sections
7. `test_adapt_plan_llm_failure` — graceful degradation when LLM fails

## Non-Functional Requirements

- Cache query latency < 200ms (ChromaDB similarity search)
- No real ChromaDB or LLM calls in tests
- All functions async
- Structured logging with trace_id
