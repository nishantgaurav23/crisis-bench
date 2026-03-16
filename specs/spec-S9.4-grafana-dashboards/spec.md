# Spec S9.4: Prometheus + Grafana Dashboards

**Phase**: 9 — Optimization & Polish
**Depends On**: S2.5 (Telemetry)
**Location**: `monitoring/`
**Status**: spec-written

---

## Overview

Create Prometheus alerting rules and Grafana dashboard provisioning for CRISIS-BENCH observability. This includes:
1. Prometheus alerting rules for budget overruns, high error rates, and agent timeouts
2. Grafana datasource provisioning (auto-configure Prometheus)
3. Grafana dashboard provisioning (auto-load dashboards on startup)
4. A comprehensive "Crisis Ops" Grafana dashboard JSON covering: tokens per agent, cost per provider, LLM latency, cache hit rate, agent task duration, error rates, and budget alerts

## Outcomes

1. **Prometheus alerting rules** (`monitoring/alerts.yml`) with rules for:
   - `HighLLMErrorRate`: >10% error rate over 5min window
   - `BudgetExceeded`: cumulative cost > $8 (monthly budget)
   - `AgentTaskTimeout`: p99 agent task duration > 60s
   - `CacheHitRateLow`: cache hit rate < 50% over 15min
2. **Prometheus config updated** to load alerting rules
3. **Grafana provisioning** (`monitoring/grafana/provisioning/`) with:
   - `datasources/prometheus.yml`: auto-configure Prometheus datasource
   - `dashboards/dashboard.yml`: point to dashboard JSON directory
4. **Crisis Ops Dashboard** (`monitoring/grafana/dashboards/crisis-ops.json`):
   - Row 1: LLM Overview — requests/s by provider, tokens/s by direction, cost accumulation
   - Row 2: Latency — LLM latency heatmap, p50/p95/p99 latency by provider
   - Row 3: Agents — tasks/s by agent, task duration histogram, error rate by agent
   - Row 4: Cache & Budget — cache hit/miss ratio, budget gauge, budget burn rate
5. **Docker Compose updated** to mount provisioning volumes for Grafana
6. **All configuration validated** by unit tests

## TDD Notes

### Test Cases
- `test_alerts_yml_valid`: Parse alerts.yml as valid YAML, verify all rule groups/rules present
- `test_alerts_rules_structure`: Each rule has `alert`, `expr`, `for`, `labels`, `annotations`
- `test_prometheus_yml_has_alerting`: prometheus.yml references alerts.yml
- `test_grafana_datasource_valid`: datasource YAML has correct Prometheus URL
- `test_grafana_dashboard_provider_valid`: dashboard provider YAML points to correct path
- `test_dashboard_json_valid`: crisis-ops.json is valid JSON with expected panels
- `test_dashboard_panels_cover_metrics`: all Prometheus metrics from telemetry.py appear in at least one panel
- `test_dashboard_has_required_rows`: 4 rows (LLM Overview, Latency, Agents, Cache & Budget)
- `test_docker_compose_grafana_volumes`: Grafana service mounts provisioning directories

## Non-Goals

- Grafana user management or authentication (beyond default admin)
- Custom Grafana plugins
- Alertmanager configuration (just Prometheus rules; Alertmanager is Phase 10+)
