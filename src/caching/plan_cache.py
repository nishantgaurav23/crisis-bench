"""Agentic Plan Caching — ChromaDB-based storage and retrieval of agent plans.

Stores completed disaster response plans in ChromaDB's plan_cache collection,
enabling similarity-based retrieval for recurring disaster patterns. Plans above
the similarity threshold are returned as cache hits, reducing expensive LLM calls.

Similarity tiers:
    HIGH (>= 0.85): Use cached plan with minimal adaptation (routine LLM tier)
    MEDIUM (0.70 - 0.84): Use cached plan with significant adaptation (standard LLM tier)
    MISS (< 0.70): Generate fresh plan (no cache benefit)
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.data.ingest.embeddings import EmbeddingPipeline
from src.shared.config import CrisisSettings, get_settings
from src.shared.errors import VectorStoreError
from src.shared.telemetry import get_logger

logger = get_logger("plan_cache")

COLLECTION_NAME = "plan_cache"
HIGH_THRESHOLD = 0.85
MEDIUM_THRESHOLD = 0.70


# =============================================================================
# Data Models
# =============================================================================


class CacheMatchTier(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    MISS = "miss"


class CachedPlan(BaseModel):
    plan_text: str
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    match_tier: CacheMatchTier
    metadata: dict[str, Any] = Field(default_factory=dict)
    document_id: str = ""


class PlanCacheStats(BaseModel):
    total_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_similarity: float = 0.0
    hit_rate: float = 0.0


# =============================================================================
# PlanCache
# =============================================================================


class PlanCache:
    """ChromaDB-backed cache for agent response plans."""

    def __init__(
        self,
        pipeline: EmbeddingPipeline | None = None,
        settings: CrisisSettings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._pipeline = pipeline or EmbeddingPipeline(settings=self._settings)
        self._total_queries = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._similarity_sum = 0.0

    def classify_match(self, score: float) -> CacheMatchTier:
        """Classify a similarity score into a cache match tier."""
        if score >= HIGH_THRESHOLD:
            return CacheMatchTier.HIGH
        if score >= MEDIUM_THRESHOLD:
            return CacheMatchTier.MEDIUM
        return CacheMatchTier.MISS

    async def store_plan(
        self,
        plan_text: str,
        metadata: dict[str, Any],
    ) -> int:
        """Embed and store a plan in the plan_cache collection.

        Returns the number of chunks stored.
        """
        metadata = dict(metadata)
        metadata["stored_at"] = str(time.time())

        return await self._pipeline.embed_and_store(
            collection_name=COLLECTION_NAME,
            texts=[plan_text],
            metadatas=[metadata],
        )

    async def query_similar_plans(
        self,
        scenario_description: str,
        *,
        top_k: int = 5,
    ) -> list[CachedPlan]:
        """Query for similar cached plans. Returns only hits (>= MEDIUM threshold).

        Gracefully returns empty list if ChromaDB is unavailable.
        """
        try:
            results = await self._pipeline.query_similar(
                collection_name=COLLECTION_NAME,
                query_text=scenario_description,
                top_k=top_k,
            )
        except (VectorStoreError, Exception) as exc:
            if isinstance(exc, VectorStoreError):
                logger.warning("plan_cache_query_failed", error=str(exc))
                self._total_queries += 1
                self._cache_misses += 1
                return []
            raise

        # Track best similarity for stats
        best_score = max((r.score for r in results), default=0.0)
        self._total_queries += 1
        self._similarity_sum += best_score

        # Filter out misses and convert to CachedPlan
        cached_plans: list[CachedPlan] = []
        for result in results:
            tier = self.classify_match(result.score)
            if tier == CacheMatchTier.MISS:
                continue
            cached_plans.append(
                CachedPlan(
                    plan_text=result.text,
                    similarity_score=result.score,
                    match_tier=tier,
                    metadata=result.metadata,
                    document_id=result.document_id,
                )
            )

        if cached_plans:
            self._cache_hits += 1
        else:
            self._cache_misses += 1

        return cached_plans

    async def invalidate_stale(self, ttl_days: int = 30) -> int:
        """Remove plans older than ttl_days. Returns count of removed items."""
        collection = self._pipeline.chroma_manager.get_or_create_collection(COLLECTION_NAME)
        all_docs = collection.get(include=["metadatas"])
        cutoff = time.time() - (ttl_days * 86400)

        stale_ids: list[str] = []
        for doc_id, meta in zip(all_docs["ids"], all_docs["metadatas"]):
            stored_at = float(meta.get("stored_at", time.time()))
            if stored_at < cutoff:
                stale_ids.append(doc_id)

        if stale_ids:
            collection.delete(ids=stale_ids)
            logger.info("plan_cache_invalidated", count=len(stale_ids), ttl_days=ttl_days)

        return len(stale_ids)

    def get_stats(self) -> PlanCacheStats:
        """Return current cache statistics."""
        hit_rate = (
            self._cache_hits / self._total_queries if self._total_queries > 0 else 0.0
        )
        avg_sim = (
            self._similarity_sum / self._total_queries if self._total_queries > 0 else 0.0
        )
        return PlanCacheStats(
            total_queries=self._total_queries,
            cache_hits=self._cache_hits,
            cache_misses=self._cache_misses,
            avg_similarity=avg_sim,
            hit_rate=hit_rate,
        )


__all__ = [
    "COLLECTION_NAME",
    "CacheMatchTier",
    "CachedPlan",
    "PlanCache",
    "PlanCacheStats",
]
