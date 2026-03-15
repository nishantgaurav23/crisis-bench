# Spec S5.6 — Explanation: NASA FIRMS Fire MCP Server

## Why This Spec Exists

India faces two critical fire-related challenges: (1) devastating forest fires in states like Uttarakhand, Himachal Pradesh, and the Western Ghats, and (2) seasonal crop residue burning in Punjab/Haryana that causes Delhi's annual air quality crisis. For disaster response, detecting active fires within hours (not days) is essential for evacuation planning, resource deployment, and public health alerts.

NASA FIRMS (Fire Information for Resource Management System) is the **only free, global, near-real-time fire detection dataset**. It provides data from VIIRS (375m resolution, ~4 hour latency) and MODIS (1km resolution, ~3 hour latency) satellites. By wrapping FIRMS as an MCP server, our agents can query active fire data using a standard tool interface without knowing anything about the FIRMS API specifics.

## What It Does

`FIRMSServer` extends `BaseMCPServer` and exposes 5 tools:

| Tool | Purpose |
|------|---------|
| `get_active_fires` | All fire detections in India bounding box (6-37N, 68-98E) |
| `get_fires_by_region` | Fires in a custom lat/lon bounding box |
| `get_high_confidence_fires` | Only high-confidence detections (filters out false positives) |
| `get_fire_detail` | Fires near a specific lat/lon point within a radius (haversine filtering) |
| `get_fire_summary` | Aggregated stats: total fires, confidence breakdown, day/night split, max FRP |

Each fire detection is normalized to a consistent JSON structure with: latitude, longitude, brightness temperature, Fire Radiative Power (FRP), confidence level, satellite source, acquisition date/time, day/night flag, and pixel dimensions.

## How It Works

1. **URL Construction**: FIRMS uses a path-based API (`/api/area/json/{MAP_KEY}/{source}/{bbox}/{days}`) rather than query parameters. The server builds URLs dynamically from the source, bounding box, and time window.

2. **Bounding Box Format**: FIRMS expects `W,S,E,N` (lon_min, lat_min, lon_max, lat_max) — the `_bbox_str()` helper formats this correctly.

3. **Confidence Filtering**: VIIRS uses categorical confidence ("low", "nominal", "high"). `get_high_confidence_fires` fetches all data then client-side filters to "high" only — reducing false positives from sun glint, volcanic activity, or industrial heat sources.

4. **Proximity Search**: `get_fire_detail` builds a generous bounding box around the target point (~1.5x the radius), fetches fires, then applies haversine distance filtering for precise radius-based results. This avoids downloading the entire India dataset when looking at a specific location.

5. **Authentication**: Uses the free `NASA_FIRMS_KEY` (MAP_KEY) from settings, passed via the URL path (not headers). Registration is free at the FIRMS website.

## How It Connects

- **Depends on**: S4.4 (MCP base framework) — inherits HTTP client, retries, rate limiting, error mapping, Prometheus metrics
- **Used by**: S7.3 (SituationSense agent) — fuses fire data with weather and other hazard data for multi-hazard situational awareness
- **Used by**: S7.4 (PredictiveRisk agent) — tracks fire spread patterns and combines with wind data from IMD for fire spread prediction
- **Complements**: S5.1 (IMD) — wind speed/direction data + fire detections = fire spread modeling
- **Complements**: S5.5 (Bhuvan) — satellite imagery + FIRMS thermal anomalies = validated fire confirmation

## Interview Talking Points

**Q: Why does FIRMS use VIIRS and MODIS — what's the difference?**
A: VIIRS (375m resolution, Suomi-NPP/NOAA-20 satellites) detects smaller fires than MODIS (1km resolution, Terra/Aqua satellites). VIIRS has a 375m spatial resolution vs MODIS's 1km, so it can detect fires 1/7th the size. However, MODIS has a 20+ year archive (since 2000) vs VIIRS (since 2012), so for historical analysis MODIS is better. We default to `VIIRS_SNPP_NRT` for near-real-time because of its superior spatial resolution.

**Q: What is Fire Radiative Power (FRP) and why track it?**
A: FRP measures the rate of radiant energy released by a fire in megawatts. It correlates with fire intensity, rate of biomass combustion, and smoke emission rates. A high FRP fire (>50 MW) is likely a large, intense wildfire requiring immediate response, while low FRP (<5 MW) might be agricultural burning. Our summary tool reports max FRP to help agents prioritize the most dangerous active fires.

**Q: Why client-side filtering instead of server-side for confidence?**
A: The FIRMS API doesn't support confidence-level filtering as a query parameter — it returns all detections in the bounding box. We fetch the full dataset (typically a few hundred to few thousand records for India per day) and filter in-memory. This is fast (<1ms for filtering) and avoids making multiple API calls. The trade-off is slightly more bandwidth usage, but for JSON records it's negligible.
