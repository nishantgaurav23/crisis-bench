"""MCP server for USGS Earthquake FDSNWS API (S5.3).

Wraps the USGS Federation of Digital Seismograph Networks Web Services API
as MCP tools for agent consumption. Provides earthquake data for the India
region (6°N–37°N, 68°E–98°E) with magnitude/depth/region filtering.

The FDSNWS API is free, requires no authentication, and returns GeoJSON.

Usage::

    server = create_server()
    await server.run_stdio()
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from mcp.types import TextContent

from src.protocols.mcp.base import BaseMCPServer
from src.shared.config import CrisisSettings, get_settings

_USGS_BASE_URL = "https://earthquake.usgs.gov/fdsnws/event/1"
_USGS_RATE_LIMIT_RPM = 60

# India bounding box (mainland + Andaman & Nicobar + buffer)
_INDIA_MIN_LAT = 6.0
_INDIA_MAX_LAT = 37.0
_INDIA_MIN_LON = 68.0
_INDIA_MAX_LON = 98.0


class USGSServer(BaseMCPServer):
    """MCP server wrapping USGS FDSNWS earthquake API."""

    def __init__(self, *, settings: CrisisSettings | None = None) -> None:
        super().__init__(
            name="mcp-usgs",
            api_base_url=_USGS_BASE_URL,
            rate_limit_rpm=_USGS_RATE_LIMIT_RPM,
            settings=settings,
        )
        self.register_tool(self.get_recent_earthquakes)
        self.register_tool(self.get_earthquakes_by_region)
        self.register_tool(self.get_significant_earthquakes)
        self.register_tool(self.get_earthquake_detail)
        self.register_tool(self.get_seismic_summary)

    # ------------------------------------------------------------------
    # Response Normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_feature(feature: dict[str, Any]) -> dict[str, Any]:
        """Extract key fields from a USGS GeoJSON Feature."""
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        coords = geom.get("coordinates", [0, 0, 0])

        # Convert epoch ms to ISO string
        time_ms = props.get("time")
        time_str = ""
        if time_ms is not None:
            time_str = datetime.fromtimestamp(
                time_ms / 1000, tz=timezone.utc
            ).isoformat()

        return {
            "event_id": feature.get("id", ""),
            "magnitude": props.get("mag"),
            "magnitude_type": props.get("magType", ""),
            "place": props.get("place", ""),
            "time": time_str,
            "depth_km": coords[2] if len(coords) > 2 else 0.0,
            "latitude": coords[1] if len(coords) > 1 else 0.0,
            "longitude": coords[0] if len(coords) > 0 else 0.0,
            "tsunami_alert": bool(props.get("tsunami", 0)),
            "felt_reports": props.get("felt") or 0,
            "alert_level": props.get("alert"),
            "url": props.get("url", ""),
        }

    def _normalize_collection(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Normalize all features in a GeoJSON FeatureCollection."""
        features = data.get("features", [])
        return [self._normalize_feature(f) for f in features]

    # ------------------------------------------------------------------
    # MCP Tools
    # ------------------------------------------------------------------

    async def get_recent_earthquakes(
        self, min_magnitude: float = 2.5, hours: int = 24,
    ) -> list[TextContent]:
        """Get recent earthquakes in the India region.

        Returns earthquakes above the given magnitude threshold from the
        last N hours within the India bounding box (6°N–37°N, 68°E–98°E).
        """
        start = datetime.now(timezone.utc) - timedelta(hours=hours)
        data = await self.api_get(
            "/query",
            params={
                "format": "geojson",
                "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
                "minmagnitude": min_magnitude,
                "minlatitude": _INDIA_MIN_LAT,
                "maxlatitude": _INDIA_MAX_LAT,
                "minlongitude": _INDIA_MIN_LON,
                "maxlongitude": _INDIA_MAX_LON,
                "orderby": "time",
            },
        )
        return self.normalize_json(self._normalize_collection(data))

    async def get_earthquakes_by_region(
        self,
        min_lat: float,
        max_lat: float,
        min_lon: float,
        max_lon: float,
        min_magnitude: float = 2.5,
        days: int = 7,
    ) -> list[TextContent]:
        """Get earthquakes in a custom bounding box.

        Specify latitude/longitude bounds and time window in days.
        """
        start = datetime.now(timezone.utc) - timedelta(days=days)
        data = await self.api_get(
            "/query",
            params={
                "format": "geojson",
                "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
                "minmagnitude": min_magnitude,
                "minlatitude": min_lat,
                "maxlatitude": max_lat,
                "minlongitude": min_lon,
                "maxlongitude": max_lon,
                "orderby": "time",
            },
        )
        return self.normalize_json(self._normalize_collection(data))

    async def get_significant_earthquakes(
        self, days: int = 30,
    ) -> list[TextContent]:
        """Get significant (M5.0+) earthquakes near India.

        Returns earthquakes of magnitude 5.0 or above within the India
        bounding box over the specified number of days.
        """
        start = datetime.now(timezone.utc) - timedelta(days=days)
        data = await self.api_get(
            "/query",
            params={
                "format": "geojson",
                "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
                "minmagnitude": 5.0,
                "minlatitude": _INDIA_MIN_LAT,
                "maxlatitude": _INDIA_MAX_LAT,
                "minlongitude": _INDIA_MIN_LON,
                "maxlongitude": _INDIA_MAX_LON,
                "orderby": "magnitude",
            },
        )
        return self.normalize_json(self._normalize_collection(data))

    async def get_earthquake_detail(
        self, event_id: str,
    ) -> list[TextContent]:
        """Get full detail for a specific earthquake event by USGS event ID."""
        data = await self.api_get(
            "/query",
            params={
                "format": "geojson",
                "eventid": event_id,
            },
        )
        return self.normalize_json(self._normalize_feature(data))

    async def get_seismic_summary(
        self, days: int = 7,
    ) -> list[TextContent]:
        """Get summary of seismic activity in the India region.

        Returns counts by magnitude range, max magnitude event, and
        tsunami alert count over the specified number of days.
        """
        start = datetime.now(timezone.utc) - timedelta(days=days)
        data = await self.api_get(
            "/query",
            params={
                "format": "geojson",
                "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
                "minmagnitude": 2.0,
                "minlatitude": _INDIA_MIN_LAT,
                "maxlatitude": _INDIA_MAX_LAT,
                "minlongitude": _INDIA_MIN_LON,
                "maxlongitude": _INDIA_MAX_LON,
                "orderby": "magnitude",
            },
        )
        earthquakes = self._normalize_collection(data)

        # Build magnitude range counts
        ranges: dict[str, int] = {
            "2.0-2.9": 0,
            "3.0-3.9": 0,
            "4.0-4.9": 0,
            "5.0-5.9": 0,
            "6.0+": 0,
        }
        max_mag = None
        max_mag_event = None
        tsunami_count = 0

        for eq in earthquakes:
            mag = eq.get("magnitude") or 0
            if max_mag is None or mag > max_mag:
                max_mag = mag
                max_mag_event = eq.get("place", "")

            if mag >= 6.0:
                ranges["6.0+"] += 1
            elif mag >= 5.0:
                ranges["5.0-5.9"] += 1
            elif mag >= 4.0:
                ranges["4.0-4.9"] += 1
            elif mag >= 3.0:
                ranges["3.0-3.9"] += 1
            else:
                ranges["2.0-2.9"] += 1

            if eq.get("tsunami_alert"):
                tsunami_count += 1

        return self.normalize_json({
            "total_earthquakes": len(earthquakes),
            "by_magnitude_range": ranges,
            "max_magnitude": max_mag,
            "max_magnitude_event": max_mag_event,
            "tsunami_alerts": tsunami_count,
            "period_days": days,
        })


def create_server(*, settings: CrisisSettings | None = None) -> USGSServer:
    """Factory function to create a USGSServer instance."""
    return USGSServer(settings=settings or get_settings())


__all__ = ["USGSServer", "create_server"]
