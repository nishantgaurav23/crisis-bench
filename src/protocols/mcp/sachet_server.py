"""MCP server for NDMA SACHET Common Alerting Protocol feed (S5.2).

Wraps India's unified all-hazard alert system (``sachet.ndma.gov.in/CapFeed``)
as an MCP server. SACHET aggregates warnings from 7 national agencies
(IMD, CWC, INCOIS, NCS, GSI, DGRE, FSI) + 36 state/UT disaster authorities
into a single RSS feed using the international CAP v1.2 XML standard.

MCP Tools:
    - ``get_active_alerts``    — all alerts, optional state filter
    - ``get_alerts_by_hazard`` — filter by hazard type keyword
    - ``get_alerts_by_severity`` — filter by CAP severity level
    - ``get_alert_detail``     — single alert by identifier
    - ``get_alerts_summary``   — aggregate counts + affected states
"""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from typing import Any

from mcp.types import TextContent

from src.protocols.mcp.base import BaseMCPServer
from src.shared.config import CrisisSettings

# ---------------------------------------------------------------------------
# CAP v1.2 namespace
# ---------------------------------------------------------------------------

CAP_NS = "urn:oasis:names:tc:emergency:cap:1.2"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"

# ---------------------------------------------------------------------------
# Hazard keyword mapping (India-specific)
# ---------------------------------------------------------------------------

HAZARD_KEYWORDS: dict[str, list[str]] = {
    "cyclone": [
        "cyclone", "cyclonic storm", "depression", "vscs", "escs", "sucs",
    ],
    "flood": [
        "flood", "inundation", "waterlogging", "deluge", "dam",
    ],
    "earthquake": [
        "earthquake", "seismic", "tremor",
    ],
    "tsunami": [
        "tsunami",
    ],
    "landslide": [
        "landslide", "mudslide", "debris flow",
    ],
    "heatwave": [
        "heatwave", "heat wave", "hot weather",
    ],
    "fire": [
        "fire", "wildfire", "forest fire",
    ],
    "thunderstorm": [
        "thunderstorm", "lightning", "squall", "dust storm",
    ],
}

# Indian states for extraction from areaDesc
INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar",
    "Chhattisgarh", "Goa", "Gujarat", "Haryana", "Himachal Pradesh",
    "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra",
    "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Delhi", "Jammu and Kashmir", "Ladakh", "Puducherry",
    "Chandigarh", "Dadra and Nagar Haveli", "Lakshadweep",
    "Andaman and Nicobar",
]


