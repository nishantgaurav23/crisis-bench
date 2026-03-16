# Spec S5.1: IMD Weather MCP Server

**Status**: done

**Phase**: 5 — MCP Data Servers
**Depends On**: S4.4 (MCP server base framework)
**Location**: `src/protocols/mcp/imd_server.py`
**Tests**: `tests/unit/test_mcp_imd.py`

---

## Overview

MCP server wrapping India Meteorological Department (IMD) APIs. Provides district weather warnings, rainfall data, cyclone bulletins, and Automatic Weather Station (AWS) observations as MCP tools that agents can invoke.

IMD is the authoritative weather data source for India. Access is via IP whitelisting (free, no API key) — the server uses `BaseMCPServer` with no auth header.

## IMD API Endpoints

| Tool | IMD Endpoint | Purpose |
|------|-------------|---------|
| `get_district_warnings` | `/api/warnings_district_api.php?id={district_id}` | Weather warnings per district (Green/Yellow/Orange/Red) |
| `get_district_rainfall` | `/api/districtwise_rainfall_api.php` | District-wise rainfall data across India |
| `get_cyclone_info` | `/api/cyclone_api.php` | Active tropical cyclone bulletins (North Indian Ocean) |
| `get_city_forecast` | `/api/city_weather_api.php?id={city_id}` | City-level weather forecast |
| `get_aws_data` | `/api/aws_data_api.php?station_id={station_id}` | Automatic Weather Station observations |

## Outcomes

1. `IMDServer` extends `BaseMCPServer` with 5 tools registered
2. All tools are async and return `list[TextContent]` via `normalize_json()`
3. API base URL: `https://mausam.imd.gov.in`
4. No authentication (IP whitelisted)
5. Rate limit: 60 RPM (conservative, to respect IMD servers)
6. All external HTTP calls are mocked in tests
7. Warning color codes (Green/Yellow/Orange/Red) are preserved in responses

## TDD Notes

- Mock all `httpx.AsyncClient.request` calls — never hit real IMD API
- Test tool registration (all 5 tools present)
- Test each tool with mock responses
- Test error handling: timeouts, 404s, malformed JSON
- Test rate limiting inherited from BaseMCPServer
- Test `create_server()` factory function
