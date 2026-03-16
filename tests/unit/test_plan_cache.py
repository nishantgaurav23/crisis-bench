"""Tests for Agentic Plan Caching (S9.1) — PlanCache.

Tests cover: plan storage, similarity-based retrieval, cache match tiers,
plan invalidation, cache statistics, and graceful degradation.
All external services (ChromaDB, Ollama) are mocked — no real calls.
"""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.caching.plan_cache import (
    CachedPlan,
    CacheMatchTier,
    PlanCache,
    PlanCacheStats,
)
from src.data.ingest.embeddings import EmbeddingPipeline, SimilarityResult
from src.shared.config import CrisisSettings
from src.shared.errors import VectorStoreError

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def settings() -> CrisisSettings:
    return CrisisSettings(
        CHROMA_HOST="localhost",
        CHROMA_PORT=8100,
        OLLAMA_HOST="http://localhost:11434",
        OLLAMA_EMBED_MODEL="nomic-embed-text",
        _env_file=None,
    )


@pytest.fixture
def mock_pipeline() -> AsyncMock:
    pipeline = AsyncMock(spec=EmbeddingPipeline)
    pipeline.embed_and_store = AsyncMock(return_value=1)
    pipeline.query_similar = AsyncMock(return_value=[])
    return pipeline


@pytest.fixture
def cache(settings, mock_pipeline) -> PlanCache:
    return PlanCache(pipeline=mock_pipeline, settings=settings)


# =============================================================================
# CacheMatchTier Model
# =============================================================================


class TestCacheMatchTier:
    def test_high_tier(self):
        assert CacheMatchTier.HIGH == "high"

    def test_medium_tier(self):
        assert CacheMatchTier.MEDIUM == "medium"

    def test_miss_tier(self):
        assert CacheMatchTier.MISS == "miss"


# =============================================================================
# CachedPlan Model
# =============================================================================


class TestCachedPlan:
    def test_cached_plan_creation(self):
        plan = CachedPlan(
            plan_text="Evacuate Puri district via NH-16",
            similarity_score=0.92,
            match_tier=CacheMatchTier.HIGH,
            metadata={"disaster_type": "cyclone", "severity": 4},
            document_id="plan_cyclone_odisha_001",
        )
        assert plan.plan_text == "Evacuate Puri district via NH-16"
        assert plan.similarity_score == 0.92
        assert plan.match_tier == CacheMatchTier.HIGH


# =============================================================================
# PlanCacheStats Model
# =============================================================================


class TestPlanCacheStats:
    def test_default_stats(self):
        stats = PlanCacheStats()
        assert stats.total_queries == 0
        assert stats.cache_hits == 0
        assert stats.cache_misses == 0
        assert stats.avg_similarity == 0.0
        assert stats.hit_rate == 0.0


# =============================================================================
# PlanCache.classify_match
# =============================================================================


class TestClassifyMatch:
    def test_high_at_threshold(self, cache):
        assert cache.classify_match(0.85) == CacheMatchTier.HIGH

    def test_high_above_threshold(self, cache):
        assert cache.classify_match(0.95) == CacheMatchTier.HIGH

    def test_medium_at_lower_threshold(self, cache):
        assert cache.classify_match(0.70) == CacheMatchTier.MEDIUM

    def test_medium_in_range(self, cache):
        assert cache.classify_match(0.80) == CacheMatchTier.MEDIUM

    def test_medium_just_below_high(self, cache):
        assert cache.classify_match(0.849) == CacheMatchTier.MEDIUM

    def test_miss_below_threshold(self, cache):
        assert cache.classify_match(0.69) == CacheMatchTier.MISS

    def test_miss_at_zero(self, cache):
        assert cache.classify_match(0.0) == CacheMatchTier.MISS


# =============================================================================
# PlanCache.store_plan
# =============================================================================


