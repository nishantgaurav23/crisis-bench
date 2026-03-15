# S5.3 Implementation Checklist

## Phase 1: Red (Tests First)
- [x] Write test fixtures (settings, server instance, mock GeoJSON data)
- [x] Write TestUSGSServerInit (name, base_url, no auth, rate limit, tools registered)
- [x] Write TestGetRecentEarthquakes (returns data, default params, custom magnitude)
- [x] Write TestGetEarthquakesByRegion (custom bounding box, params passed correctly)
- [x] Write TestGetSignificantEarthquakes (M5.0+ filter)
- [x] Write TestGetEarthquakeDetail (found, not found)
- [x] Write TestGetSeismicSummary (structure, counts)
- [x] Write TestNormalizeFeature (field extraction from GeoJSON)
- [x] Write TestErrorHandling (timeout, 500, empty response)
- [x] Verify all tests FAIL (Red)

## Phase 2: Green (Implement)
- [x] Create `src/protocols/mcp/usgs_server.py`
- [x] Implement `USGSServer.__init__` with tool registration
- [x] Implement `_normalize_feature()` for GeoJSON → flat dict
- [x] Implement `get_recent_earthquakes()`
- [x] Implement `get_earthquakes_by_region()`
- [x] Implement `get_significant_earthquakes()`
- [x] Implement `get_earthquake_detail()`
- [x] Implement `get_seismic_summary()`
- [x] Verify all tests PASS (Green)

## Phase 3: Refactor
- [x] Run ruff — fix any lint issues
- [x] Verify all tests still pass
- [x] Check no secrets / no paid API dependencies
