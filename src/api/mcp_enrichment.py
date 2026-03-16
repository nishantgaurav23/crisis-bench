"""Live MCP data enrichment for benchmark runs (S9.1 integration).

Lazily initializes the 4 free MCP servers (IMD, SACHET, USGS, OSM) and
provides functions to enrich benchmark scenarios with real-time data from
Indian government and open data sources.

All external calls are wrapped in try/except with a 10-second timeout.
If ANY server fails, the benchmark continues normally with original data.

Usage::

    live_data = await enrich_scenario_with_live_data(scenario)
    enriched_desc = enrich_event_with_context(event, scenario, live_data)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from mcp.types import TextContent

_log = logging.getLogger("mcp_enrichment")

# ---------------------------------------------------------------------------
# MCP call timeout (seconds)
# ---------------------------------------------------------------------------
_MCP_CALL_TIMEOUT = 10.0

# Max chars per live-data source to avoid token bloat
_MAX_CHARS_PER_SOURCE = 500

# ---------------------------------------------------------------------------
# Lazy singleton MCP server instances
# ---------------------------------------------------------------------------
_imd_server = None
_sachet_server = None
_usgs_server = None
_osm_server = None


def _get_imd_server():
    """Return cached IMDServer singleton."""
    global _imd_server
    if _imd_server is None:
        try:
            from src.protocols.mcp.imd_server import IMDServer
            _imd_server = IMDServer()
        except Exception as exc:
            _log.warning("Could not initialize IMDServer: %s", exc)
    return _imd_server


def _get_sachet_server():
    """Return cached SACHETServer singleton."""
    global _sachet_server
    if _sachet_server is None:
        try:
            from src.protocols.mcp.sachet_server import SACHETServer
            _sachet_server = SACHETServer()
        except Exception as exc:
            _log.warning("Could not initialize SACHETServer: %s", exc)
    return _sachet_server


def _get_usgs_server():
    """Return cached USGSServer singleton."""
    global _usgs_server
    if _usgs_server is None:
        try:
            from src.protocols.mcp.usgs_server import USGSServer
            _usgs_server = USGSServer()
        except Exception as exc:
            _log.warning("Could not initialize USGSServer: %s", exc)
    return _usgs_server


def _get_osm_server():
    """Return cached OSMOverpassServer singleton."""
    global _osm_server
    if _osm_server is None:
        try:
            from src.protocols.mcp.osm_server import OSMOverpassServer
            _osm_server = OSMOverpassServer()
        except Exception as exc:
            _log.warning("Could not initialize OSMOverpassServer: %s", exc)
    return _osm_server


# ---------------------------------------------------------------------------
# State/district → approximate centroid mapping for OSM queries
# ---------------------------------------------------------------------------
_STATE_CENTROIDS: dict[str, tuple[float, float]] = {
    "Andhra Pradesh": (15.9129, 79.7400),
    "Arunachal Pradesh": (28.2180, 94.7278),
    "Assam": (26.2006, 92.9376),
    "Bihar": (25.0961, 85.3131),
    "Chhattisgarh": (21.2787, 81.8661),
    "Delhi": (28.7041, 77.1025),
    "Goa": (15.2993, 74.1240),
    "Gujarat": (22.2587, 71.1924),
    "Haryana": (29.0588, 76.0856),
    "Himachal Pradesh": (31.1048, 77.1734),
    "Jharkhand": (23.6102, 85.2799),
    "Karnataka": (15.3173, 75.7139),
    "Kerala": (10.8505, 76.2711),
    "Madhya Pradesh": (22.9734, 78.6569),
    "Maharashtra": (19.7515, 75.7139),
    "Manipur": (24.6637, 93.9063),
    "Meghalaya": (25.4670, 91.3662),
    "Mizoram": (23.1645, 92.9376),
    "Nagaland": (26.1584, 94.5624),
    "Odisha": (20.9517, 85.0985),
    "Punjab": (31.1471, 75.3412),
    "Rajasthan": (27.0238, 74.2179),
    "Sikkim": (27.5330, 88.5122),
    "Tamil Nadu": (11.1271, 78.6569),
    "Telangana": (18.1124, 79.0193),
    "Tripura": (23.9408, 91.9882),
    "Uttar Pradesh": (26.8467, 80.9462),
    "Uttarakhand": (30.0668, 79.0193),
    "West Bengal": (22.9868, 87.8550),
    "Jammu and Kashmir": (33.7782, 76.5762),
    "Ladakh": (34.1526, 77.5771),
    "Puducherry": (11.9416, 79.8083),
    "Chandigarh": (30.7333, 76.7794),
    "Andaman and Nicobar": (11.7401, 92.6586),
    "Lakshadweep": (10.5667, 72.6417),
}

# Categories that trigger IMD weather data
_WEATHER_CATEGORIES = {"cyclone", "monsoon_flood", "urban_waterlogging", "landslide"}

# Categories that trigger USGS earthquake data
_EARTHQUAKE_CATEGORIES = {"earthquake"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_text(text_contents: list[TextContent]) -> str:
    """Extract raw text from MCP TextContent list."""
    parts = []
    for tc in text_contents:
        if hasattr(tc, "text"):
            parts.append(tc.text)
    return " ".join(parts)


def _truncate(text: str, max_chars: int = _MAX_CHARS_PER_SOURCE) -> str:
    """Truncate text to max_chars, appending '...' if truncated."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


