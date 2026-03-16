# S6.4 Implementation Checklist

## Phase 1: Red (Write Failing Tests)
- [x] Create `tests/unit/test_imd_ingest.py`
- [x] Write 23 test cases covering models, download, parse, extract, insert, query, pipeline
- [x] All tests fail (no implementation yet)

## Phase 2: Green (Implement)
- [x] Create `src/data/ingest/imd.py`
- [x] Implement Pydantic models: IMDGridPoint, IMDDownloadConfig, IMDIngestionReport
- [x] Implement `download_imd_data()` with imdlib wrapper
- [x] Implement `parse_imd_data()` with imdlib.open_data
- [x] Implement `extract_grid_points()` for rainfall and temperature
- [x] Implement `async bulk_insert_observations()` with batch INSERT
- [x] Implement `async query_rainfall_timeseries()` with spatial + temporal query
- [x] Implement `async query_district_rainfall()` with spatial join
- [x] Implement `async ingest_imd_variable()` full pipeline
- [x] All 23 tests pass

## Phase 3: Refactor
- [x] ruff lint clean
- [x] Review code for clarity and consistency with project patterns
- [x] Verify all exports in `__all__`
