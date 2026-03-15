# Explanation — S4.4 MCP Server Base Framework

## Why This Spec Exists

Phase 5 requires 6 MCP data servers (IMD, SACHET, USGS, OSM, Bhuvan, FIRMS), each wrapping a different external API. Without a base class, every server would duplicate: HTTP client setup, authentication, timeout handling, retries, rate limiting, error mapping, response normalization, and telemetry. `BaseMCPServer` eliminates this duplication so each Phase 5 server is a thin ~50-line wrapper focused purely on API-specific logic.

## What It Does

`BaseMCPServer` wraps Anthropic's `FastMCP` SDK and provides:

1. **Tool Registration** — `register_tool(func)` validates the function is async and registers it with FastMCP. Supports custom names and descriptions.

2. **HTTP Client Management** — Lazily-created shared `httpx.AsyncClient` with configurable timeout. Gracefully shut down via `close()`.

3. **API Requests** — `api_get(path)` and `api_post(path, json_body)` handle:
   - Authentication headers (configurable key + header name)
   - Automatic retries on 502/503/504 with exponential backoff
   - Rate limiting (RPM-based sliding window)
   - Timeout detection

4. **Error Mapping** — HTTP errors map to the CrisisError hierarchy:
   - 404 → `MCPError`
   - 429 → `APIRateLimitError`
   - 5xx → `ExternalAPIError`
   - Timeout → `MCPError`
   - All errors include context (server name, method, path, status code)

5. **Response Normalization** — `normalize_json(data)` and `normalize_xml(xml_str)` convert API responses into `list[TextContent]` for the MCP protocol.

6. **Telemetry** — Prometheus counters (`crisis_mcp_tool_calls_total`) and histograms (`crisis_mcp_tool_duration_seconds`) track every HTTP call by server, tool, and status.

## How It Works

```
Subclass (e.g., IMDServer)
  → calls super().__init__(name, api_base_url, ...)
  → registers tools via self.register_tool(self.get_warnings)
  → tools call self.api_get("/warnings/district/123")
    → BaseMCPServer checks rate limit
    → sends HTTP request with auth headers
    → retries on transient failures (502/503/504)
    → maps errors to CrisisError hierarchy
    → returns parsed JSON
  → tool normalizes response via self.normalize_json(data)
```

## Connections

- **Upstream**: S1.3 (config — `CrisisSettings` for API keys, timeouts)
- **Downstream**: S5.1-S5.6 (all 6 MCP data servers subclass `BaseMCPServer`)
- **Uses**: S2.4 errors (`MCPError`, `APIRateLimitError`, `ExternalAPIError`), S2.5 telemetry (`get_logger`, Prometheus metrics)
- **Transport**: FastMCP supports stdio and SSE — each MCP server can run standalone or embedded

## Interview Talking Points

- **Why a base class?** — DRY principle. 6 servers × (HTTP + auth + retries + rate limit + errors + logging) = massive duplication. The base class is the HTTP middleware layer for all external API integrations.
- **Why httpx over aiohttp?** — httpx has a cleaner async API, built-in timeout configuration, and HTTP/2 support. It's the modern replacement for requests in async Python.
- **Why local rate limiting?** — Some Indian government APIs (IMD, Bhuvan) have undocumented rate limits. Client-side enforcement prevents 429 errors and maintains good API citizenship.
- **Why XML normalization?** — SACHET uses CAP v1.2 (XML). IMD also returns XML for some endpoints. Having XML→JSON→TextContent built into the base class means every MCP server gets it for free.
