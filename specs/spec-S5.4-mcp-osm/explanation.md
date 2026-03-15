# Spec S5.4 Explanation: OpenStreetMap Overpass MCP Server

## Why This Exists

Disaster response agents need to answer spatial infrastructure questions: "Where are the nearest hospitals?", "Which roads are in this flood zone?", "Are there helipads for aerial rescue?" OpenStreetMap is the best free, open-source infrastructure dataset for India — with excellent coverage of hospitals, roads, bridges, and public buildings. The Overpass API provides a powerful query language for filtering this data by type and geography.

Wrapping Overpass as an MCP server decouples the query syntax, rate limiting, and response normalization from the agents. Agents call `find_hospitals(lat, lon, radius_km)` — they never need to know Overpass QL.

## What It Does

`OSMOverpassServer` extends `BaseMCPServer` with 7 MCP tools:

| Tool | Query Type | Use Case |
|------|-----------|----------|
| `find_hospitals` | Radius (around) | Locate medical facilities for casualty evacuation |
| `find_shelters` | Radius | Find shelters, community halls, schools for displaced populations |
| `find_roads` | Bounding box | Map road network for evacuation routing, flood intersection |
| `find_bridges` | Bounding box | Identify bridge chokepoints vulnerable to flooding |
| `find_helipads` | Radius | Locate aerial rescue landing points |
| `find_fire_stations` | Radius | Find firefighting resources |
| `find_police_stations` | Radius | Locate law enforcement for coordination |

**Radius queries** use `out center` — returns point coordinates (simpler for agents).
**Bounding box queries** use `out geom` — returns full geometry (needed for routing/intersection).

## How It Works

1. **Query Building**: Two static methods (`_build_radius_query`, `_build_bbox_query`) generate Overpass QL with proper tag filters, geographic bounds, JSON output format, and 25s timeout.

2. **Query Execution**: `_run_query()` sends the Overpass QL via POST to `/api/interpreter` (POST avoids URL length limits for complex queries). Uses `BaseMCPServer.api_post()` which provides retries, rate limiting, and error mapping.

3. **Response Normalization**: `_normalize_elements()` converts raw Overpass JSON elements into a consistent format: `{osm_id, osm_type, name, lat, lon, tags, geometry?}`. Handles nodes (direct lat/lon), ways with center point, and ways with full geometry.

4. **Rate Limiting**: Self-imposed 10 RPM via `BaseMCPServer`'s built-in rate limiter. Overpass is a shared community resource — being polite prevents IP bans.

## How It Connects

- **Depends on**: S4.4 (`BaseMCPServer`) — HTTP client, retries, rate limiting, error mapping, Prometheus metrics
- **Used by**: S7.3 (SituationSense) — finds hospitals/shelters near disaster zones; S7.5 (ResourceAllocation) — road network for evacuation routing; S7.7 (InfraStatus) — bridge/infrastructure status during floods
- **Pattern**: Same pattern as `mcp-imd` (S5.1) and `mcp-sachet` (S5.2) — extend `BaseMCPServer`, register tools, normalize responses

## Key Design Decisions

1. **Shelters include schools**: NDMA guidelines specify schools and community halls as primary shelter types during Indian disasters. OSM's `amenity=shelter` alone would miss most actual shelters.

2. **POST not GET**: Overpass QL queries with multiple tag unions and geographic bounds can exceed URL length limits. POST is the standard approach.

3. **Separate radius vs bbox**: Infrastructure points (hospitals, shelters) use radius search — agents specify "within X km of disaster center". Linear features (roads, bridges) use bounding boxes — agents need the full network within an area.

## Interview Q&A

**Q: Why Overpass API instead of downloading the full India OSM extract?**
A: India's OSM extract is ~1.5GB compressed, ~30GB uncompressed. Importing into PostGIS takes hours and requires keeping it updated. Overpass lets us query only what we need, when we need it, with zero storage cost. Trade-off: network dependency and rate limits, but for a disaster response system that queries infrastructure on-demand, this is the right trade-off.

**Q: How does the rate limiting work across multiple agents?**
A: Each `OSMOverpassServer` instance tracks its own call timestamps in a `deque`. Since all agents share the same MCP server process, there's a single rate limiter. The 10 RPM limit is conservative — Overpass can handle more, but during a crisis when agents are making many queries, we want to avoid hitting Overpass's server-side rate limits (which result in IP bans).

**Q: Why normalize OSM elements instead of passing raw JSON?**
A: Raw Overpass JSON has inconsistent structure — nodes have `lat/lon`, ways have `center` or `geometry`, tags are nested differently. Normalization gives agents a consistent interface: every result has `osm_id`, `name`, `lat`, `lon`, `tags`. The agent's LLM doesn't need to handle OSM's structural quirks.
