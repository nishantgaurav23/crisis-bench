# Spec S5.3 — MCP: USGS Earthquake Server

**Phase**: 5 (MCP Data Servers)
**Depends On**: S4.4 (MCP server base framework)
**Location**: `src/protocols/mcp/usgs_server.py`
**Tests**: `tests/unit/test_mcp_usgs.py`
**Status**: done

---

## Summary

MCP server wrapping the USGS FDSNWS (Federation of Digital Seismograph Networks Web Services) API to provide earthquake data for the India region. Exposes tools for querying recent earthquakes, filtering by magnitude/depth/region, getting earthquake detail, and retrieving a summary of seismic activity relevant to India.

## Why

India spans seismic zones II–V, with the Himalayan belt (Zone V) being one of the most seismically active regions globally. The USGS FDSNWS API is the standard, free, no-auth-required source for global seismological data. This MCP server filters earthquakes to the India region and presents them in a format agents can consume for disaster response.

## USGS FDSNWS API

- **Base URL**: `https://earthquake.usgs.gov/fdsnws/event/1`
- **Auth**: None required (public API)
- **Format**: GeoJSON (default)
- **Rate Limit**: None specified (but be polite — ~60 RPM reasonable)
- **Key endpoint**: `/query` with parameters:
  - `format=geojson`
  - `starttime`, `endtime` (ISO8601)
  - `minlatitude`, `maxlatitude`, `minlongitude`, `maxlongitude` (bounding box)
  - `minmagnitude`, `maxmagnitude`
  - `mindepth`, `maxdepth`
  - `orderby` (time, magnitude, etc.)
  - `limit` (max results)

### India Bounding Box

- Latitude: 6.0°N to 37.0°N
- Longitude: 68.0°E to 98.0°E
- Covers mainland India + Andaman & Nicobar + buffer for nearby seismicity

## MCP Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `get_recent_earthquakes` | `min_magnitude: float = 2.5`, `hours: int = 24` | Recent earthquakes in India region above magnitude threshold |
| `get_earthquakes_by_region` | `min_lat: float`, `max_lat: float`, `min_lon: float`, `max_lon: float`, `min_magnitude: float = 2.5`, `days: int = 7` | Earthquakes in a custom bounding box |
| `get_significant_earthquakes` | `days: int = 30` | Significant (M5.0+) earthquakes near India |
| `get_earthquake_detail` | `event_id: str` | Full detail for a specific earthquake event |
| `get_seismic_summary` | `days: int = 7` | Summary: counts by magnitude range, max magnitude, most active region |

## Response Normalization

USGS returns GeoJSON FeatureCollection. Each feature is normalized to:

```json
{
  "event_id": "us7000xxxx",
  "magnitude": 5.2,
  "magnitude_type": "mww",
  "place": "45km NNE of Uttarkashi, India",
  "time": "2026-03-15T10:30:00Z",
  "depth_km": 10.0,
  "latitude": 30.73,
  "longitude": 78.44,
  "tsunami_alert": false,
  "felt_reports": 150,
  "alert_level": "green",
  "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000xxxx"
}
```

## Outcomes

1. `USGSServer` extends `BaseMCPServer` with 5 registered tools
2. All tools return `list[TextContent]` with normalized JSON
3. India bounding box applied by default, configurable for custom regions
4. No API key required — fully free
5. Response normalization extracts key fields from GeoJSON features
6. Polite rate limiting at 60 RPM
7. All external HTTP calls mocked in tests

## TDD Notes

- **Red**: Write tests for init, all 5 tools with mock GeoJSON responses, error handling
- **Green**: Implement USGSServer following IMDServer/SACHETServer pattern
- **Refactor**: Clean up, ensure ruff compliance
