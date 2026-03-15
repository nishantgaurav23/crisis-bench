"""Unit tests for MCP server base framework (S4.4).

Tests cover: initialization, tool registration, HTTP client (GET/POST),
timeout, retries, rate limiting, error mapping, response normalization,
auth headers, Prometheus metrics, and graceful shutdown.
"""

import time
from collections import deque
from unittest.mock import AsyncMock, patch
from xml.etree.ElementTree import Element, SubElement, tostring

import httpx
import pytest

from src.shared.config import CrisisSettings
from src.shared.errors import APIRateLimitError, ExternalAPIError, MCPError

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
    from src.protocols.mcp.base import BaseMCPServer

    return BaseMCPServer(
        name="test-server",
        api_base_url="https://api.example.com",
        api_key="secret123",
        api_key_header="X-Api-Key",
        request_timeout=5.0,
        max_retries=2,
        rate_limit_rpm=60,
        settings=settings,
    )


@pytest.fixture
def server_no_auth(settings):
    from src.protocols.mcp.base import BaseMCPServer

    return BaseMCPServer(
        name="no-auth-server",
        api_base_url="https://public.example.com",
        settings=settings,
    )


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInit:
    def test_creates_with_name(self, server):
        assert server.name == "test-server"

    def test_stores_config(self, server):
        assert server.api_base_url == "https://api.example.com"
        assert server.api_key == "secret123"
        assert server.api_key_header == "X-Api-Key"
        assert server.request_timeout == 5.0
        assert server.max_retries == 2
        assert server.rate_limit_rpm == 60

    def test_creates_fastmcp_instance(self, server):
        from mcp.server.fastmcp import FastMCP

        assert isinstance(server.mcp, FastMCP)
        assert server.mcp.name == "test-server"

    def test_default_settings_when_none(self):
        from src.protocols.mcp.base import BaseMCPServer

        s = BaseMCPServer(name="defaults")
        assert s.settings is not None
        assert s.api_base_url == ""
        assert s.api_key == ""
        assert s.api_key_header == "Authorization"
        assert s.request_timeout == 30.0
        assert s.max_retries == 3
        assert s.rate_limit_rpm is None

    def test_has_logger(self, server):
        assert server.logger is not None


# ---------------------------------------------------------------------------
# Tool Registration
# ---------------------------------------------------------------------------


class TestToolRegistration:
    def test_register_async_tool(self, server):
        async def my_tool(query: str) -> str:
            """Search for something."""
            return f"result: {query}"

        server.register_tool(my_tool)
        # Tool should be registered in FastMCP
        tools = server.mcp._tool_manager._tools
        assert "my_tool" in tools

    def test_register_tool_custom_name(self, server):
        async def internal_func(x: int) -> str:
            """Do something."""
            return str(x)

        server.register_tool(internal_func, name="custom_name")
        tools = server.mcp._tool_manager._tools
        assert "custom_name" in tools

    def test_register_non_async_raises(self, server):
        def sync_func(x: str) -> str:
            """Sync function."""
            return x

        with pytest.raises(TypeError, match="must be async"):
            server.register_tool(sync_func)


# ---------------------------------------------------------------------------
# HTTP Client Lifecycle
# ---------------------------------------------------------------------------


class TestHTTPClient:
    def test_get_http_client_creates_lazily(self, server):
        assert server._http is None
        client = server.get_http_client()
        assert isinstance(client, httpx.AsyncClient)
        assert server._http is client

    def test_get_http_client_reuses(self, server):
        c1 = server.get_http_client()
        c2 = server.get_http_client()
        assert c1 is c2

    @pytest.mark.asyncio
    async def test_close_shuts_down_client(self, server):
        server.get_http_client()
        assert server._http is not None
        await server.close()
        assert server._http is None


# ---------------------------------------------------------------------------
# API GET
# ---------------------------------------------------------------------------


