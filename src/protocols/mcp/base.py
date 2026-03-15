"""MCP server base framework for CRISIS-BENCH (S4.4).

Provides ``BaseMCPServer`` — a reusable foundation for every MCP data server
(IMD, SACHET, USGS, OSM, Bhuvan, FIRMS). Handles HTTP client management,
retries, rate limiting, response normalization, error mapping, and telemetry.

Usage::

    class IMDServer(BaseMCPServer):
        def __init__(self):
            super().__init__(
                name="mcp-imd",
                api_base_url="https://mausam.imd.gov.in/api",
            )
            self.register_tool(self.get_district_warnings)

        async def get_district_warnings(self, district_id: str) -> str:
            \"\"\"Get IMD weather warnings for a district.\"\"\"
            data = await self.api_get(f"/warnings/{district_id}")
            return self.normalize_json(data)
"""

from __future__ import annotations

import asyncio
import inspect
import json
import time
import xml.etree.ElementTree as ET
from collections import deque
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent
from prometheus_client import Counter, Histogram

from src.shared.config import CrisisSettings, get_settings
from src.shared.errors import APIRateLimitError, ExternalAPIError, MCPError
from src.shared.telemetry import get_logger

# ---------------------------------------------------------------------------
# Prometheus metrics (module-level singletons)
# ---------------------------------------------------------------------------

MCP_TOOL_CALLS: Counter = Counter(
    "crisis_mcp_tool_calls_total",
    "Total MCP tool invocations",
    ["server", "tool", "status"],
)

MCP_TOOL_DURATION: Histogram = Histogram(
    "crisis_mcp_tool_duration_seconds",
    "MCP tool call duration in seconds",
    ["server", "tool"],
)

# HTTP status codes that trigger automatic retry
_RETRYABLE_STATUS = frozenset({502, 503, 504})


