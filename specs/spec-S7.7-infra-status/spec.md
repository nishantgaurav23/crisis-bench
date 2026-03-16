# Spec S7.7: InfraStatus Agent

**Status**: done

## Overview
The InfraStatus agent tracks infrastructure health (power, telecom, water, hospitals, roads, shelters), predicts cascading failures via Neo4j graph traversal, estimates restoration timelines, and applies NDMA priority restoration framework.

**Tier**: routine (Qwen Flash, $0.04/M tokens)
**Dependencies**: S7.1 (BaseAgent), S6.3 (Neo4j Infrastructure Graph)

## Requirements (from FR-006)

| ID | Requirement |
|----|-------------|
| FR-006.1 | Track infrastructure: power grid, highways, state roads, railways, telecom towers, water supply, hospitals |
| FR-006.2 | Use OSM + Bhuvan + Neo4j graph data |
| FR-006.3 | India-specific cascading failures: power → telecom backup exhaustion (4-8h) → comms blackout → water treatment failure |
| FR-006.4 | Predict restoration timelines based on NDRF/SDRF capacity and historical patterns |
| FR-006.5 | Maintain infrastructure dependency graph in Neo4j Community |
| FR-006.6 | Priority restoration: hospitals > water treatment > telecom > power > roads (NDMA framework) |

## LangGraph State Machine

```
ingest_data -> query_infra_graph -> assess_damage -> predict_cascading
-> estimate_restoration -> produce_report
```

### Node Descriptions

1. **ingest_data** — Extract affected area, disaster type, and reported damage from task payload
2. **query_infra_graph** — Query Neo4j (via InfraGraphManager) for infrastructure in affected area + simulate failures
3. **assess_damage** — LLM-based damage assessment combining graph data with disaster context
4. **predict_cascading** — Use Neo4j graph traversal + LLM to predict cascading failure timeline
5. **estimate_restoration** — Estimate restoration timelines per infrastructure type using NDMA priority framework
6. **produce_report** — Compile final infrastructure status report with priority-ordered restoration plan

## State Schema (InfraStatusState extends AgentState)

```python
class InfraStatusState(AgentState):
    infrastructure_data: list[dict]     # Raw graph query results
    damage_assessment: dict             # Per-node damage evaluation
    cascading_failures: list[dict]      # Predicted cascade timeline
    restoration_plan: list[dict]        # Priority-ordered restoration
    affected_state: str                 # Indian state name
    affected_districts: list[str]       # District names
```

## NDMA Priority Framework

```python
RESTORATION_PRIORITY = {
    "Hospital": 1,         # Life-critical
    "WaterTreatment": 2,   # Public health
    "TelecomTower": 3,     # Communication
    "PowerGrid": 4,        # Infrastructure backbone
    "Road": 5,             # Access routes
    "Shelter": 6,          # Temporary housing
}
```

## Restoration Timeline Estimates

Based on NDRF/SDRF deployment patterns and historical data:

| Infrastructure | Minor Damage | Moderate | Severe |
|---------------|-------------|----------|--------|
| Hospital (generator) | 2-4h | 8-12h | 24-48h |
| Water Treatment | 4-8h | 12-24h | 48-72h |
| Telecom Tower | 2-6h | 8-16h | 24-48h |
| Power Grid | 4-12h | 24-48h | 72-168h |
| Road | 6-12h | 24-72h | 72-336h |
| Shelter | 2-4h | 6-12h | 24-48h |

## Outcomes

- [ ] InfraStatus agent initializes with AgentType.INFRA_STATUS, LLMTier.ROUTINE
- [ ] LangGraph with 6 nodes compiles and executes
- [ ] Neo4j InfraGraphManager integration for graph queries and failure simulation
- [ ] NDMA priority framework correctly orders restoration
- [ ] Cascading failure prediction with timeline
- [ ] Restoration timeline estimation per infrastructure type
- [ ] Graceful degradation when Neo4j is unavailable
- [ ] All LLM calls through router.reason()
- [ ] Final report artifact includes damage assessment, cascade timeline, and restoration plan

## TDD Notes

- Mock InfraGraphManager for all unit tests
- Mock LLM router responses with realistic JSON
- Test NDMA priority ordering as pure function
- Test restoration time estimation as pure function
- Test graceful degradation when Neo4j fails
- Test full graph execution end-to-end with mocks
