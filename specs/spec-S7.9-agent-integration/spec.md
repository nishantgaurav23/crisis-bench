# Spec S7.9 — End-to-End Agent Pipeline Integration Test

## Status
spec-written

## Summary
Integration tests that validate the full multi-agent pipeline: SACHET alert ingestion → Orchestrator decomposition → parallel specialist agent execution → synthesis → bilingual briefing → WebSocket dashboard update. All external services mocked.

## Depends On
- S7.2 (Orchestrator agent) — done
- S7.3 (SituationSense agent) — done
- S7.4 (PredictiveRisk agent) — done
- S7.5 (ResourceAllocation agent) — done
- S7.6 (CommunityComms agent) — done
- S7.7 (InfraStatus agent) — done
- S7.8 (HistoricalMemory agent) — done
- S3.2 (WebSocket server) — done

## Location
- `tests/integration/test_agent_pipeline.py`

## Outcomes

### O1: Full Pipeline Smoke Test
- SACHET CAP alert → Orchestrator receives mission → decomposes into sub-tasks → delegates to specialist agents → collects results → synthesizes briefing
- Mocked LLM returns realistic JSON for each agent
- All 7 agents (Orchestrator + 6 specialists) participate
- Pipeline completes without exceptions

### O2: Phase-Based Agent Activation
- PRE_EVENT phase only activates SituationSense, PredictiveRisk, HistoricalMemory
- ACTIVE_RESPONSE phase activates all 6 specialists
- RECOVERY phase excludes SituationSense and PredictiveRisk
- Sub-tasks are correctly filtered by phase

### O3: Orchestrator → Agent → Result Flow
- Orchestrator sends A2ATask to each specialist via A2A server
- Each specialist processes its task and returns A2ATaskResult
- Results are collected with timeout enforcement
- Failed/timed-out agents produce FAILED results (not exceptions)

### O4: Synthesis and Bilingual Briefing
- Orchestrator synthesizes all agent results into a structured briefing
- Briefing contains: situation_summary, risk_assessment, resource_plan, communication_directives
- Confidence-gated escalation: low confidence → needs_escalation = True
- Budget tracking across all LLM calls

### O5: WebSocket Dashboard Integration
- ConnectionManager broadcasts agent events
- Events include: agent status updates, disaster events, metrics
- Clients subscribed to "agents" channel receive agent updates
- Clients subscribed to "disasters" channel receive disaster events

### O6: Error Resilience
- Pipeline continues when one agent fails (graceful degradation)
- Timeout on slow agent produces FAILED result, not pipeline crash
- Invalid LLM JSON response → fallback handling, not exception
- Budget exceeded → orchestrator tracks and reports

### O7: Concurrent Agent Execution
- Multiple specialist agents can process tasks concurrently
- Results are correctly attributed to their source agents
- No race conditions in result collection

## TDD Notes

### Test Structure
```
TestPipelineSmoke          — O1: Full pipeline end-to-end
TestPhaseActivation        — O2: Phase-based filtering
TestAgentTaskFlow          — O3: Task delegation + result collection
TestSynthesis              — O4: Briefing generation + escalation
TestWebSocketIntegration   — O5: Dashboard event broadcasting
TestErrorResilience        — O6: Failure handling + degradation
TestConcurrency            — O7: Parallel execution safety
```

### Mocking Strategy
- All LLM calls mocked via `router.call` — returns realistic JSON per agent type
- A2A server/client mocked — in-memory message passing
- WebSocket — use httpx/starlette test client for WebSocket testing
- ChromaDB, Neo4j, PostgreSQL — not needed (agents mock their data layer)
- No real Redis — mock A2A transport layer

### Key Test Data
- **SACHET Alert**: Category 4 cyclone (VSCS) approaching Odisha coast
- **IMD Warning**: Red alert for Puri, Ganjam, Khordha districts
- **Expected agents**: All 6 specialists (active_response phase)
- **Expected briefing**: Bilingual (English + Odia) evacuation directive

## Technical Notes
- All tests use `pytest-asyncio` with `@pytest.mark.asyncio`
- Agent initialization uses test settings (short timeouts, $0 budget limit)
- No Docker services required — pure Python mocks
- Tests should complete in <5 seconds total
