"""Unit tests for USGS Earthquake MCP server (S5.3).

Tests cover: initialization, tool registration, all 5 tool methods with
mock GeoJSON responses, response normalization, error handling (timeout,
server error, empty results), and the create_server() factory.
"""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.shared.config import CrisisSettings
from src.shared.errors import ExternalAPIError, MCPError

# ---------------------------------------------------------------------------
# Sample USGS GeoJSON Responses (mock data)
# ---------------------------------------------------------------------------

MOCK_FEATURE_INDIA = {
    "type": "Feature",
    "id": "us7000abc1",
    "properties": {
        "mag": 5.2,
        "place": "45km NNE of Uttarkashi, India",
        "time": 1773753000000,  # epoch ms
        "updated": 1773756600000,
        "tz": None,
        "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000abc1",
        "detail": "https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=us7000abc1&format=geojson",
        "felt": 150,
        "cdi": 5.0,
        "mmi": 4.5,
        "alert": "green",
        "status": "reviewed",
        "tsunami": 0,
        "sig": 416,
        "net": "us",
        "code": "7000abc1",
        "ids": ",us7000abc1,",
        "sources": ",us,",
        "types": ",dyfi,origin,phase-data,",
        "nst": 45,
        "dmin": 1.2,
        "rms": 0.8,
        "gap": 50,
        "magType": "mww",
        "type": "earthquake",
        "title": "M 5.2 - 45km NNE of Uttarkashi, India",
    },
    "geometry": {
        "type": "Point",
        "coordinates": [78.44, 30.73, 10.0],
    },
}

MOCK_FEATURE_NEPAL = {
    "type": "Feature",
    "id": "us7000abc2",
    "properties": {
        "mag": 4.1,
        "place": "20km SSW of Kathmandu, Nepal",
        "time": 1773749400000,
        "updated": 1773753000000,
        "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000abc2",
        "detail": "https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=us7000abc2&format=geojson",
        "felt": 30,
        "cdi": 3.5,
        "mmi": 3.0,
        "alert": None,
        "status": "reviewed",
        "tsunami": 0,
        "sig": 259,
        "net": "us",
        "code": "7000abc2",
        "magType": "mb",
        "type": "earthquake",
        "title": "M 4.1 - 20km SSW of Kathmandu, Nepal",
    },
    "geometry": {
        "type": "Point",
        "coordinates": [85.30, 27.60, 15.0],
    },
}

MOCK_FEATURE_ANDAMAN = {
    "type": "Feature",
    "id": "us7000abc3",
    "properties": {
        "mag": 6.0,
        "place": "Andaman Islands region",
        "time": 1773742800000,
        "updated": 1773746400000,
        "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000abc3",
        "detail": "https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=us7000abc3&format=geojson",
        "felt": 500,
        "cdi": 6.0,
        "mmi": 5.5,
        "alert": "yellow",
        "status": "reviewed",
        "tsunami": 1,
        "sig": 554,
        "net": "us",
        "code": "7000abc3",
        "magType": "mww",
        "type": "earthquake",
        "title": "M 6.0 - Andaman Islands region",
    },
    "geometry": {
        "type": "Point",
        "coordinates": [92.50, 12.20, 25.0],
    },
}


def _geojson_collection(*features) -> dict:
    """Build a USGS-style GeoJSON FeatureCollection."""
    return {
        "type": "FeatureCollection",
        "metadata": {
            "generated": 1773756600000,
            "url": "https://earthquake.usgs.gov/fdsnws/event/1/query",
            "title": "USGS Earthquakes",
            "status": 200,
            "api": "1.14.1",
            "count": len(features),
        },
        "features": list(features),
    }


MOCK_COLLECTION_ALL = _geojson_collection(
    MOCK_FEATURE_INDIA, MOCK_FEATURE_NEPAL, MOCK_FEATURE_ANDAMAN
)

MOCK_COLLECTION_SIGNIFICANT = _geojson_collection(
    MOCK_FEATURE_INDIA, MOCK_FEATURE_ANDAMAN
)

MOCK_COLLECTION_EMPTY = _geojson_collection()