async def _safe_call(coro, label: str) -> str:
    """Await a coroutine with timeout and error handling. Returns text or ''."""
    try:
        result = await asyncio.wait_for(coro, timeout=_MCP_CALL_TIMEOUT)
        if isinstance(result, list):
            return _extract_text(result)
        return str(result) if result else ""
    except asyncio.TimeoutError:
        _log.warning("MCP call '%s' timed out after %.0fs", label, _MCP_CALL_TIMEOUT)
        return ""
    except Exception as exc:
        _log.warning("MCP call '%s' failed: %s", label, exc)
        return ""


def _get_scenario_centroid(
    scenario: dict[str, Any],
) -> tuple[float, float] | None:
    """Extract approximate lat/lon for a scenario from its affected states."""
    states = scenario.get("affected_states") or []
    for state in states:
        centroid = _STATE_CENTROIDS.get(state)
        if centroid is not None:
            return centroid
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def enrich_scenario_with_live_data(
    scenario: dict[str, Any],
) -> dict[str, str]:
    """Fetch live data from free MCP servers relevant to the scenario.

    Called ONCE at the start of a benchmark run. Results are cached and
    reused for every event in that run.

    Returns a dict with keys:
        - live_sachet_alerts
        - live_imd_data
        - live_usgs_earthquakes
        - live_osm_infrastructure

    Each value is a truncated string (max ~500 chars). Empty string if
    the source was not applicable or failed.
    """
    category = (scenario.get("category") or "").lower()
    states = scenario.get("affected_states") or []
    centroid = _get_scenario_centroid(scenario)

    live_data: dict[str, str] = {
        "live_sachet_alerts": "",
        "live_imd_data": "",
        "live_usgs_earthquakes": "",
        "live_osm_infrastructure": "",
    }

    # Collect async tasks to run in parallel
    tasks: dict[str, Any] = {}

    # SACHET: always fetch for any scenario (all-hazard alert system)
    sachet = _get_sachet_server()
    if sachet is not None:
        state_filter = states[0] if states else ""
        tasks["live_sachet_alerts"] = _safe_call(
            sachet.get_active_alerts(state=state_filter),
            f"sachet_alerts({state_filter})",
        )

    # IMD: fetch cyclone info for weather-related categories
    if category in _WEATHER_CATEGORIES:
        imd = _get_imd_server()
        if imd is not None:
            tasks["live_imd_data"] = _safe_call(
                imd.get_cyclone_info(),
                "imd_cyclone_info",
            )

    # USGS: fetch for earthquake scenarios
    if category in _EARTHQUAKE_CATEGORIES:
        usgs = _get_usgs_server()
        if usgs is not None:
            tasks["live_usgs_earthquakes"] = _safe_call(
                usgs.get_recent_earthquakes(min_magnitude=2.5, hours=72),
                "usgs_recent_earthquakes",
            )

    # OSM: fetch hospitals + shelters for any scenario with location data
    if centroid is not None:
        osm = _get_osm_server()
        if osm is not None:
            lat, lon = centroid

            async def _fetch_osm_combined(
                server, lat: float, lon: float,
            ) -> str:
                """Fetch hospitals and shelters, combine results."""
                hospitals_raw = await _safe_call(
                    server.find_hospitals(lat=lat, lon=lon, radius_km=15.0),
                    f"osm_hospitals({lat:.2f},{lon:.2f})",
                )
                shelters_raw = await _safe_call(
                    server.find_shelters(lat=lat, lon=lon, radius_km=15.0),
                    f"osm_shelters({lat:.2f},{lon:.2f})",
                )
                parts = []
                if hospitals_raw:
                    parts.append(f"Hospitals: {hospitals_raw}")
                if shelters_raw:
                    parts.append(f"Shelters: {shelters_raw}")
                return " | ".join(parts)

            tasks["live_osm_infrastructure"] = _fetch_osm_combined(osm, lat, lon)

    # Execute all tasks in parallel
    if tasks:
        keys = list(tasks.keys())
        coros = [tasks[k] for k in keys]
        results = await asyncio.gather(*coros, return_exceptions=True)

        for key, result in zip(keys, results):
            if isinstance(result, Exception):
                _log.warning(
                    "MCP enrichment task '%s' raised: %s", key, result,
                )
                live_data[key] = ""
            elif isinstance(result, str):
                live_data[key] = _truncate(result)
            else:
                live_data[key] = ""

    # Log summary
    populated = [k for k, v in live_data.items() if v]
    _log.info(
        "MCP enrichment complete: %d/%d sources returned data (%s)",
        len(populated),
        len(tasks),
        ", ".join(populated) if populated else "none",
    )

    return live_data


