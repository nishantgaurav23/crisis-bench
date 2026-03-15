# Spec S5.1 Explanation: IMD Weather MCP Server

## Why This Spec Exists

IMD (India Meteorological Department) is the authoritative weather and cyclone data source for India. Every disaster response decision — evacuation timing, resource pre-positioning, warning dissemination — starts with IMD data. This MCP server wraps IMD's public APIs so agents (especially SituationSense and PredictiveRisk) can query weather data through the standard MCP tool protocol without knowing HTTP details.

## What It Does

`IMDServer` extends `BaseMCPServer` (S4.4) and registers 5 MCP tools:

| Tool | Purpose | Used By |
|------|---------|---------|
| `get_district_warnings` | Weather warnings with IMD color codes (Green/Yellow/Orange/Red) | SituationSense (urgency scoring), Orchestrator (activation) |
| `get_district_rainfall` | Pan-India district rainfall vs. normal | PredictiveRisk (flood forecasting) |
| `get_cyclone_info` | Active cyclone bulletins (classification, track, landfall) | PredictiveRisk (cyclone tracking), Orchestrator (mission planning) |
| `get_city_forecast` | City-level weather forecast | CommunityComms (public alerts) |
| `get_aws_data` | Automatic Weather Station real-time observations | SituationSense (ground truth validation) |

## How It Works

1. `IMDServer.__init__()` calls `BaseMCPServer.__init__()` with:
   - `api_base_url="https://mausam.imd.gov.in"` — IMD's public API host
   - No API key (access is IP-whitelisted, not token-based)
   - `rate_limit_rpm=60` — conservative limit to respect IMD servers
2. Each tool method calls `self.api_get(path, params=...)` which handles retries, timeout, and error mapping
3. Responses are normalized via `self.normalize_json(data)` to `list[TextContent]`
4. `create_server()` factory provides a clean entry point

## How It Connects

- **Depends on**: S4.4 (BaseMCPServer — HTTP, retries, rate limiting, Prometheus metrics)
- **Used by**: S7.3 (SituationSense agent), S7.4 (PredictiveRisk agent) — both invoke IMD tools via MCP
- **Sibling servers**: S5.2 (SACHET), S5.3 (USGS), S5.4 (OSM), S5.5 (Bhuvan), S5.6 (FIRMS)
- **Data flows to**: Redis Stream `crisis:data:imd` for real-time event bus distribution

## Key Design Decisions

1. **No API key**: IMD uses IP whitelisting, not tokens. The server works without auth headers.
2. **60 RPM rate limit**: Conservative to avoid being blocked. IMD doesn't publish rate limits.
3. **Parameters via query string**: IMD APIs use PHP-style `?id=X` parameters, passed via `params` dict.
4. **All tools return `list[TextContent]`**: MCP standard format — agents parse JSON from the text field.

## Interview Q&A

**Q: Why wrap IMD APIs in an MCP server instead of calling them directly from agents?**
A: Three reasons: (1) Separation of concerns — the agent's LLM doesn't need to know about IMD's PHP API conventions or IP whitelisting. (2) Testability — we mock the entire MCP server in agent tests without mocking HTTP. (3) Reusability — any agent can discover and call IMD tools at runtime via MCP's tool discovery.

**Q: How does IMD IP whitelisting work?**
A: You email IMD with your server's public IP address. They add it to their whitelist. No tokens, no OAuth — just IP-based access control. This is common for government APIs in India. For local development, you need your ISP's public IP whitelisted.

**Q: What are IMD warning color codes?**
A: IMD uses a 4-color warning system: Green (no action), Yellow (be aware), Orange (be prepared), Red (take action). Our UrgencyClassifier (S2.7) maps these to urgency levels 1-5 which determine the LLM tier used for response.
