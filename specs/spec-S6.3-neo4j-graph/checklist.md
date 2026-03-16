# Checklist S6.3: Neo4j Infrastructure Dependency Graph

## Phase 1: Test Setup (Red)
- [x] Create `tests/unit/test_infra_graph.py`
- [x] Write all 21 test cases (all must fail initially)
- [x] Run tests — confirm all RED

## Phase 2: Neo4j Connection (Green)
- [x] Implement `get_neo4j_driver()` with config from CrisisSettings
- [x] Implement `health_check()` with DataError on failure
- [x] Implement `close()` for clean shutdown
- [x] Tests pass: health check success/failure

## Phase 3: Models + Schema (Green)
- [x] Define Pydantic models for all 8 node types
- [x] Define `CascadeResult` model
- [x] Implement `init_schema()` with constraints and indexes
- [x] Tests pass: schema creation, idempotency, models

## Phase 4: Seed Data (Green)
- [x] Create seed data for 5 Indian cities
- [x] Implement `seed_city()` and `seed_all()`
- [x] Tests pass: node/edge creation, all cities

## Phase 5: Query + Analysis (Green)
- [x] Implement `simulate_failure()` with cascading traversal
- [x] Implement `get_downstream_impacts()` and `get_upstream_dependencies()`
- [x] Implement district/state/status queries
- [x] Implement `update_node_status()`
- [x] Tests pass: cascading failure, queries, status updates

## Phase 6: Refactor + Lint
- [x] Run `ruff check --fix` — zero errors
- [x] Run `ruff format` — clean
- [x] All 21 tests pass
- [x] Code review: async patterns, error handling, no hardcoded secrets