def enrich_event_with_context(
    event: dict[str, Any],
    scenario: dict[str, Any],
    live_data: dict[str, str],
) -> str:
    """Enrich an event description with pre-fetched live MCP data.

    Appends a concise ``[LIVE DATA]`` section to the original event
    description. If no live data is available, returns the original
    description unchanged.

    Args:
        event: Single event dict with 'description' key.
        scenario: The parent scenario dict.
        live_data: Dict returned by ``enrich_scenario_with_live_data()``.

    Returns:
        Enriched description string.
    """
    original = event.get("description", "")
    category = (scenario.get("category") or "").lower()

    sections: list[str] = []

    # SACHET alerts — always relevant
    if live_data.get("live_sachet_alerts"):
        sections.append(f"SACHET Alerts: {live_data['live_sachet_alerts']}")

    # IMD data — weather categories only
    if category in _WEATHER_CATEGORIES and live_data.get("live_imd_data"):
        sections.append(f"IMD Weather: {live_data['live_imd_data']}")

    # USGS earthquakes — earthquake category only
    if category in _EARTHQUAKE_CATEGORIES and live_data.get("live_usgs_earthquakes"):
        sections.append(f"USGS Seismic: {live_data['live_usgs_earthquakes']}")

    # OSM infrastructure — always relevant if available
    if live_data.get("live_osm_infrastructure"):
        sections.append(f"Nearby Infra: {live_data['live_osm_infrastructure']}")

    if not sections:
        return original

    live_block = " | ".join(sections)
    # Cap the total live block to avoid excessive token usage
    live_block = _truncate(live_block, max_chars=800)

    return f"{original}\n\n[LIVE DATA] {live_block}"


__all__ = [
    "enrich_scenario_with_live_data",
    "enrich_event_with_context",
]
