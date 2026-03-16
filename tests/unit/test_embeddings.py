"""Tests for ChromaDB setup + embedding pipeline (S6.1).

Tests cover: ChromaDB client management, collection registry, Ollama embeddings,
text chunking, document ingestion, similarity search, deduplication, batch processing.
All external services (ChromaDB, Ollama) are mocked — no real calls.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.data.ingest.embeddings import (
    COLLECTION_REGISTRY,
    ChromaDBManager,
    EmbeddingPipeline,
    EmbeddingResult,
    OllamaEmbedder,
    SimilarityResult,
    TextChunk,
    TextChunker,
)
from src.shared.config import CrisisSettings
from src.shared.errors import DataError, VectorStoreError

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def settings() -> CrisisSettings:
    """CrisisSettings with test values."""
    return CrisisSettings(
        CHROMA_HOST="localhost",
        CHROMA_PORT=8100,
        OLLAMA_HOST="http://localhost:11434",
        OLLAMA_EMBED_MODEL="nomic-embed-text",
        _env_file=None,
    )


@pytest.fixture
def mock_chroma_client():
    """Mock chromadb.HttpClient."""
    client = MagicMock()
    client.heartbeat.return_value = 1
    mock_collection = MagicMock()
    mock_collection.name = "test_collection"
    mock_collection.count.return_value = 0
    client.get_or_create_collection.return_value = mock_collection
    return client


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient for Ollama API."""
    client = AsyncMock()
    return client


@pytest.fixture
def embedder(settings, mock_httpx_client):
    """OllamaEmbedder with mocked HTTP client."""
    emb = OllamaEmbedder(settings)
    emb._client = mock_httpx_client
    return emb


@pytest.fixture
def chunker():
    """TextChunker with default settings."""
    return TextChunker(chunk_size=512, chunk_overlap=64)


@pytest.fixture
def chroma_manager(settings, mock_chroma_client):
    """ChromaDBManager with mocked client."""
    mgr = ChromaDBManager(settings)
    mgr._client = mock_chroma_client
    return mgr


# =============================================================================
# Collection Registry
# =============================================================================


class TestCollectionRegistry:
    def test_all_six_collections_defined(self):
        """COLLECTION_REGISTRY has all 6 collections from design.md."""
        expected = {
            "ndma_guidelines",
            "ndma_sops",
            "state_sdma_reports",
            "ndma_annual",
            "historical_events",
            "plan_cache",
        }
        assert set(COLLECTION_REGISTRY.keys()) == expected

    def test_collections_have_metadata(self):
        """Each collection entry has description and distance metric."""
        for name, info in COLLECTION_REGISTRY.items():
            assert "description" in info, f"{name} missing description"
            assert info.get("distance_fn") == "cosine", f"{name} should use cosine"


# =============================================================================
# TextChunk Model
# =============================================================================


class TestTextChunk:
    def test_text_chunk_creation(self):
        chunk = TextChunk(
            text="Some disaster text",
            chunk_index=0,
            metadata={"source": "ndma_flood.pdf", "page_number": 1},
        )
        assert chunk.text == "Some disaster text"
        assert chunk.chunk_index == 0
        assert chunk.metadata["source"] == "ndma_flood.pdf"

    def test_text_chunk_requires_text(self):
        with pytest.raises(Exception):
            TextChunk(text="", chunk_index=0, metadata={})


# =============================================================================
# EmbeddingResult Model
# =============================================================================


class TestEmbeddingResult:
    def test_embedding_result_creation(self):
        result = EmbeddingResult(
            embedding=[0.1] * 768,
            text="test",
            model="nomic-embed-text",
        )
        assert len(result.embedding) == 768
        assert result.model == "nomic-embed-text"


# =============================================================================
# SimilarityResult Model
# =============================================================================


class TestSimilarityResult:
    def test_similarity_result_creation(self):
        result = SimilarityResult(
            text="matching chunk",
            score=0.92,
            metadata={"source": "ndma_flood.pdf"},
            document_id="doc_001",
        )
        assert result.score == 0.92
        assert result.document_id == "doc_001"


# =============================================================================
# OllamaEmbedder
# =============================================================================