MOCK_DETAIL_RESPONSE = {
    "type": "Feature",
    "id": "us7000abc1",
    "properties": {
        **MOCK_FEATURE_INDIA["properties"],
        "products": {"dyfi": [], "origin": []},
    },
    "geometry": MOCK_FEATURE_INDIA["geometry"],
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings():
    return CrisisSettings(LOG_LEVEL="WARNING")


@pytest.fixture
def usgs_server(settings):
    from src.protocols.mcp.usgs_server import USGSServer

    return USGSServer(settings=settings)


# ---------------------------------------------------------------------------
# Initialization & Tool Registration
# ---------------------------------------------------------------------------


class TestUSGSServerInit:
    def test_name(self, usgs_server):
        assert usgs_server.name == "mcp-usgs"

    def test_api_base_url(self, usgs_server):
        assert "earthquake.usgs.gov" in usgs_server.api_base_url

    def test_no_api_key(self, usgs_server):
        assert usgs_server.api_key == ""

    def test_rate_limit_set(self, usgs_server):
        assert usgs_server.rate_limit_rpm == 60

    def test_all_tools_registered(self, usgs_server):
        tools = usgs_server.mcp._tool_manager._tools
        expected = {
            "get_recent_earthquakes",
            "get_earthquakes_by_region",
            "get_significant_earthquakes",
            "get_earthquake_detail",
            "get_seismic_summary",
        }
        assert expected.issubset(set(tools.keys()))


# ---------------------------------------------------------------------------
# _normalize_feature
# ---------------------------------------------------------------------------


class TestNormalizeFeature:
    def test_extracts_event_id(self, usgs_server):
        result = usgs_server._normalize_feature(MOCK_FEATURE_INDIA)
        assert result["event_id"] == "us7000abc1"

    def test_extracts_magnitude(self, usgs_server):
        result = usgs_server._normalize_feature(MOCK_FEATURE_INDIA)
        assert result["magnitude"] == 5.2

    def test_extracts_magnitude_type(self, usgs_server):
        result = usgs_server._normalize_feature(MOCK_FEATURE_INDIA)
        assert result["magnitude_type"] == "mww"

    def test_extracts_place(self, usgs_server):
        result = usgs_server._normalize_feature(MOCK_FEATURE_INDIA)
        assert "Uttarkashi" in result["place"]

    def test_extracts_coordinates(self, usgs_server):
        result = usgs_server._normalize_feature(MOCK_FEATURE_INDIA)
        assert result["latitude"] == 30.73
        assert result["longitude"] == 78.44
        assert result["depth_km"] == 10.0

    def test_extracts_tsunami_alert(self, usgs_server):
        result_no = usgs_server._normalize_feature(MOCK_FEATURE_INDIA)
        assert result_no["tsunami_alert"] is False
        result_yes = usgs_server._normalize_feature(MOCK_FEATURE_ANDAMAN)
        assert result_yes["tsunami_alert"] is True

    def test_extracts_felt_reports(self, usgs_server):
        result = usgs_server._normalize_feature(MOCK_FEATURE_INDIA)
        assert result["felt_reports"] == 150

    def test_extracts_alert_level(self, usgs_server):
        result = usgs_server._normalize_feature(MOCK_FEATURE_INDIA)
        assert result["alert_level"] == "green"

    def test_extracts_url(self, usgs_server):
        result = usgs_server._normalize_feature(MOCK_FEATURE_INDIA)
        assert "eventpage" in result["url"]

    def test_null_alert_becomes_none(self, usgs_server):
        result = usgs_server._normalize_feature(MOCK_FEATURE_NEPAL)
        assert result["alert_level"] is None

    def test_time_converted_to_iso(self, usgs_server):
        result = usgs_server._normalize_feature(MOCK_FEATURE_INDIA)
        assert "time" in result
        # Should be an ISO string, not epoch ms
        assert isinstance(result["time"], str)
        assert "T" in result["time"]


# ---------------------------------------------------------------------------
# get_recent_earthquakes
# ---------------------------------------------------------------------------


class TestGetRecentEarthquakes:
    @pytest.mark.asyncio
    async def test_returns_earthquake_data(self, usgs_server):
        mock_resp = httpx.Response(200, json=MOCK_COLLECTION_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await usgs_server.get_recent_earthquakes()
        data = json.loads(result[0].text)
        assert len(data) == 3

    @pytest.mark.asyncio
    async def test_default_params_include_india_bbox(self, usgs_server):
        mock_resp = httpx.Response(200, json=MOCK_COLLECTION_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await usgs_server.get_recent_earthquakes()
        params = mock_req.call_args.kwargs.get("params", {})
        assert params["minlatitude"] == 6.0
        assert params["maxlatitude"] == 37.0
        assert params["minlongitude"] == 68.0
        assert params["maxlongitude"] == 98.0

    @pytest.mark.asyncio
    async def test_custom_magnitude(self, usgs_server):
        mock_resp = httpx.Response(200, json=MOCK_COLLECTION_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await usgs_server.get_recent_earthquakes(min_magnitude=4.0)
        params = mock_req.call_args.kwargs.get("params", {})
        assert params["minmagnitude"] == 4.0

    @pytest.mark.asyncio
    async def test_custom_hours(self, usgs_server):
        mock_resp = httpx.Response(200, json=MOCK_COLLECTION_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await usgs_server.get_recent_earthquakes(hours=48)
        params = mock_req.call_args.kwargs.get("params", {})
        assert "starttime" in params

    @pytest.mark.asyncio
    async def test_empty_result(self, usgs_server):
        mock_resp = httpx.Response(200, json=MOCK_COLLECTION_EMPTY)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await usgs_server.get_recent_earthquakes()
        data = json.loads(result[0].text)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_normalized_fields(self, usgs_server):
        mock_resp = httpx.Response(200, json=MOCK_COLLECTION_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await usgs_server.get_recent_earthquakes()
        data = json.loads(result[0].text)
        eq = data[0]
        assert "event_id" in eq
        assert "magnitude" in eq
        assert "latitude" in eq
        assert "longitude" in eq
        assert "depth_km" in eq


# ---------------------------------------------------------------------------
# get_earthquakes_by_region
# ---------------------------------------------------------------------------


class TestGetEarthquakesByRegion:
    @pytest.mark.asyncio
    async def test_custom_bbox(self, usgs_server):
        mock_resp = httpx.Response(200, json=MOCK_COLLECTION_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await usgs_server.get_earthquakes_by_region(
                min_lat=28.0, max_lat=32.0, min_lon=76.0, max_lon=80.0
            )
        params = mock_req.call_args.kwargs.get("params", {})
        assert params["minlatitude"] == 28.0
        assert params["maxlatitude"] == 32.0
        assert params["minlongitude"] == 76.0
        assert params["maxlongitude"] == 80.0

    @pytest.mark.asyncio
    async def test_custom_days(self, usgs_server):
        mock_resp = httpx.Response(200, json=MOCK_COLLECTION_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await usgs_server.get_earthquakes_by_region(
                min_lat=10.0, max_lat=15.0, min_lon=70.0, max_lon=80.0, days=30
            )
        params = mock_req.call_args.kwargs.get("params", {})
        assert "starttime" in params

    @pytest.mark.asyncio
    async def test_returns_normalized(self, usgs_server):
        mock_resp = httpx.Response(200, json=MOCK_COLLECTION_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await usgs_server.get_earthquakes_by_region(
                min_lat=10.0, max_lat=15.0, min_lon=70.0, max_lon=80.0
            )
        data = json.loads(result[0].text)
        assert isinstance(data, list)


# ---------------------------------------------------------------------------
# get_significant_earthquakes
# ---------------------------------------------------------------------------


class TestGetSignificantEarthquakes:
    @pytest.mark.asyncio
    async def test_uses_min_magnitude_5(self, usgs_server):
        mock_resp = httpx.Response(200, json=MOCK_COLLECTION_SIGNIFICANT)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await usgs_server.get_significant_earthquakes()
        params = mock_req.call_args.kwargs.get("params", {})
        assert params["minmagnitude"] == 5.0

    @pytest.mark.asyncio
    async def test_returns_data(self, usgs_server):
        mock_resp = httpx.Response(200, json=MOCK_COLLECTION_SIGNIFICANT)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await usgs_server.get_significant_earthquakes()
        data = json.loads(result[0].text)
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_custom_days(self, usgs_server):
        mock_resp = httpx.Response(200, json=MOCK_COLLECTION_SIGNIFICANT)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await usgs_server.get_significant_earthquakes(days=60)
        params = mock_req.call_args.kwargs.get("params", {})
        assert "starttime" in params


# ---------------------------------------------------------------------------
# get_earthquake_detail
# ---------------------------------------------------------------------------


class TestGetEarthquakeDetail:
    @pytest.mark.asyncio
    async def test_returns_detail(self, usgs_server):
        mock_resp = httpx.Response(200, json=MOCK_DETAIL_RESPONSE)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await usgs_server.get_earthquake_detail(event_id="us7000abc1")
        data = json.loads(result[0].text)
        assert data["event_id"] == "us7000abc1"
        assert data["magnitude"] == 5.2

    @pytest.mark.asyncio
    async def test_passes_event_id_in_params(self, usgs_server):
        mock_resp = httpx.Response(200, json=MOCK_DETAIL_RESPONSE)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await usgs_server.get_earthquake_detail(event_id="us7000abc1")
        params = mock_req.call_args.kwargs.get("params", {})
        assert params["eventid"] == "us7000abc1"

    @pytest.mark.asyncio
    async def test_not_found_raises(self, usgs_server):
        mock_resp = httpx.Response(404, text="Not Found")
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            with pytest.raises(MCPError, match="404"):
                await usgs_server.get_earthquake_detail(event_id="INVALID")


# ---------------------------------------------------------------------------
# get_seismic_summary
# ---------------------------------------------------------------------------


class TestGetSeismicSummary:
    @pytest.mark.asyncio
    async def test_summary_structure(self, usgs_server):
        mock_resp = httpx.Response(200, json=MOCK_COLLECTION_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await usgs_server.get_seismic_summary()
        data = json.loads(result[0].text)
        assert "total_earthquakes" in data
        assert "by_magnitude_range" in data
        assert "max_magnitude" in data
        assert "max_magnitude_event" in data

    @pytest.mark.asyncio
    async def test_summary_counts(self, usgs_server):
        mock_resp = httpx.Response(200, json=MOCK_COLLECTION_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await usgs_server.get_seismic_summary()
        data = json.loads(result[0].text)
        assert data["total_earthquakes"] == 3
        assert data["max_magnitude"] == 6.0

    @pytest.mark.asyncio
    async def test_summary_magnitude_ranges(self, usgs_server):
        mock_resp = httpx.Response(200, json=MOCK_COLLECTION_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await usgs_server.get_seismic_summary()
        data = json.loads(result[0].text)
        ranges = data["by_magnitude_range"]
        # M4.1 -> "4.0-4.9", M5.2 -> "5.0-5.9", M6.0 -> "6.0+"
        assert ranges.get("4.0-4.9", 0) >= 1
        assert ranges.get("5.0-5.9", 0) >= 1
        assert ranges.get("6.0+", 0) >= 1

    @pytest.mark.asyncio
    async def test_summary_empty(self, usgs_server):
        mock_resp = httpx.Response(200, json=MOCK_COLLECTION_EMPTY)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await usgs_server.get_seismic_summary()
        data = json.loads(result[0].text)
        assert data["total_earthquakes"] == 0
        assert data["max_magnitude"] is None

    @pytest.mark.asyncio
    async def test_summary_tsunami_count(self, usgs_server):
        mock_resp = httpx.Response(200, json=MOCK_COLLECTION_ALL)
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await usgs_server.get_seismic_summary()
        data = json.loads(result[0].text)
        assert data["tsunami_alerts"] == 1


# ---------------------------------------------------------------------------
# Error Handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_timeout_raises_mcp_error(self, usgs_server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            with pytest.raises(MCPError, match="timed out"):
                await usgs_server.get_recent_earthquakes()

    @pytest.mark.asyncio
    async def test_server_error_raises(self, usgs_server):
        mock_resp = httpx.Response(500, text="Internal Server Error")
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            with pytest.raises(ExternalAPIError):
                await usgs_server.get_recent_earthquakes()


# ---------------------------------------------------------------------------
# create_server() Factory
# ---------------------------------------------------------------------------


class TestCreateServer:
    def test_factory_returns_usgs_server(self, settings):
        from src.protocols.mcp.usgs_server import USGSServer, create_server

        server = create_server(settings=settings)
        assert isinstance(server, USGSServer)
        assert server.name == "mcp-usgs"

    def test_factory_default_settings(self):
        from src.protocols.mcp.usgs_server import create_server

        server = create_server()
        assert server.name == "mcp-usgs"
