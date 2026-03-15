# S5.2 Explanation: SACHET CAP Feed MCP Server

## Why This Spec Exists

SACHET (NDMA's Common Alerting Protocol feed) is the **single most important data integration** for CRISIS-BENCH. Instead of integrating with 7 national agencies + 36 state disaster authorities separately, this one RSS/CAP feed aggregates all Indian hazard alerts into a single stream. It has delivered 68.99 billion SMS alerts — this is India's production alert system.

Without this MCP server, the SituationSense agent (S7.3) and Orchestrator (S7.2) cannot receive real-time hazard alerts. The entire end-to-end pipeline (`SACHET alert → agents → bilingual briefing`) depends on this.

## What It Does

`SACHETServer` extends `BaseMCPServer` (S4.4) and exposes 5 MCP tools:

| Tool | Input | Purpose |
|------|-------|---------|
| `get_active_alerts` | state (optional) | All alerts, optionally filtered by Indian state |
| `get_alerts_by_hazard` | hazard_type | Filter by cyclone/flood/earthquake/etc. via keyword matching |
| `get_alerts_by_severity` | severity | Filter by CAP severity (Extreme/Severe/Moderate/Minor) |
| `get_alert_detail` | alert_id | Single alert lookup by CAP identifier |
| `get_alerts_summary` | none | Aggregate counts by severity, category, + affected states |

## How It Works

1. **Feed Fetching**: HTTP GET to `sachet.ndma.gov.in/CapFeed` returns RSS XML with CAP v1.2 entries in `<content:encoded>` CDATA blocks
2. **Caching**: Feed is cached for 60 seconds to avoid hammering the server. Cache is invalidated by timestamp comparison
3. **CAP XML Parsing**: `_parse_cap_entry()` extracts all standard CAP fields (identifier, sender, severity, urgency, event, area, polygon, etc.) using `xml.etree.ElementTree` with CAP namespace handling
4. **Hazard Matching**: `_matches_hazard()` maps free-text event descriptions to hazard categories using keyword lists (e.g., "Very Severe Cyclonic Storm" → "cyclone")
5. **State Extraction**: `_extract_states()` identifies Indian state names within `areaDesc` strings for geographic filtering and summary aggregation
6. **Error Handling**: Malformed CAP entries are skipped with a warning log; valid entries in the same feed are still returned

## Key Design Decisions

- **Regex-based RSS parsing** instead of feedparser library: The RSS structure is simple (extract CDATA blocks). Avoids adding a dependency for trivial XML extraction.
- **Keyword matching** instead of LLM classification for hazard types: Zero cost, deterministic, sub-millisecond. LLM classification would be overkill for this structured data.
- **60-second cache TTL**: Balances freshness (SACHET updates every few minutes during active events) with politeness to NDMA servers.
- **No auth required**: SACHET is a public RSS feed — no API key, no registration.

## Connections

- **Depends on**: S4.4 (BaseMCPServer) — inherits HTTP client, retries, rate limiting, error mapping, Prometheus metrics
- **Used by**: S7.3 (SituationSense agent) — ingests SACHET alerts for real-time situational awareness
- **Used by**: S7.2 (Orchestrator) — SACHET alerts trigger agent activation
- **Related**: S5.1 (IMD MCP) — SACHET includes IMD alerts, but IMD MCP provides detailed weather data beyond what SACHET carries

## Interview Q&A

**Q: What is CAP v1.2 and why does SACHET use it?**
A: CAP (Common Alerting Protocol) is an OASIS international standard for emergency alerts (like HTTP is for web). It defines a structured XML format with severity, urgency, certainty, geographic area, and instructions. SACHET uses it because: (1) it's the global standard adopted by WMO and ITU, (2) it enables interoperability between agencies, (3) it's machine-parseable with well-defined semantics. The alternative — unstructured text alerts — would require NLP to extract severity and location, introducing errors.

**Q: Why cache the feed instead of fetching fresh every time?**
A: Rate limiting politeness + latency. SACHET updates every few minutes, not every second. Fetching on every tool call would be wasteful and could get us IP-blocked. The 60s cache means at most one HTTP request per minute while still providing near-real-time data. Trade-off: during rapidly evolving events, we might be up to 60s stale — but for a system processing alerts, this is acceptable.

**Q: How does keyword matching compare to ML classification for hazard types?**
A: For structured CAP data where the `event` field is human-curated by government agencies, keyword matching is superior: (1) deterministic — same input always gives same output, (2) zero latency — no model inference, (3) zero cost — no API calls, (4) debuggable — you can see exactly which keyword matched. ML classification adds value for unstructured social media text (that's what CrisisBERT is for in S7.3), but not for structured government alerts.