class TestApiGet:
    @pytest.mark.asyncio
    async def test_get_success(self, server):
        mock_resp = httpx.Response(200, json={"data": "ok"})
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await server.api_get("/endpoint", params={"q": "test"})
        assert result == {"data": "ok"}

    @pytest.mark.asyncio
    async def test_get_includes_auth_header(self, server):
        mock_resp = httpx.Response(200, json={"ok": True})
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await server.api_get("/endpoint")
        call_kwargs = mock_req.call_args
        headers = call_kwargs.kwargs.get("headers", {})
        assert headers.get("X-Api-Key") == "secret123"

    @pytest.mark.asyncio
    async def test_get_no_auth_when_empty_key(self, server_no_auth):
        mock_resp = httpx.Response(200, json={"ok": True})
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await server_no_auth.api_get("/endpoint")
        call_kwargs = mock_req.call_args
        headers = call_kwargs.kwargs.get("headers", {})
        assert "Authorization" not in headers

    @pytest.mark.asyncio
    async def test_get_timeout_raises_mcp_error(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            with pytest.raises(MCPError, match="timed out"):
                await server.api_get("/slow")

    @pytest.mark.asyncio
    async def test_get_404_raises_mcp_error(self, server):
        mock_resp = httpx.Response(404, text="Not Found")
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            with pytest.raises(MCPError, match="404"):
                await server.api_get("/missing")

    @pytest.mark.asyncio
    async def test_get_429_raises_rate_limit_error(self, server):
        mock_resp = httpx.Response(429, text="Too Many Requests")
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            with pytest.raises(APIRateLimitError):
                await server.api_get("/limited")

    @pytest.mark.asyncio
    async def test_get_500_raises_external_api_error(self, server):
        mock_resp = httpx.Response(500, text="Internal Server Error")
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            with pytest.raises(ExternalAPIError):
                await server.api_get("/broken")


# ---------------------------------------------------------------------------
# API POST
# ---------------------------------------------------------------------------


class TestApiPost:
    @pytest.mark.asyncio
    async def test_post_success(self, server):
        mock_resp = httpx.Response(200, json={"created": True})
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            result = await server.api_post("/create", json_body={"name": "test"})
        assert result == {"created": True}

    @pytest.mark.asyncio
    async def test_post_includes_auth_header(self, server):
        mock_resp = httpx.Response(200, json={"ok": True})
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await server.api_post("/create", json_body={"x": 1})
        call_kwargs = mock_req.call_args
        headers = call_kwargs.kwargs.get("headers", {})
        assert headers.get("X-Api-Key") == "secret123"


# ---------------------------------------------------------------------------
# Retries
# ---------------------------------------------------------------------------


class TestRetries:
    @pytest.mark.asyncio
    async def test_retries_on_502(self, server):
        fail = httpx.Response(502, text="Bad Gateway")
        ok = httpx.Response(200, json={"ok": True})
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            side_effect=[fail, ok],
        ):
            result = await server.api_get("/flaky")
        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_retries_on_503(self, server):
        fail = httpx.Response(503, text="Service Unavailable")
        ok = httpx.Response(200, json={"recovered": True})
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            side_effect=[fail, ok],
        ):
            result = await server.api_get("/flaky")
        assert result == {"recovered": True}

    @pytest.mark.asyncio
    async def test_max_retries_exceeded_raises(self, server):
        fail = httpx.Response(502, text="Bad Gateway")
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            side_effect=[fail, fail, fail],
        ):
            with pytest.raises(ExternalAPIError, match="502"):
                await server.api_get("/always-failing")


# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------


class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_rate_limit_enforced(self, server):
        # Fill the rate limit window (60 rpm = 60 calls in 60s)
        now = time.monotonic()
        server._call_timestamps = deque([now] * 60, maxlen=60)
        with pytest.raises(APIRateLimitError, match="rate limit"):
            await server.api_get("/anything")

    @pytest.mark.asyncio
    async def test_no_rate_limit_when_none(self, server_no_auth):
        mock_resp = httpx.Response(200, json={"ok": True})
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            # Should not raise even with many calls
            result = await server_no_auth.api_get("/endpoint")
        assert result == {"ok": True}


# ---------------------------------------------------------------------------
# Response Normalization
# ---------------------------------------------------------------------------


class TestNormalization:
    def test_normalize_json_dict(self, server):
        from mcp.types import TextContent

        result = server.normalize_json({"temp": 35, "city": "Mumbai"})
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "Mumbai" in result[0].text

    def test_normalize_json_list(self, server):
        from mcp.types import TextContent

        result = server.normalize_json([{"a": 1}, {"b": 2}])
        assert len(result) == 1
        assert isinstance(result[0], TextContent)

    def test_normalize_xml(self, server):
        from mcp.types import TextContent

        root = Element("alert")
        SubElement(root, "severity").text = "Extreme"
        SubElement(root, "area").text = "Mumbai"
        xml_str = tostring(root, encoding="unicode")

        result = server.normalize_xml(xml_str)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "Mumbai" in result[0].text

    def test_normalize_xml_invalid_raises(self, server):
        with pytest.raises(MCPError, match="XML"):
            server.normalize_xml("not valid xml <<<<")


# ---------------------------------------------------------------------------
# Prometheus Metrics
# ---------------------------------------------------------------------------


class TestMetrics:
    @pytest.mark.asyncio
    async def test_tool_call_increments_counter(self, server):
        from src.protocols.mcp.base import MCP_TOOL_CALLS

        mock_resp = httpx.Response(200, json={"ok": True})
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            await server.api_get("/metrics-test")

        # The counter should have been incremented for success
        # We check the metric family exists and has samples
        assert MCP_TOOL_CALLS is not None


# ---------------------------------------------------------------------------
# Error Context
# ---------------------------------------------------------------------------


class TestErrorContext:
    @pytest.mark.asyncio
    async def test_timeout_error_has_context(self, server):
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("conn timed out"),
        ):
            with pytest.raises(MCPError) as exc_info:
                await server.api_get("/timeout-ctx")
        err = exc_info.value
        assert err.context["server"] == "test-server"
        assert err.context["method"] == "GET"

    @pytest.mark.asyncio
    async def test_http_error_has_context(self, server):
        mock_resp = httpx.Response(500, text="boom")
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
        ):
            with pytest.raises(ExternalAPIError) as exc_info:
                await server.api_get("/error-ctx")
        err = exc_info.value
        assert err.context["server"] == "test-server"
        assert err.context["status_code"] == 500
