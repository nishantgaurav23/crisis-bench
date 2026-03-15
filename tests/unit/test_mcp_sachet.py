"""Unit tests for SACHET CAP Feed MCP server (S5.2).

Tests cover: initialization, CAP XML parsing, feed fetching with cache,
get_active_alerts (all + state filter), get_alerts_by_hazard,
get_alerts_by_severity, get_alert_detail, get_alerts_summary,
error handling (feed down, malformed XML).
"""

import json
import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.shared.config import CrisisSettings
from src.shared.errors import ExternalAPIError, MCPError

# ---------------------------------------------------------------------------
# Sample CAP XML data
# ---------------------------------------------------------------------------

SAMPLE_CAP_ENTRY_CYCLONE = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>SACHET-IMD-2026-001</identifier>
  <sender>IMD</sender>
  <sent>2026-03-15T08:00:00+05:30</sent>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <category>Met</category>
    <event>Very Severe Cyclonic Storm Warning</event>
    <urgency>Immediate</urgency>
    <severity>Extreme</severity>
    <certainty>Observed</certainty>
    <senderName>India Meteorological Department</senderName>
    <headline>VSCS approaching Odisha coast</headline>
    <description>Very Severe Cyclonic Storm with wind speed 120-130 kmph approaching Odisha coast. Expected landfall near Puri within 24 hours.</description>
    <instruction>Evacuate coastal areas immediately. Move to designated shelters.</instruction>
    <area>
      <areaDesc>Odisha, Puri, Ganjam, Khordha</areaDesc>
      <polygon>19.5,84.5 20.5,84.5 20.5,86.5 19.5,86.5 19.5,84.5</polygon>
    </area>
  </info>
</alert>"""

SAMPLE_CAP_ENTRY_FLOOD = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>SACHET-CWC-2026-042</identifier>
  <sender>CWC</sender>
  <sent>2026-03-15T10:30:00+05:30</sent>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <category>Met</category>
    <event>Flood Warning</event>
    <urgency>Expected</urgency>
    <severity>Severe</severity>
    <certainty>Likely</certainty>
    <senderName>Central Water Commission</senderName>
    <headline>Flood alert for Mahanadi basin</headline>
    <description>Water level in Mahanadi at Mundali is rising. Expected to cross danger level within 12 hours.</description>
    <instruction>Residents in low-lying areas along Mahanadi should move to higher ground.</instruction>
    <area>
      <areaDesc>Odisha, Cuttack, Jagatsinghpur</areaDesc>
    </area>
  </info>
</alert>"""

SAMPLE_CAP_ENTRY_EARTHQUAKE = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>SACHET-NCS-2026-015</identifier>
  <sender>NCS</sender>
  <sent>2026-03-14T23:15:00+05:30</sent>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <category>Geo</category>
    <event>Earthquake Alert</event>
    <urgency>Past</urgency>
    <severity>Moderate</severity>
    <certainty>Observed</certainty>
    <senderName>National Center for Seismology</senderName>
    <headline>M4.5 earthquake near Uttarkashi</headline>
    <description>An earthquake of magnitude 4.5 occurred near Uttarkashi, Uttarakhand at 23:10 IST. Depth: 10km.</description>
    <instruction>Check buildings for damage. Stay away from damaged structures.</instruction>
    <area>
      <areaDesc>Uttarakhand, Uttarkashi, Dehradun</areaDesc>
    </area>
  </info>
</alert>"""

SAMPLE_CAP_ENTRY_HEATWAVE = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>SACHET-IMD-2026-099</identifier>
  <sender>IMD</sender>
  <sent>2026-03-15T06:00:00+05:30</sent>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <category>Met</category>
    <event>Heat Wave Warning</event>
    <urgency>Expected</urgency>
    <severity>Severe</severity>
    <certainty>Likely</certainty>
    <senderName>India Meteorological Department</senderName>
    <headline>Severe heat wave over Rajasthan</headline>
    <description>Maximum temperature likely to exceed 45 deg C over western Rajasthan during next 3 days.</description>
    <instruction>Avoid outdoor work between 12-4 PM. Stay hydrated.</instruction>
    <area>
      <areaDesc>Rajasthan, Jodhpur, Jaisalmer, Barmer</areaDesc>
    </area>
  </info>
</alert>"""


