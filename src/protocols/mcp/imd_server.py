"""MCP server for India Meteorological Department (IMD) APIs (S5.1).

Wraps IMD's public weather APIs as MCP tools for agent consumption.
Provides district warnings, rainfall data, cyclone bulletins, city forecasts,
and Automatic Weather Station (AWS) observations.

IMD access requires IP whitelisting (free) — no API key needed.

Usage::

    server = create_server()
    await server.run_stdio()
"""

from __future__ import annotations

from mcp.types import TextContent

from src.protocols.mcp.base import BaseMCPServer
from src.shared.config import CrisisSettings, get_settings

_IMD_BASE_URL = "https://mausam.imd.gov.in"
_IMD_RATE_LIMIT_RPM = 60


class IMDServer(BaseMCPServer):
    """MCP server wrapping IMD weather APIs."""

    def __init__(self, *, settings: CrisisSettings | None = None) -> None:
        super().__init__(
            name="mcp-imd",
            api_base_url=_IMD_BASE_URL,
            rate_limit_rpm=_IMD_RATE_LIMIT_RPM,
            settings=settings,
        )
        self.register_tool(self.get_district_warnings)
        self.register_tool(self.get_district_rainfall)
        self.register_tool(self.get_cyclone_info)
        self.register_tool(self.get_city_forecast)
        self.register_tool(self.get_aws_data)

    async def get_district_warnings(self, district_id: str) -> list[TextContent]:
        """Get IMD weather warnings for an Indian district (Green/Yellow/Orange/Red)."""
        data = await self.api_get(
            "/api/warnings_district_api.php", params={"id": district_id}
        )
        return self.normalize_json(data)

    async def get_district_rainfall(self) -> list[TextContent]:
        """Get district-wise rainfall data across India."""
        data = await self.api_get("/api/districtwise_rainfall_api.php")
        return self.normalize_json(data)

    async def get_cyclone_info(self) -> list[TextContent]:
        """Get active tropical cyclone bulletins for the North Indian Ocean."""
        data = await self.api_get("/api/cyclone_api.php")
        return self.normalize_json(data)

    async def get_city_forecast(self, city_id: str) -> list[TextContent]:
        """Get city-level weather forecast from IMD."""
        data = await self.api_get(
            "/api/city_weather_api.php", params={"id": city_id}
        )
        return self.normalize_json(data)

    async def get_aws_data(self, station_id: str) -> list[TextContent]:
        """Get Automatic Weather Station observations."""
        data = await self.api_get(
            "/api/aws_data_api.php", params={"station_id": station_id}
        )
        return self.normalize_json(data)


def create_server(*, settings: CrisisSettings | None = None) -> IMDServer:
    """Factory function to create an IMDServer instance."""
    return IMDServer(settings=settings or get_settings())


__all__ = ["IMDServer", "create_server"]
