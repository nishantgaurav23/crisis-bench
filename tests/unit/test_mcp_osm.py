"""Unit tests for OpenStreetMap Overpass MCP server (S5.4).

Tests cover: initialization, tool registration, all 7 tool methods with
mock HTTP responses, response normalization (nodes, ways with center,
ways with geometry), error handling (timeout, 429, empty results),
and the create_server() factory function.
"""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.shared.config import CrisisSettings
from src.shared.errors import APIRateLimitError, MCPError

# ---------------------------------------------------------------------------
# Mock Overpass API Responses
# ---------------------------------------------------------------------------

MOCK_HOSPITALS_RESPONSE = {
    "version": 0.6,
    "elements": [
        {
            "type": "node",
            "id": 1234567,
            "lat": 19.0760,
            "lon": 72.8777,
            "tags": {
                "amenity": "hospital",
                "name": "KEM Hospital",
                "beds": "1800",
                "emergency": "yes",
            },
        },
        {
            "type": "way",
            "id": 2345678,
            "center": {"lat": 19.0820, "lon": 72.8860},
            "tags": {
                "amenity": "hospital",
                "name": "Sion Hospital",
                "beds": "600",
            },
        },
        {
            "type": "node",
            "id": 3456789,
            "lat": 19.0650,
            "lon": 72.8690,
            "tags": {
                "amenity": "clinic",
                "name": "Worli Health Centre",
            },
        },
    ],
}

MOCK_SHELTERS_RESPONSE = {
    "version": 0.6,
    "elements": [
        {
            "type": "node",
            "id": 4001,
            "lat": 19.0500,
            "lon": 72.8800,
            "tags": {
                "amenity": "shelter",
                "name": "Dharavi Relief Camp",
                "capacity": "500",
            },
        },
        {
            "type": "node",
            "id": 4002,
            "lat": 19.0600,
            "lon": 72.8700,
            "tags": {
                "amenity": "community_centre",
                "name": "Worli Community Hall",
            },
        },
        {
            "type": "way",
            "id": 4003,
            "center": {"lat": 19.0550, "lon": 72.8750},
            "tags": {
                "amenity": "school",
                "name": "Municipal School No. 42",
            },
        },
    ],
}

MOCK_ROADS_RESPONSE = {
    "version": 0.6,
    "elements": [
        {
            "type": "way",
            "id": 5001,
            "tags": {
                "highway": "trunk",
                "name": "Eastern Express Highway",
                "lanes": "6",
            },
            "geometry": [
                {"lat": 19.07, "lon": 72.87},
                {"lat": 19.08, "lon": 72.88},
                {"lat": 19.09, "lon": 72.89},
            ],
        },
        {
            "type": "way",
            "id": 5002,
            "tags": {
                "highway": "primary",
                "name": "LBS Marg",
            },
            "geometry": [
                {"lat": 19.06, "lon": 72.88},
                {"lat": 19.07, "lon": 72.89},
            ],
        },
    ],
}

MOCK_BRIDGES_RESPONSE = {
    "version": 0.6,
    "elements": [
        {
            "type": "way",
            "id": 6001,
            "tags": {
                "bridge": "yes",
                "name": "Bandra-Worli Sea Link",
                "highway": "trunk",
            },
            "geometry": [
                {"lat": 19.0380, "lon": 72.8160},
                {"lat": 19.0450, "lon": 72.8200},
            ],
        },
    ],
}

MOCK_HELIPADS_RESPONSE = {
    "version": 0.6,
    "elements": [
        {
            "type": "node",
            "id": 7001,
            "lat": 18.9960,
            "lon": 72.8480,
            "tags": {
                "aeroway": "helipad",
                "name": "NSCI Helipad",
            },
        },
    ],
}

MOCK_FIRE_STATIONS_RESPONSE = {
    "version": 0.6,
    "elements": [
        {
            "type": "node",
            "id": 8001,
            "lat": 19.0170,
            "lon": 72.8560,
            "tags": {
                "amenity": "fire_station",
                "name": "Byculla Fire Station",
            },
        },
    ],
}