class TestStorePlan:
    async def test_store_plan_calls_embed_and_store(self, cache, mock_pipeline):
        await cache.store_plan(
            plan_text="Deploy 4 NDRF battalions to Puri",
            metadata={
                "document_id": "plan_cyclone_puri_001",
                "disaster_type": "cyclone",
                "severity": 4,
                "affected_states": ["Odisha"],
            },
        )
        mock_pipeline.embed_and_store.assert_awaited_once()
        call_args = mock_pipeline.embed_and_store.call_args
        assert call_args[1]["collection_name"] == "plan_cache"
        assert call_args[1]["texts"] == ["Deploy 4 NDRF battalions to Puri"]
        assert call_args[1]["metadatas"][0]["disaster_type"] == "cyclone"

    async def test_store_plan_returns_chunk_count(self, cache, mock_pipeline):
        mock_pipeline.embed_and_store.return_value = 3
        count = await cache.store_plan(
            plan_text="Some plan text",
            metadata={"document_id": "plan_001"},
        )
        assert count == 3

    async def test_store_plan_adds_timestamp(self, cache, mock_pipeline):
        await cache.store_plan(
            plan_text="Plan text",
            metadata={"document_id": "plan_002"},
        )
        call_args = mock_pipeline.embed_and_store.call_args
        stored_meta = call_args[1]["metadatas"][0]
        assert "stored_at" in stored_meta


# =============================================================================
# PlanCache.query_similar_plans
# =============================================================================


class TestQuerySimilarPlans:
    async def test_high_match_returned(self, cache, mock_pipeline):
        mock_pipeline.query_similar.return_value = [
            SimilarityResult(
                text="Evacuate coastal Odisha for VSCS cyclone",
                score=0.92,
                metadata={"disaster_type": "cyclone", "document_id": "plan_001"},
                document_id="plan_001",
            ),
        ]
        results = await cache.query_similar_plans("Cyclone approaching Odisha coast")
        assert len(results) == 1
        assert results[0].match_tier == CacheMatchTier.HIGH
        assert results[0].similarity_score == 0.92

    async def test_medium_match_returned(self, cache, mock_pipeline):
        mock_pipeline.query_similar.return_value = [
            SimilarityResult(
                text="Evacuate for flood in Bihar",
                score=0.75,
                metadata={"disaster_type": "flood", "document_id": "plan_002"},
                document_id="plan_002",
            ),
        ]
        results = await cache.query_similar_plans("Flood in Assam")
        assert len(results) == 1
        assert results[0].match_tier == CacheMatchTier.MEDIUM

    async def test_miss_filtered_out(self, cache, mock_pipeline):
        mock_pipeline.query_similar.return_value = [
            SimilarityResult(
                text="Earthquake in Gujarat",
                score=0.50,
                metadata={"disaster_type": "earthquake", "document_id": "plan_003"},
                document_id="plan_003",
            ),
        ]
        results = await cache.query_similar_plans("Cyclone in Tamil Nadu")
        assert len(results) == 0

    async def test_mixed_results_filtered(self, cache, mock_pipeline):
        mock_pipeline.query_similar.return_value = [
            SimilarityResult(
                text="Plan A", score=0.90,
                metadata={"document_id": "p1"}, document_id="p1",
            ),
            SimilarityResult(
                text="Plan B", score=0.75,
                metadata={"document_id": "p2"}, document_id="p2",
            ),
            SimilarityResult(
                text="Plan C", score=0.40,
                metadata={"document_id": "p3"}, document_id="p3",
            ),
        ]
        results = await cache.query_similar_plans("Some scenario")
        assert len(results) == 2  # Plan C filtered (miss)
        assert results[0].match_tier == CacheMatchTier.HIGH
        assert results[1].match_tier == CacheMatchTier.MEDIUM

    async def test_query_passes_top_k(self, cache, mock_pipeline):
        await cache.query_similar_plans("test", top_k=3)
        mock_pipeline.query_similar.assert_awaited_once()
        call_args = mock_pipeline.query_similar.call_args
        assert call_args[1]["top_k"] == 3


