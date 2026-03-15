"""Unit tests for IMD Weather MCP server (S5.1).

Tests cover: initialization, tool registration, all 5 tool methods with
mock HTTP responses, error handling (timeout, 404, malformed), and the
create_server() factory function.
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
    return CrisisSettings(LOG_LEVEL="WARNING")


@pytest.fixture
def imd_server(settings):
    from src.protocols.mcp.imd_server import IMDServer

    return IMDServer(settings=settings)


# ---------------------------------------------------------------------------
# Sample IMD API Responses (mock data)
# ---------------------------------------------------------------------------

MOCK_DISTRICT_WARNING = {
    "district_id": "MH001",
    "district_name": "Mumbai",
    "state": "Maharashtra",
    "warnings": [
        {
            "date": "2026-03-15",
            "color_code": "Orange",
            "warning": "Heavy to very heavy rainfall likely",
            "action": "Be prepared to move to safer areas",
        }
    ],
}

MOCK_DISTRICT_RAINFALL = {
    "date": "2026-03-15",
    "districts": [
        {
            "district": "Mumbai",
            "state": "Maharashtra",
            "actual_mm": 45.2,
            "normal_mm": 30.0,
            "departure_pct": 50.7,
        },
        {
            "district": "Pune",
            "state": "Maharashtra",
            "actual_mm": 22.1,
            "normal_mm": 25.0,
            "departure_pct": -11.6,
        },
    ],
}

MOCK_CYCLONE_INFO = {
    "active_cyclones": [
        {
            "name": "REMAL",
            "classification": "VSCS",
            "lat": 18.5,
            "lon": 87.3,
            "max_wind_kmh": 165,
            "central_pressure_hpa": 970,
            "movement": "North-Northwest at 15 km/h",
            "landfall_expected": "2026-03-16T06:00:00Z",
            "affected_states": ["Odisha", "West Bengal"],
        }
    ],
    "basin": "North Indian Ocean",
}

MOCK_CITY_FORECAST = {
    "city_id": "DEL",
    "city_name": "New Delhi",
    "forecast": [
        {
            "date": "2026-03-15",
            "max_temp_c": 38,
            "min_temp_c": 24,
            "weather": "Partly cloudy",
            "humidity_pct": 45,
            "wind_speed_kmh": 12,
            "wind_direction": "NW",
        }
    ],
}

MOCK_AWS_DATA = {
    "station_id": "AWS_MH_001",
    "station_name": "Colaba, Mumbai",
    "observations": [
        {
            "timestamp": "2026-03-15T10:00:00Z",
            "temperature_c": 31.2,
            "humidity_pct": 78,
            "rainfall_mm": 5.4,
            "wind_speed_kmh": 18,
            "wind_direction": "SW",
            "pressure_hpa": 1008.2,
        }
    ],
}


# ---------------------------------------------------------------------------
# Initialization & Tool Registration
# ---------------------------------------------------------------------------


class TestIMDServerInit:
    def test_name_is_mcp_imd(self, imd_server):
        assert imd_server.name == "mcp-imd"

    def test_api_base_url(self, imd_server):
        assert "mausam.imd.gov.in" in imd_server.api_base_url

    def test_no_api_key(self, imd_server):
        assert imd_server.api_key == ""

    def test_rate_limit_set(self, imd_server):
        assert imd_server.rate_limit_rpm == 60

    def test_all_tools_registered(self, imd_server):
        tools = imd_server.mcp._tool_manager._tools
        expected = {
            "get_district_warnings",
            "get_district_rainfall",
            "get_cyclone_info",
            "get_city_forecast",
            "get_aws_data",
        }
        assert expected.issubset(set(tools.keys()))


# ---------------------------------------------------------------------------
# get_district_warnings
# ---------------------------------------------------------------------------


class TestGetDistrictWarnings:
    @pytest.mark.asyncio
    async def test_returns_warning_data(self, imd_server):
        mock_resp = httpx.Response(200, json=MOCK_DISTRICT_WARNING)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await imd_server.get_district_warnings(district_id="MH001")
        assert len(result) == 1
        assert "Mumbai" in result[0].text
        assert "Orange" in result[0].text

    @pytest.mark.asyncio
    async def test_passes_district_id_as_param(self, imd_server):
        mock_resp = httpx.Response(200, json=MOCK_DISTRICT_WARNING)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await imd_server.get_district_warnings(district_id="MH001")
        call_kwargs = mock_req.call_args
        params = call_kwargs.kwargs.get("params", {})
        assert params.get("id") == "MH001"

    @pytest.mark.asyncio
    async def test_timeout_raises_mcp_error(self, imd_server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            with pytest.raises(MCPError, match="timed out"):
                await imd_server.get_district_warnings(district_id="MH001")


# ---------------------------------------------------------------------------
# get_district_rainfall
# ---------------------------------------------------------------------------


class TestGetDistrictRainfall:
    @pytest.mark.asyncio
    async def test_returns_rainfall_data(self, imd_server):
        mock_resp = httpx.Response(200, json=MOCK_DISTRICT_RAINFALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await imd_server.get_district_rainfall()
        assert len(result) == 1
        assert "Mumbai" in result[0].text
        assert "45.2" in result[0].text

    @pytest.mark.asyncio
    async def test_server_error_raises(self, imd_server):
        mock_resp = httpx.Response(500, text="Internal Server Error")
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            with pytest.raises(ExternalAPIError):
                await imd_server.get_district_rainfall()


# ---------------------------------------------------------------------------
# get_cyclone_info
# ---------------------------------------------------------------------------


class TestGetCycloneInfo:
    @pytest.mark.asyncio
    async def test_returns_cyclone_data(self, imd_server):
        mock_resp = httpx.Response(200, json=MOCK_CYCLONE_INFO)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await imd_server.get_cyclone_info()
        assert len(result) == 1
        assert "REMAL" in result[0].text
        assert "VSCS" in result[0].text

    @pytest.mark.asyncio
    async def test_no_active_cyclones(self, imd_server):
        mock_resp = httpx.Response(200, json={"active_cyclones": [], "basin": "NIO"})
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await imd_server.get_cyclone_info()
        assert len(result) == 1
        assert "[]" in result[0].text


# ---------------------------------------------------------------------------
# get_city_forecast
# ---------------------------------------------------------------------------


class TestGetCityForecast:
    @pytest.mark.asyncio
    async def test_returns_forecast_data(self, imd_server):
        mock_resp = httpx.Response(200, json=MOCK_CITY_FORECAST)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await imd_server.get_city_forecast(city_id="DEL")
        assert len(result) == 1
        assert "New Delhi" in result[0].text

    @pytest.mark.asyncio
    async def test_passes_city_id_as_param(self, imd_server):
        mock_resp = httpx.Response(200, json=MOCK_CITY_FORECAST)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await imd_server.get_city_forecast(city_id="DEL")
        call_kwargs = mock_req.call_args
        params = call_kwargs.kwargs.get("params", {})
        assert params.get("id") == "DEL"

    @pytest.mark.asyncio
    async def test_404_raises_mcp_error(self, imd_server):
        mock_resp = httpx.Response(404, text="Not Found")
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            with pytest.raises(MCPError, match="404"):
                await imd_server.get_city_forecast(city_id="INVALID")


# ---------------------------------------------------------------------------
# get_aws_data
# ---------------------------------------------------------------------------


class TestGetAWSData:
    @pytest.mark.asyncio
    async def test_returns_aws_observations(self, imd_server):
        mock_resp = httpx.Response(200, json=MOCK_AWS_DATA)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await imd_server.get_aws_data(station_id="AWS_MH_001")
        assert len(result) == 1
        assert "Colaba" in result[0].text
        assert "31.2" in result[0].text

    @pytest.mark.asyncio
    async def test_passes_station_id_as_param(self, imd_server):
        mock_resp = httpx.Response(200, json=MOCK_AWS_DATA)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await imd_server.get_aws_data(station_id="AWS_MH_001")
        call_kwargs = mock_req.call_args
        params = call_kwargs.kwargs.get("params", {})
        assert params.get("station_id") == "AWS_MH_001"


# ---------------------------------------------------------------------------
# create_server() Factory
# ---------------------------------------------------------------------------


class TestCreateServer:
    def test_factory_returns_imd_server(self, settings):
        from src.protocols.mcp.imd_server import IMDServer, create_server

        server = create_server(settings=settings)
        assert isinstance(server, IMDServer)
        assert server.name == "mcp-imd"

    def test_factory_default_settings(self):
        from src.protocols.mcp.imd_server import create_server

        server = create_server()
        assert server.name == "mcp-imd"