MOCK_POLICE_STATIONS_RESPONSE = {
    "version": 0.6,
    "elements": [
        {
            "type": "node",
            "id": 9001,
            "lat": 19.0760,
            "lon": 72.8777,
            "tags": {
                "amenity": "police",
                "name": "Azad Maidan Police Station",
            },
        },
    ],
}

MOCK_EMPTY_RESPONSE = {
    "version": 0.6,
    "elements": [],
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings():
    return CrisisSettings(LOG_LEVEL="WARNING")


@pytest.fixture
def server(settings):
    from src.protocols.mcp.osm_server import OSMOverpassServer

    return OSMOverpassServer(settings=settings)


def _mock_overpass_response(data: dict) -> httpx.Response:
    """Create a mock httpx.Response for Overpass API."""
    return httpx.Response(200, json=data)


# ---------------------------------------------------------------------------
# Initialization & Tool Registration
# ---------------------------------------------------------------------------


class TestInit:
    def test_server_name(self, server):
        assert server.name == "mcp-osm"

    def test_base_url(self, server):
        assert "overpass-api.de" in server.api_base_url

    def test_no_auth_required(self, server):
        assert server.api_key == ""

    def test_rate_limit_set(self, server):
        assert server.rate_limit_rpm == 10

    def test_all_tools_registered(self, server):
        tools = server.mcp._tool_manager._tools
        expected = {
            "find_hospitals",
            "find_shelters",
            "find_roads",
            "find_bridges",
            "find_helipads",
            "find_fire_stations",
            "find_police_stations",
        }
        assert expected.issubset(set(tools.keys()))


# ---------------------------------------------------------------------------
# Response Normalization
# ---------------------------------------------------------------------------


class TestNormalization:
    def test_normalize_node_element(self, server):
        elements = [MOCK_HOSPITALS_RESPONSE["elements"][0]]
        result = server._normalize_elements(elements)
        assert len(result) == 1
        r = result[0]
        assert r["osm_id"] == 1234567
        assert r["osm_type"] == "node"
        assert r["name"] == "KEM Hospital"
        assert r["lat"] == 19.0760
        assert r["lon"] == 72.8777
        assert r["tags"]["beds"] == "1800"

    def test_normalize_way_with_center(self, server):
        elements = [MOCK_HOSPITALS_RESPONSE["elements"][1]]
        result = server._normalize_elements(elements)
        assert len(result) == 1
        r = result[0]
        assert r["osm_id"] == 2345678
        assert r["osm_type"] == "way"
        assert r["name"] == "Sion Hospital"
        assert r["lat"] == 19.0820
        assert r["lon"] == 72.8860

    def test_normalize_way_with_geometry(self, server):
        elements = [MOCK_ROADS_RESPONSE["elements"][0]]
        result = server._normalize_elements(elements)
        r = result[0]
        assert r["osm_id"] == 5001
        assert "geometry" in r
        assert len(r["geometry"]) == 3

    def test_normalize_element_without_name(self, server):
        elem = {
            "type": "node",
            "id": 9999,
            "lat": 19.0,
            "lon": 72.0,
            "tags": {"amenity": "hospital"},
        }
        result = server._normalize_elements([elem])
        assert result[0]["name"] == ""

    def test_normalize_empty_list(self, server):
        result = server._normalize_elements([])
        assert result == []


# ---------------------------------------------------------------------------
# find_hospitals
# ---------------------------------------------------------------------------


class TestFindHospitals:
    @pytest.mark.asyncio
    async def test_returns_hospital_data(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_overpass_response(MOCK_HOSPITALS_RESPONSE),
        ):
            result = await server.find_hospitals(
                lat=19.076, lon=72.877, radius_km=10.0
            )
        data = json.loads(result[0].text)
        assert len(data) == 3
        assert data[0]["name"] == "KEM Hospital"

    @pytest.mark.asyncio
    async def test_includes_clinics(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_overpass_response(MOCK_HOSPITALS_RESPONSE),
        ):
            result = await server.find_hospitals(
                lat=19.076, lon=72.877, radius_km=10.0
            )
        data = json.loads(result[0].text)
        names = [d["name"] for d in data]
        assert "Worli Health Centre" in names

    @pytest.mark.asyncio
    async def test_empty_result(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_overpass_response(MOCK_EMPTY_RESPONSE),
        ):
            result = await server.find_hospitals(
                lat=19.076, lon=72.877, radius_km=1.0
            )
        data = json.loads(result[0].text)
        assert data == []


# ---------------------------------------------------------------------------
# find_shelters
# ---------------------------------------------------------------------------


class TestFindShelters:
    @pytest.mark.asyncio
    async def test_returns_shelter_data(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_overpass_response(MOCK_SHELTERS_RESPONSE),
        ):
            result = await server.find_shelters(
                lat=19.055, lon=72.875, radius_km=5.0
            )
        data = json.loads(result[0].text)
        assert len(data) == 3

    @pytest.mark.asyncio
    async def test_includes_schools_and_community_centres(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_overpass_response(MOCK_SHELTERS_RESPONSE),
        ):
            result = await server.find_shelters(
                lat=19.055, lon=72.875, radius_km=5.0
            )
        data = json.loads(result[0].text)
        names = [d["name"] for d in data]
        assert "Worli Community Hall" in names
        assert "Municipal School No. 42" in names


# ---------------------------------------------------------------------------
# find_roads
# ---------------------------------------------------------------------------


class TestFindRoads:
    @pytest.mark.asyncio
    async def test_returns_road_data(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_overpass_response(MOCK_ROADS_RESPONSE),
        ):
            result = await server.find_roads(
                south=19.0, west=72.8, north=19.1, east=72.9
            )
        data = json.loads(result[0].text)
        assert len(data) == 2
        assert data[0]["name"] == "Eastern Express Highway"

    @pytest.mark.asyncio
    async def test_roads_include_geometry(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_overpass_response(MOCK_ROADS_RESPONSE),
        ):
            result = await server.find_roads(
                south=19.0, west=72.8, north=19.1, east=72.9
            )
        data = json.loads(result[0].text)
        assert "geometry" in data[0]
        assert len(data[0]["geometry"]) == 3


# ---------------------------------------------------------------------------
# find_bridges
# ---------------------------------------------------------------------------


class TestFindBridges:
    @pytest.mark.asyncio
    async def test_returns_bridge_data(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_overpass_response(MOCK_BRIDGES_RESPONSE),
        ):
            result = await server.find_bridges(
                south=19.0, west=72.8, north=19.1, east=72.9
            )
        data = json.loads(result[0].text)
        assert len(data) == 1
        assert data[0]["name"] == "Bandra-Worli Sea Link"

    @pytest.mark.asyncio
    async def test_bridges_include_geometry(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_overpass_response(MOCK_BRIDGES_RESPONSE),
        ):
            result = await server.find_bridges(
                south=19.0, west=72.8, north=19.1, east=72.9
            )
        data = json.loads(result[0].text)
        assert "geometry" in data[0]


# ---------------------------------------------------------------------------
# find_helipads
# ---------------------------------------------------------------------------


class TestFindHelipads:
    @pytest.mark.asyncio
    async def test_returns_helipad_data(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_overpass_response(MOCK_HELIPADS_RESPONSE),
        ):
            result = await server.find_helipads(
                lat=19.0, lon=72.85, radius_km=10.0
            )
        data = json.loads(result[0].text)
        assert len(data) == 1
        assert data[0]["name"] == "NSCI Helipad"


# ---------------------------------------------------------------------------
# find_fire_stations
# ---------------------------------------------------------------------------


class TestFindFireStations:
    @pytest.mark.asyncio
    async def test_returns_fire_station_data(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_overpass_response(MOCK_FIRE_STATIONS_RESPONSE),
        ):
            result = await server.find_fire_stations(
                lat=19.017, lon=72.856, radius_km=5.0
            )
        data = json.loads(result[0].text)
        assert len(data) == 1
        assert data[0]["name"] == "Byculla Fire Station"


# ---------------------------------------------------------------------------
# find_police_stations
# ---------------------------------------------------------------------------


class TestFindPoliceStations:
    @pytest.mark.asyncio
    async def test_returns_police_station_data(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_overpass_response(MOCK_POLICE_STATIONS_RESPONSE),
        ):
            result = await server.find_police_stations(
                lat=19.076, lon=72.877, radius_km=5.0
            )
        data = json.loads(result[0].text)
        assert len(data) == 1
        assert data[0]["name"] == "Azad Maidan Police Station"


# ---------------------------------------------------------------------------
# Error Handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_timeout_raises_mcp_error(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            with pytest.raises(MCPError, match="timed out"):
                await server.find_hospitals(
                    lat=19.076, lon=72.877, radius_km=10.0
                )

    @pytest.mark.asyncio
    async def test_429_raises_rate_limit_error(self, server):
        mock_resp = httpx.Response(429, text="Too Many Requests")
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_resp,
        ):
            with pytest.raises(APIRateLimitError):
                await server.find_hospitals(
                    lat=19.076, lon=72.877, radius_km=10.0
                )

    @pytest.mark.asyncio
    async def test_500_raises_external_api_error(self, server):
        from src.shared.errors import ExternalAPIError

        mock_resp = httpx.Response(500, text="Server Error")
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_resp,
        ):
            with pytest.raises(ExternalAPIError):
                await server.find_hospitals(
                    lat=19.076, lon=72.877, radius_km=10.0
                )