# =============================================================================
# PlanCache.invalidate_stale
# =============================================================================


class TestInvalidateStale:
    async def test_invalidate_removes_old_plans(self, cache, mock_pipeline):
        mock_collection = MagicMock()
        old_ts = str(time.time() - 86400 * 60)  # 60 days ago
        mock_collection.get.return_value = {
            "ids": ["old_plan_chunk_0", "old_plan_chunk_1"],
            "metadatas": [
                {"stored_at": old_ts, "document_id": "old_plan"},
                {"stored_at": old_ts, "document_id": "old_plan"},
            ],
        }
        mock_pipeline.chroma_manager = MagicMock()
        mock_pipeline.chroma_manager.get_or_create_collection.return_value = mock_collection

        removed = await cache.invalidate_stale(ttl_days=30)
        assert removed > 0
        mock_collection.delete.assert_called()

    async def test_invalidate_keeps_fresh_plans(self, cache, mock_pipeline):
        mock_collection = MagicMock()
        fresh_ts = str(time.time())  # just now
        mock_collection.get.return_value = {
            "ids": ["fresh_plan_chunk_0"],
            "metadatas": [
                {"stored_at": fresh_ts, "document_id": "fresh_plan"},
            ],
        }
        mock_pipeline.chroma_manager = MagicMock()
        mock_pipeline.chroma_manager.get_or_create_collection.return_value = mock_collection

        removed = await cache.invalidate_stale(ttl_days=30)
        assert removed == 0


# =============================================================================
# PlanCache stats tracking
# =============================================================================


class TestCacheStats:
    async def test_stats_after_hit(self, cache, mock_pipeline):
        mock_pipeline.query_similar.return_value = [
            SimilarityResult(
                text="Plan", score=0.90,
                metadata={"document_id": "p1"}, document_id="p1",
            ),
        ]
        await cache.query_similar_plans("test")
        stats = cache.get_stats()
        assert stats.total_queries == 1
        assert stats.cache_hits == 1
        assert stats.cache_misses == 0
        assert stats.hit_rate == 1.0

    async def test_stats_after_miss(self, cache, mock_pipeline):
        mock_pipeline.query_similar.return_value = [
            SimilarityResult(
                text="Plan", score=0.40,
                metadata={"document_id": "p1"}, document_id="p1",
            ),
        ]
        await cache.query_similar_plans("test")
        stats = cache.get_stats()
        assert stats.total_queries == 1
        assert stats.cache_hits == 0
        assert stats.cache_misses == 1
        assert stats.hit_rate == 0.0

    async def test_stats_avg_similarity(self, cache, mock_pipeline):
        mock_pipeline.query_similar.return_value = [
            SimilarityResult(
                text="Plan", score=0.90,
                metadata={"document_id": "p1"}, document_id="p1",
            ),
        ]
        await cache.query_similar_plans("test1")

        mock_pipeline.query_similar.return_value = [
            SimilarityResult(
                text="Plan", score=0.80,
                metadata={"document_id": "p2"}, document_id="p2",
            ),
        ]
        await cache.query_similar_plans("test2")

        stats = cache.get_stats()
        assert stats.avg_similarity == pytest.approx(0.85, abs=0.01)


# =============================================================================
# Graceful degradation
# =============================================================================


class TestGracefulDegradation:
    async def test_query_returns_empty_on_chromadb_failure(self, cache, mock_pipeline):
        mock_pipeline.query_similar.side_effect = VectorStoreError("ChromaDB down")
        results = await cache.query_similar_plans("test")
        assert results == []

    async def test_store_raises_on_failure(self, cache, mock_pipeline):
        mock_pipeline.embed_and_store.side_effect = VectorStoreError("ChromaDB down")
        with pytest.raises(VectorStoreError):
            await cache.store_plan(
                plan_text="Some plan",
                metadata={"document_id": "plan_001"},
            )
