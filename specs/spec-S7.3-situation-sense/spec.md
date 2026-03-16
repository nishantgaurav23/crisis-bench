# Spec S7.3 — SituationSense Agent

**Status**: spec-written
**Location**: `src/agents/situation_sense.py`
**Depends On**: S7.1 (BaseAgent), S5.1 (MCP IMD), S5.2 (MCP SACHET)
**Depended By**: S7.9 (Agent Integration Test), S9.2 (Dashboard Integration)

---

## 1. Overview

SituationSense is the first-responder agent — it fuses multi-source data (IMD weather, SACHET alerts, social media, satellite imagery) into a unified situational picture. It runs on the **routine** tier (Qwen Flash, $0.04/M tokens) for most operations and **vision** tier for satellite imagery analysis.

Key capabilities per FR-002:
- FR-002.1: Ingest IMD warnings + SACHET CAP alerts
- FR-002.3: Maintain GeoJSON situational awareness map
- FR-002.5: Assign urgency scores (1-5) based on IMD color codes
- FR-002.6: Detect and flag misinformation
- FR-002.7: Publish situation updates to Redis Streams at 60s intervals

---

## 2. Outcomes

1. `SituationSense` class in `src/agents/situation_sense.py` extending `BaseAgent`
2. LangGraph state machine with nodes: `ingest_data`, `fuse_sources`, `score_urgency`, `detect_misinfo`, `produce_sitrep`
3. Custom `SituationState` extending `AgentState` with situation-specific fields
4. `get_system_prompt()` with India-specific disaster expertise
5. `get_agent_card()` declaring all capabilities
6. MCP tool integration — calls IMD + SACHET servers via tool interfaces
7. GeoJSON situation report output as an artifact
8. Urgency scoring aligned with IMD color codes (Green=1, Yellow=2, Orange=3, Red=4, Red+=5)
9. Misinformation detection flags in output
10. All LLM calls via `self.reason()` (routine tier)

---

## 3. Design

### 3.1 SituationState

```python
class SituationState(AgentState):
    """Extended state for SituationSense agent."""
    imd_data: list[dict]           # Raw IMD warnings/rainfall
    sachet_alerts: list[dict]      # Parsed SACHET CAP alerts
    social_media: list[dict]       # Social media posts (if provided)
    fused_picture: dict            # Merged situational data
    urgency_score: int             # 1-5 urgency
    imd_color: str                 # IMD warning color code
    misinfo_flags: list[dict]      # Detected misinformation
    geojson: dict                  # GeoJSON situation report
```

### 3.2 LangGraph Nodes

```
[START] -> ingest_data -> fuse_sources -> score_urgency -> detect_misinfo -> produce_sitrep -> [END]
```

1. **ingest_data**: Calls IMD + SACHET MCP tools, collects raw data
2. **fuse_sources**: LLM merges multiple data streams into coherent picture
3. **score_urgency**: Maps IMD color codes + alert severity to 1-5 urgency
4. **detect_misinfo**: LLM flags contradictions/suspicious claims
5. **produce_sitrep**: Generates GeoJSON situation report artifact

### 3.3 Urgency Mapping

| IMD Color | SACHET Severity | Urgency Score |
|-----------|----------------|---------------|
| Green     | Minor/Unknown  | 1             |
| Yellow    | Moderate       | 2             |
| Orange    | Severe         | 3             |
| Red       | Extreme        | 4             |
| Red + multiple agencies | Extreme + Immediate | 5 |

### 3.4 MCP Tool Integration

The agent receives pre-fetched data in the task payload (MCP tools are called by the orchestrator or data pipeline, not directly by the agent graph). The agent processes this data using LLM reasoning.

---

## 4. TDD Plan

### Test File: `tests/unit/test_situation_sense.py`

#### Test Group 1: Initialization
- `test_creates_with_correct_type` — AgentType.SITUATION_SENSE
- `test_default_tier_is_routine` — LLMTier.ROUTINE
- `test_system_prompt_contains_india_context` — mentions IMD, NDMA, India
- `test_agent_card_has_capabilities` — lists data fusion, urgency scoring, etc.

#### Test Group 2: State Machine Structure
- `test_build_graph_has_all_nodes` — ingest, fuse, score, misinfo, sitrep
- `test_graph_compiles` — no compilation errors
- `test_graph_runs_end_to_end` — full pipeline with mocked LLM

#### Test Group 3: Data Ingestion
- `test_ingest_processes_imd_data` — parses IMD warnings
- `test_ingest_processes_sachet_alerts` — parses SACHET alerts
- `test_ingest_handles_empty_data` — graceful with no data

#### Test Group 4: Urgency Scoring
- `test_urgency_green_maps_to_1` — IMD Green = urgency 1
- `test_urgency_yellow_maps_to_2`
- `test_urgency_orange_maps_to_3`
- `test_urgency_red_maps_to_4`
- `test_urgency_extreme_maps_to_5` — Red + Extreme severity
- `test_urgency_defaults_to_1` — unknown/missing data

#### Test Group 5: Misinformation Detection
- `test_misinfo_flags_contradictions` — LLM detects contradictory reports
- `test_misinfo_empty_when_no_issues` — no false positives on clean data

#### Test Group 6: Situation Report Output
- `test_sitrep_produces_geojson` — output has valid GeoJSON structure
- `test_sitrep_includes_urgency` — urgency score in output
- `test_sitrep_includes_affected_areas` — areas from alerts in output

#### Test Group 7: Edge Cases
- `test_handles_task_with_no_disaster_data` — graceful degradation
- `test_handles_malformed_imd_data` — doesn't crash on bad data
- `test_confidence_reflects_data_quality` — low confidence with sparse data

---

## 5. Dependencies

All dependencies already in pyproject.toml from prior specs.

---

## 6. Files to Create/Modify

| File | Action |
|------|--------|
| `src/agents/situation_sense.py` | Create — SituationSense agent |
| `tests/unit/test_situation_sense.py` | Create — all tests |
