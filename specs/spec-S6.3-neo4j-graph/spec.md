# Spec S6.3: Neo4j Infrastructure Dependency Graph

**Phase**: 6 — Data Pipeline
**Location**: `src/data/ingest/infra_graph.py`
**Depends On**: S1.3 (Environment Config)
**Status**: done

---

## Overview

Build a Neo4j infrastructure dependency graph for major Indian cities. This models power grids, telecom towers, water treatment plants, hospitals, roads, and districts as nodes with dependency edges (POWERS, DEPENDS_ON, SERVES, ACCESSIBLE_VIA, ENABLES). The InfraStatus agent (S7.7) will query this graph to predict cascading failures during disasters — e.g., "power grid down → which hospitals lose power → which districts lose water?"

## Requirements

### R1: Neo4j Connection Management
- Async-compatible Neo4j driver using `neo4j` Python package with config from `CrisisSettings` (NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
- `get_neo4j_driver()` — return a cached async driver instance
- `health_check()` — verify Neo4j is reachable, return bool
- `close()` — clean shutdown of driver
- Raise `DataError` from `src/shared/errors.py` when Neo4j is unreachable

### R2: Node Types (Labels)
Define Pydantic models and Neo4j labels for infrastructure nodes:
- **PowerGrid** — `name`, `type` (generation/transmission/distribution), `state`, `capacity_mw`, `status` (operational/damaged/destroyed)
- **TelecomTower** — `name`, `operator`, `backup_hours` (battery backup), `type` (4G/5G), `state`, `status`
- **MobileNetwork** — `name`, `operator`, `coverage_type`, `state`, `status`
- **WaterTreatment** — `name`, `capacity_mld` (million liters/day), `state`, `status`
- **Hospital** — `name`, `beds`, `type` (government/private), `district`, `state`, `status`
- **Road** — `name`, `type` (highway/state/district), `state`, `status`
- **District** — `name`, `state`, `population`
- **Shelter** — `name`, `capacity`, `type` (cyclone/flood/general), `district`, `state`, `status`

### R3: Relationship Types (Edges)
- **POWERS** — PowerGrid → TelecomTower, WaterTreatment, Hospital, Shelter
- **DEPENDS_ON** — Hospital → PowerGrid, WaterTreatment; WaterTreatment → PowerGrid
- **ENABLES** — TelecomTower → MobileNetwork
- **SERVES** — WaterTreatment → District; Hospital → District
- **ACCESSIBLE_VIA** — Hospital → Road; Shelter → Road
- All edges can carry metadata: `priority` (critical/high/medium), `backup_available` (bool)

### R4: Schema Initialization
- `init_schema()` — create uniqueness constraints and indexes:
  - Uniqueness: each node type by `(name, state)` composite
  - Indexes: `status` on all node types, `state` on all, `district` on Hospital/Shelter
- Idempotent — safe to call multiple times

### R5: Seed Data for Major Indian Cities
- Pre-built infrastructure data for 5 cities: Mumbai, Chennai, Kolkata, Bhubaneswar, Guwahati
- Each city: 2-4 power grids, 3-5 telecom towers, 1-2 water treatment plants, 3-5 hospitals, 2-4 roads, 1-2 shelters, 1 district
- Total: ~100 nodes, ~200 edges (within NFR-010 limit of 5000 nodes / 20000 edges)
- `seed_city(city_name)` — load one city's infrastructure
- `seed_all()` — load all 5 cities

### R6: Cascading Failure Analysis
- `simulate_failure(node_name, state)` — mark a node as "damaged"/"destroyed" and traverse downstream dependencies to find all affected nodes
- Returns a list of `CascadeResult` Pydantic models: `affected_node`, `impact_type`, `estimated_recovery_hours`, `path` (the dependency chain)
- Cypher: `MATCH (failed {status:'damaged'})-[:POWERS|DEPENDS_ON*]->(affected) RETURN affected`
- `get_downstream_impacts(node_label, node_name, state)` — find all nodes that depend on a given node (transitively)
- `get_upstream_dependencies(node_label, node_name, state)` — find all nodes a given node depends on

### R7: Graph Query Utilities
- `get_infrastructure_by_district(district_name, state)` — all infra nodes serving a district
- `get_infrastructure_by_state(state)` — all infra nodes in a state
- `get_infrastructure_status_summary()` — count of operational/damaged/destroyed nodes per type
- `update_node_status(node_label, node_name, state, new_status)` — update a node's status

## Outcomes

1. Neo4j driver connects and passes health check
2. Schema constraints and indexes created idempotently
3. 5 Indian cities seeded with realistic infrastructure (~100 nodes, ~200 edges)
4. Cascading failure analysis traverses dependency chains correctly
5. District/state queries return relevant infrastructure
6. Status updates propagate correctly

## TDD Notes

### Test Cases
- `test_neo4j_health_check_success` — mock driver, verify connectivity
- `test_neo4j_health_check_failure` — mock driver error, verify DataError raised
- `test_init_schema_creates_constraints` — verify constraint Cypher executed
- `test_init_schema_idempotent` — calling twice doesn't error
- `test_seed_city_creates_nodes` — seed Mumbai, verify node count
- `test_seed_city_creates_relationships` — verify edges created
- `test_seed_all_creates_all_cities` — 5 cities, ~100 nodes
- `test_simulate_failure_power_grid` — knock out power → hospitals, telecom, water affected
- `test_simulate_failure_no_cascade` — knock out leaf node → no downstream impact
- `test_get_downstream_impacts` — power grid → list of dependent nodes
- `test_get_upstream_dependencies` — hospital → power grid, water treatment
- `test_get_infrastructure_by_district` — returns all infra for Mumbai Suburban
- `test_get_infrastructure_by_state` — returns all Maharashtra infra
- `test_get_infrastructure_status_summary` — counts by type and status
- `test_update_node_status` — change status, verify updated
- `test_node_pydantic_models` — validate node data models
- `test_cascade_result_model` — validate CascadeResult structure

### Mocking Strategy
- Mock `neo4j.AsyncGraphDatabase.driver` for all tests
- Mock session `run()` to return predefined records
- Never hit real Neo4j in tests
