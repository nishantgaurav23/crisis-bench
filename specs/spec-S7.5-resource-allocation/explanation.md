# Spec S7.5 — ResourceAllocation Agent: Explanation

## Why This Spec Exists

During an active disaster, the most critical operational question is: **"Where do we send what, and how fast?"** India's disaster response infrastructure — 16 NDRF battalions, state-level SDRF forces, thousands of shelters, and centrally stockpiled relief supplies — must be deployed optimally across affected districts. Manual allocation leads to over-concentration in accessible areas and under-coverage in remote districts. This agent automates that optimization.

## What It Does

The ResourceAllocation agent takes three inputs and produces one output:

**Inputs:**
1. **Demand assessment** — affected districts with population, severity (1-5), and coordinates
2. **Resource inventory** — available NDRF battalions (with base locations), shelters (with capacity/occupancy), and relief kits
3. **Constraints** — max shelter occupancy (90%), max travel time, minimum coverage per district

**Output:** An optimized deployment plan with:
- NDRF battalion assignments to districts (with distance and ETA)
- Shelter population assignments (respecting capacity limits)
- Relief kit distribution (proportional to severity × population)
- Human-readable recommendations via LLM

## How It Works

### LangGraph State Machine

```
assess_demand → inventory_resources → optimize → format_plan → END
```

1. **assess_demand** — Extracts affected districts from the A2A task payload. Each district has name, state, population, severity, and coordinates.

2. **inventory_resources** — Parses available NDRF battalions, shelters, and relief kits from the payload.

3. **optimize** — Runs OR-Tools MIP (Mixed Integer Programming) solver:
   - **Decision variables**: Battalion-to-district assignment (binary), shelter population allocation (integer), relief kit distribution (integer)
   - **Objective**: Maximize severity-weighted coverage
   - **Constraints**: Each battalion assigned to at most one district; shelter occupancy ≤ 90%; total relief kits ≤ available; minimum kits per district
   - **Fallback**: If OR-Tools fails or isn't installed, a greedy heuristic sorts districts by severity and allocates nearest resources first

4. **format_plan** — Uses LLM (standard tier) to convert the optimization result into a human-readable deployment plan with district-level recommendations.

### Key Algorithms

**Haversine Distance**: Used to estimate travel distance between resource bases and affected districts. Avoids dependency on mapping APIs. Formula: `2R × arcsin(√(sin²(Δlat/2) + cos(lat1)cos(lat2)sin²(Δlon/2)))`.

**OR-Tools MIP Solver**: SCIP backend with 5-second timeout. The problem is formulated as a maximization of severity-weighted resource coverage subject to capacity and availability constraints. Runs in <200ms for typical scenarios (2-10 districts, 2-5 battalions, 5-20 shelters).

**Greedy Fallback**: When OR-Tools is unavailable: sort districts by severity descending, assign nearest available battalion to each, distribute relief kits proportionally to severity weight.

### Confidence Scoring

- **optimal** (SCIP found proven optimal) → 0.9
- **feasible** (valid but not proven optimal) → 0.75
- **greedy_heuristic** (fallback used) → 0.6
- **failed/unknown** → 0.4

## How It Connects

### Upstream Dependencies
- **S7.1 BaseAgent** — Inherits LangGraph state machine, LLM Router, A2A, health checks
- **S6.5 Census** — District population and vulnerability data used for demand assessment

### Downstream Consumers
- **S7.2 Orchestrator** — Delegates resource allocation tasks during ACTIVE_RESPONSE and RECOVERY phases
- **S7.9 Agent Integration** — End-to-end test will verify ResourceAllocation receives tasks from Orchestrator and returns deployment plans
- **S8.7 Resource Efficiency Metric** — Benchmark evaluates this agent's allocation quality against OR-Tools baseline

### Lateral Connections
- **S7.3 SituationSense** — Provides severity scores and affected area data that feed into demand assessment
- **S7.7 InfraStatus** — Damaged roads/infrastructure would constrain resource deployment (future enhancement)
- **S7.4 PredictiveRisk** — Risk forecasts could trigger pre-positioning of resources before disaster hits

## Interview Q&A

**Q: Why OR-Tools over a commercial solver like Gurobi?**
A: OR-Tools is Apache 2.0 licensed and free. Gurobi is commercial ($10K+/year). For our problem size (≤50 districts, ≤20 battalions, ≤100 shelters), SCIP in OR-Tools solves to optimality in <200ms. Commercial solvers only matter at scale (1000+ variables with complex nonlinear constraints).

**Q: Why MIP instead of LP?**
A: Battalion assignments are binary (either a battalion goes to a district or it doesn't — you can't send half a battalion). Relief kit allocation must be integer (you can't give 3.7 kits). MIP (Mixed Integer Programming) handles both binary and integer variables natively. LP would give fractional solutions that need rounding, which can violate constraints.

**Q: How does rolling re-optimization work?**
A: The agent is stateless per invocation. When the situation changes (new damage reports, resources arriving, shelter filling up), the Orchestrator sends a new task with updated data. The agent re-runs the full optimization with current state. This is simpler and more reliable than maintaining incremental solver state across calls.

**Q: What's the worst case for the greedy heuristic vs. optimal?**
A: Greedy can be up to 2x suboptimal in adversarial cases (all resources clustered near low-severity areas while high-severity areas are far away). In practice, the gap is <15% because NDRF bases are strategically distributed across India. The greedy fallback exists for robustness, not as a primary strategy.
