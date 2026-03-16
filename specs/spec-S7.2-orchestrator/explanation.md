# Spec S7.2 — Orchestrator Agent: Explanation

## Why This Spec Exists

The Orchestrator is the brain of the multi-agent system. Without it, the 6 specialist agents have no coordination — each would operate independently with no mission decomposition, no budget control, and no synthesis of results. The Orchestrator transforms a high-level disaster mission ("Cyclone approaching Odisha") into coordinated multi-agent action and a unified briefing.

## What It Does

**OrchestratorAgent** (`src/agents/orchestrator.py`) extends BaseAgent (S7.1) with:

1. **Mission Decomposition** — Uses CRITICAL-tier LLM to break a disaster mission into sub-tasks targeting specific specialist agents (SituationSense, PredictiveRisk, ResourceAllocation, etc.)

2. **Phase-Based Agent Activation** — Maps disaster lifecycle phases to active agents:
   - `pre_event`: SituationSense + PredictiveRisk + HistoricalMemory
   - `active_response`: all 6 specialists
   - `recovery`: ResourceAllocation + CommunityComms + InfraStatus + HistoricalMemory
   - `post_event`: HistoricalMemory only

3. **A2A Task Delegation** — Sends sub-tasks to agents via A2AServer.send_task() with incremented depth tracking

4. **Result Collection with Timeout** — Waits for agent results with configurable timeout; marks timed-out tasks as failed and proceeds with partial results

5. **Budget Management** — Tracks cumulative LLM cost per scenario against `BUDGET_LIMIT_PER_SCENARIO` ($0.05 default). Logs warnings when exceeded.

6. **Result Synthesis** — Uses CRITICAL-tier LLM to combine agent results into a structured briefing with situation summary, risk assessment, resource plan, and communication directives

7. **Confidence-Gated Escalation** — If aggregate confidence < 0.7, flags the briefing with `needs_escalation: true` for human review

## How It Works

### LangGraph State Machine

```
parse_mission → decompose → delegate → collect_results → synthesize → END
```

- **parse_mission**: Extracts disaster type, severity, phase from the task payload
- **decompose**: LLM call returns JSON with sub-tasks; filters by phase-active agents
- **delegate**: Creates A2ATask objects with depth+1 and sends via A2A server
- **collect_results**: Polls for results with timeout; creates FAILED results for timed-out tasks
- **synthesize**: LLM call combines results into briefing; checks confidence threshold

### State (OrchestratorState)

Extends AgentState with: `sub_tasks`, `pending_task_ids`, `agent_results`, `budget_used`, `budget_exceeded`, `needs_escalation`, `phase`, `mission`

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| CRITICAL tier for decompose + synthesize | These are the highest-stakes decisions — wrong decomposition = wrong response |
| Phase-based activation | Saves LLM cost by not engaging irrelevant agents (e.g., no ResourceAllocation in pre_event) |
| 0.7 confidence threshold | Below 70% = too uncertain for automated action; requires human review |
| JSON-based LLM output | Structured output enables programmatic routing; graceful fallback on parse failure |
| Budget per scenario | Prevents runaway cost; $0.05/scenario × 100 = $5 for full benchmark |

## How It Connects

### Dependencies (uses)
- **S7.1 BaseAgent** — Inherits LangGraph, LLM Router, A2A, health check, timeout enforcement
- **S2.6 LLM Router** — All LLM calls go through router.call() with CRITICAL tier
- **S4.2 A2A Server** — Delegates tasks to specialist agents via send_task()
- **S4.3 A2A Client** — Receives results and handles message deduplication
- **S2.5 Telemetry** — Structured logging of decomposition, delegation, synthesis, escalation

### Dependents (used by)
- **S7.3–S7.8 Specialist Agents** — Receive tasks from orchestrator, send results back
- **S7.9 Integration Test** — End-to-end test: mission → all agents → briefing
- **S8.3 Scenario Runner** — Drives the orchestrator with benchmark scenarios
- **S3.2 WebSocket** — Dashboard receives orchestrator status updates
- **S9.1 Plan Caching** — Cached plans reduce orchestrator's LLM calls

## Interview Q&A

**Q: How does the Orchestrator prevent infinite agent loops?**
A: Three layers: (1) Delegation depth counter — each task increments depth; at depth > 5, BaseAgent rejects it. (2) Message deduplication — A2A client tracks processed message IDs in Redis with TTL. (3) Per-task timeout — collect_results applies AGENT_TIMEOUT_SECONDS (120s default); timed-out tasks get marked as failed and partial results are used.

**Q: Why use an LLM for mission decomposition instead of rule-based routing?**
A: Disasters are inherently unpredictable. A rule-based system would need rules for every combination of disaster type × severity × phase × geographic context. An LLM can reason about novel combinations: "This is a cyclone + industrial accident compound disaster in a coastal industrial zone — we need SituationSense for the cyclone AND InfraStatus for chemical plant impact." The LLM also outputs structured JSON, so we get programmatic routing with natural language understanding.

**Q: What happens when the budget is exceeded mid-scenario?**
A: The Orchestrator logs a warning and the `is_budget_exceeded()` flag becomes true. The current implementation tracks costs but doesn't auto-switch tiers — that will be handled by the cost tracker (S2.8). The budget check enables downstream components to make tier decisions. In the full system, when budget is exceeded, remaining calls would use free tier (Groq/Ollama) instead of paid DeepSeek.

**Q: Why is confidence-gated escalation important for a disaster system?**
A: In disaster response, a wrong decision (e.g., evacuate to a shelter in the storm path) can be worse than no decision. If the system's confidence is below 0.7, it means the agents disagree, data is uncertain, or the scenario is novel. Flagging for human review prevents automated action on uncertain analysis. The escalation includes the trace_id so a human operator can inspect exactly which agent produced low-confidence results.
