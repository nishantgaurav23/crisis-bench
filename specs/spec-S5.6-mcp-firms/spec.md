# Spec S5.6 — MCP: NASA FIRMS Fire Server

**Phase**: 5 (MCP Data Servers)
**Depends On**: S4.4 (MCP server base framework)
**Location**: `src/protocols/mcp/firms_server.py`
**Tests**: `tests/unit/test_mcp_firms.py`
**Status**: pending

---

## Summary

MCP server wrapping the NASA FIRMS (Fire Information for Resource Management System) API to provide active fire detection data for the India region. Exposes tools for querying active fires, hotspot clusters, fire alerts by state, and fire activity summaries using VIIRS and MODIS satellite data.

## Why

India experiences devastating wildfires — from Uttarakhand forest fires to crop residue burning in Punjab/Haryana that causes Delhi's annual air quality crisis. NASA FIRMS provides near-real-time (NRT) active fire data from VIIRS (375m resolution) and MODIS (1km resolution) satellites, updated every few hours. This is the only free, global, near-real-time fire detection dataset available. For disaster response, detecting and tracking fires within hours is critical for evacuation planning and resource deployment.

## NASA FIRMS API

- **Base URL**: `https://firms.modaps.eosdis.nasa.gov/api`
- **Auth**: Free API key (MAP_KEY) — register at https://firms.modaps.eosdis.nasa.gov/api/area/
- **Format**: JSON (CSV also available)
- **Rate Limit**: ~100 requests/minute (reasonable use)
- **Key endpoints**:
  - `/area/csv/{MAP_KEY}/{source}/{bbox}/{days}` — fires in bounding box
  - `/country/csv/{MAP_KEY}/{source}/{country_code}/{days}` — fires by country
- **Sources**: `VIIRS_SNPP_NRT`, `VIIRS_NOAA20_NRT`, `MODIS_NRT`
- **Fire data fields**:
  - `latitude`, `longitude` — fire location
  - `brightness` / `bright_ti4` — brightness temperature (K)
  - `scan`, `track` — pixel size (km)
  - `acq_date`, `acq_time` — acquisition date/time
  - `satellite` — VIIRS/MODIS
  - `confidence` — low/nominal/high (VIIRS) or 0-100% (MODIS)
  - `frp` — Fire Radiative Power (MW)
  - `daynight` — D (day) / N (night)

### India Bounding Box

- Latitude: 6.0°N to 37.0°N
- Longitude: 68.0°E to 98.0°E
- Same as USGS server — covers mainland India + Andaman & Nicobar

## MCP Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `get_active_fires` | `source: str = "VIIRS_SNPP_NRT"`, `days: int = 1` | Active fires in India region from VIIRS/MODIS |
| `get_fires_by_region` | `min_lat: float`, `max_lat: float`, `min_lon: float`, `max_lon: float`, `source: str = "VIIRS_SNPP_NRT"`, `days: int = 1` | Fires in a custom bounding box |
| `get_high_confidence_fires` | `source: str = "VIIRS_SNPP_NRT"`, `days: int = 1` | Only high-confidence fire detections in India |
| `get_fire_detail` | `latitude: float`, `longitude: float`, `radius_km: float = 10.0`, `days: int = 2` | Fire detections near a specific location |
| `get_fire_summary` | `days: int = 1` | Summary: total fires, by confidence, max FRP, by day/night |

## Response Normalization

FIRMS returns CSV/JSON with fire detection records. Each record is normalized to:

```json
{
  "latitude": 30.45,
  "longitude": 78.12,
  "brightness": 312.5,
  "frp": 15.3,
  "confidence": "high",
  "satellite": "VIIRS",
  "acq_date": "2026-03-15",
  "acq_time": "0630",
  "daynight": "D",
  "scan": 0.39,
  "track": 0.36
}
```

## Outcomes

1. `FIRMSServer` extends `BaseMCPServer` with 5 registered tools
2. All tools return `list[TextContent]` with normalized JSON
3. India bounding box applied by default, configurable for custom regions
4. API key from settings (`FIRMS_API_KEY` env var)
5. Response normalization extracts key fields from FIRMS records
6. Rate limiting at 100 RPM
7. All external HTTP calls mocked in tests

## TDD Notes

- **Red**: Write tests for init, all 5 tools with mock FIRMS responses, error handling
- **Green**: Implement FIRMSServer following USGS/IMD pattern
- **Refactor**: Clean up, ensure ruff compliance
