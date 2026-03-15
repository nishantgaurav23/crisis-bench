"""MCP server for NASA FIRMS Fire Detection API (S5.6).

Wraps NASA's Fire Information for Resource Management System (FIRMS) API
as MCP tools for agent consumption. Provides active fire detections from
VIIRS and MODIS satellites for the India region, with filtering by
confidence, location, and time window.

FIRMS access requires a free MAP_KEY — register at
https://firms.modaps.eosdis.nasa.gov/api/area/

Usage::

    server = create_server()
    await server.run_stdio()
"""

from __future__ import annotations

import math
from typing import Any

from mcp.types import TextContent

from src.protocols.mcp.base import BaseMCPServer
from src.shared.config import CrisisSettings, get_settings

_FIRMS_BASE_URL = "https://firms.modaps.eosdis.nasa.gov"
_FIRMS_RATE_LIMIT_RPM = 100

# India bounding box (same as USGS server)
_INDIA_MIN_LAT = 6.0
_INDIA_MAX_LAT = 37.0
_INDIA_MIN_LON = 68.0
_INDIA_MAX_LON = 98.0


class FIRMSServer(BaseMCPServer):
    """MCP server wrapping NASA FIRMS active fire detection API."""

    def __init__(self, *, settings: CrisisSettings | None = None) -> None:
        _settings = settings or get_settings()
        super().__init__(
            name="mcp-firms",
            api_base_url=_FIRMS_BASE_URL,
            api_key=_settings.NASA_FIRMS_KEY,
            rate_limit_rpm=_FIRMS_RATE_LIMIT_RPM,
            settings=_settings,
        )
        self.register_tool(self.get_active_fires)
        self.register_tool(self.get_fires_by_region)
        self.register_tool(self.get_high_confidence_fires)
        self.register_tool(self.get_fire_detail)
        self.register_tool(self.get_fire_summary)

    # ------------------------------------------------------------------
    # Response Normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_fire(record: dict[str, Any]) -> dict[str, Any]:
        """Extract key fields from a FIRMS fire detection record."""
        return {
            "latitude": record.get("latitude", 0.0),
            "longitude": record.get("longitude", 0.0),
            "brightness": record.get("bright_ti4") or record.get("brightness", 0.0),
            "frp": record.get("frp", 0.0),
            "confidence": record.get("confidence", ""),
            "satellite": record.get("instrument") or record.get("satellite", ""),
            "acq_date": record.get("acq_date", ""),
            "acq_time": record.get("acq_time", ""),
            "daynight": record.get("daynight", ""),
            "scan": record.get("scan", 0.0),
            "track": record.get("track", 0.0),
        }

    def _normalize_fires(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize all fire records."""
        return [self._normalize_fire(r) for r in records]

    # ------------------------------------------------------------------
    # Helper: build FIRMS area URL
    # ------------------------------------------------------------------

    def _area_url(
        self,
        source: str,
        bbox: str,
        days: int,
    ) -> str:
        """Build the FIRMS area API URL path."""
        return f"/api/area/json/{self.api_key}/{source}/{bbox}/{days}"

    @staticmethod
    def _bbox_str(
        min_lat: float, max_lat: float, min_lon: float, max_lon: float,
    ) -> str:
        """Format bounding box as FIRMS expects: W,S,E,N."""
        return f"{min_lon},{min_lat},{max_lon},{max_lat}"

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine distance in km between two lat/lon points."""
        r = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        return r * 2 * math.asin(math.sqrt(a))

    # ------------------------------------------------------------------
    # MCP Tools
    # ------------------------------------------------------------------

    async def get_active_fires(
        self,
        source: str = "VIIRS_SNPP_NRT",
        days: int = 1,
    ) -> list[TextContent]:
        """Get active fires in the India region from VIIRS/MODIS satellites.

        Returns fire detections from the last N days within the India
        bounding box (6N-37N, 68E-98E).
        """
        bbox = self._bbox_str(_INDIA_MIN_LAT, _INDIA_MAX_LAT, _INDIA_MIN_LON, _INDIA_MAX_LON)
        path = self._area_url(source, bbox, days)
        data = await self.api_get(path)
        return self.normalize_json(self._normalize_fires(data))

    async def get_fires_by_region(
        self,
        min_lat: float,
        max_lat: float,
        min_lon: float,
        max_lon: float,
        source: str = "VIIRS_SNPP_NRT",
        days: int = 1,
    ) -> list[TextContent]:
        """Get fire detections in a custom bounding box.

        Specify latitude/longitude bounds, satellite source, and time window.
        """
        bbox = self._bbox_str(min_lat, max_lat, min_lon, max_lon)
        path = self._area_url(source, bbox, days)
        data = await self.api_get(path)
        return self.normalize_json(self._normalize_fires(data))

    async def get_high_confidence_fires(
        self,
        source: str = "VIIRS_SNPP_NRT",
        days: int = 1,
    ) -> list[TextContent]:
        """Get only high-confidence fire detections in India.

        Filters the full fire dataset to return only detections with
        'high' confidence (VIIRS) or confidence >= 80 (MODIS).
        """
        bbox = self._bbox_str(_INDIA_MIN_LAT, _INDIA_MAX_LAT, _INDIA_MIN_LON, _INDIA_MAX_LON)
        path = self._area_url(source, bbox, days)
        data = await self.api_get(path)
        normalized = self._normalize_fires(data)
        high = [f for f in normalized if f["confidence"] == "high"]
        return self.normalize_json(high)

    async def get_fire_detail(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 10.0,
        days: int = 2,
    ) -> list[TextContent]:
        """Get fire detections near a specific location.

        Fetches fires in a bounding box around the point, then filters
        by haversine distance to the given radius.
        """
        # Build a generous bounding box (~1 degree ≈ 111km)
        delta = radius_km / 111.0 * 1.5  # 1.5x for safety margin
        min_lat = latitude - delta
        max_lat = latitude + delta
        min_lon = longitude - delta
        max_lon = longitude + delta

        bbox = self._bbox_str(min_lat, max_lat, min_lon, max_lon)
        path = self._area_url("VIIRS_SNPP_NRT", bbox, days)
        data = await self.api_get(path)
        normalized = self._normalize_fires(data)

        # Filter by actual haversine distance
        nearby = [
            f for f in normalized
            if self._haversine_km(latitude, longitude, f["latitude"], f["longitude"]) <= radius_km
        ]
        return self.normalize_json(nearby)

    async def get_fire_summary(
        self,
        days: int = 1,
    ) -> list[TextContent]:
        """Get summary of fire activity in the India region.

        Returns total fire count, breakdown by confidence level and
        day/night, maximum FRP, and period in days.
        """
        bbox = self._bbox_str(_INDIA_MIN_LAT, _INDIA_MAX_LAT, _INDIA_MIN_LON, _INDIA_MAX_LON)
        path = self._area_url("VIIRS_SNPP_NRT", bbox, days)
        data = await self.api_get(path)
        fires = self._normalize_fires(data)

        by_confidence: dict[str, int] = {}
        by_daynight: dict[str, int] = {"D": 0, "N": 0}
        max_frp: float | None = None
        max_frp_location: dict[str, float] | None = None

        for f in fires:
            conf = f["confidence"]
            by_confidence[conf] = by_confidence.get(conf, 0) + 1

            dn = f["daynight"]
            if dn in by_daynight:
                by_daynight[dn] += 1

            frp = f.get("frp") or 0.0
            if max_frp is None or frp > max_frp:
                max_frp = frp
                max_frp_location = {"latitude": f["latitude"], "longitude": f["longitude"]}

        return self.normalize_json({
            "total_fires": len(fires),
            "by_confidence": by_confidence,
            "by_daynight": by_daynight,
            "max_frp": max_frp,
            "max_frp_location": max_frp_location,
            "period_days": days,
        })


def create_server(*, settings: CrisisSettings | None = None) -> FIRMSServer:
    """Factory function to create a FIRMSServer instance."""
    return FIRMSServer(settings=settings or get_settings())


__all__ = ["FIRMSServer", "create_server"]
