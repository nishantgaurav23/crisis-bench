"""ResourceAllocation agent — OR-Tools optimization for disaster resource deployment (S7.5).

Optimizes NDRF/SDRF battalion deployment, shelter matching, and relief supply
distribution across affected districts using constrained optimization.

Runs on the **standard** tier (DeepSeek Chat, $0.28/M tokens).

LangGraph nodes:
    assess_demand -> inventory_resources -> optimize_allocation -> format_plan -> END

Usage::

    agent = ResourceAllocation()
    await agent.start()
"""

from __future__ import annotations

import json
import math
import time
from typing import Any

from langgraph.graph import END, StateGraph

from src.agents.base import AgentState, BaseAgent
from src.protocols.a2a.schemas import A2AAgentCard
from src.routing.llm_router import LLMTier
from src.shared.models import AgentType
from src.shared.telemetry import get_logger

logger = get_logger("agent.resource_allocation")

# =============================================================================
# Constants
# =============================================================================

_EARTH_RADIUS_KM = 6371.0
_DEFAULT_MAX_SHELTER_PCT = 90
_SOLVER_TIMEOUT_MS = 5000

# =============================================================================
# Haversine Distance
# =============================================================================


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance between two points in kilometers.

    Args:
        lat1, lon1: First point coordinates (degrees).
        lat2, lon2: Second point coordinates (degrees).

    Returns:
        Distance in kilometers.
    """
    if lat1 == lat2 and lon1 == lon2:
        return 0.0

    rlat1, rlon1 = math.radians(lat1), math.radians(lon1)
    rlat2, rlon2 = math.radians(lat2), math.radians(lon2)

    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1

    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return _EARTH_RADIUS_KM * c


# =============================================================================
# OR-Tools Optimization
# =============================================================================


def optimize_allocation(
    *,
    districts: list[dict],
    battalions: list[dict],
    shelters: list[dict],
    relief_kits: int,
    max_shelter_pct: int = _DEFAULT_MAX_SHELTER_PCT,
) -> dict[str, Any]:
    """Run OR-Tools MIP solver to allocate resources to affected districts.

    Args:
        districts: Affected districts with name, severity, population, lat, lon.
        battalions: Available NDRF battalions with name, base_lat, base_lon, strength.
        shelters: Available shelters with name, capacity, current_occupancy, lat, lon.
        relief_kits: Total relief kits available.
        max_shelter_pct: Maximum shelter occupancy percentage.

    Returns:
        Dict with solver_status, ndrf_deployments, shelter_assignments,
        supply_distribution, and solve_time_ms.
    """
    if not districts:
        return {
            "solver_status": "no_resources",
            "ndrf_deployments": [],
            "shelter_assignments": [],
            "supply_distribution": [],
            "solve_time_ms": 0,
        }

    has_any_resource = bool(battalions) or bool(shelters) or relief_kits > 0
    if not has_any_resource:
        return {
            "solver_status": "no_resources",
            "ndrf_deployments": [],
            "shelter_assignments": [],
            "supply_distribution": [],
            "solve_time_ms": 0,
        }

    try:
        from ortools.linear_solver import pywraplp
    except ImportError:
        logger.warning("ortools_not_available, falling back to greedy")
        return greedy_allocate(
            districts=districts,
            battalions=battalions,
            shelters=shelters,
            relief_kits=relief_kits,
            max_shelter_pct=max_shelter_pct,
        )

    start_time = time.monotonic()
    solver = pywraplp.Solver.CreateSolver("SCIP")
    if solver is None:
        return greedy_allocate(
            districts=districts,
            battalions=battalions,
            shelters=shelters,
            relief_kits=relief_kits,
            max_shelter_pct=max_shelter_pct,
        )

    solver.SetTimeLimit(_SOLVER_TIMEOUT_MS)

    n_districts = len(districts)
    n_battalions = len(battalions)
    n_shelters = len(shelters)

    # Severity weights for prioritization (higher severity = higher weight)
    severity_weights = [d.get("severity", 1) for d in districts]
    total_severity = sum(severity_weights) or 1

    # --- Decision Variables ---

    # Battalion assignment: x[b][d] = 1 if battalion b assigned to district d
    x_bn = {}
    for b in range(n_battalions):
        for d in range(n_districts):
            x_bn[b, d] = solver.IntVar(0, 1, f"bn_{b}_{d}")

    # Shelter assignment: x_sh[s][d] = people from district d assigned to shelter s
    x_sh = {}
    for s in range(n_shelters):
        for d in range(n_districts):
            avail = int(shelters[s]["capacity"] * max_shelter_pct / 100) - shelters[s].get(
                "current_occupancy", 0
            )
            avail = max(0, avail)
            x_sh[s, d] = solver.IntVar(0, avail, f"sh_{s}_{d}")

    # Relief kit distribution: x_rk[d] = kits allocated to district d
    x_rk = {}
    for d in range(n_districts):
        x_rk[d] = solver.IntVar(0, relief_kits, f"rk_{d}")

    # --- Constraints ---

    # Each battalion assigned to at most one district
    for b in range(n_battalions):
        solver.Add(sum(x_bn[b, d] for d in range(n_districts)) <= 1)

    # Shelter capacity: total people assigned to shelter s <= available capacity
    for s in range(n_shelters):
        avail = int(shelters[s]["capacity"] * max_shelter_pct / 100) - shelters[s].get(
            "current_occupancy", 0
        )
        avail = max(0, avail)
        solver.Add(sum(x_sh[s, d] for d in range(n_districts)) <= avail)

    # Total relief kits cannot exceed available
    solver.Add(sum(x_rk[d] for d in range(n_districts)) <= relief_kits)

    # Every district must get at least 1 relief kit if kits are available
    if relief_kits > 0 and n_districts > 0:
        min_per_district = max(1, relief_kits // (n_districts * 10))
        for d in range(n_districts):
            solver.Add(x_rk[d] >= min_per_district)

    # --- Objective: maximize weighted coverage ---
    objective = solver.Objective()

    # Maximize: severity-weighted battalion assignments (high priority)
    for b in range(n_battalions):
        for d in range(n_districts):
            weight = severity_weights[d] * 100  # High weight for battalion placement
            objective.SetCoefficient(x_bn[b, d], weight)

    # Maximize: severity-weighted shelter assignments
    for s in range(n_shelters):
        for d in range(n_districts):
            weight = severity_weights[d]
            objective.SetCoefficient(x_sh[s, d], weight)

    # Maximize: severity-weighted relief kit distribution
    for d in range(n_districts):
        weight = severity_weights[d] / total_severity
        objective.SetCoefficient(x_rk[d], weight)

    objective.SetMaximization()

    status = solver.Solve()
    solve_time = (time.monotonic() - start_time) * 1000

    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        return greedy_allocate(
            districts=districts,
            battalions=battalions,
            shelters=shelters,
            relief_kits=relief_kits,
            max_shelter_pct=max_shelter_pct,
        )

    # --- Extract Solution ---
    ndrf_deployments = []
    for b in range(n_battalions):
        for d in range(n_districts):
            if x_bn[b, d].solution_value() > 0.5:
                dist_info = districts[d]
                bn_info = battalions[b]
                dist_km = haversine_distance(
                    bn_info["base_lat"],
                    bn_info["base_lon"],
                    dist_info.get("lat", 0),
                    dist_info.get("lon", 0),
                )
                eta_hours = round(dist_km / 80, 1)  # ~80 km/h avg speed
                ndrf_deployments.append({
                    "battalion": bn_info["name"],
                    "deploy_to": dist_info["name"],
                    "distance_km": round(dist_km, 1),
                    "eta_hours": eta_hours,
                    "strength": bn_info.get("strength", 0),
                })

    shelter_assignments = []
    for s in range(n_shelters):
        total_assigned = 0
        for d in range(n_districts):
            assigned = int(x_sh[s, d].solution_value())
            total_assigned += assigned
        if total_assigned > 0:
            shelter_assignments.append({
                "shelter": shelters[s]["name"],
                "assigned_people": total_assigned,
                "remaining_capacity": int(
                    shelters[s]["capacity"] * max_shelter_pct / 100
                ) - shelters[s].get("current_occupancy", 0) - total_assigned,
            })

    supply_distribution = []
    for d in range(n_districts):
        kits = int(x_rk[d].solution_value())
        if kits > 0:
            supply_distribution.append({
                "district": districts[d]["name"],
                "relief_kits": kits,
            })

    solver_status = "optimal" if status == pywraplp.Solver.OPTIMAL else "feasible"

    return {
        "solver_status": solver_status,
        "ndrf_deployments": ndrf_deployments,
        "shelter_assignments": shelter_assignments,
        "supply_distribution": supply_distribution,
        "solve_time_ms": round(solve_time, 1),
        "objective_value": round(solver.Objective().Value(), 2),
    }


# =============================================================================
# Greedy Fallback
# =============================================================================


def greedy_allocate(
    *,
    districts: list[dict],
    battalions: list[dict],
    shelters: list[dict],
    relief_kits: int,
    max_shelter_pct: int = _DEFAULT_MAX_SHELTER_PCT,
) -> dict[str, Any]:
    """Greedy heuristic fallback when OR-Tools is unavailable or fails.

    Strategy: sort districts by severity (descending), allocate resources
    proportionally to severity.
    """
    if not districts:
        return {
            "solver_status": "greedy_heuristic",
            "ndrf_deployments": [],
            "shelter_assignments": [],
            "supply_distribution": [],
            "solve_time_ms": 0,
        }

    sorted_districts = sorted(districts, key=lambda d: d.get("severity", 0), reverse=True)
    severity_weights = [d.get("severity", 1) for d in sorted_districts]
    total_severity = sum(severity_weights) or 1

    # Assign battalions to highest-severity districts
    ndrf_deployments = []
    available_battalions = list(battalions)
    for dist in sorted_districts:
        if not available_battalions:
            break
        # Find nearest battalion
        best_bn = min(
            available_battalions,
            key=lambda bn: haversine_distance(
                bn["base_lat"], bn["base_lon"],
                dist.get("lat", 0), dist.get("lon", 0),
            ),
        )
        dist_km = haversine_distance(
            best_bn["base_lat"], best_bn["base_lon"],
            dist.get("lat", 0), dist.get("lon", 0),
        )
        ndrf_deployments.append({
            "battalion": best_bn["name"],
            "deploy_to": dist["name"],
            "distance_km": round(dist_km, 1),
            "eta_hours": round(dist_km / 80, 1),
            "strength": best_bn.get("strength", 0),
        })
        available_battalions.remove(best_bn)

    # Assign shelters to nearest districts
    shelter_assignments = []
    for shelter in shelters:
        avail = int(shelter["capacity"] * max_shelter_pct / 100) - shelter.get(
            "current_occupancy", 0
        )
        if avail > 0:
            shelter_assignments.append({
                "shelter": shelter["name"],
                "assigned_people": avail,
                "remaining_capacity": 0,
            })

    # Distribute relief kits proportionally to severity
    supply_distribution = []
    remaining_kits = relief_kits
    for i, dist in enumerate(sorted_districts):
        share = int(relief_kits * severity_weights[i] / total_severity)
        share = min(share, remaining_kits)
        if share > 0:
            supply_distribution.append({
                "district": dist["name"],
                "relief_kits": share,
            })
            remaining_kits -= share

    # Distribute any remaining kits to highest-severity district
    if remaining_kits > 0 and supply_distribution:
        supply_distribution[0]["relief_kits"] += remaining_kits

    return {
        "solver_status": "greedy_heuristic",
        "ndrf_deployments": ndrf_deployments,
        "shelter_assignments": shelter_assignments,
        "supply_distribution": supply_distribution,
        "solve_time_ms": 0,
    }


# =============================================================================
# ResourceAllocation State
# =============================================================================


class ResourceAllocationState(AgentState, total=False):
    """Extended state for ResourceAllocation agent."""

    demand_assessment: list[dict]
    resource_inventory: dict
    optimization_result: dict
    allocation_plan: dict


# =============================================================================
# ResourceAllocation Agent
# =============================================================================


class ResourceAllocation(BaseAgent):
    """Resource allocation agent using OR-Tools optimization.

    Optimizes NDRF/SDRF deployment, shelter matching, and relief supply
    distribution across affected districts.
    """

    def __init__(self, *, settings=None) -> None:
        from src.shared.config import get_settings

        super().__init__(
            agent_id="resource_allocation",
            agent_type=AgentType.RESOURCE_ALLOCATION,
            llm_tier=LLMTier.STANDARD,
            settings=settings or get_settings(),
        )

    def get_system_prompt(self) -> str:
        return (
            "You are the ResourceAllocation agent for India's CRISIS-BENCH disaster "
            "response system. Your role is to optimize deployment of disaster response "
            "resources across affected districts.\n\n"
            "Resources you manage:\n"
            "- NDRF/SDRF battalion deployment to affected districts\n"
            "- Evacuation shelter matching and capacity management\n"
            "- Relief supply (food kits, medical kits, tarpaulins) distribution\n\n"
            "Your optimization approach:\n"
            "1. Assess demand: district population, severity, vulnerability\n"
            "2. Inventory resources: available battalions, shelters, supplies\n"
            "3. Run constrained optimization (OR-Tools MIP solver)\n"
            "4. Generate actionable deployment plan with ETAs\n\n"
            "Constraints you enforce:\n"
            "- Shelter occupancy never exceeds 90% capacity\n"
            "- Every affected district receives minimum coverage\n"
            "- NDRF battalions assigned based on proximity and severity\n"
            "- Relief kits distributed proportionally to population × severity\n\n"
            "Always output structured JSON with deployment details and ETAs.\n\n"
            "NDMA Standard Operating Procedures:\n"
            "Follow NDMA resource deployment guidelines: NDRF has 16 battalions "
            "(12 regular + 4 CBRN), each with 1,149 personnel and 18 specialist teams. "
            "SDRF is state-level first responder. Deployment priority: life-saving first "
            "(golden hour), then relief, then restoration. Standard kit: rescue boats, "
            "life jackets, medical supplies, communication equipment. Pre-positioning "
            "within 12h of warning. Use district-wise shelter capacity data. Factor in: "
            "road accessibility, helicopter landing zones, naval staging areas. Include "
            "cost estimates in INR crores."
        )

    def get_agent_card(self) -> A2AAgentCard:
        return A2AAgentCard(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            name="ResourceAllocation",
            description=(
                "Optimizes disaster resource deployment: NDRF battalions, "
                "shelter matching, relief supply distribution using OR-Tools"
            ),
            capabilities=[
                "optimization",
                "ndrf_deployment",
                "shelter_matching",
                "supply_distribution",
                "rolling_reoptimization",
            ],
            llm_tier=self.llm_tier,
        )

    def build_graph(self) -> StateGraph:
        graph = StateGraph(ResourceAllocationState)

        graph.add_node("assess_demand", self._assess_demand)
        graph.add_node("inventory_resources", self._inventory_resources)
        graph.add_node("optimize", self._optimize)
        graph.add_node("format_plan", self._format_plan)

        graph.set_entry_point("assess_demand")
        graph.add_edge("assess_demand", "inventory_resources")
        graph.add_edge("inventory_resources", "optimize")
        graph.add_edge("optimize", "format_plan")
        graph.add_edge("format_plan", END)

        return graph

    # -----------------------------------------------------------------
    # Graph Nodes
    # -----------------------------------------------------------------

    async def _assess_demand(self, state: ResourceAllocationState) -> dict[str, Any]:
        """Extract affected districts and severity from task payload."""
        task = state.get("task", {})
        affected = task.get("affected_districts", [])

        demand = []
        for d in affected:
            demand.append({
                "name": d.get("name", "Unknown"),
                "state": d.get("state", ""),
                "population": d.get("population", 0),
                "severity": d.get("severity", 1),
                "lat": d.get("lat", 0.0),
                "lon": d.get("lon", 0.0),
            })

        logger.info(
            "demand_assessed",
            district_count=len(demand),
            trace_id=state.get("trace_id", ""),
        )

        return {"demand_assessment": demand}

    async def _inventory_resources(self, state: ResourceAllocationState) -> dict[str, Any]:
        """Build resource inventory from task payload."""
        task = state.get("task", {})
        resources = task.get("available_resources", {})

        inventory = {
            "ndrf_battalions": resources.get("ndrf_battalions", []),
            "shelters": resources.get("shelters", []),
            "relief_kits": resources.get("relief_kits", 0),
        }

        logger.info(
            "resources_inventoried",
            battalions=len(inventory["ndrf_battalions"]),
            shelters=len(inventory["shelters"]),
            relief_kits=inventory["relief_kits"],
            trace_id=state.get("trace_id", ""),
        )

        return {"resource_inventory": inventory}

    async def _optimize(self, state: ResourceAllocationState) -> dict[str, Any]:
        """Run OR-Tools optimization or greedy fallback."""
        demand = state.get("demand_assessment", [])
        inventory = state.get("resource_inventory", {})
        task = state.get("task", {})
        constraints = task.get("constraints", {})

        max_pct = constraints.get("shelter_max_occupancy_pct", _DEFAULT_MAX_SHELTER_PCT)

        try:
            result = optimize_allocation(
                districts=demand,
                battalions=inventory.get("ndrf_battalions", []),
                shelters=inventory.get("shelters", []),
                relief_kits=inventory.get("relief_kits", 0),
                max_shelter_pct=max_pct,
            )
        except Exception as e:
            logger.error(
                "optimization_failed",
                error=str(e),
                trace_id=state.get("trace_id", ""),
            )
            result = greedy_allocate(
                districts=demand,
                battalions=inventory.get("ndrf_battalions", []),
                shelters=inventory.get("shelters", []),
                relief_kits=inventory.get("relief_kits", 0),
                max_shelter_pct=max_pct,
            )

        logger.info(
            "optimization_complete",
            solver_status=result.get("solver_status"),
            deployments=len(result.get("ndrf_deployments", [])),
            solve_time_ms=result.get("solve_time_ms", 0),
            trace_id=state.get("trace_id", ""),
        )

        return {"optimization_result": result}

    async def _format_plan(self, state: ResourceAllocationState) -> dict[str, Any]:
        """Use LLM to generate human-readable allocation plan."""
        opt_result = state.get("optimization_result", {})
        demand = state.get("demand_assessment", [])
        trace_id = state.get("trace_id", "")

        prompt = (
            "Generate a concise, actionable resource allocation plan based on these results. "
            "Include district-level recommendations with ETAs and priorities.\n\n"
            f"Affected Districts: {json.dumps(demand)}\n\n"
            f"Optimization Result: {json.dumps(opt_result)}\n\n"
            "Output valid JSON with keys: recommendations (string), summary (string)."
        )

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        resp = await self.reason(messages, trace_id=trace_id)

        try:
            plan = json.loads(resp.content)
        except (json.JSONDecodeError, TypeError):
            plan = {"recommendations": resp.content, "summary": "Plan generated"}

        # Compute confidence based on solver status
        solver_status = opt_result.get("solver_status", "")
        if solver_status == "optimal":
            confidence = 0.9
        elif solver_status == "feasible":
            confidence = 0.75
        elif solver_status == "greedy_heuristic":
            confidence = 0.6
        else:
            confidence = 0.4

        return {
            "reasoning": json.dumps(plan),
            "confidence": confidence,
            "artifacts": [{
                "type": "allocation_plan",
                "optimization_result": opt_result,
                "plan": plan,
            }],
            "allocation_plan": plan,
        }


__all__ = [
    "ResourceAllocation",
    "ResourceAllocationState",
    "greedy_allocate",
    "haversine_distance",
    "optimize_allocation",
]
