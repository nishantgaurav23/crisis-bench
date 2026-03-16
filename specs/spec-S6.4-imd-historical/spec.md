# Spec S6.4: IMD Historical Gridded Data Ingestion

**Status**: done

## Overview
Ingest IMD historical gridded rainfall and temperature data into PostgreSQL/PostGIS using `imdlib`. Downloads binary IMD data, converts to xarray datasets, and stores daily district-level aggregated time-series in the `imd_observations` table.

## Depends On
- **S2.2** (PostgreSQL/PostGIS async connection) — `src/shared/db.py`

## Location
- `src/data/ingest/imd.py`
- `tests/unit/test_imd_ingest.py`

## Feature
IMD gridded data ingestion pipeline:
1. **Download**: Use `imdlib` to download IMD binary gridded data (rainfall, temperature) for specified year ranges
2. **Parse**: Convert binary IMD data to xarray Datasets via `imdlib.open_data()`
3. **Aggregate**: Extract daily values at grid points, optionally aggregate to district level using PostGIS spatial join
4. **Store**: Bulk insert into `imd_observations` partitioned table via asyncpg `COPY`
5. **Query**: Provide async query helpers for time-range + spatial lookups

## Data Source
- **IMD Gridded Rainfall**: 0.25° × 0.25° daily grid (1901-present), ~2 GB
- **IMD Gridded Temperature**: 1° × 1° daily grid (min/max), ~500 MB
- Both downloaded as binary files via `imdlib` Python package (public, no auth)

## Pydantic Models

### IMDGridPoint
- `latitude`: float — grid point latitude
- `longitude`: float — grid point longitude
- `date`: date — observation date
- `rainfall_mm`: float | None — daily rainfall in mm
- `temperature_min_c`: float | None — daily min temperature °C
- `temperature_max_c`: float | None — daily max temperature °C

### IMDDownloadConfig
- `variable`: Literal["rain", "tmin", "tmax"] — which variable to download
- `start_year`: int — start year (1901+)
- `end_year`: int — end year
- `output_dir`: Path — directory to store downloaded files

### IMDIngestionReport
- `variable`: str — variable ingested
- `year_range`: tuple[int, int]
- `grid_points_processed`: int
- `rows_inserted`: int
- `errors`: list[str]

## Key Functions

### `download_imd_data(config: IMDDownloadConfig) -> Path`
Download IMD binary data using imdlib. Returns path to downloaded file.

### `parse_imd_data(file_path: Path, variable: str) -> xarray.Dataset`
Open downloaded IMD binary file as xarray Dataset using imdlib.

### `extract_grid_points(ds: xarray.Dataset, variable: str, year: int) -> list[IMDGridPoint]`
Extract daily values from xarray Dataset into list of IMDGridPoint models.

### `async bulk_insert_observations(points: list[IMDGridPoint], batch_size: int = 5000) -> int`
Bulk insert grid point data into imd_observations table. Returns count inserted.

### `async query_rainfall_timeseries(lat: float, lon: float, start_date: date, end_date: date, radius_km: float = 25.0) -> list[Record]`
Query rainfall time-series near a point within date range.

### `async query_district_rainfall(district_id: int, start_date: date, end_date: date) -> list[Record]`
Query rainfall aggregated for a district using spatial join.

### `async ingest_imd_variable(config: IMDDownloadConfig) -> IMDIngestionReport`
Full pipeline: download → parse → extract → bulk insert. Processes year by year.

## TDD Notes

### Tests to Write First
1. **test_imd_grid_point_validation** — Pydantic model validates lat/lon ranges, date, values
2. **test_download_config_validation** — validates year range, variable enum
3. **test_parse_imd_data** — mock imdlib.open_data, verify xarray Dataset structure
4. **test_extract_grid_points_rainfall** — extract from mock xarray, verify IMDGridPoint list
5. **test_extract_grid_points_temperature** — extract tmin/tmax from mock xarray
6. **test_extract_grid_points_handles_nan** — NaN values become None
7. **test_bulk_insert_observations** — mock asyncpg, verify batch INSERT
8. **test_bulk_insert_empty_list** — returns 0, no DB calls
9. **test_query_rainfall_timeseries** — mock DB, verify spatial + temporal query
10. **test_query_district_rainfall** — mock DB, verify spatial join query
11. **test_ingest_pipeline_full** — mock download + parse + insert, verify report
12. **test_ingest_pipeline_download_error** — imdlib download fails, DataError raised
13. **test_ingestion_report_model** — verify report model fields

### What to Mock
- `imdlib.get_data()` — download function
- `imdlib.open_data()` — file parser
- `asyncpg` pool/connection — all DB operations
- File system operations (Path.exists, etc.)

## Outcomes
- [ ] IMDGridPoint, IMDDownloadConfig, IMDIngestionReport models defined and validated
- [ ] Download function wraps imdlib with error handling
- [ ] Parse function converts binary to xarray Dataset
- [ ] Extract function converts xarray to list of Pydantic models
- [ ] Bulk insert uses parameterized queries with batching
- [ ] Spatial + temporal query helpers for downstream agents (PredictiveRisk S7.4)
- [ ] Full pipeline orchestrates download → parse → extract → insert
- [ ] All tests pass with mocked external dependencies
- [ ] ruff lint clean