class BaseMCPServer:
    """Reusable base for all CRISIS-BENCH MCP data servers.

    Wraps Anthropic's ``FastMCP`` and adds HTTP client management, retries,
    rate limiting, response normalization, error mapping, and logging.
    """

    def __init__(
        self,
        name: str,
        *,
        api_base_url: str = "",
        api_key: str = "",
        api_key_header: str = "Authorization",
        request_timeout: float = 30.0,
        max_retries: int = 3,
        rate_limit_rpm: int | None = None,
        settings: CrisisSettings | None = None,
    ) -> None:
        self.name = name
        self.api_base_url = api_base_url.rstrip("/")
        self.api_key = api_key
        self.api_key_header = api_key_header
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.rate_limit_rpm = rate_limit_rpm
        self.settings = settings or get_settings()

        self.mcp = FastMCP(name=name)
        self.logger = get_logger(f"mcp.{name}", server=name)
        self._http: httpx.AsyncClient | None = None
        self._call_timestamps: deque[float] = deque(
            maxlen=rate_limit_rpm if rate_limit_rpm else 0
        )

    # ------------------------------------------------------------------
    # Tool Registration
    # ------------------------------------------------------------------

    def register_tool(
        self,
        func: Any,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> None:
        """Register an async callable as an MCP tool.

        Raises ``TypeError`` if *func* is not a coroutine function.
        """
        if not inspect.iscoroutinefunction(func):
            raise TypeError(
                f"Tool function {getattr(func, '__name__', func)} must be async "
                f"(use 'async def')"
            )
        tool_name = name or func.__name__
        tool_desc = description or (func.__doc__ or "").strip() or tool_name
        self.mcp.add_tool(func, name=tool_name, description=tool_desc)

    # ------------------------------------------------------------------
    # HTTP Client
    # ------------------------------------------------------------------

    def get_http_client(self) -> httpx.AsyncClient:
        """Return the shared ``httpx.AsyncClient``, creating it lazily."""
        if self._http is None:
            self._http = httpx.AsyncClient(
                timeout=httpx.Timeout(self.request_timeout),
            )
        return self._http

    async def close(self) -> None:
        """Shut down the HTTP client."""
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    # ------------------------------------------------------------------
    # Rate Limiting
    # ------------------------------------------------------------------

    def _check_rate_limit(self) -> None:
        """Raise ``APIRateLimitError`` if local RPM limit is exceeded."""
        if self.rate_limit_rpm is None:
            return
        now = time.monotonic()
        # Remove timestamps older than 60 seconds
        while self._call_timestamps and (now - self._call_timestamps[0]) > 60:
            self._call_timestamps.popleft()
        if len(self._call_timestamps) >= self.rate_limit_rpm:
            raise APIRateLimitError(
                f"Local rate limit exceeded ({self.rate_limit_rpm} rpm)",
                context={"server": self.name},
            )
        self._call_timestamps.append(now)

    # ------------------------------------------------------------------
    # HTTP Requests
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        """Execute an HTTP request with auth, retries, and error mapping."""
        self._check_rate_limit()

        url = f"{self.api_base_url}{path}" if self.api_base_url else path
        headers: dict[str, str] = {}
        if self.api_key:
            headers[self.api_key_header] = self.api_key

        client = self.get_http_client()
        for attempt in range(self.max_retries + 1):
            t0 = time.monotonic()
            try:
                resp = await client.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=headers,
                )
                elapsed = time.monotonic() - t0
                self.logger.debug(
                    "mcp_http_response",
                    method=method,
                    path=path,
                    status=resp.status_code,
                    elapsed_s=round(elapsed, 3),
                )
                MCP_TOOL_DURATION.labels(server=self.name, tool=path).observe(elapsed)

                if resp.status_code == 200:
                    MCP_TOOL_CALLS.labels(
                        server=self.name, tool=path, status="success"
                    ).inc()
                    return resp.json()

                # Retryable status — try again (unless last attempt)
                if resp.status_code in _RETRYABLE_STATUS and attempt < self.max_retries:
                    delay = 0.1 * (2**attempt)
                    self.logger.warning(
                        "mcp_http_retry",
                        status=resp.status_code,
                        attempt=attempt + 1,
                        delay_s=delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                # Non-retryable or final attempt — raise
                MCP_TOOL_CALLS.labels(
                    server=self.name, tool=path, status="error"
                ).inc()
                self._raise_for_status(resp, method, path)

            except httpx.TimeoutException as exc:
                elapsed = time.monotonic() - t0
                MCP_TOOL_CALLS.labels(
                    server=self.name, tool=path, status="timeout"
                ).inc()
                self.logger.error(
                    "mcp_http_timeout", method=method, path=path, elapsed_s=round(elapsed, 3)
                )
                raise MCPError(
                    f"Request timed out after {self.request_timeout}s",
                    context={
                        "server": self.name,
                        "method": method,
                        "path": path,
                    },
                ) from exc
            except (MCPError, APIRateLimitError, ExternalAPIError):
                raise
            except Exception as exc:
                MCP_TOOL_CALLS.labels(
                    server=self.name, tool=path, status="error"
                ).inc()
                if attempt < self.max_retries:
                    await asyncio.sleep(0.1 * (2**attempt))
                    continue
                raise MCPError(
                    f"Unexpected error: {exc}",
                    context={"server": self.name, "method": method, "path": path},
                ) from exc

        # Should not reach here, but just in case
        raise MCPError(  # pragma: no cover
            "Max retries exhausted",
            context={"server": self.name, "method": method, "path": path},
        )

    def _raise_for_status(self, resp: httpx.Response, method: str, path: str) -> None:
        """Map HTTP error status codes to CRISIS-BENCH exceptions."""
        ctx = {
            "server": self.name,
            "method": method,
            "path": path,
            "status_code": resp.status_code,
        }

        if resp.status_code == 429:
            raise APIRateLimitError(
                f"API rate limit: {resp.status_code} on {method} {path}",
                context=ctx,
            )
        if resp.status_code >= 500:
            raise ExternalAPIError(
                f"Server error: {resp.status_code} on {method} {path}",
                context=ctx,
            )
        # 4xx (including 404)
        raise MCPError(
            f"HTTP {resp.status_code} on {method} {path}",
            context=ctx,
        )

    async def api_get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """HTTP GET with auth, timeout, retries, and rate limiting."""
        return await self._request("GET", path, params=params)

    async def api_post(
        self,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """HTTP POST with auth, timeout, retries, and rate limiting."""
        return await self._request("POST", path, params=params, json_body=json_body)

    # ------------------------------------------------------------------
    # Response Normalization
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_json(data: Any) -> list[TextContent]:
        """Convert a JSON-serializable value to ``list[TextContent]``."""
        return [TextContent(type="text", text=json.dumps(data, default=str))]

    @staticmethod
    def normalize_xml(xml_str: str) -> list[TextContent]:
        """Parse XML string and convert to ``list[TextContent]`` (JSON)."""
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError as exc:
            raise MCPError(
                f"XML parse error: {exc}",
                context={"raw_length": len(xml_str)},
            ) from exc

        def _elem_to_dict(elem: ET.Element) -> dict[str, Any]:
            result: dict[str, Any] = {}
            if elem.attrib:
                result["@attributes"] = dict(elem.attrib)
            for child in elem:
                child_data = _elem_to_dict(child)
                tag = child.tag
                if tag in result:
                    existing = result[tag]
                    if not isinstance(existing, list):
                        result[tag] = [existing]
                    result[tag].append(child_data)
                else:
                    result[tag] = child_data
            if elem.text and elem.text.strip():
                if result:
                    result["#text"] = elem.text.strip()
                else:
                    return elem.text.strip()  # type: ignore[return-value]
            return result

        data = _elem_to_dict(root)
        return [TextContent(type="text", text=json.dumps(data, default=str))]

    # ------------------------------------------------------------------
    # MCP Transport Runners
    # ------------------------------------------------------------------

    async def run_stdio(self) -> None:
        """Run this MCP server on stdio transport."""
        await self.mcp.run_stdio_async()

    async def run_sse(self, host: str = "127.0.0.1", port: int = 8000) -> None:
        """Run this MCP server on SSE transport."""
        await self.mcp.run_sse_async()


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "BaseMCPServer",
    "MCP_TOOL_CALLS",
    "MCP_TOOL_DURATION",
]