def _build_rss_feed(*cap_entries: str) -> str:
    """Build a mock RSS feed wrapping CAP entries."""
    items = ""
    for entry in cap_entries:
        items += f"""
    <item>
      <title>Alert</title>
      <description>CAP Alert</description>
      <content:encoded><![CDATA[{entry}]]></content:encoded>
    </item>"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>SACHET CAP Feed</title>
    <link>https://sachet.ndma.gov.in/CapFeed</link>
    <description>NDMA Common Alerting Protocol Feed</description>
    {items}
  </channel>
</rss>"""


SAMPLE_RSS_ALL = _build_rss_feed(
    SAMPLE_CAP_ENTRY_CYCLONE,
    SAMPLE_CAP_ENTRY_FLOOD,
    SAMPLE_CAP_ENTRY_EARTHQUAKE,
    SAMPLE_CAP_ENTRY_HEATWAVE,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings():
    return CrisisSettings(
        BHUVAN_TOKEN="test-token",
        NASA_FIRMS_KEY="test-firms",
        LOG_LEVEL="WARNING",
    )


@pytest.fixture
def server(settings):
    from src.protocols.mcp.sachet_server import SACHETServer

    return SACHETServer(settings=settings)


def _mock_feed_response(rss_text: str = SAMPLE_RSS_ALL) -> httpx.Response:
    """Create a mock httpx.Response returning RSS text."""
    return httpx.Response(200, text=rss_text, headers={"content-type": "application/xml"})


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInit:
    def test_server_name(self, server):
        assert server.name == "mcp-sachet"

    def test_base_url(self, server):
        assert "sachet.ndma.gov.in" in server.api_base_url

    def test_no_auth_required(self, server):
        assert server.api_key == ""

    def test_tools_registered(self, server):
        tools = server.mcp._tool_manager._tools
        expected = {
            "get_active_alerts",
            "get_alerts_by_hazard",
            "get_alerts_by_severity",
            "get_alert_detail",
            "get_alerts_summary",
        }
        assert expected.issubset(set(tools.keys()))


# ---------------------------------------------------------------------------
# CAP XML Parsing
# ---------------------------------------------------------------------------


class TestCAPParsing:
    def test_parse_cyclone_entry(self, server):
        alert = server._parse_cap_entry(SAMPLE_CAP_ENTRY_CYCLONE)
        assert alert["identifier"] == "SACHET-IMD-2026-001"
        assert alert["sender"] == "IMD"
        assert alert["status"] == "Actual"
        assert alert["severity"] == "Extreme"
        assert alert["urgency"] == "Immediate"
        assert alert["category"] == "Met"
        assert "cyclonic" in alert["event"].lower()
        assert "Odisha" in alert["area_desc"]

    def test_parse_flood_entry(self, server):
        alert = server._parse_cap_entry(SAMPLE_CAP_ENTRY_FLOOD)
        assert alert["identifier"] == "SACHET-CWC-2026-042"
        assert alert["sender"] == "CWC"
        assert alert["severity"] == "Severe"
        assert "flood" in alert["event"].lower()

    def test_parse_earthquake_entry(self, server):
        alert = server._parse_cap_entry(SAMPLE_CAP_ENTRY_EARTHQUAKE)
        assert alert["identifier"] == "SACHET-NCS-2026-015"
        assert alert["category"] == "Geo"
        assert alert["severity"] == "Moderate"

    def test_parse_extracts_headline(self, server):
        alert = server._parse_cap_entry(SAMPLE_CAP_ENTRY_CYCLONE)
        assert "VSCS" in alert["headline"]

    def test_parse_extracts_description(self, server):
        alert = server._parse_cap_entry(SAMPLE_CAP_ENTRY_CYCLONE)
        assert "120-130 kmph" in alert["description"]

    def test_parse_extracts_instruction(self, server):
        alert = server._parse_cap_entry(SAMPLE_CAP_ENTRY_CYCLONE)
        assert "Evacuate" in alert["instruction"]

    def test_parse_extracts_polygon(self, server):
        alert = server._parse_cap_entry(SAMPLE_CAP_ENTRY_CYCLONE)
        assert alert["polygon"] is not None
        assert "19.5" in alert["polygon"]

    def test_parse_no_polygon_returns_none(self, server):
        alert = server._parse_cap_entry(SAMPLE_CAP_ENTRY_FLOOD)
        assert alert["polygon"] is None

    def test_parse_extracts_sent_timestamp(self, server):
        alert = server._parse_cap_entry(SAMPLE_CAP_ENTRY_CYCLONE)
        assert "2026-03-15" in alert["sent"]

    def test_parse_extracts_sender_name(self, server):
        alert = server._parse_cap_entry(SAMPLE_CAP_ENTRY_CYCLONE)
        assert "India Meteorological Department" in alert["sender_name"]


# ---------------------------------------------------------------------------
# Feed Fetching + Cache
# ---------------------------------------------------------------------------


class TestFeedFetch:
    @pytest.mark.asyncio
    async def test_fetch_returns_parsed_alerts(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_feed_response(),
        ):
            alerts = await server._fetch_feed()
        assert len(alerts) == 4

    @pytest.mark.asyncio
    async def test_fetch_caches_for_60s(self, server):
        mock_resp = _mock_feed_response()
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_resp,
        ) as mock_req:
            alerts1 = await server._fetch_feed()
            alerts2 = await server._fetch_feed()
        # Only one HTTP call — second was served from cache
        assert mock_req.call_count == 1
        assert alerts1 == alerts2

    @pytest.mark.asyncio
    async def test_fetch_cache_expires(self, server):
        mock_resp = _mock_feed_response()
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_resp,
        ) as mock_req:
            await server._fetch_feed()
            # Expire cache by setting timestamp to past
            server._cache_timestamp = time.monotonic() - 61
            await server._fetch_feed()
        assert mock_req.call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_feed_down_raises(self, server):
        mock_resp = httpx.Response(503, text="Service Unavailable")
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_resp,
        ):
            with pytest.raises((ExternalAPIError, MCPError)):
                await server._fetch_feed()


