"""Tests for HistoricalMemory agent — RAG knowledge retrieval + post-event learning.

Tests cover: initialization, state machine structure, query parsing,
RAG retrieval, response synthesis, post-event learning ingestion,
and edge cases. All external services (LLM, Redis, ChromaDB) are mocked.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.historical_memory import (
    HistoricalMemory,
    HistoricalMemoryState,
)
from src.protocols.a2a.schemas import A2AAgentCard
from src.routing.llm_router import LLMResponse, LLMTier
from src.shared.config import CrisisSettings
from src.shared.models import AgentType

# =============================================================================
# Helpers
# =============================================================================


def _make_settings(**overrides) -> CrisisSettings:
    defaults = dict(
        DEEPSEEK_API_KEY="",
        QWEN_API_KEY="",
        KIMI_API_KEY="",
        GROQ_API_KEY="",
        GOOGLE_API_KEY="",
        OLLAMA_HOST="http://localhost:11434",
        AGENT_TIMEOUT_SECONDS=10,
        AGENT_MAX_DELEGATION_DEPTH=5,
        _env_file=None,
    )
    defaults.update(overrides)
    return CrisisSettings(**defaults)


def _make_llm_response(content: str = "test output", **kw) -> LLMResponse:
    defaults = dict(
        content=content,
        provider="ollama_local",
        model="qwen2.5:7b",
        input_tokens=10,
        output_tokens=5,
        cost_usd=0.0,
        latency_s=0.1,
        tier="standard",
    )
    defaults.update(kw)
    return LLMResponse(**defaults)


def _mock_similarity_results(n: int = 3) -> list:
    """Create mock SimilarityResult-like dicts for patching."""
    from src.data.ingest.embeddings import SimilarityResult

    results = []
    for i in range(n):
        results.append(
            SimilarityResult(
                text=f"NDMA guideline chunk {i}: Standard evacuation procedure "
                f"for cyclone-prone districts includes pre-positioning of NDRF.",
                score=0.95 - i * 0.1,
                metadata={
                    "document_id": f"doc_{i}",
                    "category": "guidelines",
                    "disaster_type": "cyclone",
                    "source_filename": f"ndma_cyclone_guide_{i}.pdf",
                },
                document_id=f"doc_{i}",
            )
        )
    return results


def _guideline_query_payload() -> dict:
    """Task payload for a guideline lookup query."""
    return {
        "query_type": "guideline_lookup",
        "query": "What are the NDMA evacuation procedures for cyclone-prone districts?",
        "disaster_type": "cyclone",
        "state": "Odisha",
    }


def _historical_search_payload() -> dict:
    """Task payload for a historical disaster search."""
    return {
        "query_type": "historical_search",
        "query": "Find similar past disasters to Cyclone Fani 2019",
        "disaster_type": "cyclone",
        "state": "Odisha",
    }


def _post_event_payload() -> dict:
    """Task payload for post-event learning ingestion."""
    return {
        "query_type": "post_event_learning",
        "scenario_id": "test-scenario-001",
        "disaster_type": "cyclone",
        "state": "Odisha",
        "learnings": [
            {
                "decision": "Evacuated 50,000 people from coastal villages in 24h",
                "outcome": "Zero casualties in evacuated areas",
                "lesson": "Early evacuation with community-level drills is effective",
            },
            {
                "decision": "Pre-positioned NDRF battalions 48h before landfall",
                "outcome": "Response time reduced by 60%",
                "lesson": "Pre-positioning based on IMD 72h forecast improves response",
            },
        ],
    }


def _empty_initial_state(agent, task: dict | None = None) -> HistoricalMemoryState:
    """Build an empty initial state for the agent."""
    return {
        "task": task or {},
        "disaster_id": None,
        "trace_id": "test-trace-001",
        "messages": [],
        "reasoning": "",
        "confidence": 0.0,
        "artifacts": [],
        "error": None,
        "iteration": 0,
        "metadata": {},
        "query_type": "",
        "query_text": "",
        "disaster_type": "",
        "state_filter": "",
        "retrieved_chunks": [],
        "synthesis": "",
        "learnings_stored": 0,
    }


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def settings() -> CrisisSettings:
    return _make_settings()


@pytest.fixture
def mock_router():
    router = AsyncMock()
    synthesis_json = json.dumps({
        "recommendations": [
            "Follow NDMA cyclone evacuation SOP: 48h advance warning, "
            "community-level drills, NDRF pre-positioning",
            "Reference Cyclone Fani 2019: Odisha evacuated 1.2M in 48h with "
            "zero casualties using door-to-door verification",
        ],
        "historical_analogies": [
            {
                "event": "Cyclone Fani 2019",
                "similarity_score": 0.89,
                "key_metric": "1.2M evacuated in 48h",
            }
        ],
        "confidence": 0.85,
    })
    learning_json = json.dumps({
        "extracted_learnings": 2,
        "summary": "Captured evacuation and pre-positioning learnings from scenario",
    })
    router.call = AsyncMock(
        side_effect=[
            _make_llm_response(synthesis_json),
            _make_llm_response(learning_json),
        ]
    )
    return router


@pytest.fixture
def mock_a2a_client():
    client = AsyncMock()
    client.start = AsyncMock()
    client.stop = AsyncMock()
    client.send_result = AsyncMock(return_value="msg-123")
    client.on_message = MagicMock()
    return client


@pytest.fixture
def mock_a2a_server():
    server = AsyncMock()
    server.register_agent_card = AsyncMock(return_value="msg-card")
    return server


@pytest.fixture
def mock_pipeline():
    pipeline = AsyncMock()
    pipeline.query_similar = AsyncMock(return_value=_mock_similarity_results())
    pipeline.embed_and_store = AsyncMock(return_value=2)
    return pipeline


@pytest.fixture
def agent(settings, mock_router, mock_a2a_client, mock_a2a_server, mock_pipeline):
    a = HistoricalMemory(settings=settings)
    a._router = mock_router
    a._a2a_client = mock_a2a_client
    a._a2a_server = mock_a2a_server
    a._pipeline = mock_pipeline
    return a


# =============================================================================
# Test Group 1: Initialization
# =============================================================================


class TestInitialization:
    def test_creates_with_correct_type(self, agent):
        """HistoricalMemory must use AgentType.HISTORICAL_MEMORY."""
        assert agent.agent_type == AgentType.HISTORICAL_MEMORY

    def test_default_tier_is_standard(self, agent):
        """HistoricalMemory operates on the standard (DeepSeek Chat) tier."""
        assert agent.llm_tier == LLMTier.STANDARD

    def test_system_prompt_contains_rag_context(self, agent):
        """System prompt must reference RAG, NDMA, and historical disasters."""
        prompt = agent.get_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 50
        prompt_lower = prompt.lower()
        assert "ndma" in prompt_lower
        assert "historical" in prompt_lower or "history" in prompt_lower
        assert "rag" in prompt_lower or "retrieval" in prompt_lower or "knowledge" in prompt_lower

    def test_agent_card_has_capabilities(self, agent):
        """Agent card must declare RAG and historical search capabilities."""
        card = agent.get_agent_card()
        assert isinstance(card, A2AAgentCard)
        assert card.agent_type == AgentType.HISTORICAL_MEMORY
        assert len(card.capabilities) >= 3
        caps_text = " ".join(card.capabilities).lower()
        assert "rag" in caps_text or "retrieval" in caps_text or "knowledge" in caps_text
        assert "historical" in caps_text or "history" in caps_text

    def test_agent_id(self, agent):
        """Agent ID must be 'historical_memory'."""
        assert agent.agent_id == "historical_memory"


# =============================================================================
# Test Group 2: State Machine Structure
# =============================================================================


class TestStateMachine:
    def test_build_graph_has_all_nodes(self, agent):
        """Graph must contain receive_query, retrieve_context, synthesize, ingest nodes."""
        graph = agent.build_graph()
        node_names = set(graph.nodes.keys())
        expected = {
            "receive_query",
            "retrieve_context",
            "synthesize_response",
            "ingest_learning",
        }
        assert expected.issubset(node_names), (
            f"Missing nodes: {expected - node_names}"
        )

    def test_graph_compiles(self, agent):
        """Graph must compile without errors."""
        graph = agent.build_graph()
        compiled = graph.compile()
        assert compiled is not None

    @pytest.mark.asyncio
    async def test_graph_runs_guideline_query(self, agent):
        """Full pipeline should execute for a guideline lookup query."""
        state = _empty_initial_state(agent, _guideline_query_payload())
        result = await agent.run_graph(state)
        assert result is not None
        assert result.get("synthesis")
        assert result.get("confidence", 0) > 0

    @pytest.mark.asyncio
    async def test_graph_runs_historical_search(self, agent):
        """Full pipeline should execute for a historical search query."""
        state = _empty_initial_state(agent, _historical_search_payload())
        result = await agent.run_graph(state)
        assert result is not None
        assert result.get("synthesis")


# =============================================================================
# Test Group 3: Query Parsing
# =============================================================================


class TestQueryParsing:
    @pytest.mark.asyncio
    async def test_parses_guideline_query_type(self, agent):
        """receive_query should extract query_type from task payload."""
        state = _empty_initial_state(agent, _guideline_query_payload())
        result = await agent._receive_query(state)
        assert result["query_type"] == "guideline_lookup"
        assert result["query_text"] != ""

    @pytest.mark.asyncio
    async def test_parses_historical_search_type(self, agent):
        """receive_query should extract historical_search type."""
        state = _empty_initial_state(agent, _historical_search_payload())
        result = await agent._receive_query(state)
        assert result["query_type"] == "historical_search"

    @pytest.mark.asyncio
    async def test_parses_post_event_type(self, agent):
        """receive_query should extract post_event_learning type."""
        state = _empty_initial_state(agent, _post_event_payload())
        result = await agent._receive_query(state)
        assert result["query_type"] == "post_event_learning"

    @pytest.mark.asyncio
    async def test_defaults_to_guideline_on_unknown(self, agent):
        """Unknown query_type should default to guideline_lookup."""
        state = _empty_initial_state(agent, {"query": "some question"})
        result = await agent._receive_query(state)
        assert result["query_type"] == "guideline_lookup"

    @pytest.mark.asyncio
    async def test_extracts_disaster_type_filter(self, agent):
        """receive_query should extract disaster_type for filtering."""
        state = _empty_initial_state(agent, _guideline_query_payload())
        result = await agent._receive_query(state)
        assert result["disaster_type"] == "cyclone"

    @pytest.mark.asyncio
    async def test_extracts_state_filter(self, agent):
        """receive_query should extract state for filtering."""
        state = _empty_initial_state(agent, _guideline_query_payload())
        result = await agent._receive_query(state)
        assert result["state_filter"] == "Odisha"


# =============================================================================
# Test Group 4: RAG Retrieval
# =============================================================================


class TestRAGRetrieval:
    @pytest.mark.asyncio
    async def test_queries_chromadb_for_guidelines(self, agent, mock_pipeline):
        """retrieve_context should call query_similar on relevant collections."""
        state = _empty_initial_state(agent, _guideline_query_payload())
        state["query_type"] = "guideline_lookup"
        state["query_text"] = "cyclone evacuation procedures"
        state["disaster_type"] = "cyclone"
        state["state_filter"] = "Odisha"

        result = await agent._retrieve_context(state)
        mock_pipeline.query_similar.assert_called()
        assert len(result.get("retrieved_chunks", [])) > 0

    @pytest.mark.asyncio
    async def test_queries_historical_events_collection(self, agent, mock_pipeline):
        """Historical search should query the historical_events collection."""
        state = _empty_initial_state(agent, _historical_search_payload())
        state["query_type"] = "historical_search"
        state["query_text"] = "Cyclone Fani 2019"
        state["disaster_type"] = "cyclone"
        state["state_filter"] = "Odisha"

        await agent._retrieve_context(state)
        # Should have queried historical_events
        call_args_list = mock_pipeline.query_similar.call_args_list
        collections_queried = [call.args[0] for call in call_args_list]
        assert "historical_events" in collections_queried

    @pytest.mark.asyncio
    async def test_handles_empty_retrieval(self, agent, mock_pipeline):
        """Should handle empty results from ChromaDB gracefully."""
        mock_pipeline.query_similar = AsyncMock(return_value=[])
        state = _empty_initial_state(agent, _guideline_query_payload())
        state["query_type"] = "guideline_lookup"
        state["query_text"] = "nonexistent topic"
        state["disaster_type"] = ""
        state["state_filter"] = ""

        result = await agent._retrieve_context(state)
        assert result.get("retrieved_chunks") == []

    @pytest.mark.asyncio
    async def test_retrieval_returns_scored_chunks(self, agent, mock_pipeline):
        """Retrieved chunks should include text and similarity scores."""
        state = _empty_initial_state(agent, _guideline_query_payload())
        state["query_type"] = "guideline_lookup"
        state["query_text"] = "cyclone evacuation"
        state["disaster_type"] = "cyclone"
        state["state_filter"] = ""

        result = await agent._retrieve_context(state)
        chunks = result.get("retrieved_chunks", [])
        assert len(chunks) > 0
        assert "text" in chunks[0]
        assert "score" in chunks[0]


# =============================================================================
# Test Group 5: Response Synthesis
# =============================================================================


class TestResponseSynthesis:
    @pytest.mark.asyncio
    async def test_synthesizes_from_retrieved_context(self, agent):
        """synthesize_response should use LLM to combine retrieved chunks."""
        state = _empty_initial_state(agent, _guideline_query_payload())
        state["query_type"] = "guideline_lookup"
        state["query_text"] = "cyclone evacuation procedures"
        state["retrieved_chunks"] = [
            {"text": "NDMA cyclone SOP: evacuate within 48h", "score": 0.95,
             "collection": "ndma_sops", "metadata": {}, "document_id": "d1"},
            {"text": "Pre-position NDRF battalions before landfall", "score": 0.88,
             "collection": "ndma_guidelines", "metadata": {}, "document_id": "d2"},
        ]

        result = await agent._synthesize_response(state)
        assert result.get("synthesis") != ""
        assert result.get("confidence", 0) > 0
        assert len(result.get("artifacts", [])) > 0

    @pytest.mark.asyncio
    async def test_confidence_scales_with_retrieval_quality(self, agent):
        """Higher retrieval scores should produce higher confidence."""
        state = _empty_initial_state(agent, _guideline_query_payload())
        state["query_type"] = "guideline_lookup"
        state["query_text"] = "cyclone evacuation"
        state["retrieved_chunks"] = [
            {"text": "Highly relevant NDMA procedure", "score": 0.98,
             "collection": "ndma_guidelines", "metadata": {}, "document_id": "d1"},
            {"text": "Another relevant chunk", "score": 0.95,
             "collection": "ndma_sops", "metadata": {}, "document_id": "d2"},
        ]

        result = await agent._synthesize_response(state)
        assert result.get("confidence", 0) >= 0.7

    @pytest.mark.asyncio
    async def test_low_confidence_on_no_chunks(self, agent):
        """No retrieved chunks should produce low confidence."""
        state = _empty_initial_state(agent, _guideline_query_payload())
        state["query_type"] = "guideline_lookup"
        state["query_text"] = "irrelevant query"
        state["retrieved_chunks"] = []

        result = await agent._synthesize_response(state)
        assert result.get("confidence", 1.0) <= 0.3


# =============================================================================
# Test Group 6: Post-Event Learning Ingestion
# =============================================================================


class TestPostEventLearning:
    @pytest.mark.asyncio
    async def test_ingests_learnings_into_chromadb(self, agent, mock_pipeline):
        """ingest_learning should call embed_and_store with extracted learnings."""
        state = _empty_initial_state(agent, _post_event_payload())
        state["query_type"] = "post_event_learning"
        state["query_text"] = ""
        task = _post_event_payload()
        state["task"] = task

        result = await agent._ingest_learning(state)
        mock_pipeline.embed_and_store.assert_called_once()
        assert result.get("learnings_stored", 0) > 0

    @pytest.mark.asyncio
    async def test_stores_in_historical_events_collection(self, agent, mock_pipeline):
        """Learnings should be stored in the historical_events collection."""
        state = _empty_initial_state(agent, _post_event_payload())
        state["query_type"] = "post_event_learning"
        state["task"] = _post_event_payload()

        await agent._ingest_learning(state)
        call_args = mock_pipeline.embed_and_store.call_args
        assert call_args.kwargs.get("collection_name") == "historical_events" or \
            call_args.args[0] == "historical_events"

    @pytest.mark.asyncio
    async def test_handles_empty_learnings(self, agent, mock_pipeline):
        """Should handle task with no learnings gracefully."""
        state = _empty_initial_state(agent, {
            "query_type": "post_event_learning",
            "learnings": [],
        })
        state["query_type"] = "post_event_learning"
        state["task"] = {"query_type": "post_event_learning", "learnings": []}

        result = await agent._ingest_learning(state)
        assert result.get("learnings_stored", 0) == 0

    @pytest.mark.asyncio
    async def test_full_post_event_pipeline(self, agent, mock_pipeline):
        """End-to-end test: post-event query should route through ingest_learning."""
        # Reset the router side_effect for post-event path (only synthesize is called)
        synthesis_json = json.dumps({
            "recommendations": ["Learning captured successfully"],
            "confidence": 0.9,
        })
        agent._router.call = AsyncMock(
            return_value=_make_llm_response(synthesis_json)
        )

        state = _empty_initial_state(agent, _post_event_payload())
        result = await agent.run_graph(state)
        assert result is not None
        assert result.get("learnings_stored", 0) > 0


# =============================================================================
# Test Group 7: Edge Cases
# =============================================================================


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_handles_empty_task_payload(self, agent):
        """Agent should not crash with empty task payload."""
        state = _empty_initial_state(agent, {})
        result = await agent.run_graph(state)
        assert result is not None

    @pytest.mark.asyncio
    async def test_handles_missing_query_field(self, agent):
        """Agent should handle task with no 'query' field."""
        state = _empty_initial_state(agent, {"query_type": "guideline_lookup"})
        result = await agent.run_graph(state)
        assert result is not None

    @pytest.mark.asyncio
    async def test_handles_chromadb_returning_none_metadata(self, agent, mock_pipeline):
        """Should handle chunks with None metadata."""
        from src.data.ingest.embeddings import SimilarityResult

        mock_pipeline.query_similar = AsyncMock(return_value=[
            SimilarityResult(
                text="Some chunk",
                score=0.8,
                metadata={},
                document_id="doc_x",
            ),
        ])
        state = _empty_initial_state(agent, _guideline_query_payload())
        state["query_type"] = "guideline_lookup"
        state["query_text"] = "test query"
        state["disaster_type"] = ""
        state["state_filter"] = ""

        result = await agent._retrieve_context(state)
        # Returns 1 result per collection queried (4 guideline collections)
        assert len(result.get("retrieved_chunks", [])) >= 1

    @pytest.mark.asyncio
    async def test_agent_health_check(self, agent):
        """Health check should return valid data."""
        health = agent.health()
        assert health["agent_id"] == "historical_memory"
        assert health["agent_type"] == "historical_memory"
        assert health["llm_tier"] == "standard"