# ---------------------------------------------------------------------------
# Overpass QL Query Building
# ---------------------------------------------------------------------------


class TestQueryBuilding:
    def test_radius_query_contains_around(self, server):
        query = server._build_radius_query(
            tags=[("amenity", "hospital")],
            lat=19.076,
            lon=72.877,
            radius_m=10000,
        )
        assert "around:10000" in query
        assert "19.076" in query
        assert "72.877" in query
        assert "amenity" in query
        assert "hospital" in query

    def test_radius_query_multi_tags(self, server):
        query = server._build_radius_query(
            tags=[("amenity", "hospital"), ("amenity", "clinic")],
            lat=19.076,
            lon=72.877,
            radius_m=5000,
        )
        assert "hospital" in query
        assert "clinic" in query

    def test_bbox_query_contains_coords(self, server):
        query = server._build_bbox_query(
            tags=[("highway", "trunk|primary")],
            south=19.0,
            west=72.8,
            north=19.1,
            east=72.9,
        )
        assert "19.0" in query
        assert "72.8" in query
        assert "19.1" in query
        assert "72.9" in query

    def test_radius_query_has_json_output(self, server):
        query = server._build_radius_query(
            tags=[("amenity", "hospital")],
            lat=19.076,
            lon=72.877,
            radius_m=10000,
        )
        assert "[out:json]" in query

    def test_bbox_query_has_geom_output(self, server):
        query = server._build_bbox_query(
            tags=[("highway", "trunk|primary")],
            south=19.0,
            west=72.8,
            north=19.1,
            east=72.9,
        )
        assert "out geom" in query


# ---------------------------------------------------------------------------
# create_server() Factory
# ---------------------------------------------------------------------------


class TestCreateServer:
    def test_factory_returns_osm_server(self, settings):
        from src.protocols.mcp.osm_server import OSMOverpassServer, create_server

        server = create_server(settings=settings)
        assert isinstance(server, OSMOverpassServer)
        assert server.name == "mcp-osm"

    def test_factory_default_settings(self):
        from src.protocols.mcp.osm_server import create_server

        server = create_server()
        assert server.name == "mcp-osm"
