# Spec S8.8 — Coordination Quality Metric: Explanation

## Why This Spec Exists

Individual agent quality (S8.5–S8.7) is necessary but not sufficient for effective disaster response. A system where SituationSense detects a cyclone but doesn't share that information with ResourceAllocation will fail at coordination even if each agent performs well in isolation. This metric captures the **emergent system-level coordination** quality that arises from inter-agent communication patterns.

In the CRISIS-BENCH framework, Coordination Quality is the 4th of 5 evaluation dimensions (alongside Situational Accuracy, Decision Timeliness, Resource Efficiency, and Communication Appropriateness), contributing to the aggregate Disaster Response Score (DRS).

## What It Does

Evaluates coordination quality across 4 weighted components:

| Component | Weight | What It Measures |
|-----------|--------|------------------|
| **Information Sharing** | 30% | Were expected inter-agent messages sent? Parses "share X with Y" actions from ground truth and checks if matching (from, to) pairs exist in actual messages. |
| **Milestone Achievement** | 30% | Were coordination milestones reached on time? Compares actual milestone timestamps against deadlines from `decision_timeline`. Late milestones get partial credit via exponential decay. |
| **Response Coverage** | 25% | Did all required agents participate? Checks which expected agents appear in the actual decision records. |
| **Redundancy Avoidance** | 15% | Were duplicate messages avoided? Measures unique/total message ratio — redundant messages waste processing time. |

Each component produces a ratio (0.0–1.0) mapped linearly to a 1.0–5.0 score. The composite score is a weighted sum, clamped to [1.0, 5.0].

## How It Works

### Data Flow

```
EvaluationRun.agent_decisions → extract_messages() → MessageRecord[]
                               → extract_milestones() → MilestoneRecord[]
                               → {agent_id} set

GroundTruthDecisions → extract_expected_coordination() → expected (from,to) pairs
                                                        → expected milestones {id: deadline}
                                                        → expected agent set
```

### Scoring Pipeline

1. **Extract** — Parse messages, milestones, and participating agents from `agent_decisions`
2. **Extract expected** — Parse "share X with Y" patterns from ground truth `expected_actions`, milestone deadlines from `decision_timeline`
3. **Score components** — Compute each ratio independently
4. **Composite** — `ratio_to_score(r) = 1.0 + r * 4.0`, then weighted sum

### Key Design Decisions

- **Regex-based action parsing**: Uses `share\s+.+\s+with\s+(\w+)` to extract expected message flows from natural language ground truth actions. This keeps ground truth human-readable while enabling automated evaluation.
- **Partial credit for late milestones**: Uses `exp(-2.0 * lateness)` decay so late-but-completed milestones get some credit, while missing milestones get zero.
- **No expectations = full score**: If ground truth has no coordination expectations, the metric returns 5.0 rather than penalizing.

## How It Connects

### Depends On
- **S8.4 (Evaluation Engine)** — Provides the `EvaluationRun` and `BenchmarkScenario` models consumed by this metric
- **S8.1 (Scenario Models)** — `GroundTruthDecisions`, `AgentExpectation` models define the ground truth format

### Depended On By
- **S8.10 (Aggregate DRS)** — Combines this metric's score with the other 4 dimensions into the aggregate Disaster Response Score
- **S9.2 (Dashboard Integration)** — Displays coordination quality breakdown in the metrics panel

### Sibling Metrics
- **S8.5 (Situational Accuracy)** — Evaluates observation correctness (precision/recall/F1)
- **S8.6 (Decision Timeliness)** — Evaluates decision speed vs NDMA SOP windows
- **S8.7 (Resource Efficiency)** — Evaluates allocation quality vs OR-Tools baseline
- **S8.9 (Communication Appropriateness)** — Evaluates multilingual output quality

## Interview Q&A

**Q: Why 4 components instead of just counting messages?**
A: Raw message count is a poor proxy for coordination quality. An agent could spam 100 messages and score high on "information sharing" while duplicating effort and missing milestones. The 4-component design captures different aspects: (1) Did the right information flow between the right agents? (2) Were coordination milestones met on time? (3) Did all required agents participate? (4) Was communication efficient (no spam)?

**Q: Why use regex to parse expected coordination from ground truth?**
A: The alternative is a structured format (separate `expected_messages` field in ground truth). We chose regex on natural language because: (1) ground truth `expected_actions` are already written by the scenario generator in natural language ("share situation report with predictive_risk"), (2) it keeps the ground truth format simple and human-readable, (3) the regex `share\s+.+\s+with\s+(\w+)` is robust enough for our controlled vocabulary. Trade-off: fragile if someone writes "send data to agent_x" instead of "share data with agent_x" — but we control the scenario generator.

**Q: How does the milestone partial credit decay work?**
A: `credit = exp(-2.0 * (actual - deadline) / deadline)`. If a milestone with deadline=10 minutes is completed at 15 minutes, lateness = (15-10)/10 = 0.5, credit = exp(-1.0) ≈ 0.37. At 20 minutes (100% late), credit = exp(-2.0) ≈ 0.14. This is harsher than linear decay because in disaster response, late coordination has cascading consequences — a late resource plan means late evacuation, which means casualties.
