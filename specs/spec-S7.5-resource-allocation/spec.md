# Spec S7.5 — ResourceAllocation Agent

**Status**: done
**Depends On**: S7.1 (BaseAgent), S6.5 (Census + admin boundaries)
**Location**: `src/agents/resource_allocation.py`
**Test**: `tests/unit/test_resource_allocation.py`

---

## Overview

ResourceAllocation is a specialist agent that optimizes the deployment of disaster response resources (NDRF/SDRF battalions, shelters, relief supplies) across affected districts. It uses OR-Tools for constrained optimization and the LLM for natural language constraint formulation and result interpretation.

Runs on **standard** tier (DeepSeek Chat, $0.28/M tokens) — resource optimization decisions require moderate reasoning.

## Architecture

### LangGraph State Machine

```
assess_demand → inventory_resources → optimize_allocation → format_plan → END
```

**Nodes:**
1. **assess_demand** — Extract affected districts, population counts, severity from task payload. Query census data for demographics.
2. **inventory_resources** — Build available resource inventory (NDRF battalions, shelters, supplies) from task payload.
3. **optimize_allocation** — Run OR-Tools MIP solver to minimize total response time subject to capacity, distance, and availability constraints.
4. **format_plan** — Use LLM to generate human-readable allocation plan with district-level recommendations.

### OR-Tools Optimization Model

**Decision Variables:**
- `x[i][j]` = number of units of resource `i` allocated to district `j` (integer)

**Objective:** Minimize total weighted response time (distance × urgency)

**Constraints:**
- Each resource cannot exceed its available quantity
- Each shelter cannot exceed 90% capacity
- Every affected district must receive minimum coverage
- Total deployed resources ≤ total available
- Priority weighting: higher urgency districts get more resources

### Inputs (via A2A task payload)

```json
{
  "affected_districts": [
    {"name": "Puri", "state": "Odisha", "population": 1698730, "severity": 4}
  ],
  "available_resources": {
    "ndrf_battalions": [
      {"name": "12 Bn NDRF", "base": "Arakkonam", "strength": 1000, "status": "standby"}
    ],
    "shelters": [
      {"name": "Govt School Puri", "capacity": 500, "occupancy": 100, "lat": 19.8, "lon": 85.8}
    ],
    "relief_kits": 5000
  },
  "constraints": {
    "max_travel_hours": 12,
    "shelter_max_occupancy_pct": 90,
    "min_coverage_per_district": 0.5
  }
}
```

### Outputs

```json
{
  "allocation_plan": {
    "ndrf_deployments": [{"battalion": "12 Bn", "deploy_to": "Puri", "eta_hours": 4}],
    "shelter_assignments": [{"shelter": "Govt School Puri", "assigned_population": 350}],
    "supply_distribution": [{"district": "Puri", "relief_kits": 2000}]
  },
  "optimization_metrics": {
    "solver_status": "optimal",
    "objective_value": 42.5,
    "solve_time_ms": 150,
    "total_population_covered": 150000,
    "coverage_pct": 88.3
  },
  "recommendations": "Deploy 12 Bn NDRF to Puri district within 4 hours..."
}
```

## Key Design Decisions

1. **OR-Tools over PuLP**: OR-Tools provides both LP and constraint programming; we use the MIP solver (`pywraplp`) for integer allocation variables.
2. **Haversine distance**: Approximate travel distance between resource bases and districts using haversine formula (no external API needed).
3. **Rolling re-optimization**: The agent can be called repeatedly as the situation evolves — each call takes current state and re-optimizes.
4. **Graceful fallback**: If OR-Tools fails or times out (>5s), fall back to a greedy heuristic (sort by urgency, allocate proportionally).

## TDD Plan

### Test Cases

1. **test_resource_allocation_init** — Agent initializes with correct type, tier, ID
2. **test_agent_card** — Agent card has correct capabilities
3. **test_system_prompt** — System prompt mentions optimization, NDRF, shelters
4. **test_build_graph** — Graph compiles and has correct nodes
5. **test_haversine_distance** — Distance calculation between known Indian cities
6. **test_assess_demand_extracts_districts** — Demand assessment extracts district info from payload
7. **test_assess_demand_empty_payload** — Handles empty/missing district data gracefully
8. **test_inventory_resources_parses_payload** — Resource inventory correctly parsed
9. **test_optimize_allocation_basic** — OR-Tools produces a valid allocation for simple case
10. **test_optimize_allocation_respects_capacity** — Shelter assignments don't exceed 90% capacity
11. **test_optimize_allocation_covers_all_districts** — Every affected district gets some allocation
12. **test_optimize_allocation_empty_resources** — Handles zero available resources gracefully
13. **test_greedy_fallback** — Greedy heuristic runs when OR-Tools fails
14. **test_format_plan_calls_llm** — Format node calls LLM and produces structured output
15. **test_full_graph_execution** — End-to-end graph run with mocked LLM produces valid state
16. **test_rolling_reoptimization** — Calling agent twice with updated state produces different plans

## Non-Goals

- Real-time vehicle routing (VRP) — that's a Phase 9 optimization
- Integration with real NDRF deployment APIs — we use mock data
- Road network modeling — we use haversine approximation
