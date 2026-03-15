# S5.4 Implementation Checklist

## Red Phase (Tests First)
- [x] Write `tests/unit/test_mcp_osm.py` with all test cases
- [x] Verify all tests fail (no implementation yet)

## Green Phase (Minimum Implementation)
- [x] Create `src/protocols/mcp/osm_server.py`
- [x] `OSMOverpassServer.__init__` — name, base URL, rate limit, tool registration
- [x] `_build_radius_query()` — Overpass QL for around queries
- [x] `_build_bbox_query()` — Overpass QL for bounding box queries
- [x] `_normalize_elements()` — extract osm_id, name, lat, lon, tags
- [x] `find_hospitals` tool
- [x] `find_shelters` tool
- [x] `find_roads` tool
- [x] `find_bridges` tool
- [x] `find_helipads` tool
- [x] `find_fire_stations` tool
- [x] `find_police_stations` tool
- [x] `create_server()` factory
- [x] All 32 tests pass

## Refactor Phase
- [x] Run ruff — lint clean
- [x] Remove any duplication
- [x] Verify all tests still pass (806 passed, 1 pre-existing failure unrelated)
