# S4.4 MCP Server Base Framework — Checklist

## Red Phase (Tests First)
- [x] Write all unit tests in `tests/unit/test_mcp_base.py`
- [x] Confirm all tests fail (no implementation yet)

## Green Phase (Implement)
- [x] `BaseMCPServer.__init__` — FastMCP, config, logger, metrics
- [x] `register_tool` — wraps FastMCP.tool()
- [x] `get_http_client` / `close` — httpx lifecycle
- [x] `api_get` / `api_post` — HTTP with auth, timeout, retries, rate limit
- [x] `normalize_json` / `normalize_xml` — response normalization
- [x] Error mapping (404 → MCPError, 429 → APIRateLimitError, 5xx → ExternalAPIError)
- [x] Prometheus metrics (counter + histogram)
- [x] structlog logging per tool call

## Refactor Phase
- [x] ruff clean
- [x] All 32 tests pass
- [x] Update `__init__.py` exports
