# Explanation — S7.4 PredictiveRisk Agent

## Why This Spec Exists

The PredictiveRisk agent is the system's "crystal ball" — it forecasts how a disaster will evolve over time and predicts cascading failures specific to Indian infrastructure. Without prediction, the system can only react; with it, responders get 1h/6h/24h/72h advance warning aligned with IMD bulletin cycles. This agent transforms raw weather data into actionable risk intelligence.

## What It Does

### Core Capabilities
1. **Multi-horizon forecasting** — Produces structured risk predictions at 1h, 6h, 24h, and 72h windows, aligned with how IMD issues bulletins
2. **India-specific cascading failure prediction** — Models failure chains like: cyclone → storm surge → dam overtopping → downstream flooding → power grid failure → telecom backup exhaustion (4-8h) → communication blackout
3. **Probabilistic risk maps** — Generates GeoJSON FeatureCollections with risk levels (low/medium/high/critical), population at risk, and vulnerability indices
4. **Historical analogy retrieval** — Uses RAG over ChromaDB `historical_events` collection to find past disasters similar to the current one (e.g., "Similar to Mumbai floods 2005")
5. **IMD cyclone classification tracking** — Maps wind speeds to the 7-level IMD scale: D → DD → CS → SCS → VSCS → ESCS → SuCS

### Key Functions
- `classify_cyclone(wind_speed_kt)` — Pure function mapping wind speed to IMD classification code
- `get_cascade_chain(disaster_type)` — Returns predefined cascading failure chains for 7 Indian disaster types + generic fallback

### LangGraph Pipeline
```
ingest_data → retrieve_historical → forecast_risk → predict_cascading → generate_risk_map → produce_report
```

Nodes 1 and 6 are pure data extraction/aggregation (no LLM calls). Nodes 3-5 use the standard tier (DeepSeek Chat) for reasoning. Node 2 uses ChromaDB for RAG retrieval.

## How It Works

### Agent Configuration
- **Type**: `AgentType.PREDICTIVE_RISK`
- **LLM Tier**: `LLMTier.STANDARD` (DeepSeek Chat, $0.28/M tokens) — forecasting needs stronger reasoning than routine classification but doesn't need the full Reasoner
- **A2A**: Receives tasks from Orchestrator, returns risk reports

### Graceful Degradation
- If ChromaDB is unavailable, the agent continues without historical analogies (confidence decreases)
- If LLM returns non-JSON, fallback structures are used
- Confidence score dynamically reflects data quality: more sources = higher confidence

### Confidence Calculation
- Weather data present: +0.3
- Historical analogies found (weighted by similarity): +0.2 × avg_similarity
- Forecast confidence from LLM: +0.3 × LLM confidence
- Cascading failures predicted: +0.1
- Risk map features generated: +0.1
- Clamped to [0.1, 0.95]

### IMD Cyclone Scale (India-specific)
| Code | Name | Wind Speed (kt) |
|------|------|-----------------|
| LOW | Not classified | <17 |
| D | Depression | 17-27 |
| DD | Deep Depression | 28-33 |
| CS | Cyclonic Storm | 34-47 |
| SCS | Severe Cyclonic Storm | 48-63 |
| VSCS | Very Severe Cyclonic Storm | 64-89 |
| ESCS | Extremely Severe Cyclonic Storm | 90-119 |
| SuCS | Super Cyclonic Storm | >=120 |

## How It Connects

### Dependencies (upstream)
- **S7.1 BaseAgent** — Inherits LangGraph state machine, LLM routing, A2A protocol, health checks
- **S6.1 ChromaDB setup** — Uses `EmbeddingPipeline.query_similar()` for historical event retrieval
- **S6.4 IMD historical data** — The ingested historical IMD data feeds the RAG queries

### Dependents (downstream)
- **S7.5 ResourceAllocation** — Uses PredictiveRisk's forecasts and risk maps to optimize resource deployment
- **S7.7 InfraStatus** — Uses cascading failure predictions to prioritize infrastructure monitoring
- **S7.9 Agent Integration** — PredictiveRisk is part of the full agent pipeline test
- **S8.5 Metric: Situational Accuracy** — Evaluates forecast quality against ground truth

### Data Flow
```
SituationSense (current data) → Orchestrator → PredictiveRisk (forecast) → Orchestrator → ResourceAllocation (optimize)
                                                     ↓
                                              InfraStatus (monitor cascades)
```

## Interview Q&A

**Q: Why does PredictiveRisk use the standard tier instead of routine?**
A: Forecasting requires multi-step reasoning — analyzing current conditions, identifying historical parallels, projecting cascading effects, and quantifying uncertainty. This is qualitatively harder than classification (routine tier). The standard tier (DeepSeek Chat at $0.28/M) provides chain-of-thought reasoning at 7x less than the critical tier. The cost is justified because bad forecasts lead to misallocated resources.

**Q: How does the cascading failure chain work?**
A: We model cascading failures as predefined chain templates per disaster type, then use the LLM to estimate probabilities and timelines for each step given current conditions. For example, the cyclone chain is: landfall → storm surge → dam overtopping → downstream flooding → power grid failure → telecom backup exhaustion → communication blackout → water treatment disruption. Each step has a probability and ETA in hours. The predefined chains encode domain knowledge from NDMA guidelines; the LLM adapts them to the specific scenario.

**Q: Why use RAG for historical analogies instead of fine-tuning?**
A: (1) No training cost — we just embed documents into ChromaDB ($0). (2) Updatable — adding a new disaster event means embedding one new document, not retraining. (3) Transparent — we can show which historical event was retrieved and its similarity score, making the reasoning auditable. (4) Works with any LLM — the retrieved context is in the prompt, so it works across DeepSeek, Qwen, Groq, and Ollama equally.

**Q: What happens if all data sources fail?**
A: The agent degrades gracefully at each step. No ChromaDB → empty analogies (confidence drops). No weather data → generic forecast (confidence drops further). Even with zero data, the agent still produces a valid (low-confidence) output rather than crashing. The Orchestrator can see the low confidence and decide to wait for more data or proceed with the best available information.
