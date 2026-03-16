# Spec S6.1: ChromaDB Setup + Embedding Pipeline — Explanation

## Why This Spec Exists

Every RAG (Retrieval-Augmented Generation) operation in CRISIS-BENCH needs two things: (1) a vector database to store and search document embeddings, and (2) a pipeline to convert text into those embeddings. This spec provides both, serving as the foundation for:

- **S6.2** (NDMA Guidelines Ingestion) — chunks and embeds 30+ NDMA PDFs
- **S7.4** (PredictiveRisk Agent) — retrieves historical disaster analogies
- **S7.8** (HistoricalMemory Agent) — RAG over NDMA docs and past events
- **S9.1** (Agentic Plan Caching) — stores/retrieves cached agent plans

Without this module, none of the RAG-dependent agents or data pipelines can function.

## What It Does

### Components

1. **`COLLECTION_REGISTRY`** — Defines 6 ChromaDB collections matching the design doc: `ndma_guidelines`, `ndma_sops`, `state_sdma_reports`, `ndma_annual`, `historical_events`, `plan_cache`. All use cosine distance.

2. **`TextChunker`** — Splits long text into overlapping chunks (default 512 chars, 64 overlap) with sentence-boundary awareness. Preserves metadata through chunking.

3. **`OllamaEmbedder`** — Generates 768-dimensional embeddings via Ollama's HTTP API using `nomic-embed-text`. Supports single and batch embedding. Raises `DataError` if Ollama is unreachable.

4. **`ChromaDBManager`** — Manages the ChromaDB HTTP client connection. Provides health check and idempotent `get_or_create_collection` that enforces the collection registry.

5. **`EmbeddingPipeline`** — Orchestrates the full flow: chunk text → embed via Ollama → store in ChromaDB. Also provides `query_similar` for retrieval. Handles deduplication (skips documents already stored by `document_id`) and batch processing.

### Pydantic Models

- `TextChunk` — text + chunk_index + metadata
- `EmbeddingResult` — embedding vector + source text + model name
- `SimilarityResult` — matching text + similarity score + metadata + document_id

## How It Works

### Ingestion Flow
```
Text → TextChunker.chunk() → [TextChunk, ...] → OllamaEmbedder.embed_batch() → [EmbeddingResult, ...] → ChromaDB.add()
```

### Query Flow
```
Query → OllamaEmbedder.embed() → EmbeddingResult → ChromaDB.query() → [SimilarityResult, ...]
```

### Key Design Decisions

- **Ollama for embeddings** ($0 cost): `nomic-embed-text` runs locally, producing 768-dim vectors. Competitive with OpenAI's ada-002 on retrieval benchmarks but completely free.
- **Sentence-boundary chunking**: Chunks break at `.!?` boundaries, preventing mid-sentence splits that degrade retrieval quality.
- **Deduplication by document_id**: Prevents re-embedding the same document if ingestion is run multiple times.
- **Cosine distance for all collections**: Standard for text similarity — measures directional similarity regardless of vector magnitude.

## How It Connects

| Upstream (depends on) | This Spec | Downstream (depends on this) |
|---|---|---|
| S1.3 (Config) — `CHROMA_HOST`, `CHROMA_PORT`, `OLLAMA_HOST`, `OLLAMA_EMBED_MODEL` | S6.1 — ChromaDB + Embedding Pipeline | S6.2 (NDMA Ingestion), S7.4 (PredictiveRisk), S7.8 (HistoricalMemory), S9.1 (Plan Caching) |
| S2.4 (Errors) — `DataError`, `VectorStoreError` | | |

## Interview Talking Points

**Q: Why ChromaDB instead of Pinecone or Weaviate?**
A: ChromaDB is self-hosted (Docker), free (Apache 2.0), and the simplest vector DB to set up. For ~50K document chunks, it's more than adequate. Pinecone is SaaS (costs $), Weaviate has more complex setup. We can migrate to Qdrant later if we need better performance.

**Q: Why nomic-embed-text over sentence-transformers?**
A: nomic-embed-text via Ollama gives us a clean HTTP API with no Python dependency management for model loading. sentence-transformers would require loading the model in the same Python process, consuming GPU memory that Ollama manages separately. Same quality, cleaner architecture.

**Q: Why sentence-boundary chunking instead of token-based?**
A: Token-based chunking (using tiktoken or similar) is more precise for token budgets, but sentence-boundary chunking produces more semantically coherent chunks. When a retrieval chunk starts mid-sentence ("...flooded areas should evacuate"), the LLM gets less context. Starting at sentence boundaries preserves complete thoughts.
