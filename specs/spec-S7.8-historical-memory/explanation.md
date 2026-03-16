# S7.8 — HistoricalMemory Agent: Explanation

## Why This Spec Exists

The HistoricalMemory agent is the **knowledge grounding layer** for the entire multi-agent system. Without it, agents generate disaster response plans from LLM training data alone — which may be generic, outdated, or hallucinated. HistoricalMemory retrieves real NDMA guidelines, validated SOPs, and actual Indian disaster response records, ensuring every recommendation is traceable to authoritative sources.

It also closes the **learning loop**: after each benchmark scenario, the agent captures what worked and what didn't, embedding those learnings for future retrieval. This makes the system self-improving — each scenario run makes the next one better.

## What It Does

### Core Capabilities

1. **RAG Knowledge Retrieval** — Queries 5 ChromaDB collections (`ndma_guidelines`, `ndma_sops`, `state_sdma_reports`, `ndma_annual`, `historical_events`) for context relevant to the current disaster scenario. Returns ranked chunks with similarity scores.

2. **Historical Disaster Search** — Finds analogous past Indian disasters (e.g., "Similar to Cyclone Phailin 2013, score: 0.89") by searching the `historical_events` collection. Surfaces specific response metrics like "Odisha evacuated 1.2M in 48h."

3. **Response Synthesis** — Uses the standard-tier LLM (DeepSeek Chat) to synthesize retrieved chunks into actionable recommendations with confidence scores that blend LLM assessment (60%) and retrieval quality (40%).

4. **Post-Event Learning** — After benchmark scenarios complete, extracts key decisions, outcomes, and lessons, then embeds and stores them in `historical_events` for future retrieval.

### LangGraph State Machine

```
receive_query → retrieve_context → synthesize_response → [conditional] → END
                                                         ↓ (post_event)
                                                   ingest_learning → END
```

- **receive_query**: Parses task payload for query type, text, disaster type, and state filter
- **retrieve_context**: Queries relevant ChromaDB collections, merges and ranks results
- **synthesize_response**: LLM-powered synthesis with confidence scoring
- **ingest_learning**: (conditional) Stores post-event learnings as new embeddings

## How It Works

### Query Routing

The agent supports 3 query types:
- `guideline_lookup` → queries `ndma_guidelines`, `ndma_sops`, `state_sdma_reports`, `ndma_annual`
- `historical_search` → queries `historical_events`, `ndma_guidelines`
- `post_event_learning` → retrieves context normally, then routes to ingestion after synthesis

### Confidence Scoring

Confidence = `LLM_confidence * 0.6 + avg_retrieval_score * 0.4`, capped at 0.95. This ensures:
- High retrieval quality + high LLM confidence = high overall confidence
- No retrieval results = confidence drops to 0.2 (signals "I'm guessing")
- Pure LLM hallucination is penalized by low retrieval scores

### Collection Selection Strategy

Rather than querying all 5 collections for every query (expensive), the agent selects collections based on query type. Guideline queries skip `historical_events`; historical searches prioritize it. Results from all queried collections are merged and sorted by score, taking the top 10.

## How It Connects

### Dependencies (consumes)
- **S7.1 BaseAgent** — Inherits LangGraph state machine, LLM Router, A2A protocol, health checks
- **S6.1 ChromaDB setup** — Uses `EmbeddingPipeline` for `query_similar()` and `embed_and_store()`
- **S6.2 NDMA ingestion** — Collections populated by NDMA PDF ingestion pipeline

### Dependents (provides to)
- **S7.2 Orchestrator** — Delegates historical context queries to this agent
- **S7.9 Integration Test** — Part of the end-to-end agent pipeline validation
- **S9.1 Plan Caching** — Shares the `EmbeddingPipeline` and ChromaDB infrastructure

### Inter-Agent Communication
- Receives A2A tasks from Orchestrator with query payloads
- Returns A2A results with synthesized recommendations, confidence, and retrieval metadata
- Active in `pre_event` (historical context), `recovery` (past patterns), and `post_event` (learning capture) phases

## Interview Q&A

**Q: How does the confidence scoring prevent hallucination?**
A: The confidence formula blends two independent signals: the LLM's self-assessed confidence (which can be overconfident) and the average retrieval similarity score (a factual measure of how relevant the source documents are). If retrieval scores are low — meaning the knowledge base doesn't contain relevant information — the confidence drops even if the LLM claims high confidence. This surfaces the "I'm guessing" signal to downstream agents.

**Q: Why not query all collections for every request?**
A: Cost and latency. Each `query_similar()` call embeds the query text and runs a vector search. Querying 5 collections means 5 embedding calls and 5 searches. For a guideline lookup, the `historical_events` collection is unlikely to have relevant results — it contains disaster records, not procedures. Collection selection reduces unnecessary work by 20-40%.

**Q: How does post-event learning prevent the knowledge base from growing unbounded?**
A: Currently, deduplication happens at the `EmbeddingPipeline` level — documents with the same `document_id` are not re-embedded. Each learning gets a unique ID based on `scenario_id` and index. In practice, the knowledge base grows slowly (2-5 learnings per scenario × ~100 scenarios = ~500 chunks). ChromaDB handles this scale easily. Future work could add decay/pruning for outdated learnings.
