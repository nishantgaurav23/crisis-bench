"""Unit tests for ISRO Bhuvan MCP server (S5.5).

Tests cover: initialization, tool registration, all 5 tool methods with
mock HTTP responses, token injection, error handling (timeout, 404, 401,
server error), and the create_server() factory function.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.shared.config import CrisisSettings
from src.shared.errors import ExternalAPIError, MCPError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings():
    return CrisisSettings(LOG_LEVEL="WARNING", BHUVAN_TOKEN="test-bhuvan-token-123")


@pytest.fixture
def bhuvan_server(settings):
    from src.protocols.mcp.bhuvan_server import BhuvanServer

    return BhuvanServer(settings=settings)


# ---------------------------------------------------------------------------
# Sample Bhuvan API Responses (mock data)
# ---------------------------------------------------------------------------

MOCK_VILLAGE_GEOCODE = {
    "village_name": "Paradip",
    "state": "Odisha",
    "district": "Jagatsinghpur",
    "block": "Kujang",
    "census_code": "396595",
    "latitude": 20.3165,
    "longitude": 86.6114,
    "pin_code": "754142",
}

MOCK_SATELLITE_LAYERS = {
    "category": "disaster",
    "layers": [
        {
            "layer_id": "NDEM_FLOOD_2024",
            "name": "Flood Inundation Map 2024",
            "type": "WMS",
            "resolution_m": 56,
            "source": "IRS-R2 LISS-IV",
        },
        {
            "layer_id": "NDEM_LANDSLIDE_2024",
            "name": "Landslide Susceptibility 2024",
            "type": "WMS",
            "resolution_m": 23.5,
            "source": "Cartosat-2S",
        },
    ],
}

MOCK_LULC_DATA = {
    "center": {"latitude": 20.3165, "longitude": 86.6114},
    "radius_km": 5,
    "classification": [
        {"category": "Built-up", "area_sq_km": 3.2, "percentage": 40.7},
        {"category": "Cropland", "area_sq_km": 2.8, "percentage": 35.6},
        {"category": "Water bodies", "area_sq_km": 1.1, "percentage": 14.0},
        {"category": "Forest", "area_sq_km": 0.5, "percentage": 6.4},
        {"category": "Barren", "area_sq_km": 0.26, "percentage": 3.3},
    ],
    "source": "LULC 50K (2023-24)",
}

MOCK_FLOOD_LAYERS = {
    "state": "Odisha",
    "flood_layers": [
        {
            "event_id": "NDEM_FL_OD_2024_01",
            "name": "Mahanadi Flood Aug 2024",
            "date_range": "2024-08-15 to 2024-08-22",
            "affected_districts": ["Puri", "Khordha", "Cuttack", "Jagatsinghpur"],
            "inundation_area_sq_km": 1250.6,
            "wms_url": "https://bhuvan-app1.nrsc.gov.in/geoserver/ndem/wms",
            "layer_name": "ndem:flood_od_2024_01",
        }
    ],
}

MOCK_ADMIN_BOUNDARY = {
    "level": "district",
    "code": "OD_JAGATSINGHPUR",
    "name": "Jagatsinghpur",
    "state": "Odisha",
    "area_sq_km": 1668.0,
    "population_2011": 1136604,
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [
                [86.0, 20.0],
                [86.5, 20.0],
                [86.5, 20.5],
                [86.0, 20.5],
                [86.0, 20.0],
            ]
        ],
    },
}


# ---------------------------------------------------------------------------
# Initialization & Tool Registration
# ---------------------------------------------------------------------------


class TestBhuvanServerInit:
    def test_name_is_mcp_bhuvan(self, bhuvan_server):
        assert bhuvan_server.name == "mcp-bhuvan"

    def test_api_base_url(self, bhuvan_server):
        assert "bhuvan-app1.nrsc.gov.in" in bhuvan_server.api_base_url

    def test_rate_limit_set(self, bhuvan_server):
        assert bhuvan_server.rate_limit_rpm == 30

    def test_token_stored(self, bhuvan_server):
        assert bhuvan_server.token == "test-bhuvan-token-123"

    def test_all_tools_registered(self, bhuvan_server):
        tools = bhuvan_server.mcp._tool_manager._tools
        expected = {
            "geocode_village",
            "get_satellite_layers",
            "get_lulc_data",
            "get_flood_layers",
            "get_admin_boundary",
        }
        assert expected.issubset(set(tools.keys()))


# ---------------------------------------------------------------------------
# Token Injection
# ---------------------------------------------------------------------------


class TestTokenInjection:
    @pytest.mark.asyncio
    async def test_token_injected_into_params(self, bhuvan_server):
        mock_resp = httpx.Response(200, json=MOCK_VILLAGE_GEOCODE)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await bhuvan_server.geocode_village(name="Paradip", state="Odisha")
        call_kwargs = mock_req.call_args
        params = call_kwargs.kwargs.get("params", {})
        assert params.get("token") == "test-bhuvan-token-123"


# ---------------------------------------------------------------------------
# geocode_village
# ---------------------------------------------------------------------------


class TestGeocodeVillage:
    @pytest.mark.asyncio
    async def test_returns_village_data(self, bhuvan_server):
        mock_resp = httpx.Response(200, json=MOCK_VILLAGE_GEOCODE)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await bhuvan_server.geocode_village(name="Paradip", state="Odisha")
        assert len(result) == 1
        assert "Paradip" in result[0].text
        assert "20.3165" in result[0].text

    @pytest.mark.asyncio
    async def test_passes_name_and_state_as_params(self, bhuvan_server):
        mock_resp = httpx.Response(200, json=MOCK_VILLAGE_GEOCODE)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await bhuvan_server.geocode_village(name="Paradip", state="Odisha")
        call_kwargs = mock_req.call_args
        params = call_kwargs.kwargs.get("params", {})
        assert params.get("name") == "Paradip"
        assert params.get("state") == "Odisha"

    @pytest.mark.asyncio
    async def test_timeout_raises_mcp_error(self, bhuvan_server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            with pytest.raises(MCPError, match="timed out"):
                await bhuvan_server.geocode_village(name="Paradip", state="Odisha")


# ---------------------------------------------------------------------------
# get_satellite_layers
# ---------------------------------------------------------------------------


class TestGetSatelliteLayers:
    @pytest.mark.asyncio
    async def test_returns_layer_data(self, bhuvan_server):
        mock_resp = httpx.Response(200, json=MOCK_SATELLITE_LAYERS)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await bhuvan_server.get_satellite_layers(category="disaster")
        assert len(result) == 1
        assert "NDEM_FLOOD_2024" in result[0].text

    @pytest.mark.asyncio
    async def test_passes_category_as_param(self, bhuvan_server):
        mock_resp = httpx.Response(200, json=MOCK_SATELLITE_LAYERS)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await bhuvan_server.get_satellite_layers(category="disaster")
        call_kwargs = mock_req.call_args
        params = call_kwargs.kwargs.get("params", {})
        assert params.get("category") == "disaster"


# ---------------------------------------------------------------------------
# get_lulc_data
# ---------------------------------------------------------------------------


class TestGetLULCData:
    @pytest.mark.asyncio
    async def test_returns_lulc_data(self, bhuvan_server):
        mock_resp = httpx.Response(200, json=MOCK_LULC_DATA)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await bhuvan_server.get_lulc_data(
                lat=20.3165, lng=86.6114, radius_km=5.0
            )
        assert len(result) == 1
        assert "Built-up" in result[0].text
        assert "Cropland" in result[0].text

    @pytest.mark.asyncio
    async def test_passes_coordinates_as_params(self, bhuvan_server):
        mock_resp = httpx.Response(200, json=MOCK_LULC_DATA)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await bhuvan_server.get_lulc_data(lat=20.3165, lng=86.6114, radius_km=5.0)
        call_kwargs = mock_req.call_args
        params = call_kwargs.kwargs.get("params", {})
        assert params.get("lat") == 20.3165
        assert params.get("lng") == 86.6114
        assert params.get("radius_km") == 5.0

    @pytest.mark.asyncio
    async def test_server_error_raises(self, bhuvan_server):
        mock_resp = httpx.Response(500, text="Internal Server Error")
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            with pytest.raises(ExternalAPIError):
                await bhuvan_server.get_lulc_data(lat=20.0, lng=86.0, radius_km=5.0)


# ---------------------------------------------------------------------------
# get_flood_layers
# ---------------------------------------------------------------------------


class TestGetFloodLayers:
    @pytest.mark.asyncio
    async def test_returns_flood_data(self, bhuvan_server):
        mock_resp = httpx.Response(200, json=MOCK_FLOOD_LAYERS)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await bhuvan_server.get_flood_layers(state="Odisha")
        assert len(result) == 1
        assert "Mahanadi" in result[0].text
        assert "Jagatsinghpur" in result[0].text

    @pytest.mark.asyncio
    async def test_passes_state_as_param(self, bhuvan_server):
        mock_resp = httpx.Response(200, json=MOCK_FLOOD_LAYERS)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await bhuvan_server.get_flood_layers(state="Odisha")
        call_kwargs = mock_req.call_args
        params = call_kwargs.kwargs.get("params", {})
        assert params.get("state") == "Odisha"


# ---------------------------------------------------------------------------
# get_admin_boundary
# ---------------------------------------------------------------------------


class TestGetAdminBoundary:
    @pytest.mark.asyncio
    async def test_returns_boundary_data(self, bhuvan_server):
        mock_resp = httpx.Response(200, json=MOCK_ADMIN_BOUNDARY)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await bhuvan_server.get_admin_boundary(
                level="district", code="OD_JAGATSINGHPUR"
            )
        assert len(result) == 1
        assert "Jagatsinghpur" in result[0].text
        assert "Polygon" in result[0].text

    @pytest.mark.asyncio
    async def test_passes_level_and_code_as_params(self, bhuvan_server):
        mock_resp = httpx.Response(200, json=MOCK_ADMIN_BOUNDARY)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await bhuvan_server.get_admin_boundary(
                level="district", code="OD_JAGATSINGHPUR"
            )
        call_kwargs = mock_req.call_args
        params = call_kwargs.kwargs.get("params", {})
        assert params.get("level") == "district"
        assert params.get("code") == "OD_JAGATSINGHPUR"

    @pytest.mark.asyncio
    async def test_404_raises_mcp_error(self, bhuvan_server):
        mock_resp = httpx.Response(404, text="Not Found")
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            with pytest.raises(MCPError, match="404"):
                await bhuvan_server.get_admin_boundary(
                    level="district", code="INVALID"
                )


# ---------------------------------------------------------------------------
# Error Handling — 401 Expired Token
# ---------------------------------------------------------------------------


class TestExpiredToken:
    @pytest.mark.asyncio
    async def test_401_raises_mcp_error(self, bhuvan_server):
        mock_resp = httpx.Response(401, text="Unauthorized — token expired")
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            with pytest.raises(MCPError, match="401"):
                await bhuvan_server.geocode_village(name="Paradip", state="Odisha")


# ---------------------------------------------------------------------------
# create_server() Factory
# ---------------------------------------------------------------------------


class TestCreateServer:
    def test_factory_returns_bhuvan_server(self, settings):
        from src.protocols.mcp.bhuvan_server import BhuvanServer, create_server

        server = create_server(settings=settings)
        assert isinstance(server, BhuvanServer)
        assert server.name == "mcp-bhuvan"

    def test_factory_default_settings(self):
        from src.protocols.mcp.bhuvan_server import create_server

        server = create_server()
        assert server.name == "mcp-bhuvan"
