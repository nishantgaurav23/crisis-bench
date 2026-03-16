# Spec S7.8 — HistoricalMemory Agent

**Status**: spec-written
**Depends On**: S7.1 (BaseAgent), S6.1 (ChromaDB setup), S6.2 (NDMA ingestion)
**Location**: `src/agents/historical_memory.py`
**Test File**: `tests/unit/test_historical_memory.py`

---

## Overview

The HistoricalMemory agent provides RAG-based retrieval over NDMA guidelines, historical disaster records, and past response patterns. It grounds other agents' decisions in validated procedures and real Indian disaster history, and captures post-event learnings to continuously evolve the knowledge base.

**LLM Tier**: standard (DeepSeek Chat $0.28/M, fallback: Qwen Flash -> Groq -> Ollama)

## Functional Requirements

### FR-007.1: RAG Knowledge Base Queries
- Query ChromaDB collections: `ndma_guidelines`, `ndma_sops`, `state_sdma_reports`, `ndma_annual`, `historical_events`
- Return top-K similar chunks with similarity scores
- Support filtering by disaster type, state, and document category

### FR-007.2: Historical Disaster Retrieval
- Retrieve similar past Indian disasters from `historical_events` collection
- Return similarity scores and key response metrics (people evacuated, timeline, etc.)
- Example: "Similar to Cyclone Phailin 2013 trajectory" (score: 0.89)

### FR-007.3: Past Decision Surfacing
- Surface historical decisions with specific metrics from retrieved context
- Use LLM to synthesize retrieved chunks into actionable recommendations
- Example: "During Cyclone Fani 2019, Odisha evacuated 1.2M people in 48h"

### FR-007.4: Notable Indian Disaster Learnings
- Knowledge of key Indian disasters: Kerala 2018, Mumbai 26/7 2005, Uttarakhand 2013, Bhopal 1984
- Surface relevant learnings when disaster type/region matches

### FR-007.5: Bilingual Query Support
- Accept queries in English and Hindi
- Return results in the query language

### FR-007.6: Post-Event Learning Ingestion
- After benchmark scenarios, extract key decisions and outcomes
- Embed learnings into `historical_events` collection for future retrieval

## LangGraph State Machine

```
receive_query -> retrieve_context -> synthesize_response -> [conditional] -> END
                                                          |
                                                          v (if post_event)
                                                    ingest_learning -> END
```

### Nodes

1. **receive_query** — Parse task payload, determine query type (guideline_lookup, historical_search, post_event_learning)
2. **retrieve_context** — Query ChromaDB for relevant chunks across collections, filter by disaster type/state
3. **synthesize_response** — Use LLM to synthesize retrieved chunks into actionable recommendations with confidence score
4. **ingest_learning** — (post-event only) Extract learnings from scenario results, embed and store in `historical_events`

## Agent Card Capabilities

- `rag_knowledge_retrieval` — Query NDMA guidelines and SOPs
- `historical_disaster_search` — Find similar past disasters
- `past_decision_surfacing` — Surface historical response patterns
- `post_event_learning` — Capture and store new learnings
- `bilingual_query` — English + Hindi query support

## Data Dependencies

| Collection | Source | Content |
|-----------|--------|---------|
| `ndma_guidelines` | S6.2 | 30+ NDMA guideline PDFs |
| `ndma_sops` | S6.2 | Standard Operating Procedures |
| `state_sdma_reports` | S6.2 | State SDMA after-action reports |
| `ndma_annual` | S6.2 | NDMA annual reports |
| `historical_events` | S6.2 + post-event | EM-DAT + state records + benchmark learnings |

## TDD Notes

### Test Categories

1. **Initialization** — Agent type, LLM tier, system prompt, agent card
2. **State Machine** — Graph nodes, edges, compilation, entry/exit points
3. **Query Parsing** — Guideline lookup, historical search, post-event learning routing
4. **RAG Retrieval** — ChromaDB query calls, filtering, top-K, empty results
5. **Response Synthesis** — LLM reasoning with retrieved context, confidence scoring
6. **Post-Event Learning** — Learning extraction, embedding, storage
7. **Edge Cases** — Empty queries, no matching results, malformed payloads

### Mock Strategy
- Mock `EmbeddingPipeline.query_similar()` for retrieval
- Mock `EmbeddingPipeline.embed_and_store()` for ingestion
- Mock `LLMRouter.call()` for LLM reasoning
- Mock A2A client/server (same pattern as other agents)

## Outcomes

- [ ] HistoricalMemory agent subclasses BaseAgent correctly
- [ ] LangGraph with 4 nodes compiles and runs
- [ ] Queries ChromaDB across 5 collections with filtering
- [ ] Synthesizes retrieved context into actionable recommendations
- [ ] Post-event learning ingestion stores new embeddings
- [ ] All external services mocked in tests
- [ ] >80% test coverage
- [ ] ruff lint clean
