"""MCP server for OpenStreetMap Overpass API (S5.4).

Wraps the Overpass API as MCP tools for querying Indian infrastructure:
hospitals, shelters, roads, bridges, helipads, fire stations, police stations.

The Overpass API is free, requires no authentication, and has excellent India
coverage. We self-impose a 10 RPM rate limit to be a good community citizen.

MCP Tools:
    - ``find_hospitals``       — hospitals/clinics within radius
    - ``find_shelters``        — shelters, community halls, schools within radius
    - ``find_roads``           — major roads in bounding box (with geometry)
    - ``find_bridges``         — bridges in bounding box (with geometry)
    - ``find_helipads``        — helipads/airstrips within radius
    - ``find_fire_stations``   — fire stations within radius
    - ``find_police_stations`` — police stations within radius
"""

from __future__ import annotations

from typing import Any

from mcp.types import TextContent

from src.protocols.mcp.base import BaseMCPServer
from src.shared.config import CrisisSettings, get_settings

_OVERPASS_BASE_URL = "https://overpass-api.de"
_OVERPASS_RATE_LIMIT_RPM = 10
_OVERPASS_TIMEOUT = 25


class OSMOverpassServer(BaseMCPServer):
    """MCP server wrapping the OpenStreetMap Overpass API."""

    def __init__(self, *, settings: CrisisSettings | None = None) -> None:
        super().__init__(
            name="mcp-osm",
            api_base_url=_OVERPASS_BASE_URL,
            rate_limit_rpm=_OVERPASS_RATE_LIMIT_RPM,
            request_timeout=_OVERPASS_TIMEOUT,
            settings=settings,
        )
        self.register_tool(self.find_hospitals)
        self.register_tool(self.find_shelters)
        self.register_tool(self.find_roads)
        self.register_tool(self.find_bridges)
        self.register_tool(self.find_helipads)
        self.register_tool(self.find_fire_stations)
        self.register_tool(self.find_police_stations)

    # ------------------------------------------------------------------
    # Overpass QL Query Builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_radius_query(
        tags: list[tuple[str, str]],
        lat: float,
        lon: float,
        radius_m: int,
    ) -> str:
        """Build an Overpass QL radius query with ``out center``."""
        union_parts = []
        for key, value in tags:
            around = f"(around:{radius_m},{lat},{lon})"
            if "|" in value:
                filter_expr = f'["{key}"~"{value}"]'
            else:
                filter_expr = f'["{key}"="{value}"]'
            union_parts.append(f"  node{filter_expr}{around};")
            union_parts.append(f"  way{filter_expr}{around};")
        body = "\n".join(union_parts)
        return (
            f"[out:json][timeout:{_OVERPASS_TIMEOUT}];\n"
            f"(\n{body}\n);\n"
            f"out center;"
        )

    @staticmethod
    def _build_bbox_query(
        tags: list[tuple[str, str]],
        south: float,
        west: float,
        north: float,
        east: float,
    ) -> str:
        """Build an Overpass QL bounding box query with ``out geom``."""
        bbox = f"({south},{west},{north},{east})"
        union_parts = []
        for key, value in tags:
            if "|" in value:
                filter_expr = f'["{key}"~"{value}"]'
            else:
                filter_expr = f'["{key}"="{value}"]'
            union_parts.append(f"  way{filter_expr}{bbox};")
        body = "\n".join(union_parts)
        return (
            f"[out:json][timeout:{_OVERPASS_TIMEOUT}];\n"
            f"(\n{body}\n);\n"
            f"out geom;"
        )

    # ------------------------------------------------------------------
    # Response Normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_elements(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize Overpass elements to a consistent format."""
        results: list[dict[str, Any]] = []
        for elem in elements:
            osm_type = elem.get("type", "")
            tags = elem.get("tags", {})
            record: dict[str, Any] = {
                "osm_id": elem.get("id"),
                "osm_type": osm_type,
                "name": tags.get("name", ""),
                "tags": tags,
            }

            # Coordinates: node has lat/lon directly, way may have center or geometry
            if osm_type == "node":
                record["lat"] = elem.get("lat")
                record["lon"] = elem.get("lon")
            elif "center" in elem:
                record["lat"] = elem["center"]["lat"]
                record["lon"] = elem["center"]["lon"]

            # Geometry for ways (roads, bridges)
            if "geometry" in elem:
                record["geometry"] = elem["geometry"]
                # Use first point as lat/lon if no center
                if "lat" not in record and elem["geometry"]:
                    record["lat"] = elem["geometry"][0]["lat"]
                    record["lon"] = elem["geometry"][0]["lon"]

            results.append(record)
        return results

    # ------------------------------------------------------------------
    # Internal query executor
    # ------------------------------------------------------------------

    async def _run_query(self, query: str) -> list[dict[str, Any]]:
        """Execute an Overpass QL query and return normalized elements."""
        data = await self.api_post(
            "/api/interpreter",
            params={"data": query},
        )
        elements = data.get("elements", [])
        return self._normalize_elements(elements)

    # ------------------------------------------------------------------
    # MCP Tools
    # ------------------------------------------------------------------

    async def find_hospitals(
        self, lat: float, lon: float, radius_km: float = 10.0,
    ) -> list[TextContent]:
        """Find hospitals and clinics within a radius (km) of a point.

        Returns hospitals and clinics from OpenStreetMap with name, location,
        and tags (beds, emergency, etc.).
        """
        query = self._build_radius_query(
            tags=[("amenity", "hospital"), ("amenity", "clinic")],
            lat=lat,
            lon=lon,
            radius_m=int(radius_km * 1000),
        )
        results = await self._run_query(query)
        return self.normalize_json(results)

    async def find_shelters(
        self, lat: float, lon: float, radius_km: float = 10.0,
    ) -> list[TextContent]:
        """Find emergency shelters within a radius (km) of a point.

        Includes shelters, community centres, and schools — all common
        shelter types used during disasters in India per NDMA guidelines.
        """
        query = self._build_radius_query(
            tags=[
                ("amenity", "shelter"),
                ("amenity", "community_centre"),
                ("amenity", "school"),
            ],
            lat=lat,
            lon=lon,
            radius_m=int(radius_km * 1000),
        )
        results = await self._run_query(query)
        return self.normalize_json(results)

    async def find_roads(
        self, south: float, west: float, north: float, east: float,
    ) -> list[TextContent]:
        """Find major roads in a bounding box (south,west,north,east).

        Returns motorways, trunk roads, primary, and secondary roads with
        full geometry for routing and flood intersection analysis.
        """
        query = self._build_bbox_query(
            tags=[("highway", "motorway|trunk|primary|secondary")],
            south=south,
            west=west,
            north=north,
            east=east,
        )
        results = await self._run_query(query)
        return self.normalize_json(results)

    async def find_bridges(
        self, south: float, west: float, north: float, east: float,
    ) -> list[TextContent]:
        """Find bridges in a bounding box (south,west,north,east).

        Critical for flood assessment — bridges are key chokepoints.
        Returns bridges with full geometry.
        """
        query = self._build_bbox_query(
            tags=[("bridge", "yes")],
            south=south,
            west=west,
            north=north,
            east=east,
        )
        results = await self._run_query(query)
        return self.normalize_json(results)

    async def find_helipads(
        self, lat: float, lon: float, radius_km: float = 25.0,
    ) -> list[TextContent]:
        """Find helipads and airstrips within a radius (km) of a point.

        Used for identifying aerial rescue landing points during disasters.
        """
        query = self._build_radius_query(
            tags=[("aeroway", "helipad"), ("aeroway", "aerodrome")],
            lat=lat,
            lon=lon,
            radius_m=int(radius_km * 1000),
        )
        results = await self._run_query(query)
        return self.normalize_json(results)

    async def find_fire_stations(
        self, lat: float, lon: float, radius_km: float = 15.0,
    ) -> list[TextContent]:
        """Find fire stations within a radius (km) of a point."""
        query = self._build_radius_query(
            tags=[("amenity", "fire_station")],
            lat=lat,
            lon=lon,
            radius_m=int(radius_km * 1000),
        )
        results = await self._run_query(query)
        return self.normalize_json(results)

    async def find_police_stations(
        self, lat: float, lon: float, radius_km: float = 15.0,
    ) -> list[TextContent]:
        """Find police stations within a radius (km) of a point."""
        query = self._build_radius_query(
            tags=[("amenity", "police")],
            lat=lat,
            lon=lon,
            radius_m=int(radius_km * 1000),
        )
        results = await self._run_query(query)
        return self.normalize_json(results)


def create_server(
    *, settings: CrisisSettings | None = None,
) -> OSMOverpassServer:
    """Factory function to create an OSMOverpassServer instance."""
    return OSMOverpassServer(settings=settings or get_settings())


__all__ = ["OSMOverpassServer", "create_server"]
