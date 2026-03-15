# Spec S5.2: SACHET CAP Feed MCP Server

**Phase**: 5 — MCP Data Servers
**Depends On**: S4.4 (MCP server base framework)
**Location**: `src/protocols/mcp/sachet_server.py`
**Tests**: `tests/unit/test_mcp_sachet.py`

---

## 1. Purpose

Wrap NDMA's SACHET Common Alerting Protocol (CAP v1.2) feed as an MCP server, providing structured access to India's unified all-hazard alert system. SACHET aggregates warnings from 7 national agencies (IMD, CWC, INCOIS, NCS, GSI, DGRE, FSI) + 36 state/UT disaster authorities into a single RSS/CAP feed at `https://sachet.ndma.gov.in/CapFeed`.

This is the **single most important data integration** for the system — one feed covers all Indian hazards.

---

## 2. Background: CAP v1.2 Format

CAP (Common Alerting Protocol) is an OASIS standard for emergency alerts. Each alert contains:

- **identifier**: Unique alert ID
- **sender**: Issuing agency
- **sent**: Timestamp (ISO 8601)
- **status**: Actual | Exercise | System | Test | Draft
- **msgType**: Alert | Update | Cancel | Ack | Error
- **scope**: Public | Restricted | Private
- **info** block(s):
  - **category**: Geo | Met | Safety | Security | Rescue | Fire | Health | Env | Transport | Infra | CBRNE | Other
  - **event**: Free-text event type (e.g., "Cyclone Warning", "Flood Alert")
  - **urgency**: Immediate | Expected | Future | Past | Unknown
  - **severity**: Extreme | Severe | Moderate | Minor | Unknown
  - **certainty**: Observed | Likely | Possible | Unlikely | Unknown
  - **senderName**: Human-readable sender name
  - **headline**: Short alert headline
  - **description**: Detailed description
  - **instruction**: Recommended action
  - **area** block(s):
    - **areaDesc**: Area description (state/district names)
    - **polygon**: Geographic boundary (optional)
    - **geocode**: Coded area identifiers

---

## 3. MCP Tools

### 3.1 `get_active_alerts`
- **Input**: `state` (optional str) — Indian state name to filter by
- **Output**: JSON array of parsed CAP alerts
- Fetches the SACHET feed, parses all CAP entries, optionally filters by state name (case-insensitive match in `areaDesc`)

### 3.2 `get_alerts_by_hazard`
- **Input**: `hazard_type` (str) — one of: cyclone, flood, earthquake, tsunami, landslide, heatwave, fire, thunderstorm
- **Output**: JSON array of alerts matching the hazard type
- Matches against `event` and `category` fields (case-insensitive)

### 3.3 `get_alerts_by_severity`
- **Input**: `severity` (str) — one of: Extreme, Severe, Moderate, Minor, Unknown
- **Output**: JSON array of alerts matching the severity level

### 3.4 `get_alert_detail`
- **Input**: `alert_id` (str) — CAP alert identifier
- **Output**: Full parsed alert JSON or error if not found

### 3.5 `get_alerts_summary`
- **Input**: none
- **Output**: JSON summary: count by severity, count by category, list of affected states

---

## 4. Implementation Details

### 4.1 Feed Fetching
- Fetch RSS from `https://sachet.ndma.gov.in/CapFeed` via `api_get` (using raw HTTP since it returns XML, not JSON)
- Override `_request` behavior to handle XML/RSS response (use `httpx` directly for text response)
- Cache feed for 60 seconds to avoid hammering the server

### 4.2 CAP XML Parsing
- Parse CAP v1.2 XML entries from the RSS feed
- Extract all standard CAP fields into a structured dict
- Handle CAP namespaces (`urn:oasis:names:tc:emergency:cap:1.2`)
- Map CAP categories to India-specific hazard types

### 4.3 Hazard Type Mapping
```python
HAZARD_KEYWORDS = {
    "cyclone": ["cyclone", "cyclonic storm", "depression", "vscs", "escs", "sucs"],
    "flood": ["flood", "inundation", "waterlogging", "deluge", "dam"],
    "earthquake": ["earthquake", "seismic", "tremor"],
    "tsunami": ["tsunami"],
    "landslide": ["landslide", "mudslide", "debris flow"],
    "heatwave": ["heatwave", "heat wave", "hot weather"],
    "fire": ["fire", "wildfire", "forest fire"],
    "thunderstorm": ["thunderstorm", "lightning", "squall", "dust storm"],
}
```

### 4.4 Error Handling
- Feed unavailable → raise `ExternalAPIError` with context
- Invalid CAP XML → raise `MCPError` with context, skip malformed entries
- No alerts matching filter → return empty array (not an error)

---

## 5. Outcomes

- [ ] `SACHETServer` extends `BaseMCPServer` with 5 MCP tools
- [ ] CAP v1.2 XML parsing extracts all standard fields
- [ ] State-based filtering works case-insensitively
- [ ] Hazard type matching uses keyword mapping
- [ ] Severity filtering works
- [ ] Alert detail lookup by ID
- [ ] Summary aggregation (counts by severity, category, states)
- [ ] Feed caching (60s TTL) prevents excessive requests
- [ ] All external HTTP calls mocked in tests
- [ ] >80% code coverage
- [ ] ruff lint clean

---

## 6. TDD Notes

### Red Phase
1. Test server initialization (name, base URL, tools registered)
2. Test CAP XML parsing with sample CAP entries
3. Test `get_active_alerts` — all alerts and state filter
4. Test `get_alerts_by_hazard` — keyword matching
5. Test `get_alerts_by_severity` — severity filter
6. Test `get_alert_detail` — found and not-found cases
7. Test `get_alerts_summary` — aggregation counts
8. Test feed caching — second call within 60s uses cache
9. Test error handling — feed unavailable, malformed XML
10. Test hazard keyword mapping

### Green Phase
- Implement `SACHETServer` with all tools
- Implement `_parse_cap_entry()` for XML parsing
- Implement `_fetch_feed()` with caching
- Implement hazard keyword matching

### Refactor Phase
- Extract common filtering logic
- Ensure ruff compliance (100 char line length)
