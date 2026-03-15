"""Unit tests for NASA FIRMS Fire MCP server (S5.6).

Tests cover: initialization, tool registration, all 5 tool methods with
mock FIRMS responses, response normalization, filtering, error handling
(timeout, server error, empty results), and the create_server() factory.
"""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.shared.config import CrisisSettings
from src.shared.errors import ExternalAPIError, MCPError

# ---------------------------------------------------------------------------
# Sample FIRMS Fire Detection Records (mock data)
# ---------------------------------------------------------------------------

MOCK_FIRE_UTTARAKHAND = {
    "latitude": 30.45,
    "longitude": 78.12,
    "brightness": 312.5,
    "bright_ti4": 312.5,
    "bright_ti5": 290.1,
    "scan": 0.39,
    "track": 0.36,
    "acq_date": "2026-03-15",
    "acq_time": "0630",
    "satellite": "N",
    "instrument": "VIIRS",
    "confidence": "high",
    "version": "2.0NRT",
    "frp": 15.3,
    "daynight": "D",
}

MOCK_FIRE_PUNJAB = {
    "latitude": 30.90,
    "longitude": 75.85,
    "brightness": 305.2,
    "bright_ti4": 305.2,
    "bright_ti5": 288.0,
    "scan": 0.40,
    "track": 0.37,
    "acq_date": "2026-03-15",
    "acq_time": "1430",
    "satellite": "N",
    "instrument": "VIIRS",
    "confidence": "nominal",
    "version": "2.0NRT",
    "frp": 8.7,
    "daynight": "D",
}

MOCK_FIRE_ANDAMAN = {
    "latitude": 12.50,
    "longitude": 92.80,
    "brightness": 340.1,
    "bright_ti4": 340.1,
    "bright_ti5": 295.0,
    "scan": 0.38,
    "track": 0.36,
    "acq_date": "2026-03-14",
    "acq_time": "2215",
    "satellite": "N",
    "instrument": "VIIRS",
    "confidence": "low",
    "version": "2.0NRT",
    "frp": 25.0,
    "daynight": "N",
}

MOCK_FIRE_HIGH_FRP = {
    "latitude": 31.20,
    "longitude": 77.50,
    "brightness": 365.0,
    "bright_ti4": 365.0,
    "bright_ti5": 300.0,
    "scan": 0.39,
    "track": 0.36,
    "acq_date": "2026-03-15",
    "acq_time": "0800",
    "satellite": "N",
    "instrument": "VIIRS",
    "confidence": "high",
    "version": "2.0NRT",
    "frp": 55.0,
    "daynight": "D",
}

MOCK_FIRES_ALL = [
    MOCK_FIRE_UTTARAKHAND,
    MOCK_FIRE_PUNJAB,
    MOCK_FIRE_ANDAMAN,
    MOCK_FIRE_HIGH_FRP,
]

