# Spec S6.5: Implementation Checklist

## Phase 1: RED — Write Tests First
- [x] Test StateRecord Pydantic validation
- [x] Test DistrictRecord Pydantic validation
- [x] Test CensusIngestionReport model
- [x] Test upsert_states with mocked DB
- [x] Test upsert_districts with mocked DB
- [x] Test vulnerability score computation
- [x] Test spatial query helpers (get_states, get_districts_by_state, etc.)
- [x] Test find_districts_in_polygon SQL
- [x] Test find_nearby_districts SQL
- [x] Test get_population_in_area SQL
- [x] Test full ingestion pipeline
- [x] Test idempotent behavior (error capture)

## Phase 2: GREEN — Implement
- [x] StateRecord + DistrictRecord Pydantic models
- [x] INDIA_STATES hardcoded data (36 states/UTs)
- [x] INDIA_DISTRICTS representative data (100+ districts)
- [x] upsert_states() async function
- [x] upsert_districts() async function
- [x] compute_vulnerability_scores() function
- [x] Spatial query helpers
- [x] ingest_census_data() pipeline
- [x] CensusIngestionReport model
- [x] All 34 tests PASS

## Phase 3: REFACTOR
- [x] ruff lint clean
- [x] Unused import removed (DataError)
- [x] Import ordering fixed
- [x] All exports in __all__
