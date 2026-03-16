# Spec S8.8 — Metric: Coordination Quality

## Overview

**Feature**: Coordination Quality metric for CRISIS-BENCH benchmark evaluation.
**Location**: `src/benchmark/metrics/coordination.py`
**Depends On**: S8.4 (Evaluation Engine)

## What It Does

Measures how effectively agents coordinate during disaster response by evaluating:
1. **Information Sharing** — Did agents share relevant data with each other?
2. **Milestone Achievement** — Were key coordination milestones reached?
3. **Message Flow** — Were the right agents contacted at the right times?
4. **Redundancy Avoidance** — Did agents avoid duplicating work?

## Why It Matters

In a multi-agent disaster response system, individual agent quality is necessary but not sufficient. If SituationSense detects a cyclone but doesn't share it with ResourceAllocation, evacuation planning fails. This metric captures the system-level coordination quality that emerges from inter-agent communication.

## Design

### Input Data

From `EvaluationRun.agent_decisions`, extract:
- `messages_sent`: list of `{from_agent, to_agent, message_type, timestamp_minutes}` — inter-agent A2A messages
- `milestones_reached`: list of `{milestone_id, agent_id, timestamp_minutes}` — coordination milestones achieved

From `GroundTruthDecisions`, extract:
- Per-agent `expected_actions` that specify expected coordination steps
- A `coordination_milestones` key in the decision_timeline dict mapping milestone IDs to expected completion times

### Scoring Components (4 sub-scores, weighted)

| Component | Weight | What It Measures |
|-----------|--------|------------------|
| Information Sharing | 0.30 | % of expected inter-agent messages that were actually sent |
| Milestone Achievement | 0.30 | % of expected milestones reached within time windows |
| Response Coverage | 0.25 | Whether all required agents participated |
| Redundancy Avoidance | 0.15 | Penalty for duplicate/unnecessary messages |

### Score Mapping

Each component produces a ratio (0.0-1.0), mapped to 1.0-5.0 score:
- `ratio_to_score(r) = 1.0 + r * 4.0`

Composite score = weighted sum of component scores, clamped to [1.0, 5.0].

### Expected Agent Decision Format

```json
{
  "agent_id": "orchestrator",
  "messages_sent": [
    {"from_agent": "orchestrator", "to_agent": "situation_sense", "message_type": "task_assignment"},
    {"from_agent": "situation_sense", "to_agent": "predictive_risk", "message_type": "data_share"}
  ],
  "milestones_reached": [
    {"milestone_id": "initial_assessment", "agent_id": "situation_sense", "timestamp_minutes": 5},
    {"milestone_id": "resource_plan", "agent_id": "resource_allocation", "timestamp_minutes": 15}
  ]
}
```

### Ground Truth Format

Expected coordination milestones in `decision_timeline`:
```json
{
  "initial_assessment": "5",
  "resource_plan": "15",
  "evacuation_order": "20",
  "comms_broadcast": "25"
}
```

Expected inter-agent flows in agent expectations `expected_actions`:
```
["share situation report with predictive_risk", "share risk assessment with resource_allocation"]
```

## Outcomes

- [ ] `CoordinationQualityResult` Pydantic model with component scores + overall score
- [ ] `CoordinationQualityMetric` class with `async compute(scenario, evaluation_run)` interface
- [ ] Extract coordination data from agent decisions and ground truth
- [ ] 4-component weighted scoring: info sharing, milestones, coverage, redundancy
- [ ] Score range 1.0-5.0 with linear mapping
- [ ] Consistent interface with SituationalAccuracyMetric, DecisionTimelinessMetric, ResourceEfficiencyMetric

## TDD Notes

### Red Phase — Tests to Write First
1. Test extraction of messages from agent decisions (empty, single, multiple agents)
2. Test extraction of milestones from agent decisions
3. Test extraction of expected coordination from ground truth
4. Test information sharing score computation (0%, 50%, 100% coverage)
5. Test milestone achievement score computation (all met, some missed, none met)
6. Test response coverage computation (all agents present, some missing)
7. Test redundancy avoidance computation (no duplicates, some duplicates, all duplicates)
8. Test composite score computation with weights
9. Test `ratio_to_score` mapping (boundaries: 0.0, 0.5, 1.0)
10. Test full `compute()` with realistic scenario (perfect coordination, partial, no coordination)
11. Test edge cases: empty decisions, no ground truth milestones, no messages

### Green Phase — Implementation Order
1. Pydantic models (MessageRecord, MilestoneRecord, CoordinationQualityResult)
2. Extraction functions (extract_messages, extract_milestones, extract_expected_coordination)
3. Component scoring functions (info_sharing_score, milestone_score, coverage_score, redundancy_score)
4. ratio_to_score mapping
5. Composite score computation
6. CoordinationQualityMetric class with async compute()