# ---------------------------------------------------------------------------
# get_active_alerts
# ---------------------------------------------------------------------------


class TestGetActiveAlerts:
    @pytest.mark.asyncio
    async def test_returns_all_alerts(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_feed_response(),
        ):
            result = await server.get_active_alerts()
        data = json.loads(result[0].text)
        assert len(data) == 4

    @pytest.mark.asyncio
    async def test_filter_by_state_odisha(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_feed_response(),
        ):
            result = await server.get_active_alerts(state="Odisha")
        data = json.loads(result[0].text)
        # Cyclone + Flood both mention Odisha
        assert len(data) == 2
        for alert in data:
            assert "odisha" in alert["area_desc"].lower()

    @pytest.mark.asyncio
    async def test_filter_by_state_case_insensitive(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_feed_response(),
        ):
            result = await server.get_active_alerts(state="odisha")
        data = json.loads(result[0].text)
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_filter_no_match_returns_empty(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_feed_response(),
        ):
            result = await server.get_active_alerts(state="Kerala")
        data = json.loads(result[0].text)
        assert len(data) == 0


# ---------------------------------------------------------------------------
# get_alerts_by_hazard
# ---------------------------------------------------------------------------


class TestGetAlertsByHazard:
    @pytest.mark.asyncio
    async def test_cyclone(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_feed_response(),
        ):
            result = await server.get_alerts_by_hazard(hazard_type="cyclone")
        data = json.loads(result[0].text)
        assert len(data) == 1
        assert "SACHET-IMD-2026-001" == data[0]["identifier"]

    @pytest.mark.asyncio
    async def test_flood(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_feed_response(),
        ):
            result = await server.get_alerts_by_hazard(hazard_type="flood")
        data = json.loads(result[0].text)
        assert len(data) == 1
        assert data[0]["sender"] == "CWC"

    @pytest.mark.asyncio
    async def test_earthquake(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_feed_response(),
        ):
            result = await server.get_alerts_by_hazard(hazard_type="earthquake")
        data = json.loads(result[0].text)
        assert len(data) == 1
        assert data[0]["sender"] == "NCS"

    @pytest.mark.asyncio
    async def test_heatwave(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_feed_response(),
        ):
            result = await server.get_alerts_by_hazard(hazard_type="heatwave")
        data = json.loads(result[0].text)
        assert len(data) == 1
        assert "heat" in data[0]["event"].lower()

    @pytest.mark.asyncio
    async def test_unknown_hazard_returns_empty(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_feed_response(),
        ):
            result = await server.get_alerts_by_hazard(hazard_type="volcanic")
        data = json.loads(result[0].text)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_case_insensitive(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_feed_response(),
        ):
            result = await server.get_alerts_by_hazard(hazard_type="CYCLONE")
        data = json.loads(result[0].text)
        assert len(data) == 1


# ---------------------------------------------------------------------------
# get_alerts_by_severity
# ---------------------------------------------------------------------------


