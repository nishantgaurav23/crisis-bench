# Spec S9.4: Implementation Checklist

## Phase 1: RED — Write Failing Tests
- [x] Write `tests/unit/test_grafana_dashboards.py` with all test cases
- [x] Verify all tests fail (19 failed)

## Phase 2: GREEN — Implement
- [x] Create `monitoring/alerts.yml` with Prometheus alerting rules
- [x] Update `monitoring/prometheus.yml` to reference alerts
- [x] Create `monitoring/grafana/provisioning/datasources/prometheus.yml`
- [x] Create `monitoring/grafana/provisioning/dashboards/dashboard.yml`
- [x] Create `monitoring/grafana/dashboards/crisis-ops.json`
- [x] Update `docker-compose.yml` Grafana service with provisioning volumes
- [x] Verify all tests pass (19 passed)

## Phase 3: REFACTOR
- [x] Run ruff, fix any lint issues — all clean
- [x] Review dashboard JSON for completeness
- [x] Final test run — all green
