# S6.4 Explanation: IMD Historical Gridded Data Ingestion

## Why This Spec Exists

The PredictiveRisk agent (S7.4) needs historical weather data to find analogous past events ("similar to 2020 Bihar floods"), generate forecasts, and validate predictions against ground truth. IMD (India Meteorological Department) provides the authoritative gridded rainfall and temperature datasets for India — daily observations on a 0.25° grid dating back to 1901. Without this ingestion pipeline, the system has no historical weather context for Indian disaster prediction.

## What It Does

1. **Downloads** IMD binary gridded data (rainfall, min/max temperature) using the `imdlib` Python package — no authentication required, public data
2. **Parses** binary files into `xarray.Dataset` objects with (time, lat, lon) dimensions
3. **Extracts** daily grid point values into validated `IMDGridPoint` Pydantic models, handling NaN values (missing observations) gracefully
4. **Bulk inserts** into the `imd_observations` PostgreSQL table with PostGIS geometry for spatial indexing
5. **Provides query helpers** for downstream agents:
   - `query_rainfall_timeseries()` — find rainfall near a point within a date range (uses `ST_DWithin`)
   - `query_district_rainfall()` — aggregate rainfall by district using spatial join with `districts` geometry

## How It Works

### Data Flow
```
IMD binary files (imdlib.get_data)
  → xarray.Dataset (imdlib.open_data)
    → list[IMDGridPoint] (extract_grid_points)
      → imd_observations table (bulk_insert_observations via asyncpg executemany)
```

### Key Design Decisions
- **imdlib as the download layer**: Standard Python package for IMD data, handles binary format parsing natively
- **xarray for intermediate representation**: Standard scientific Python — supports lazy loading, slicing, and NetCDF compatibility
- **NaN → None conversion**: IMD grids have missing values (ocean, no-station areas). These become `None` in Pydantic models and are filtered before DB insertion
- **Batch inserts via executemany**: Groups rows into configurable batches (default 5000) to balance memory usage and insert performance
- **Station ID convention**: Grid points use `grid_{lat}_{lon}` as station_id, distinguishing them from real-time API observations (`imd_api` source)
- **Source tagging**: All rows tagged with `source='imd_gridded'` to differentiate from real-time `imd_api` data

### Pydantic Models
- `IMDGridPoint` — validates lat/lon ranges, date, and optional rainfall/temperature values
- `IMDDownloadConfig` — validates variable enum (rain/tmin/tmax), year range ordering, output directory
- `IMDIngestionReport` — tracks grid points processed, rows inserted, and errors per run

## How It Connects

### Depends On
- **S2.2** (`src/shared/db.py`) — async PostgreSQL connection pool for bulk inserts and queries
- **S1.4** (`scripts/init_db.sql`) — `imd_observations` partitioned table schema

### Depended On By
- **S7.4** (PredictiveRisk agent) — queries historical rainfall/temperature for forecasting, risk maps, and historical analogies
- **S8.1** (Benchmark scenario models) — ground truth weather data for scenario validation
- **S6.6** (Scenario generator) — historical weather patterns seed synthetic scenario generation

### Data Flow Integration
- Grid data flows into `imd_observations` → PredictiveRisk agent queries via `query_rainfall_timeseries()` / `query_district_rainfall()` → generates forecasts using historical analogies → Orchestrator synthesizes into disaster response plan

## Interview Talking Points

**Q: Why imdlib instead of downloading files manually?**
A: imdlib handles IMD's proprietary binary format (not standard NetCDF), manages year-wise file naming conventions, and provides a clean Python API. Manual download would require reverse-engineering the binary layout — imdlib has already solved this.

**Q: Why store in PostgreSQL instead of keeping as NetCDF files?**
A: PostGIS spatial indexing enables queries like "find all rainfall observations within 25km of this flood zone in the last 7 days" — impossible with flat files without loading everything into memory. The `imd_observations` table is partitioned by time for query performance.

**Q: How do you handle the 0.25° grid resolution mismatch with district boundaries?**
A: The `query_district_rainfall()` function uses a PostGIS spatial join (`ST_Contains`) between grid point locations and district polygon geometries. This aggregates all grid points falling within a district boundary, computing average and max rainfall. The 0.25° resolution (~28km) gives 3-10 grid points per typical Indian district.