class TestOllamaEmbedder:
    async def test_embed_text_returns_768_dims(self, embedder, mock_httpx_client):
        """Embedding via Ollama returns 768-dimensional vector."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": [0.1] * 768}
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.post.return_value = mock_response

        result = await embedder.embed("test text")
        assert len(result.embedding) == 768
        assert result.model == "nomic-embed-text"

    async def test_embed_batch(self, embedder, mock_httpx_client):
        """Batch embedding processes multiple texts."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": [0.2] * 768}
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.post.return_value = mock_response

        results = await embedder.embed_batch(["text1", "text2", "text3"])
        assert len(results) == 3
        for r in results:
            assert len(r.embedding) == 768

    async def test_embed_ollama_unreachable(self, embedder, mock_httpx_client):
        """Raises DataError when Ollama is unreachable."""
        import httpx

        mock_httpx_client.post.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(DataError, match="Ollama"):
            await embedder.embed("test text")

    async def test_embed_calls_correct_endpoint(self, embedder, mock_httpx_client):
        """Verify the Ollama embedding API endpoint is called correctly."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": [0.1] * 768}
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.post.return_value = mock_response

        await embedder.embed("hello")
        mock_httpx_client.post.assert_called_once()
        call_args = mock_httpx_client.post.call_args
        assert "/api/embeddings" in call_args[0][0] or "/api/embed" in str(call_args)


# =============================================================================
# TextChunker
# =============================================================================


class TestTextChunker:
    def test_chunk_text_basic(self, chunker):
        """Text is split into expected number of chunks."""
        # Create text that's clearly longer than 512 chars
        text = "This is a sentence. " * 100  # ~2000 chars
        chunks = chunker.chunk(text, metadata={"source": "test.pdf"})
        assert len(chunks) > 1
        # All text should be covered
        combined = " ".join(c.text.strip() for c in chunks)
        # Original words should appear in combined chunks
        assert "sentence" in combined

    def test_chunk_text_overlap(self, chunker):
        """Chunks overlap by configured amount."""
        text = "Word " * 500  # Long text
        chunks = chunker.chunk(text, metadata={"source": "test.pdf"})
        if len(chunks) >= 2:
            # Last part of chunk N should appear at start of chunk N+1
            end_of_first = chunks[0].text[-30:]
            # The overlap means some text from end of chunk 0 appears in chunk 1
            assert any(
                word in chunks[1].text for word in end_of_first.split() if word.strip()
            )

    def test_chunk_text_preserves_metadata(self, chunker):
        """Metadata propagated to all chunks."""
        text = "Disaster text. " * 100
        meta = {"source": "ndma_flood.pdf", "page_number": 5}
        chunks = chunker.chunk(text, metadata=meta)
        for chunk in chunks:
            assert chunk.metadata["source"] == "ndma_flood.pdf"
            assert chunk.metadata["page_number"] == 5
            assert "chunk_index" in chunk.metadata

    def test_chunk_text_sentence_boundary(self, chunker):
        """Chunks break at sentence boundaries when possible."""
        text = (
            "First sentence about floods. Second sentence about cyclones. "
            "Third sentence about earthquakes. Fourth sentence about tsunamis. "
        ) * 20
        chunks = chunker.chunk(text, metadata={"source": "test.pdf"})
        for chunk in chunks:
            # Each chunk should end with a sentence-ending character or be the last chunk
            stripped = chunk.text.strip()
            if chunk != chunks[-1]:
                assert stripped[-1] in ".!?", (
                    f"Non-final chunk should end at sentence boundary: ...{stripped[-20:]}"
                )

    def test_chunk_short_text(self, chunker):
        """Short text returns single chunk."""
        text = "Short text."
        chunks = chunker.chunk(text, metadata={"source": "test.pdf"})
        assert len(chunks) == 1
        assert chunks[0].text.strip() == "Short text."

    def test_chunk_indices_sequential(self, chunker):
        """Chunk indices are sequential starting from 0."""
        text = "Some sentence. " * 100
        chunks = chunker.chunk(text, metadata={"source": "test.pdf"})
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i


# =============================================================================
# ChromaDBManager
# =============================================================================


class TestChromaDBManager:
    def test_health_check_success(self, chroma_manager, mock_chroma_client):
        """Health check returns True when ChromaDB is reachable."""
        mock_chroma_client.heartbeat.return_value = 1
        assert chroma_manager.health_check() is True

    def test_health_check_failure(self, chroma_manager, mock_chroma_client):
        """Health check returns False when ChromaDB is down."""
        mock_chroma_client.heartbeat.side_effect = Exception("Connection refused")
        assert chroma_manager.health_check() is False

    def test_get_or_create_collection(self, chroma_manager, mock_chroma_client):
        """Idempotent collection creation."""
        collection = chroma_manager.get_or_create_collection("ndma_guidelines")
        mock_chroma_client.get_or_create_collection.assert_called_once()
        assert collection is not None

    def test_get_or_create_unknown_collection_raises(self, chroma_manager):
        """Requesting unknown collection raises VectorStoreError."""
        with pytest.raises(VectorStoreError, match="Unknown collection"):
            chroma_manager.get_or_create_collection("nonexistent_collection")

    def test_get_or_create_uses_cosine(self, chroma_manager, mock_chroma_client):
        """Collection created with cosine distance function."""
        chroma_manager.get_or_create_collection("ndma_guidelines")
        call_kwargs = mock_chroma_client.get_or_create_collection.call_args
        assert call_kwargs[1].get("metadata", {}).get("hnsw:space") == "cosine"


# =============================================================================
# EmbeddingPipeline
# =============================================================================


class TestEmbeddingPipeline:
    @pytest.fixture
    def pipeline(self, chroma_manager, embedder, chunker):
        return EmbeddingPipeline(
            chroma_manager=chroma_manager,
            embedder=embedder,
            chunker=chunker,
        )

    async def test_embed_and_store(self, pipeline, mock_httpx_client, mock_chroma_client):
        """End-to-end: chunk -> embed -> store."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": [0.1] * 768}
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.post.return_value = mock_response

        mock_collection = mock_chroma_client.get_or_create_collection.return_value
        mock_collection.get.return_value = {"ids": []}

        count = await pipeline.embed_and_store(
            collection_name="ndma_guidelines",
            texts=["Flood management guidelines. " * 20],
            metadatas=[{"source": "ndma_flood.pdf", "document_id": "doc_001"}],
        )
        assert count > 0
        mock_collection.add.assert_called()

    async def test_query_similar(self, pipeline, mock_httpx_client, mock_chroma_client):
        """Embed query -> search -> return ranked results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": [0.1] * 768}
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.post.return_value = mock_response

        mock_collection = mock_chroma_client.get_or_create_collection.return_value
        mock_collection.query.return_value = {
            "ids": [["id1", "id2"]],
            "documents": [["Flood alert text", "Cyclone warning text"]],
            "distances": [[0.1, 0.3]],
            "metadatas": [[
                {"source": "ndma_flood.pdf", "document_id": "doc_001"},
                {"source": "ndma_cyclone.pdf", "document_id": "doc_002"},
            ]],
        }

        results = await pipeline.query_similar(
            collection_name="ndma_guidelines",
            query_text="How to manage floods?",
            top_k=5,
        )
        assert len(results) == 2
        assert results[0].score > results[1].score  # Closer = higher score
        assert results[0].text == "Flood alert text"

    async def test_deduplication(self, pipeline, mock_httpx_client, mock_chroma_client):
        """Same document_id not stored twice."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": [0.1] * 768}
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.post.return_value = mock_response

        mock_collection = mock_chroma_client.get_or_create_collection.return_value
        # Simulate document already exists
        mock_collection.get.return_value = {"ids": ["doc_001_chunk_0", "doc_001_chunk_1"]}

        count = await pipeline.embed_and_store(
            collection_name="ndma_guidelines",
            texts=["Already stored text."],
            metadatas=[{"source": "ndma_flood.pdf", "document_id": "doc_001"}],
        )
        assert count == 0  # Nothing new stored
        mock_collection.add.assert_not_called()

    async def test_batch_processing(self, pipeline, mock_httpx_client, mock_chroma_client):
        """Large input split into batches."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": [0.1] * 768}
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.post.return_value = mock_response

        mock_collection = mock_chroma_client.get_or_create_collection.return_value
        mock_collection.get.return_value = {"ids": []}

        # Create many short texts that won't chunk further
        texts = [f"Short text {i}." for i in range(50)]
        metadatas = [{"source": f"doc_{i}.pdf", "document_id": f"doc_{i:03d}"} for i in range(50)]

        count = await pipeline.embed_and_store(
            collection_name="ndma_guidelines",
            texts=texts,
            metadatas=metadatas,
            batch_size=10,
        )
        assert count > 0
        # Should have called add multiple times due to batching
        assert mock_collection.add.call_count >= 2
