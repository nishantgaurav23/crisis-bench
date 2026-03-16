# Spec S4.4 — MCP Server Base Framework

**Status**: done

**Phase**: 4 — Communication Protocols
**Location**: `src/protocols/mcp/base.py`
**Depends On**: S1.3 (config)
**Consumed By**: S5.1–S5.6 (IMD, SACHET, USGS, OSM, Bhuvan, FIRMS MCP servers)

---

## Purpose

Provide a reusable base class (`BaseMCPServer`) that wraps Anthropic's `mcp` SDK (`FastMCP`).
Each of the 6 MCP data servers in Phase 5 will subclass this, inheriting:

- Tool registration via `@server.tool()` or `add_tool()`
- HTTP client management (`httpx.AsyncClient`) with timeout, retries, rate limiting
- Response normalization (JSON/XML → `TextContent`)
- Error handling mapped to `MCPError` / `ExternalAPIError`
- Structured logging via `structlog`
- Prometheus metrics per tool call
- Config integration with `CrisisSettings`

## Non-Goals (Phase 4)

- Langfuse tracing (deferred to S9.3)
- Circuit breaker pattern (deferred to Phase 5 individual servers if needed)
- Authentication middleware / OAuth (not needed for Indian govt APIs)

---

## Design

### Class: `BaseMCPServer`

```python
class BaseMCPServer:
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
    ): ...
```

**Key internals**:
- `self.mcp`: a `FastMCP` instance — the actual MCP protocol server
- `self._http`: lazily-created `httpx.AsyncClient` (shared across tools)
- `self._call_timestamps`: deque for rate limit tracking per tool
- `self.logger`: structlog bound logger

### Methods

| Method | Purpose |
|--------|---------|
| `register_tool(func, name, description)` | Register an async callable as an MCP tool |
| `api_get(path, params)` | GET request with auth, timeout, retries, rate limiting |
| `api_post(path, json, data)` | POST request with same protections |
| `normalize_json(data)` | Convert dict/list → `list[TextContent]` |
| `normalize_xml(xml_str)` | Parse XML → dict → `list[TextContent]` |
| `get_http_client()` | Return (lazily create) the shared httpx client |
| `close()` | Shut down httpx client |
| `run_stdio()` | Run MCP server on stdio transport |
| `run_sse(host, port)` | Run MCP server on SSE transport |

### Prometheus Metrics

- `crisis_mcp_tool_calls_total{server, tool, status}` — Counter
- `crisis_mcp_tool_duration_seconds{server, tool}` — Histogram

### Error Mapping

| HTTP Status | Error Raised |
|-------------|-------------|
| 404 | `MCPError("Not found", context={...})` |
| 429 | `APIRateLimitError(...)` |
| 5xx | `ExternalAPIError(...)` |
| Timeout | `MCPError("Request timed out", ...)` |

---

## Outcomes

- [ ] `src/protocols/mcp/base.py` with `BaseMCPServer` class
- [ ] Tool registration wrapping FastMCP
- [ ] `api_get` / `api_post` with timeout, retries, rate limiting
- [ ] JSON and XML response normalization to `TextContent`
- [ ] Error wrapping in `MCPError` / `ExternalAPIError` / `APIRateLimitError`
- [ ] Prometheus metrics for tool calls
- [ ] structlog JSON logging per tool call
- [ ] Config integration with `CrisisSettings`
- [ ] All tests pass, ruff clean

---

## TDD Notes

### Test file: `tests/unit/test_mcp_base.py`

1. **Init**: server creates with name and config
2. **Tool registration**: registers async func via FastMCP, rejects non-async
3. **HTTP GET success**: mocked httpx returns 200, api_get returns parsed JSON
4. **HTTP POST success**: mocked httpx returns 200, api_post returns parsed JSON
5. **HTTP timeout**: raises MCPError with timeout context
6. **HTTP 404**: raises MCPError with not-found context
7. **HTTP 429**: raises APIRateLimitError
8. **HTTP 5xx**: raises ExternalAPIError
9. **Retry on transient errors**: retries on 502/503, succeeds on retry
10. **Max retries exceeded**: raises after max_retries attempts
11. **Rate limiting**: enforces RPM limit, raises APIRateLimitError when exceeded
12. **normalize_json**: dict → TextContent list
13. **normalize_xml**: XML string → TextContent list
14. **Auth header**: api_get/post includes configured auth header
15. **Prometheus metrics**: tool call increments counter
16. **Close**: closes httpx client properly
