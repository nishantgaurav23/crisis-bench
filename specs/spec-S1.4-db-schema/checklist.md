# Spec S1.4: Database Schema — Implementation Checklist

## Phase 1: Red (Write Failing Tests)
- [x] Create `tests/unit/test_db_schema.py`
- [x] Test: SQL file exists and is non-empty
- [x] Test: PostGIS extension creation
- [x] Test: india_disaster_type ENUM with 10 values
- [x] Test: All 8 tables present (states, districts, disasters, imd_observations, cwc_river_levels, agent_decisions, benchmark_scenarios, evaluation_runs)
- [x] Test: Column validation for each table
- [x] Test: Foreign key constraints
- [x] Test: Spatial GiST indexes on geometry columns
- [x] Test: Partitioning on time-series tables
- [x] Test: Default partitions exist
- [x] Test: Idempotency (IF NOT EXISTS)
- [x] Test: No hardcoded secrets
- [x] All tests FAIL (Red) ✅

## Phase 2: Green (Implement)
- [x] Create `scripts/init_db.sql`
- [x] Enable PostGIS extension
- [x] Create india_disaster_type ENUM
- [x] Create states table
- [x] Create districts table with FK to states
- [x] Create disasters table
- [x] Create imd_observations partitioned table + default partition
- [x] Create cwc_river_levels partitioned table + default partition
- [x] Create agent_decisions table with FK to disasters
- [x] Create benchmark_scenarios table
- [x] Create evaluation_runs table with FK to benchmark_scenarios
- [x] Create spatial GiST indexes
- [x] Create BTREE indexes
- [x] All tests PASS (Green) ✅

## Phase 3: Refactor
- [x] Review SQL for consistency
- [x] Run ruff on test file
- [x] Verify idempotency
- [x] Final test run ✅