class SACHETServer(BaseMCPServer):
    """MCP server wrapping NDMA SACHET CAP v1.2 feed."""

    def __init__(self, *, settings: CrisisSettings | None = None) -> None:
        super().__init__(
            name="mcp-sachet",
            api_base_url="https://sachet.ndma.gov.in",
            settings=settings,
        )
        self._cache: list[dict[str, Any]] = []
        self._cache_timestamp: float = 0.0
        self._cache_ttl: float = 60.0

        self.register_tool(self.get_active_alerts)
        self.register_tool(self.get_alerts_by_hazard)
        self.register_tool(self.get_alerts_by_severity)
        self.register_tool(self.get_alert_detail)
        self.register_tool(self.get_alerts_summary)

    # ------------------------------------------------------------------
    # CAP XML Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_cap_entry(xml_str: str) -> dict[str, Any]:
        """Parse a single CAP v1.2 XML alert into a flat dict."""
        root = ET.fromstring(xml_str)
        ns = {"cap": CAP_NS}

        def _text(parent: ET.Element, tag: str) -> str:
            elem = parent.find(f"cap:{tag}", ns)
            if elem is None:
                elem = parent.find(tag)
            return (elem.text or "").strip() if elem is not None else ""

        info = root.find("cap:info", ns)
        if info is None:
            info = root.find("info")

        area_elem = None
        if info is not None:
            area_elem = info.find("cap:area", ns)
            if area_elem is None:
                area_elem = info.find("area")

        area_desc = ""
        polygon = None
        if area_elem is not None:
            area_desc = _text(area_elem, "areaDesc")
            poly_elem = area_elem.find("cap:polygon", ns)
            if poly_elem is None:
                poly_elem = area_elem.find("polygon")
            polygon = (
                poly_elem.text.strip()
                if poly_elem is not None and poly_elem.text
                else None
            )

        return {
            "identifier": _text(root, "identifier"),
            "sender": _text(root, "sender"),
            "sent": _text(root, "sent"),
            "status": _text(root, "status"),
            "msg_type": _text(root, "msgType"),
            "scope": _text(root, "scope"),
            "category": _text(info, "category") if info is not None else "",
            "event": _text(info, "event") if info is not None else "",
            "urgency": _text(info, "urgency") if info is not None else "",
            "severity": (
                _text(info, "severity") if info is not None else ""
            ),
            "certainty": (
                _text(info, "certainty") if info is not None else ""
            ),
            "sender_name": (
                _text(info, "senderName") if info is not None else ""
            ),
            "headline": (
                _text(info, "headline") if info is not None else ""
            ),
            "description": (
                _text(info, "description") if info is not None else ""
            ),
            "instruction": (
                _text(info, "instruction") if info is not None else ""
            ),
            "area_desc": area_desc,
            "polygon": polygon,
        }

    # ------------------------------------------------------------------
    # Feed Fetching with Cache
    # ------------------------------------------------------------------

    async def _fetch_feed(self) -> list[dict[str, Any]]:
        """Fetch and parse the SACHET RSS/CAP feed. Cached for 60s."""
        now = time.monotonic()
        if self._cache and (now - self._cache_timestamp) < self._cache_ttl:
            return self._cache

        client = self.get_http_client()
        self._check_rate_limit()
        resp = await client.request(
            "GET",
            f"{self.api_base_url}/CapFeed",
            headers={},
        )
        if resp.status_code != 200:
            self._raise_for_status(resp, "GET", "/CapFeed")

        rss_text = resp.text
        alerts = self._parse_rss_feed(rss_text)
        self._cache = alerts
        self._cache_timestamp = time.monotonic()
        return alerts

    def _parse_rss_feed(self, rss_text: str) -> list[dict[str, Any]]:
        """Extract CAP entries from RSS XML."""
        alerts: list[dict[str, Any]] = []
        # Extract content:encoded CDATA blocks containing CAP XML
        pattern = r"<content:encoded>\s*<!\[CDATA\[(.*?)\]\]>"
        matches = re.findall(pattern, rss_text, re.DOTALL)

        for cap_xml in matches:
            cap_xml = cap_xml.strip()
            if not cap_xml:
                continue
            try:
                alert = self._parse_cap_entry(cap_xml)
                if alert.get("identifier"):
                    alerts.append(alert)
            except ET.ParseError:
                self.logger.warning(
                    "sachet_cap_parse_error",
                    raw_length=len(cap_xml),
                )
                continue
        return alerts

    # ------------------------------------------------------------------
    # Hazard Matching
    # ------------------------------------------------------------------

    @staticmethod
    def _matches_hazard(event_text: str, hazard_type: str) -> bool:
        """Check if event text matches a hazard type via keywords."""
        keywords = HAZARD_KEYWORDS.get(hazard_type.lower(), [])
        if not keywords:
            return False
        event_lower = event_text.lower()
        return any(kw in event_lower for kw in keywords)

    # ------------------------------------------------------------------
    # State Extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_states(area_desc: str) -> list[str]:
        """Extract Indian state names from an areaDesc string."""
        found = []
        for state in INDIAN_STATES:
            if state.lower() in area_desc.lower():
                found.append(state)
        return found

    # ------------------------------------------------------------------
    # MCP Tools
    # ------------------------------------------------------------------

    async def get_active_alerts(
        self, state: str = "",
    ) -> list[TextContent]:
        """Get active disaster alerts from SACHET CAP feed.

        Optionally filter by Indian state name (case-insensitive).
        """
        alerts = await self._fetch_feed()
        if state:
            state_lower = state.lower()
            alerts = [
                a for a in alerts
                if state_lower in a.get("area_desc", "").lower()
            ]
        return self.normalize_json(alerts)

    async def get_alerts_by_hazard(
        self, hazard_type: str,
    ) -> list[TextContent]:
        """Get alerts filtered by hazard type.

        Supported: cyclone, flood, earthquake, tsunami, landslide,
        heatwave, fire, thunderstorm.
        """
        alerts = await self._fetch_feed()
        matched = [
            a for a in alerts
            if self._matches_hazard(a.get("event", ""), hazard_type)
        ]
        return self.normalize_json(matched)

    async def get_alerts_by_severity(
        self, severity: str,
    ) -> list[TextContent]:
        """Get alerts filtered by CAP severity level.

        Values: Extreme, Severe, Moderate, Minor, Unknown.
        """
        alerts = await self._fetch_feed()
        sev_lower = severity.lower()
        matched = [
            a for a in alerts
            if a.get("severity", "").lower() == sev_lower
        ]
        return self.normalize_json(matched)

    async def get_alert_detail(
        self, alert_id: str,
    ) -> list[TextContent]:
        """Get full detail of a specific alert by its CAP identifier."""
        alerts = await self._fetch_feed()
        for a in alerts:
            if a.get("identifier") == alert_id:
                return self.normalize_json(a)
        return self.normalize_json({"error": "not_found", "alert_id": alert_id})

    async def get_alerts_summary(self) -> list[TextContent]:
        """Get summary of all active alerts.

        Returns counts by severity, category, and list of affected states.
        """
        alerts = await self._fetch_feed()
        sev_counts = Counter(a.get("severity", "Unknown") for a in alerts)
        cat_counts = Counter(a.get("category", "Unknown") for a in alerts)
        all_states: set[str] = set()
        for a in alerts:
            all_states.update(self._extract_states(a.get("area_desc", "")))

        return self.normalize_json({
            "total_alerts": len(alerts),
            "by_severity": dict(sev_counts),
            "by_category": dict(cat_counts),
            "affected_states": sorted(all_states),
        })


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = ["SACHETServer"]
