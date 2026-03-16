# Spec S6.1: Implementation Checklist

## Phase 1: Red (Write Failing Tests)
- [x] Create `tests/unit/test_embeddings.py`
- [x] Write all 25 test cases from spec
- [x] Verify all tests fail (no implementation yet)

## Phase 2: Green (Implement)
- [x] Implement `TextChunk` Pydantic model
- [x] Implement `EmbeddingResult` Pydantic model
- [x] Implement `SimilarityResult` Pydantic model
- [x] Implement `COLLECTION_REGISTRY` with 6 collections
- [x] Implement `OllamaEmbedder` class (Ollama HTTP API)
- [x] Implement `TextChunker` class (sentence-boundary chunking)
- [x] Implement `ChromaDBManager` class (client, health, collections)
- [x] Implement `EmbeddingPipeline` class (embed_and_store, query_similar)
- [x] All 25 tests pass

## Phase 3: Refactor
- [x] Run ruff, fix lint issues (removed unused import)
- [x] Verify all tests still pass (25/25)
- [x] Full test suite: 894 passed, 1 pre-existing failure (unrelated)
