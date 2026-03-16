# Checklist — S7.4 PredictiveRisk Agent

## Phase 1: Red (Write Failing Tests)
- [x] Write test_predictive_risk.py with all test groups
- [x] Tests for initialization (agent type, tier, system prompt, agent card)
- [x] Tests for state machine structure (6 nodes, compilation)
- [x] Tests for cyclone classification (all 7 IMD categories + boundaries)
- [x] Tests for cascading failure chains (India-specific disaster types)
- [x] Tests for historical retrieval (RAG with mocked ChromaDB)
- [x] Tests for multi-horizon forecasting (1h/6h/24h/72h)
- [x] Tests for risk map generation (GeoJSON output)
- [x] Tests for edge cases (empty data, ChromaDB unavailable, malformed input)
- [x] Confirm all tests FAIL (no implementation yet)

## Phase 2: Green (Implement to Pass Tests)
- [x] Create PredictiveRiskState extending AgentState
- [x] Implement classify_cyclone() function
- [x] Implement get_cascade_chain() function
- [x] Implement PredictiveRisk class with __init__
- [x] Implement get_system_prompt()
- [x] Implement get_agent_card()
- [x] Implement build_graph() with 6 nodes
- [x] Implement _ingest_data node
- [x] Implement _retrieve_historical node (ChromaDB RAG)
- [x] Implement _forecast_risk node (LLM call)
- [x] Implement _predict_cascading node (LLM call)
- [x] Implement _generate_risk_map node (LLM call)
- [x] Implement _produce_report node
- [x] All tests pass

## Phase 3: Refactor
- [x] Run ruff lint — fix any issues
- [x] Verify all tests still pass after cleanup
- [x] Update roadmap.md status to done
