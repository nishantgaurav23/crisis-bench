# Spec S5.5 Explanation: ISRO Bhuvan MCP Server

## Why This Spec Exists

India's disaster response needs geospatial intelligence — village-level geocoding, satellite imagery layers, land use classification, flood inundation maps, and administrative boundaries. ISRO's Bhuvan platform is the authoritative source for Indian satellite-derived geospatial data, covering everything from village-level geocoding (600K+ villages) to NDEM flood maps and LULC classification. This MCP server makes Bhuvan data available to agents through the standard MCP tool interface.

## What It Does

`BhuvanServer` wraps 5 Bhuvan API endpoints as MCP tools:

1. **`geocode_village`** — Resolves village names to lat/lng + census code. Critical for translating location mentions in alerts/social media into coordinates.
2. **`get_satellite_layers`** — Lists available satellite data layers (disaster, agriculture, urban, etc.). Lets agents discover what imagery is available.
3. **`get_lulc_data`** — Land Use / Land Cover classification for a radius around a point. Tells agents whether an area is built-up, cropland, water, forest — crucial for impact assessment.
4. **`get_flood_layers`** — NDEM flood inundation maps by state. Historical and near-real-time flood extent data from ISRO's National Database for Emergency Management.
5. **`get_admin_boundary`** — Administrative boundary GeoJSON at state/district/block level. Used for spatial queries and map rendering.

## How It Works

- Extends `BaseMCPServer` (S4.4), inheriting HTTP client management, retries, rate limiting, error mapping, and Prometheus metrics.
- **Token injection**: Overrides `api_get()` to inject the `BHUVAN_TOKEN` as a query parameter on every request. The token is read from environment config (`settings.BHUVAN_TOKEN`) — never hardcoded.
- **Rate limit**: 30 RPM to respect ISRO's free-tier servers.
- **Error handling**: 401 (expired token), 404, 500, and timeouts all map to `MCPError`/`ExternalAPIError` via the base class.

## How It Connects

| Component | Relationship |
|-----------|-------------|
| **S4.4 MCP Base** | Extends `BaseMCPServer` — inherits HTTP, retries, rate limiting, metrics |
| **S7.3 SituationSense** | Will use `geocode_village` + `get_flood_layers` for situational awareness |
| **S7.4 PredictiveRisk** | Will use `get_admin_boundary` + `get_lulc_data` for probabilistic risk maps |
| **S7.5 ResourceAllocation** | Will use `get_admin_boundary` for population-based displacement estimation |
| **S7.7 InfraStatus** | Will use `get_satellite_layers` for infrastructure damage assessment |
| **S3.4 GeoMap** | Admin boundary GeoJSON feeds the Leaflet map's district overlays |

## Interview Talking Points

**Q: Why wrap Bhuvan in an MCP server instead of calling the API directly from agents?**
A: Separation of concerns. The MCP server handles auth token management (daily refresh), rate limiting (30 RPM), error mapping, and response normalization. Agents don't need to know about Bhuvan's auth scheme — they just call `geocode_village("Paradip", "Odisha")` and get structured data back. This also means we can mock the entire MCP server in tests without mocking HTTP calls.

**Q: How does the token injection work?**
A: Bhuvan uses query-parameter auth (`?token=...`) rather than header-based auth. We override `api_get()` to call a `_inject_token()` helper that merges the token into every request's params. The token comes from environment config — zero hardcoded secrets.

**Q: What's the NDEM and why is it important for flood response?**
A: NDEM (National Database for Emergency Management) is ISRO's disaster-specific data repository. It contains historical flood inundation maps derived from satellite imagery (IRS-R2, Cartosat). When a flood alert comes in, agents can query NDEM for past flood extents in the same region — "In 2024, the Mahanadi flood inundated 1,250 sq km affecting 4 districts" — providing immediate historical context for resource pre-positioning.
