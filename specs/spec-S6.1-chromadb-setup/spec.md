# Spec S6.1: ChromaDB Setup + Embedding Pipeline

**Phase**: 6 — Data Pipeline
**Location**: `src/data/ingest/embeddings.py`
**Depends On**: S1.3 (Environment Config)
**Status**: done

---

## Overview

Set up ChromaDB connection management and a reusable embedding pipeline. This is the foundation for all RAG operations in CRISIS-BENCH — NDMA guidelines ingestion (S6.2), historical memory agent (S7.8), and plan caching (S9.1) all depend on this.

## Requirements

### R1: ChromaDB Client Management
- Async-compatible ChromaDB HTTP client connecting to `CHROMA_HOST:CHROMA_PORT` from config
- Health check method to verify ChromaDB is reachable
- Collection creation/retrieval with idempotent `get_or_create_collection`

### R2: Collection Registry
- Pre-defined collection names matching design.md:
  - `ndma_guidelines` — NDMA guideline PDFs chunked and embedded
  - `ndma_sops` — Standard Operating Procedures per disaster type
  - `state_sdma_reports` — State SDMA after-action reports
  - `ndma_annual` — NDMA annual reports
  - `historical_events` — EM-DAT + state records for Indian disasters
  - `plan_cache` — Agentic Plan Caching for recurring scenarios
- Each collection uses cosine distance metric
- Metadata schema per collection (source, document_id, chunk_index, page_number, disaster_type, state)

### R3: Embedding via Ollama (nomic-embed-text)
- Generate embeddings using `nomic-embed-text` model via Ollama HTTP API
- 768-dimensional vectors
- Batch embedding support (process multiple texts in one call)
- Fallback: if Ollama is unreachable, raise a clear `DataError`

### R4: Text Chunking Strategy
- Configurable chunk size (default: 512 tokens) and overlap (default: 64 tokens)
- Character-based chunking with sentence-boundary awareness
- Preserve metadata through chunking (source doc, page number, chunk index)
- Return structured `TextChunk` Pydantic model

### R5: Document Ingestion Pipeline
- `embed_and_store(collection_name, texts, metadatas)` — chunk, embed, store in one call
- `query_similar(collection_name, query_text, top_k)` — embed query, search, return results
- Deduplication: skip documents already in collection (by document_id metadata)
- Batch processing with configurable batch size (default: 32)

## Outcomes

1. ChromaDB client connects and creates/retrieves collections
2. Embeddings generated via Ollama nomic-embed-text (768 dims)
3. Text chunked with overlap and metadata preserved
4. Documents stored in ChromaDB with deduplication
5. Similarity search returns relevant chunks with scores

## TDD Notes

### Test Cases
- `test_chromadb_client_health_check` — mock HTTP, verify health endpoint called
- `test_get_or_create_collection` — idempotent collection creation
- `test_collection_registry` — all 6 collections defined with correct names
- `test_embed_text_via_ollama` — mock Ollama API, verify 768-dim vectors returned
- `test_embed_batch` — multiple texts embedded in one call
- `test_embed_ollama_unreachable` — raises DataError when Ollama is down
- `test_chunk_text_basic` — text split into expected number of chunks
- `test_chunk_text_overlap` — chunks overlap by configured amount
- `test_chunk_text_preserves_metadata` — metadata propagated to all chunks
- `test_chunk_text_sentence_boundary` — chunks break at sentence boundaries
- `test_embed_and_store` — end-to-end: chunk → embed → store
- `test_query_similar` — embed query → search → return ranked results
- `test_deduplication` — same document_id not stored twice
- `test_batch_processing` — large input split into batches

### Mocking Strategy
- Mock `httpx.AsyncClient` for Ollama embedding API calls
- Mock `chromadb.HttpClient` for ChromaDB operations
- Never hit real Ollama or ChromaDB in tests
