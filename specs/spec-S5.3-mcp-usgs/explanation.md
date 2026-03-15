# Spec S5.3 — Explanation: USGS Earthquake MCP Server

## Why This Spec Exists

India spans seismic zones II–V, with the Himalayan belt, Andaman & Nicobar Islands, and the Kutch region being highly seismically active. The USGS FDSNWS API is the international standard for seismological data — free, no-auth, and covers the entire globe. This MCP server makes earthquake data available to agents (especially SituationSense and PredictiveRisk) through a standardized tool interface.

## What It Does

`USGSServer` extends `BaseMCPServer` (S4.4) and exposes 5 MCP tools:

| Tool | Purpose |
|------|---------|
| `get_recent_earthquakes` | Recent earthquakes in India region (configurable magnitude/hours) |
| `get_earthquakes_by_region` | Earthquakes in a custom bounding box (for focused queries) |
| `get_significant_earthquakes` | M5.0+ earthquakes over 30 days (for risk assessment) |
| `get_earthquake_detail` | Full detail for a specific event (for deep analysis) |
| `get_seismic_summary` | Aggregate stats: counts by magnitude range, max event, tsunami alerts |

## How It Works

1. **India Bounding Box** — Default region filter: 6°N–37°N, 68°E–98°E. Covers mainland India, Andaman & Nicobar, and nearby seismicity (e.g., Nepal/Myanmar earthquakes that affect Indian border regions).

2. **GeoJSON Normalization** — USGS returns GeoJSON FeatureCollections. `_normalize_feature()` extracts key fields into a flat dict: event_id, magnitude, coordinates, depth, tsunami alert, felt reports, alert level. Epoch millisecond timestamps are converted to ISO 8601 strings.

3. **Seismic Summary** — Aggregates earthquakes into magnitude ranges (2.0-2.9, 3.0-3.9, 4.0-4.9, 5.0-5.9, 6.0+), finds the maximum magnitude event, and counts tsunami alerts. This gives agents a quick overview of seismic activity without processing individual events.

4. **Rate Limiting** — 60 RPM via `BaseMCPServer`'s sliding window limiter. USGS doesn't specify limits, but this is polite usage.

5. **Error Handling** — Inherits from `BaseMCPServer`: automatic retries on 502/503/504, timeout mapping to `MCPError`, 404 mapping to `MCPError`, 500+ to `ExternalAPIError`.

## How It Connects

- **Depends on**: S4.4 (`BaseMCPServer`) for HTTP client, retries, rate limiting, tool registration, Prometheus metrics
- **Used by**: S7.3 (SituationSense agent) for real-time earthquake detection, S7.4 (PredictiveRisk agent) for seismic risk assessment and aftershock forecasting
- **Follows pattern**: Same architecture as S5.1 (IMD) and S5.2 (SACHET) — subclass `BaseMCPServer`, register tools, normalize responses

## Key Design Decisions

1. **No caching** — Unlike SACHET (60s cache), earthquake data changes infrequently and the USGS API is fast. Caching could mask new events.
2. **Epoch → ISO conversion** — USGS returns timestamps as epoch milliseconds. Converting to ISO 8601 makes the data human-readable for agents and logs.
3. **Magnitude ranges in summary** — Using discrete ranges (2.0-2.9, etc.) rather than continuous values makes the summary immediately actionable for agents deciding urgency levels.

## Interview Talking Points

- **FDSNWS** is an international standard (FDSN = International Federation of Digital Seismograph Networks). Using it demonstrates integration with real geophysical data standards.
- **GeoJSON** is the OGC standard for geospatial data. USGS returns it natively, and it's directly plottable on Leaflet maps (S3.4).
- **India's seismic zones**: Zone V (Himalayan belt, Andaman) = highest risk. The 2001 Gujarat earthquake (M7.7) killed 20,000+. The 2004 Indian Ocean tsunami originated from an M9.1 near Andaman. This data source is critical for disaster preparedness.
