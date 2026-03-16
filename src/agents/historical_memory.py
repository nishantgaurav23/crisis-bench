"""HistoricalMemory agent — RAG knowledge retrieval + post-event learning (S7.8).

Provides RAG-based retrieval over NDMA guidelines, historical disaster records,
and past response patterns. Grounds other agents' decisions in validated procedures
and real Indian disaster history. Captures post-event learnings to continuously
evolve the knowledge base.

Runs on the **standard** tier (DeepSeek Chat, $0.28/M tokens).

LangGraph nodes:
    receive_query -> retrieve_context -> synthesize_response -> [conditional] -> END
                                                               |
                                                               v (post_event)
                                                         ingest_learning -> END

Usage::

    agent = HistoricalMemory()
    await agent.start()
"""

from __future__ import annotations

import json
from typing import Any

from langgraph.graph import END, StateGraph

from src.agents.base import AgentState, BaseAgent
from src.data.ingest.embeddings import EmbeddingPipeline, SimilarityResult
from src.protocols.a2a.schemas import A2AAgentCard
from src.routing.llm_router import LLMTier
from src.shared.models import AgentType
from src.shared.telemetry import get_logger

logger = get_logger("agent.historical_memory")

# =============================================================================
# Collections to query per query type
# =============================================================================

_GUIDELINE_COLLECTIONS = [
    "ndma_guidelines",
    "ndma_sops",
    "state_sdma_reports",
    "ndma_annual",
]

_HISTORICAL_COLLECTIONS = [
    "historical_events",
    "ndma_guidelines",
]

_ALL_COLLECTIONS = [
    "ndma_guidelines",
    "ndma_sops",
    "state_sdma_reports",
    "ndma_annual",
    "historical_events",
]

VALID_QUERY_TYPES = {"guideline_lookup", "historical_search", "post_event_learning"}

# =============================================================================
# State
# =============================================================================


class HistoricalMemoryState(AgentState):
    """Extended state for HistoricalMemory agent."""

    query_type: str
    query_text: str
    disaster_type: str
    state_filter: str
    retrieved_chunks: list[dict]
    synthesis: str
    learnings_stored: int


# =============================================================================
# HistoricalMemory Agent
# =============================================================================


