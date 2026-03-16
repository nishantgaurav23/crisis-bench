# Spec S7.4 — PredictiveRisk Agent

**Status**: spec-written
**Phase**: 7 (Agent System)
**Depends On**: S7.1 (BaseAgent), S6.1 (ChromaDB setup), S6.4 (IMD historical data)
**Location**: `src/agents/predictive_risk.py`
**Test**: `tests/unit/test_predictive_risk.py`

---

## Overview

The PredictiveRisk agent forecasts disaster evolution, predicts cascading failures specific to Indian infrastructure, generates probabilistic risk maps, and retrieves historical analogies via RAG over ChromaDB. Operates on the **standard** tier (DeepSeek Chat, $0.28/M tokens) for reasoning-intensive forecasting tasks.

## Requirements (from FR-003)

1. **FR-003.1** — Run forecasting using IMD gridded data (via `src/data/ingest/imd.py` queries) + real-time IMD API observations
2. **FR-003.2** — Predict India-specific cascading failures: cyclone → storm surge → dam overtopping → downstream flooding → infrastructure failure
3. **FR-003.3** — Generate probabilistic risk maps using Bhuvan admin boundaries + Census 2011 vulnerability data
4. **FR-003.4** — RAG retrieval over historical Indian disaster database to find analogous past events (e.g., "Similar to Cyclone Phailin 2013 trajectory")
5. **FR-003.5** — Track IMD cyclone classification progression (D → DD → CS → SCS → VSCS → ESCS → SuCS) with predicted timeline
6. **FR-003.6** — Time-horizon forecasts: 1h, 6h, 24h, 72h windows aligned with IMD bulletin cycles

## Architecture

### LangGraph State Machine

```
ingest_data -> retrieve_historical -> forecast_risk -> predict_cascading -> generate_risk_map -> produce_report
```

### Extended State (PredictiveRiskState)

Extends `AgentState` with:
- `weather_data: list[dict]` — Current IMD weather observations
- `historical_analogies: list[dict]` — RAG-retrieved historical events
- `forecast: dict` — Multi-horizon forecast (1h/6h/24h/72h)
- `cascading_failures: list[dict]` — Predicted cascading failure chains
- `risk_map: dict` — Probabilistic risk map (GeoJSON)
- `cyclone_tracking: dict` — IMD classification progression
- `time_horizons: list[str]` — Forecast windows

### Agent Configuration

| Property | Value |
|----------|-------|
| agent_id | `predictive_risk` |
| agent_type | `AgentType.PREDICTIVE_RISK` |
| llm_tier | `LLMTier.STANDARD` (DeepSeek Chat) |
| Capabilities | forecasting, cascading_failure_prediction, risk_mapping, historical_analogy, cyclone_tracking |

## LangGraph Nodes

### 1. `ingest_data`
- Extract weather data, disaster context, affected regions from task payload
- Parse IMD cyclone classification if present (D/DD/CS/SCS/VSCS/ESCS/SuCS)
- No LLM call — pure data extraction

### 2. `retrieve_historical`
- Use ChromaDB `EmbeddingPipeline.query_similar()` on `historical_events` collection
- Query: disaster type + affected region + severity
- Return top-5 analogous historical events with similarity scores
- Graceful degradation: if ChromaDB unavailable, continue with empty analogies

### 3. `forecast_risk`
- LLM call (standard tier) to generate multi-horizon forecasts
- Input: weather data + historical analogies + disaster context
- Output: structured JSON with 1h/6h/24h/72h predictions
- Include cyclone track progression if applicable

### 4. `predict_cascading`
- LLM call (standard tier) to predict cascading failure chains
- India-specific chains: cyclone → storm surge → dam overtopping → flooding → infra failure
- Output: ordered list of failure events with probability and timeline

### 5. `generate_risk_map`
- LLM call (standard tier) to generate GeoJSON risk map
- Features include affected areas with risk levels (low/medium/high/critical)
- Properties include: population_at_risk, vulnerability_index, risk_level

### 6. `produce_report`
- Compile all results into final artifacts
- Calculate confidence based on data quality + historical match quality
- No LLM call — pure aggregation

## IMD Cyclone Classification

The agent must understand and track the Indian cyclone classification scale:

| Code | Name | Wind Speed (kt) |
|------|------|-----------------|
| D | Depression | 17-27 |
| DD | Deep Depression | 28-33 |
| CS | Cyclonic Storm | 34-47 |
| SCS | Severe Cyclonic Storm | 48-63 |
| VSCS | Very Severe Cyclonic Storm | 64-89 |
| ESCS | Extremely Severe Cyclonic Storm | 90-119 |
| SuCS | Super Cyclonic Storm | ≥120 |

## Key Functions (Public API)

- `classify_cyclone(wind_speed_kt: float) -> str` — Map wind speed to IMD classification
- `get_cascade_chain(disaster_type: str) -> list[str]` — Return expected cascade for disaster type

## Outcomes

1. `PredictiveRisk` class extends `BaseAgent` with all abstract methods implemented
2. LangGraph with 6 nodes executes end-to-end with mocked LLM + ChromaDB
3. `classify_cyclone()` correctly maps all 7 IMD categories
4. `get_cascade_chain()` returns India-specific cascading failure chains
5. RAG retrieval gracefully degrades when ChromaDB is unavailable
6. Multi-horizon forecasts produce structured JSON for 1h/6h/24h/72h
7. All tests pass with mocked external services

## TDD Notes

- Mock LLM router for all LLM calls (return structured JSON)
- Mock ChromaDB / EmbeddingPipeline for RAG queries
- Test cyclone classification with boundary values
- Test cascading failure chains for all India disaster types
- Test graceful degradation when historical data is empty
- Test confidence calculation varies with data quality