MOCK_FIRES_HIGH_CONFIDENCE = [
    MOCK_FIRE_UTTARAKHAND,
    MOCK_FIRE_HIGH_FRP,
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings():
    return CrisisSettings(LOG_LEVEL="WARNING", NASA_FIRMS_KEY="test_map_key_123")


@pytest.fixture
def firms_server(settings):
    from src.protocols.mcp.firms_server import FIRMSServer

    return FIRMSServer(settings=settings)


# ---------------------------------------------------------------------------
# Initialization & Tool Registration
# ---------------------------------------------------------------------------


class TestFIRMSServerInit:
    def test_name(self, firms_server):
        assert firms_server.name == "mcp-firms"

    def test_api_base_url(self, firms_server):
        assert "firms.modaps.eosdis.nasa.gov" in firms_server.api_base_url

    def test_api_key_set(self, firms_server):
        assert firms_server.api_key == "test_map_key_123"

    def test_rate_limit_set(self, firms_server):
        assert firms_server.rate_limit_rpm == 100

    def test_all_tools_registered(self, firms_server):
        tools = firms_server.mcp._tool_manager._tools
        expected = {
            "get_active_fires",
            "get_fires_by_region",
            "get_high_confidence_fires",
            "get_fire_detail",
            "get_fire_summary",
        }
        assert expected.issubset(set(tools.keys()))


# ---------------------------------------------------------------------------
# _normalize_fire
# ---------------------------------------------------------------------------


class TestNormalizeFire:
    def test_extracts_latitude(self, firms_server):
        result = firms_server._normalize_fire(MOCK_FIRE_UTTARAKHAND)
        assert result["latitude"] == 30.45

    def test_extracts_longitude(self, firms_server):
        result = firms_server._normalize_fire(MOCK_FIRE_UTTARAKHAND)
        assert result["longitude"] == 78.12

    def test_extracts_brightness(self, firms_server):
        result = firms_server._normalize_fire(MOCK_FIRE_UTTARAKHAND)
        assert result["brightness"] == 312.5

    def test_extracts_frp(self, firms_server):
        result = firms_server._normalize_fire(MOCK_FIRE_UTTARAKHAND)
        assert result["frp"] == 15.3

    def test_extracts_confidence(self, firms_server):
        result = firms_server._normalize_fire(MOCK_FIRE_UTTARAKHAND)
        assert result["confidence"] == "high"

    def test_extracts_satellite(self, firms_server):
        result = firms_server._normalize_fire(MOCK_FIRE_UTTARAKHAND)
        assert result["satellite"] == "VIIRS"

    def test_extracts_acq_date(self, firms_server):
        result = firms_server._normalize_fire(MOCK_FIRE_UTTARAKHAND)
        assert result["acq_date"] == "2026-03-15"

    def test_extracts_acq_time(self, firms_server):
        result = firms_server._normalize_fire(MOCK_FIRE_UTTARAKHAND)
        assert result["acq_time"] == "0630"

    def test_extracts_daynight(self, firms_server):
        result = firms_server._normalize_fire(MOCK_FIRE_UTTARAKHAND)
        assert result["daynight"] == "D"

    def test_extracts_scan_track(self, firms_server):
        result = firms_server._normalize_fire(MOCK_FIRE_UTTARAKHAND)
        assert result["scan"] == 0.39
        assert result["track"] == 0.36

    def test_nominal_confidence(self, firms_server):
        result = firms_server._normalize_fire(MOCK_FIRE_PUNJAB)
        assert result["confidence"] == "nominal"

    def test_night_detection(self, firms_server):
        result = firms_server._normalize_fire(MOCK_FIRE_ANDAMAN)
        assert result["daynight"] == "N"


# ---------------------------------------------------------------------------
# get_active_fires
# ---------------------------------------------------------------------------


class TestGetActiveFires:
    @pytest.mark.asyncio
    async def test_returns_fire_data(self, firms_server):
        mock_resp = httpx.Response(200, json=MOCK_FIRES_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await firms_server.get_active_fires()
        data = json.loads(result[0].text)
        assert len(data) == 4

    @pytest.mark.asyncio
    async def test_default_source_viirs(self, firms_server):
        mock_resp = httpx.Response(200, json=MOCK_FIRES_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await firms_server.get_active_fires()
        call_args = mock_req.call_args
        url = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("url", "")
        assert "VIIRS_SNPP_NRT" in url

    @pytest.mark.asyncio
    async def test_custom_source(self, firms_server):
        mock_resp = httpx.Response(200, json=MOCK_FIRES_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await firms_server.get_active_fires(source="MODIS_NRT")
        call_args = mock_req.call_args
        url = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("url", "")
        assert "MODIS_NRT" in url

    @pytest.mark.asyncio
    async def test_custom_days(self, firms_server):
        mock_resp = httpx.Response(200, json=MOCK_FIRES_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await firms_server.get_active_fires(days=3)
        call_args = mock_req.call_args
        url = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("url", "")
        assert "/3" in url

    @pytest.mark.asyncio
    async def test_empty_result(self, firms_server):
        mock_resp = httpx.Response(200, json=[])
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await firms_server.get_active_fires()
        data = json.loads(result[0].text)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_normalized_fields(self, firms_server):
        mock_resp = httpx.Response(200, json=MOCK_FIRES_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await firms_server.get_active_fires()
        data = json.loads(result[0].text)
        fire = data[0]
        assert "latitude" in fire
        assert "longitude" in fire
        assert "brightness" in fire
        assert "frp" in fire
        assert "confidence" in fire
        assert "satellite" in fire


# ---------------------------------------------------------------------------
# get_fires_by_region
# ---------------------------------------------------------------------------


class TestGetFiresByRegion:
    @pytest.mark.asyncio
    async def test_custom_bbox_in_url(self, firms_server):
        mock_resp = httpx.Response(200, json=MOCK_FIRES_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await firms_server.get_fires_by_region(
                min_lat=28.0, max_lat=32.0, min_lon=76.0, max_lon=80.0
            )
        call_args = mock_req.call_args
        url = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("url", "")
        assert "28.0" in url or "28" in url

    @pytest.mark.asyncio
    async def test_returns_normalized(self, firms_server):
        mock_resp = httpx.Response(200, json=MOCK_FIRES_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await firms_server.get_fires_by_region(
                min_lat=10.0, max_lat=15.0, min_lon=70.0, max_lon=80.0
            )
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_custom_source_and_days(self, firms_server):
        mock_resp = httpx.Response(200, json=MOCK_FIRES_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await firms_server.get_fires_by_region(
                min_lat=10.0, max_lat=15.0, min_lon=70.0, max_lon=80.0,
                source="MODIS_NRT", days=5,
            )
        call_args = mock_req.call_args
        url = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("url", "")
        assert "MODIS_NRT" in url
        assert "/5" in url


# ---------------------------------------------------------------------------
# get_high_confidence_fires
# ---------------------------------------------------------------------------


class TestGetHighConfidenceFires:
    @pytest.mark.asyncio
    async def test_filters_high_confidence(self, firms_server):
        mock_resp = httpx.Response(200, json=MOCK_FIRES_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await firms_server.get_high_confidence_fires()
        data = json.loads(result[0].text)
        for fire in data:
            assert fire["confidence"] == "high"

    @pytest.mark.asyncio
    async def test_returns_subset(self, firms_server):
        mock_resp = httpx.Response(200, json=MOCK_FIRES_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await firms_server.get_high_confidence_fires()
        data = json.loads(result[0].text)
        assert len(data) == 2  # Only Uttarakhand and High FRP

    @pytest.mark.asyncio
    async def test_empty_when_no_high(self, firms_server):
        mock_low = [MOCK_FIRE_PUNJAB, MOCK_FIRE_ANDAMAN]
        mock_resp = httpx.Response(200, json=mock_low)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await firms_server.get_high_confidence_fires()
        data = json.loads(result[0].text)
        assert len(data) == 0


# ---------------------------------------------------------------------------
# get_fire_detail
# ---------------------------------------------------------------------------


class TestGetFireDetail:
    @pytest.mark.asyncio
    async def test_returns_nearby_fires(self, firms_server):
        mock_resp = httpx.Response(200, json=MOCK_FIRES_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await firms_server.get_fire_detail(
                latitude=30.45, longitude=78.12
            )
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_filters_by_radius(self, firms_server):
        mock_resp = httpx.Response(200, json=MOCK_FIRES_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await firms_server.get_fire_detail(
                latitude=30.45, longitude=78.12, radius_km=10.0
            )
        data = json.loads(result[0].text)
        # Should only include fires near Uttarakhand (30.45, 78.12)
        for fire in data:
            assert abs(fire["latitude"] - 30.45) < 2.0  # Rough check

    @pytest.mark.asyncio
    async def test_custom_days(self, firms_server):
        mock_resp = httpx.Response(200, json=MOCK_FIRES_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await firms_server.get_fire_detail(
                latitude=30.45, longitude=78.12, days=5
            )
        call_args = mock_req.call_args
        url = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("url", "")
        assert "/5" in url


# ---------------------------------------------------------------------------
# get_fire_summary
# ---------------------------------------------------------------------------


class TestGetFireSummary:
    @pytest.mark.asyncio
    async def test_summary_structure(self, firms_server):
        mock_resp = httpx.Response(200, json=MOCK_FIRES_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await firms_server.get_fire_summary()
        data = json.loads(result[0].text)
        assert "total_fires" in data
        assert "by_confidence" in data
        assert "max_frp" in data
        assert "by_daynight" in data

    @pytest.mark.asyncio
    async def test_summary_counts(self, firms_server):
        mock_resp = httpx.Response(200, json=MOCK_FIRES_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await firms_server.get_fire_summary()
        data = json.loads(result[0].text)
        assert data["total_fires"] == 4
        assert data["max_frp"] == 55.0

    @pytest.mark.asyncio
    async def test_summary_confidence_breakdown(self, firms_server):
        mock_resp = httpx.Response(200, json=MOCK_FIRES_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await firms_server.get_fire_summary()
        data = json.loads(result[0].text)
        conf = data["by_confidence"]
        assert conf.get("high", 0) == 2
        assert conf.get("nominal", 0) == 1
        assert conf.get("low", 0) == 1

    @pytest.mark.asyncio
    async def test_summary_daynight(self, firms_server):
        mock_resp = httpx.Response(200, json=MOCK_FIRES_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await firms_server.get_fire_summary()
        data = json.loads(result[0].text)
        dn = data["by_daynight"]
        assert dn.get("D", 0) == 3
        assert dn.get("N", 0) == 1

    @pytest.mark.asyncio
    async def test_summary_empty(self, firms_server):
        mock_resp = httpx.Response(200, json=[])
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await firms_server.get_fire_summary()
        data = json.loads(result[0].text)
        assert data["total_fires"] == 0
        assert data["max_frp"] is None


# ---------------------------------------------------------------------------
# Error Handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_timeout_raises_mcp_error(self, firms_server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            with pytest.raises(MCPError, match="timed out"):
                await firms_server.get_active_fires()

    @pytest.mark.asyncio
    async def test_server_error_raises(self, firms_server):
        mock_resp = httpx.Response(500, text="Internal Server Error")
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            with pytest.raises(ExternalAPIError):
                await firms_server.get_active_fires()


# ---------------------------------------------------------------------------
# create_server() Factory
# ---------------------------------------------------------------------------


class TestCreateServer:
    def test_factory_returns_firms_server(self, settings):
        from src.protocols.mcp.firms_server import FIRMSServer, create_server

        server = create_server(settings=settings)
        assert isinstance(server, FIRMSServer)
        assert server.name == "mcp-firms"

    def test_factory_default_settings(self):
        from src.protocols.mcp.firms_server import create_server

        server = create_server()
        assert server.name == "mcp-firms"
