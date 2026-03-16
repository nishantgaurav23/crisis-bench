# Spec S5.5: ISRO Bhuvan MCP Server

**Status**: done

**Phase**: 5 — MCP Data Servers
**Depends On**: S4.4 (MCP server base framework)
**Location**: `src/protocols/mcp/bhuvan_server.py`
**Tests**: `tests/unit/test_mcp_bhuvan.py`

---

## Overview

MCP server wrapping ISRO Bhuvan REST and OGC APIs. Provides village geocoding, satellite layer metadata, Land Use / Land Cover (LULC) data, NDEM (National Database for Emergency Management) flood map layers, and administrative boundary queries as MCP tools that agents can invoke.

Bhuvan is ISRO's geospatial platform (bhuvan-app1.nrsc.gov.in) providing free access to Indian satellite imagery, village-level geocoding, DEM data, and disaster-specific layers (flood inundation, landslide susceptibility). Access requires free registration and a daily-refreshing API token passed via query parameter.

## Bhuvan API Endpoints

| Tool | Bhuvan Endpoint | Purpose |
|------|----------------|---------|
| `geocode_village` | `/api/village?name={name}&state={state}` | Village-level geocoding (lat/lng + census code) |
| `get_satellite_layers` | `/api/layers?category={category}` | List available satellite data layers by category |
| `get_lulc_data` | `/api/lulc?lat={lat}&lng={lng}&radius_km={radius_km}` | Land Use / Land Cover classification for an area |
| `get_flood_layers` | `/api/ndem/flood?state={state}` | NDEM flood inundation map layers for a state |
| `get_admin_boundary` | `/api/admin?level={level}&code={code}` | Administrative boundary GeoJSON (state/district/block) |

## Outcomes

1. `BhuvanServer` extends `BaseMCPServer` with 5 tools registered
2. All tools are async and return `list[TextContent]` via `normalize_json()`
3. API base URL: `https://bhuvan-app1.nrsc.gov.in`
4. Authentication: API token via query parameter `token={BHUVAN_TOKEN}`
5. Rate limit: 30 RPM (conservative, respects ISRO's free-tier servers)
6. Token read from `settings.BHUVAN_TOKEN` (environment variable)
7. All external HTTP calls are mocked in tests
8. GeoJSON geometry preserved in boundary responses
9. LULC categories follow ISRO's classification scheme

## TDD Notes

- Mock all `httpx.AsyncClient.request` calls — never hit real Bhuvan API
- Test tool registration (all 5 tools present)
- Test each tool with mock responses containing realistic Indian geographic data
- Test error handling: timeouts, 404s, 401 (expired token), server errors
- Test token injection into query params
- Test `create_server()` factory function
