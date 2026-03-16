# Spec S7.2 — Orchestrator Agent

**Phase**: 7 (Agent System)
**Depends On**: S7.1 (BaseAgent)
**Location**: `src/agents/orchestrator.py`
**Test**: `tests/unit/test_orchestrator.py`
**LLM Tier**: CRITICAL (DeepSeek Reasoner)

---

## Overview

The Orchestrator is the master coordinator agent. It receives high-level disaster missions, decomposes them into sub-tasks, delegates to specialist agents via A2A, collects results with timeout enforcement, synthesizes bilingual briefings, and manages the per-scenario LLM budget.

## Functional Requirements

### FR-1: Mission Decomposition
- Accept a mission payload containing disaster type, severity, affected areas, phase
- Use LLM (CRITICAL tier) to decompose mission into sub-tasks for specialist agents
- Each sub-task specifies: target agent type, task type, priority, payload
- Output: list of `A2ATask` objects ready for delegation

### FR-2: Agent Activation by Disaster Phase
- Map disaster phase to active agent set:
  - `pre_event`: SituationSense, PredictiveRisk, HistoricalMemory
  - `active_response`: all 6 specialist agents
  - `recovery`: ResourceAllocation, CommunityComms, InfraStatus, HistoricalMemory
  - `post_event`: HistoricalMemory only
- Only delegate tasks to agents active for the current phase

### FR-3: Task Delegation via A2A
- Send decomposed sub-tasks to specialist agents via `A2AServer.send_task()`
- Each task carries incremented `depth` from the parent task
- Track all pending tasks by task_id with deadlines

### FR-4: Result Collection with Timeout
- Wait for `A2ATaskResult` messages from specialist agents
- Per-task timeout: `AGENT_TIMEOUT_SECONDS` (default 120s)
- If a task times out: mark as failed, use partial results
- Collect all results (completed + timed out) before synthesis

### FR-5: Budget Management
- Track cumulative LLM cost across all agent calls for a scenario
- Budget ceiling: `BUDGET_LIMIT_PER_SCENARIO` from settings (default $0.05)
- When budget exceeded: log warning, switch remaining calls to free tier
- Expose budget status in health check

### FR-6: Loop Detection
- **Delegation depth**: reject tasks with depth > `AGENT_MAX_DELEGATION_DEPTH` (inherited from BaseAgent)
- **Message deduplication**: inherited from A2A client
- **Global timeout**: 120s per task (from settings)

### FR-7: Result Synthesis
- Aggregate results from all specialist agents
- Use LLM (CRITICAL tier) to synthesize into structured briefing
- Output includes: situation summary, risk assessment, resource plan, communication directives
- Include aggregate confidence score (weighted average of agent confidences)

### FR-8: Confidence-Gated Escalation
- If aggregate confidence < 0.7: flag for human review
- Set `needs_escalation` flag in output artifacts
- Log escalation event with trace_id

## State Machine (LangGraph)

```
START → parse_mission → decompose → delegate → collect_results → synthesize → END
                                                      ↓
                                              (timeout handling)
```

### Nodes
1. **parse_mission**: Extract disaster info from task payload
2. **decompose**: LLM call to break mission into sub-tasks
3. **delegate**: Send sub-tasks via A2A, track pending
4. **collect_results**: Wait for results with timeout
5. **synthesize**: LLM call to combine results into briefing

### State (extends AgentState)
- `sub_tasks`: list of decomposed sub-tasks
- `pending_tasks`: dict of task_id → status
- `agent_results`: dict of agent_type → result
- `budget_used`: float (cumulative USD)
- `budget_exceeded`: bool
- `needs_escalation`: bool

## Outcomes
- [ ] Orchestrator extends BaseAgent with CRITICAL tier
- [ ] Mission decomposition via LLM produces valid sub-tasks
- [ ] Phase-based agent activation filters correctly
- [ ] Tasks delegated via A2A with proper depth tracking
- [ ] Results collected with timeout enforcement
- [ ] Budget tracking prevents overspend
- [ ] Synthesis produces structured briefing with confidence
- [ ] Escalation triggered when confidence < 0.7
- [ ] Health check includes budget and active task info

## TDD Notes
- Mock LLM router to return structured JSON for decomposition/synthesis
- Mock A2A server/client — no Redis needed
- Test each node independently
- Test timeout handling with asyncio.sleep mocks
- Test budget enforcement at boundary
- Test phase-to-agent mapping exhaustively
