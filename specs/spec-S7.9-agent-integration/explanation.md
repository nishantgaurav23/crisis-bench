# Spec S7.9 — End-to-End Agent Pipeline Integration Test

## Why This Spec Exists

S7.9 is the capstone of Phase 7 (Agent System). After implementing all 7 specialist agents individually (S7.1-S7.8), this spec validates that the full multi-agent pipeline works end-to-end: from a SACHET CAP alert arriving to a synthesized bilingual briefing being produced and broadcast to the dashboard via WebSocket.

Without integration tests, individual agents could pass their unit tests while the pipeline fails due to:
- Incompatible state shapes between agents
- Trace ID validation failures across A2A boundaries
- Phase-based agent activation filtering bugs
- Concurrent execution race conditions
- WebSocket channel routing mismatches

## What It Does

38 integration tests across 8 test groups:

1. **Pipeline Smoke Tests (3)** — Full orchestrator graph: parse → decompose → delegate → collect → synthesize. Validates the complete flow produces a structured briefing with all required sections and tracks budget correctly.

2. **Phase-Based Activation (5)** — Verifies agents are correctly activated/filtered per disaster phase (PRE_EVENT, ACTIVE_RESPONSE, RECOVERY). Ensures the orchestrator's decomposition respects phase constraints.

3. **Agent Task Flow (4)** — Tests A2A task delegation (depth incrementing, multi-agent dispatch) and result collection with timeouts (FAILED status for missing results).

4. **Synthesis & Briefing (4)** — Validates structured briefing generation, confidence-gated escalation (< 0.7 triggers escalation), and multi-agent result aggregation.

5. **WebSocket Integration (6)** — Channel-based event routing (agents/disasters/metrics), multi-client broadcasting, client disconnect handling.

6. **Error Resilience (6)** — Invalid JSON from LLM returns fallback (not exception), budget tracking across calls, empty results handled, disconnected WebSocket clients don't crash broadcasts.

7. **Concurrency (3)** — Three agent graphs (SituationSense, PredictiveRisk, ResourceAllocation) run concurrently via `asyncio.gather` without interference. Result attribution verified.

8. **Agent Initialization (7)** — All 7 agents have correct IDs, system prompts, agent cards, buildable graphs, proper LLM tiers, and working health checks.

## How It Works

### Mocking Strategy
- **LLM Router**: Each agent's `_router.call` is an `AsyncMock` returning realistic JSON per agent type (e.g., SituationSense gets fused situation data, ResourceAllocation gets optimization results)
- **A2A Protocol**: Both `_a2a_client` and `_a2a_server` are fully mocked — no Redis needed
- **External Data**: ChromaDB embedding pipeline and Neo4j graph manager are mocked on agents that use them (PredictiveRisk, HistoricalMemory, InfraStatus)
- **WebSocket**: `ConnectionManager` tested with mock WebSocket objects (AsyncMock with `accept`/`send_json`)

### Key Design Decision: Hex Trace IDs
A2ATask validates trace_id must be 8 hex characters (`^[0-9a-f]{8}$`). All test trace IDs use the format `aa000001`, `bb000002`, etc. to comply with this validation while remaining human-readable in test output.

### Concurrent Test Data
The concurrent agent execution test provides structured task payloads with dict-based `affected_districts` (not string lists) because ResourceAllocation's `_assess_demand` calls `.get()` on each district entry.

## How It Connects

### Upstream Dependencies
- **S7.1 (BaseAgent)**: All agents inherit `BaseAgent.run_graph()`, `reason()`, `handle_task()` — integration tests exercise the full graph execution path
- **S7.2-S7.8 (All Agents)**: Each specialist agent is instantiated and its graph validated
- **S3.2 (WebSocket)**: `ConnectionManager` tested for channel routing and broadcasting
- **S4.1-S4.3 (A2A)**: `A2ATask` and `A2ATaskResult` schemas validated via delegation flow

### Downstream Dependents
- **S8.3 (Scenario Runner)**: Depends on S7.9 — the benchmark runner drives the agent pipeline with simulated scenarios
- **S9.1 (Plan Caching)**: Depends on S7.9 — caches the orchestrator's synthesis output
- **S9.2 (Dashboard Integration)**: Depends on S7.9 — live agent data flows through the tested WebSocket channels

## Interview Talking Points

**Q: Why integration tests when you already have unit tests?**
A: Unit tests verify individual components in isolation. Integration tests verify the *interactions*. For example, the orchestrator unit tests mock everything; the integration tests verify that when the orchestrator delegates to SituationSense, the state shapes are compatible, trace IDs validate, and the graph actually runs. The concurrent execution test caught a real issue where `affected_districts` as strings (not dicts) crashed ResourceAllocation — unit tests wouldn't catch this because they use per-agent fixtures.

**Q: How do you test concurrent agent execution without real infrastructure?**
A: `asyncio.gather(*[run_agent(aid) for aid in agents], return_exceptions=True)` runs all agent graphs concurrently in the event loop. Each agent has its own mock router returning agent-specific JSON. Since LangGraph state machines are isolated (each has its own state dict), true parallelism works without shared state. We verify: no exceptions, correct result shapes, and proper agent attribution.

**Q: What does "graceful degradation" mean in practice?**
A: When one agent fails (timeout, LLM error, invalid response), the orchestrator doesn't crash — it marks that agent's result as FAILED and continues synthesis with partial results. The confidence drops, which may trigger escalation (human review). The integration tests verify this by: (1) running the full graph where collect always times out (no real agents), (2) testing invalid JSON returns fallback briefings, (3) testing empty result sets still produce a response.