class TestGetAlertsBySeverity:
    @pytest.mark.asyncio
    async def test_extreme(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_feed_response(),
        ):
            result = await server.get_alerts_by_severity(severity="Extreme")
        data = json.loads(result[0].text)
        assert len(data) == 1
        assert data[0]["severity"] == "Extreme"

    @pytest.mark.asyncio
    async def test_severe(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_feed_response(),
        ):
            result = await server.get_alerts_by_severity(severity="Severe")
        data = json.loads(result[0].text)
        assert len(data) == 2  # Flood + Heatwave

    @pytest.mark.asyncio
    async def test_moderate(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_feed_response(),
        ):
            result = await server.get_alerts_by_severity(severity="Moderate")
        data = json.loads(result[0].text)
        assert len(data) == 1
        assert data[0]["sender"] == "NCS"

    @pytest.mark.asyncio
    async def test_case_insensitive(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_feed_response(),
        ):
            result = await server.get_alerts_by_severity(severity="extreme")
        data = json.loads(result[0].text)
        assert len(data) == 1


# ---------------------------------------------------------------------------
# get_alert_detail
# ---------------------------------------------------------------------------


class TestGetAlertDetail:
    @pytest.mark.asyncio
    async def test_found(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_feed_response(),
        ):
            result = await server.get_alert_detail(
                alert_id="SACHET-IMD-2026-001"
            )
        data = json.loads(result[0].text)
        assert data["identifier"] == "SACHET-IMD-2026-001"
        assert data["sender"] == "IMD"

    @pytest.mark.asyncio
    async def test_not_found(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_feed_response(),
        ):
            result = await server.get_alert_detail(alert_id="NONEXISTENT-123")
        data = json.loads(result[0].text)
        assert data["error"] == "not_found"


# ---------------------------------------------------------------------------
# get_alerts_summary
# ---------------------------------------------------------------------------


class TestGetAlertsSummary:
    @pytest.mark.asyncio
    async def test_summary_structure(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_feed_response(),
        ):
            result = await server.get_alerts_summary()
        data = json.loads(result[0].text)
        assert "total_alerts" in data
        assert "by_severity" in data
        assert "by_category" in data
        assert "affected_states" in data

    @pytest.mark.asyncio
    async def test_summary_counts(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_feed_response(),
        ):
            result = await server.get_alerts_summary()
        data = json.loads(result[0].text)
        assert data["total_alerts"] == 4
        assert data["by_severity"]["Extreme"] == 1
        assert data["by_severity"]["Severe"] == 2
        assert data["by_severity"]["Moderate"] == 1

    @pytest.mark.asyncio
    async def test_summary_affected_states(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=_mock_feed_response(),
        ):
            result = await server.get_alerts_summary()
        data = json.loads(result[0].text)
        states = data["affected_states"]
        assert "Odisha" in states
        assert "Uttarakhand" in states
        assert "Rajasthan" in states


# ---------------------------------------------------------------------------
# Hazard Keyword Mapping
# ---------------------------------------------------------------------------


class TestHazardMapping:
    def test_cyclone_keywords(self, server):
        assert server._matches_hazard("Very Severe Cyclonic Storm", "cyclone")
        assert server._matches_hazard("Depression over Bay of Bengal", "cyclone")

    def test_flood_keywords(self, server):
        assert server._matches_hazard("Flood Warning", "flood")
        assert server._matches_hazard("Urban waterlogging alert", "flood")

    def test_earthquake_keywords(self, server):
        assert server._matches_hazard("Earthquake Alert", "earthquake")
        assert server._matches_hazard("Seismic activity detected", "earthquake")

    def test_heatwave_keywords(self, server):
        assert server._matches_hazard("Heat Wave Warning", "heatwave")
        assert server._matches_hazard("Hot weather alert", "heatwave")

    def test_no_match(self, server):
        assert not server._matches_hazard("Random event", "cyclone")

    def test_unknown_hazard_type(self, server):
        assert not server._matches_hazard("Any event", "volcanic")


# ---------------------------------------------------------------------------
# Error Handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_malformed_rss_skips_bad_entries(self, server):
        """Malformed CAP entries should be skipped, valid ones returned."""
        bad_rss = _build_rss_feed(
            SAMPLE_CAP_ENTRY_CYCLONE,
            "<not-valid-cap>garbage</not-valid-cap>",
        )
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=httpx.Response(200, text=bad_rss),
        ):
            alerts = await server._fetch_feed()
        # Only the valid cyclone entry should be returned
        assert len(alerts) == 1
        assert alerts[0]["identifier"] == "SACHET-IMD-2026-001"

    @pytest.mark.asyncio
    async def test_empty_feed_returns_empty(self, server):
        empty_rss = _build_rss_feed()
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=httpx.Response(200, text=empty_rss),
        ):
            alerts = await server._fetch_feed()
        assert len(alerts) == 0
