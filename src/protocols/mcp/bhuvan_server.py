"""MCP server for ISRO Bhuvan REST + OGC APIs (S5.5).

Wraps Bhuvan's public geospatial APIs as MCP tools for agent consumption.
Provides village geocoding, satellite layer metadata, Land Use / Land Cover
(LULC) data, NDEM flood map layers, and administrative boundary queries.

Bhuvan access requires free registration — a daily-refreshing token is passed
via the ``token`` query parameter on every request.

Usage::

    server = create_server()
    await server.run_stdio()
"""

from __future__ import annotations

from typing import Any

from mcp.types import TextContent

from src.protocols.mcp.base import BaseMCPServer
from src.shared.config import CrisisSettings, get_settings

_BHUVAN_BASE_URL = "https://bhuvan-app1.nrsc.gov.in"
_BHUVAN_RATE_LIMIT_RPM = 30


class BhuvanServer(BaseMCPServer):
    """MCP server wrapping ISRO Bhuvan REST + OGC APIs."""

    def __init__(self, *, settings: CrisisSettings | None = None) -> None:
        settings = settings or get_settings()
        super().__init__(
            name="mcp-bhuvan",
            api_base_url=_BHUVAN_BASE_URL,
            rate_limit_rpm=_BHUVAN_RATE_LIMIT_RPM,
            settings=settings,
        )
        self.token: str = settings.BHUVAN_TOKEN

        self.register_tool(self.geocode_village)
        self.register_tool(self.get_satellite_layers)
        self.register_tool(self.get_lulc_data)
        self.register_tool(self.get_flood_layers)
        self.register_tool(self.get_admin_boundary)

    def _inject_token(self, params: dict[str, Any] | None) -> dict[str, Any]:
        """Inject Bhuvan API token into query parameters."""
        result = dict(params) if params else {}
        result["token"] = self.token
        return result

    async def api_get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """HTTP GET with Bhuvan token injected into query params."""
        return await self._request("GET", path, params=self._inject_token(params))

    async def geocode_village(self, name: str, state: str) -> list[TextContent]:
        """Geocode an Indian village by name and state using ISRO Bhuvan."""
        data = await self.api_get(
            "/api/village", params={"name": name, "state": state}
        )
        return self.normalize_json(data)

    async def get_satellite_layers(self, category: str) -> list[TextContent]:
        """List available Bhuvan satellite data layers by category."""
        data = await self.api_get(
            "/api/layers", params={"category": category}
        )
        return self.normalize_json(data)

    async def get_lulc_data(
        self, lat: float, lng: float, radius_km: float
    ) -> list[TextContent]:
        """Get Land Use / Land Cover classification for an area around a point."""
        data = await self.api_get(
            "/api/lulc",
            params={"lat": lat, "lng": lng, "radius_km": radius_km},
        )
        return self.normalize_json(data)

    async def get_flood_layers(self, state: str) -> list[TextContent]:
        """Get NDEM flood inundation map layers for an Indian state."""
        data = await self.api_get(
            "/api/ndem/flood", params={"state": state}
        )
        return self.normalize_json(data)

    async def get_admin_boundary(self, level: str, code: str) -> list[TextContent]:
        """Get administrative boundary GeoJSON (state/district/block level)."""
        data = await self.api_get(
            "/api/admin", params={"level": level, "code": code}
        )
        return self.normalize_json(data)


def create_server(*, settings: CrisisSettings | None = None) -> BhuvanServer:
    """Factory function to create a BhuvanServer instance."""
    return BhuvanServer(settings=settings or get_settings())


__all__ = ["BhuvanServer", "create_server"]