class HistoricalMemory(BaseAgent):
    """RAG knowledge retrieval agent for NDMA guidelines and historical disasters.

    Queries ChromaDB collections for relevant context, synthesizes actionable
    recommendations using LLM, and ingests post-event learnings.
    """

    def __init__(self, *, settings=None, pipeline: EmbeddingPipeline | None = None) -> None:
        from src.shared.config import get_settings

        super().__init__(
            agent_id="historical_memory",
            agent_type=AgentType.HISTORICAL_MEMORY,
            llm_tier=LLMTier.STANDARD,
            settings=settings or get_settings(),
        )
        self._pipeline = pipeline or EmbeddingPipeline()

    def get_system_prompt(self) -> str:
        return (
            "You are the HistoricalMemory agent for India's CRISIS-BENCH disaster "
            "response system. Your role is to provide RAG-based knowledge retrieval "
            "from NDMA guidelines, historical disaster records, and past response "
            "patterns.\n\n"
            "Knowledge sources you query:\n"
            "- NDMA guidelines and SOPs (30+ documents covering floods, cyclones, "
            "earthquakes, heatwaves, chemical disasters, landslides)\n"
            "- State SDMA after-action reports\n"
            "- NDMA annual reports\n"
            "- Historical Indian disaster records (EM-DAT + state records)\n\n"
            "Your outputs:\n"
            "1. Relevant NDMA procedures and guidelines for the current situation\n"
            "2. Historical analogies with similarity scores (e.g., 'Similar to "
            "Cyclone Phailin 2013, score: 0.89')\n"
            "3. Past response metrics (e.g., 'Odisha evacuated 1.2M in 48h during "
            "Cyclone Fani 2019')\n"
            "4. Post-event learning capture for knowledge base evolution\n\n"
            "Notable Indian disaster learnings to reference:\n"
            "- Kerala 2018: Fishermen boat rescue operations\n"
            "- Mumbai 26/7 2005: Urban flood disaster response\n"
            "- Uttarakhand 2013: Flash flood management\n"
            "- Bhopal 1984: Industrial disaster response\n"
            "- Cyclone Fani 2019: Odisha's exemplary evacuation model\n\n"
            "Support queries in English and Hindi. Output structured JSON with "
            "recommendations and confidence scores."
        )

    def get_agent_card(self) -> A2AAgentCard:
        return A2AAgentCard(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            name="HistoricalMemory",
            description=(
                "RAG knowledge retrieval agent: NDMA guidelines, historical "
                "disasters, past response patterns, post-event learning"
            ),
            capabilities=[
                "rag_knowledge_retrieval",
                "historical_disaster_search",
                "past_decision_surfacing",
                "post_event_learning",
                "bilingual_query",
            ],
            llm_tier=self.llm_tier,
        )

    def build_graph(self) -> StateGraph:
        graph = StateGraph(HistoricalMemoryState)

        graph.add_node("receive_query", self._receive_query)
        graph.add_node("retrieve_context", self._retrieve_context)
        graph.add_node("synthesize_response", self._synthesize_response)
        graph.add_node("ingest_learning", self._ingest_learning)

        graph.set_entry_point("receive_query")
        graph.add_edge("receive_query", "retrieve_context")
        graph.add_edge("retrieve_context", "synthesize_response")
        graph.add_conditional_edges(
            "synthesize_response",
            self._route_after_synthesis,
            {"ingest_learning": "ingest_learning", "end": END},
        )
        graph.add_edge("ingest_learning", END)

        return graph

    # -----------------------------------------------------------------
    # Routing
    # -----------------------------------------------------------------

    def _route_after_synthesis(self, state: HistoricalMemoryState) -> str:
        """Route to ingest_learning if post-event, otherwise end."""
        if state.get("query_type") == "post_event_learning":
            return "ingest_learning"
        return "end"

    # -----------------------------------------------------------------
    # Graph Nodes
    # -----------------------------------------------------------------

    async def _receive_query(self, state: HistoricalMemoryState) -> dict[str, Any]:
        """Parse task payload to determine query type, text, and filters."""
        task = state.get("task", {})
        query_type = task.get("query_type", "guideline_lookup")
        if query_type not in VALID_QUERY_TYPES:
            query_type = "guideline_lookup"

        query_text = task.get("query", "")
        disaster_type = task.get("disaster_type", "")
        state_filter = task.get("state", "")

        logger.info(
            "query_received",
            query_type=query_type,
            disaster_type=disaster_type,
            state_filter=state_filter,
            trace_id=state.get("trace_id", ""),
        )

        return {
            "query_type": query_type,
            "query_text": query_text,
            "disaster_type": disaster_type,
            "state_filter": state_filter,
        }

    async def _retrieve_context(self, state: HistoricalMemoryState) -> dict[str, Any]:
        """Query ChromaDB for relevant chunks across collections."""
        query_type = state.get("query_type", "guideline_lookup")
        query_text = state.get("query_text", "")

        if not query_text:
            return {"retrieved_chunks": []}

        # Select collections based on query type
        if query_type == "historical_search":
            collections = _HISTORICAL_COLLECTIONS
        elif query_type == "guideline_lookup":
            collections = _GUIDELINE_COLLECTIONS
        else:
            collections = _ALL_COLLECTIONS

        all_chunks: list[dict] = []
        for collection_name in collections:
            try:
                results: list[SimilarityResult] = await self._pipeline.query_similar(
                    collection_name, query_text, top_k=3
                )
                for r in results:
                    all_chunks.append({
                        "text": r.text,
                        "score": r.score,
                        "collection": collection_name,
                        "metadata": r.metadata,
                        "document_id": r.document_id,
                    })
            except Exception as exc:
                logger.warning(
                    "collection_query_failed",
                    collection=collection_name,
                    error=str(exc),
                    trace_id=state.get("trace_id", ""),
                )

        # Sort by score descending, take top results
        all_chunks.sort(key=lambda c: c["score"], reverse=True)
        top_chunks = all_chunks[:10]

        logger.info(
            "context_retrieved",
            total_chunks=len(all_chunks),
            top_chunks=len(top_chunks),
            collections_queried=len(collections),
            trace_id=state.get("trace_id", ""),
        )

        return {"retrieved_chunks": top_chunks}

    async def _synthesize_response(self, state: HistoricalMemoryState) -> dict[str, Any]:
        """Use LLM to synthesize retrieved chunks into recommendations."""
        query_text = state.get("query_text", "")
        retrieved_chunks = state.get("retrieved_chunks", [])
        query_type = state.get("query_type", "guideline_lookup")
        disaster_type = state.get("disaster_type", "")

        if not retrieved_chunks:
            return {
                "synthesis": "No relevant documents found in the knowledge base.",
                "confidence": 0.2,
                "reasoning": "No matching chunks retrieved from ChromaDB",
                "artifacts": [{
                    "type": "historical_memory_response",
                    "query_type": query_type,
                    "recommendations": [],
                    "chunks_used": 0,
                }],
            }

        # Build context from retrieved chunks
        context_parts = []
        for i, chunk in enumerate(retrieved_chunks[:5]):
            context_parts.append(
                f"[Source {i + 1}] (score: {chunk['score']:.2f}, "
                f"collection: {chunk['collection']})\n{chunk['text']}"
            )
        context_block = "\n\n".join(context_parts)

        prompt = (
            f"Based on the following retrieved NDMA guidelines and historical records, "
            f"provide actionable recommendations for: {query_text}\n\n"
            f"Disaster type: {disaster_type or 'general'}\n\n"
            f"Retrieved context:\n{context_block}\n\n"
            f"Output ONLY valid JSON with keys: recommendations (list of strings), "
            f"historical_analogies (list of objects with event, similarity_score, "
            f"key_metric), confidence (float 0-1)."
        )

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        resp = await self.reason(messages, trace_id=state.get("trace_id", ""))

        try:
            parsed = json.loads(resp.content)
        except (json.JSONDecodeError, TypeError):
            parsed = {"recommendations": [resp.content], "confidence": 0.5}

        # Confidence: blend LLM's reported confidence with retrieval quality
        llm_confidence = parsed.get("confidence", 0.5)
        avg_score = sum(c["score"] for c in retrieved_chunks) / len(retrieved_chunks)
        confidence = min(0.95, (llm_confidence * 0.6 + avg_score * 0.4))

        return {
            "synthesis": resp.content,
            "confidence": confidence,
            "reasoning": resp.content,
            "artifacts": [{
                "type": "historical_memory_response",
                "query_type": query_type,
                "recommendations": parsed.get("recommendations", []),
                "historical_analogies": parsed.get("historical_analogies", []),
                "chunks_used": len(retrieved_chunks),
                "avg_retrieval_score": round(avg_score, 3),
            }],
        }

    async def _ingest_learning(self, state: HistoricalMemoryState) -> dict[str, Any]:
        """Extract and store post-event learnings in historical_events collection."""
        task = state.get("task", {})
        learnings = task.get("learnings", [])

        if not learnings:
            return {"learnings_stored": 0}

        disaster_type = task.get("disaster_type", "general")
        scenario_id = task.get("scenario_id", "unknown")
        state_name = task.get("state", "")

        texts = []
        metadatas = []
        for learning in learnings:
            text = (
                f"Decision: {learning.get('decision', '')}\n"
                f"Outcome: {learning.get('outcome', '')}\n"
                f"Lesson: {learning.get('lesson', '')}"
            )
            texts.append(text)
            metadatas.append({
                "document_id": f"learning_{scenario_id}_{len(texts)}",
                "source": "post_event_learning",
                "disaster_type": disaster_type,
                "scenario_id": scenario_id,
                "state": state_name,
            })

        stored = await self._pipeline.embed_and_store(
            "historical_events", texts=texts, metadatas=metadatas
        )

        logger.info(
            "learnings_ingested",
            count=stored,
            scenario_id=scenario_id,
            trace_id=state.get("trace_id", ""),
        )

        return {"learnings_stored": stored}


__all__ = ["HistoricalMemory", "HistoricalMemoryState"]
