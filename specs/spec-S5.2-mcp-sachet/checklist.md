# S5.2 Implementation Checklist

## Red Phase (Tests First)
- [x] Test server initialization
- [x] Test CAP XML parsing
- [x] Test get_active_alerts (all + state filter)
- [x] Test get_alerts_by_hazard
- [x] Test get_alerts_by_severity
- [x] Test get_alert_detail (found + not found)
- [x] Test get_alerts_summary
- [x] Test feed caching
- [x] Test error handling (feed down, malformed XML)
- [x] All tests written and FAILING

## Green Phase (Implementation)
- [x] SACHETServer class extending BaseMCPServer
- [x] _parse_cap_entry() CAP XML parser
- [x] _fetch_feed() with 60s cache
- [x] get_active_alerts tool
- [x] get_alerts_by_hazard tool
- [x] get_alerts_by_severity tool
- [x] get_alert_detail tool
- [x] get_alerts_summary tool
- [x] All tests PASSING

## Refactor Phase
- [x] ruff lint clean
- [x] Code review for clarity
- [x] All tests still passing
