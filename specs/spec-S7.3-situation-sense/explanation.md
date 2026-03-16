# Explanation: S7.3 — SituationSense Agent

## Why This Spec Exists

SituationSense is the "eyes and ears" of the multi-agent system. Before any other agent can make decisions (predict risks, allocate resources, communicate alerts), someone has to fuse raw data from multiple Indian disaster agencies into a coherent picture. Without this agent, every other agent would need to independently parse IMD warnings, SACHET CAP feeds, and social media — duplicating work and risking inconsistent interpretations.

## What It Does

SituationSense takes raw data from three source types and produces:
1. **Fused situational picture** — a unified JSON summary merging IMD, SACHET, and social media
2. **Urgency score (1-5)** — mapped from IMD color codes (Green/Yellow/Orange/Red) and SACHET severity levels
3. **Misinformation flags** — contradictions between official and unofficial sources
4. **GeoJSON situation report** — geographic visualization of affected areas

## How It Works

### LangGraph State Machine

Five sequential nodes form the pipeline:

```
ingest_data → fuse_sources → score_urgency → detect_misinfo → produce_sitrep
```

1. **ingest_data** — Extracts IMD warnings, SACHET alerts, and social media from the task payload. Determines the highest IMD color code. No LLM call needed — pure data extraction.

2. **fuse_sources** — Sends all data to the LLM (routine tier, Qwen Flash) to merge into a coherent picture. If no data is available, returns early with low confidence (0.2) without calling the LLM. Confidence scales with source count: `0.3 + source_count * 0.2`.

3. **score_urgency** — Deterministic mapping (no LLM call). Uses `map_urgency()` which takes the max of IMD color score and SACHET severity score. Special case: Red + Extreme + Immediate = urgency 5.

4. **detect_misinfo** — LLM compares social media posts against the fused official picture. Skipped entirely if there are no social media posts (returns empty flags).

5. **produce_sitrep** — LLM generates a GeoJSON FeatureCollection representing affected areas. Falls back to empty FeatureCollection if JSON parsing fails.

### Urgency Mapping

| IMD Color | Score | SACHET Severity | Score |
|-----------|-------|-----------------|-------|
| Green     | 1     | Minor           | 1     |
| Yellow    | 2     | Moderate        | 2     |
| Orange    | 3     | Severe          | 3     |
| Red       | 4     | Extreme         | 4     |

The function takes `max(imd_score, sachet_score)`, so SACHET can upgrade IMD's assessment but not downgrade it. The special case of urgency 5 requires all three conditions: Red + Extreme + Immediate.

### Key Design Decisions

- **Routine tier (Qwen Flash, $0.04/M)** — Data fusion is language processing, not deep reasoning. Qwen Flash at 100x cheaper than DeepSeek Reasoner is more than adequate.
- **Pre-fetched data model** — The agent receives data in the task payload rather than calling MCP tools directly. This decouples data fetching (orchestrator's job) from analysis (this agent's job).
- **Graceful degradation** — Every node handles missing/empty data. No crashes on malformed input.
- **Deterministic urgency scoring** — The `map_urgency()` function is pure logic, not LLM-dependent. This ensures consistent, testable urgency levels.

## How It Connects

### Dependencies (upstream)
- **S7.1 BaseAgent** — Inherits LangGraph lifecycle, LLM routing, A2A, health checks
- **S5.1 MCP IMD** — Data format compatibility (IMD warning structure)
- **S5.2 MCP SACHET** — Data format compatibility (CAP alert structure)

### Dependents (downstream)
- **S7.2 Orchestrator** — Sends tasks to SituationSense, receives urgency scores
- **S7.4 PredictiveRisk** — Uses the fused picture for risk forecasting
- **S7.5 ResourceAllocation** — Uses urgency scores to prioritize resource deployment
- **S7.6 CommunityComms** — Uses the situation report to generate public alerts
- **S7.9 Integration Test** — Tests the full pipeline starting with SituationSense

### Data Flow
```
IMD API → MCP-IMD → Orchestrator → SituationSense → fused picture + urgency
SACHET Feed → MCP-SACHET → Orchestrator → SituationSense → GeoJSON report
Social Media → Pipeline → Orchestrator → SituationSense → misinfo flags
```

## Interview Talking Points

**Q: Why separate urgency scoring from the LLM?**
A: Urgency scoring is deterministic — IMD Green always means urgency 1. Using an LLM for this would add cost, latency, and non-determinism. The `map_urgency()` function is a pure function: same inputs → same output. It's also the most unit-testable part of the agent.

**Q: How does the confidence score work?**
A: Confidence scales with data availability: `0.3 + source_count * 0.2`. With 0 sources → 0.2 (very low), 1 source → 0.5, 2 sources → 0.7, 3 sources → 0.9 (capped). This lets downstream agents know how much to trust the situation report.

**Q: Why process data in a pipeline rather than all at once?**
A: The sequential pipeline (ingest → fuse → score → detect → report) follows the Single Responsibility Principle. Each node has one job, can be tested independently, and can be replaced without affecting others. It also makes the graph debuggable — you can inspect state after any node.
