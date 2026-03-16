# Spec S7.7: InfraStatus Agent — Explanation

## Why This Spec Exists

Disaster response depends critically on knowing which infrastructure is operational, damaged, or destroyed — and what will fail next. The InfraStatus agent is the system's "infrastructure nervous system," tracking power grids, telecom towers, water treatment plants, hospitals, roads, and shelters across affected areas. Without this agent, the Orchestrator would dispatch NDRF teams to hospitals that have already lost power and water, or route evacuees along roads that are flooded.

India-specific context: In the 2023 Cyclone Biparjoy, cascading failures followed a predictable pattern — power grid failure led to telecom tower backup exhaustion (4-8 hours), then communication blackout, then water treatment plant shutdown. The InfraStatus agent codifies these patterns via Neo4j graph traversal.

## What It Does

1. **Infrastructure Tracking** — Queries the Neo4j dependency graph (from S6.3) for all infrastructure nodes in the affected state/districts
2. **Damage Assessment** — Combines reported damage with LLM analysis to assess per-node damage levels (minor/moderate/severe)
3. **Cascading Failure Prediction** — Uses Neo4j graph traversal to find downstream impacts (e.g., power grid down → which hospitals/telecom/water affected), then LLM generates a timeline
4. **Restoration Planning** — Applies NDMA priority framework (hospitals > water > telecom > power > roads) with time estimates based on NDRF/SDRF historical deployment patterns
5. **Graceful Degradation** — If Neo4j is unavailable, continues with LLM-only assessment

## How It Works

### Architecture

- **LangGraph State Machine**: 6 nodes in a linear pipeline
  - `ingest_data` → `query_infra_graph` → `assess_damage` → `predict_cascading` → `estimate_restoration` → `produce_report`
- **LLM Tier**: Routine (Qwen Flash at $0.04/M tokens) — infrastructure status doesn't need deep reasoning
- **External Dependencies**: Neo4j (InfraGraphManager from S6.3), LLM Router (from S2.6)

### Key Design Decisions

1. **NDMA Priority Framework as pure function** — `RESTORATION_PRIORITY` dict and `get_priority_ordered()` are deterministic and testable without LLM mocks
2. **Restoration time estimates as pure function** — `estimate_restoration_hours()` returns (low, high) tuples based on infrastructure type + damage level
3. **Neo4j graph traversal for cascade prediction** — `InfraGraphManager.simulate_failure()` marks a node as damaged and traverses `DEPENDS_ON`/`POWERS` edges to find all downstream impacts
4. **LLM for natural language assessment** — The raw graph data needs contextual interpretation (e.g., "this power grid failure at night is more critical because backup batteries deplete faster")

### State Flow

```
Task payload (disaster_type, affected_state, reported_damage)
    ↓
Neo4j query → infrastructure_data (all nodes in state)
    ↓
Neo4j simulate_failure → graph_cascades (downstream impacts)
    ↓
LLM assess → damage_assessment (per-node damage levels)
    ↓
LLM predict → cascading_failures (timeline with probabilities)
    ↓
LLM estimate → restoration_plan (priority-ordered with hours)
    ↓
Report artifact with confidence score
```

## How It Connects

### Dependencies (upstream)
- **S7.1 (BaseAgent)** — Inherits LangGraph state machine, LLM routing, A2A protocol, health checks
- **S6.3 (Neo4j Infrastructure Graph)** — Provides `InfraGraphManager` with `get_infrastructure_by_state()`, `simulate_failure()`, `get_downstream_impacts()`

### Consumers (downstream)
- **S7.2 (Orchestrator)** — Delegates infrastructure assessment tasks to InfraStatus
- **S7.5 (ResourceAllocation)** — Uses infrastructure status to determine which shelters/hospitals are operational for resource planning
- **S7.4 (PredictiveRisk)** — Infrastructure cascade data feeds into risk forecasting
- **S7.9 (Agent Integration Test)** — InfraStatus participates in the end-to-end agent pipeline

### Interview Q&A

**Q: Why is InfraStatus on the routine tier instead of standard?**
A: Infrastructure status assessment is primarily data-driven — most intelligence comes from the Neo4j graph traversal, not LLM reasoning. The LLM's job is formatting, gap-filling, and natural language explanation. Qwen Flash at $0.04/M handles this well. If we needed complex multi-step reasoning about cascading failures, we'd escalate to standard tier.

**Q: How does the NDMA priority framework work in practice?**
A: NDMA (National Disaster Management Authority) prioritizes restoration in this order: (1) Hospitals — life-critical, every hour of downtime = potential deaths, (2) Water treatment — public health emergency within 24h without clean water, (3) Telecom — needed for coordination and public warnings, (4) Power — backbone that everything depends on but takes longest to restore, (5) Roads — needed for access but often cleared by NDRF/military quickly. This framework is a pure function (`get_priority_ordered`) so it's deterministic and testable.

**Q: Why use Neo4j for infrastructure dependency tracking instead of PostgreSQL?**
A: Multi-hop dependency traversal. "What fails if this power grid goes down?" requires traversing `DEPENDS_ON` and `POWERS` edges across multiple levels. In Neo4j: `MATCH (affected)-[:DEPENDS_ON*]->(source)` — one Cypher query, O(path_length). In PostgreSQL, this would require recursive CTEs with multiple self-joins — slower and harder to maintain as the graph grows.
