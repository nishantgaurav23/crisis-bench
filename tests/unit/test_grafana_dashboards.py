"""Tests for S9.4: Prometheus alerting rules + Grafana dashboard provisioning.

Validates that all monitoring configuration files are valid and complete.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

MONITORING_DIR = Path(__file__).resolve().parents[2] / "monitoring"
ALERTS_FILE = MONITORING_DIR / "alerts.yml"
PROMETHEUS_FILE = MONITORING_DIR / "prometheus.yml"
GRAFANA_DATASOURCE = MONITORING_DIR / "grafana" / "provisioning" / "datasources" / "prometheus.yml"
GRAFANA_DASHBOARD_PROVIDER = (
    MONITORING_DIR / "grafana" / "provisioning" / "dashboards" / "dashboard.yml"
)
DASHBOARD_JSON = MONITORING_DIR / "grafana" / "dashboards" / "crisis-ops.json"
DOCKER_COMPOSE = Path(__file__).resolve().parents[2] / "docker-compose.yml"


# ── Prometheus Alerting Rules ──────────────────────────────────────────────


class TestAlertsYml:
    def test_alerts_yml_exists(self) -> None:
        assert ALERTS_FILE.exists(), f"{ALERTS_FILE} does not exist"

    def test_alerts_yml_valid_yaml(self) -> None:
        data = yaml.safe_load(ALERTS_FILE.read_text())
        assert isinstance(data, dict)
        assert "groups" in data

    def test_alerts_rules_structure(self) -> None:
        data = yaml.safe_load(ALERTS_FILE.read_text())
        rules = []
        for group in data["groups"]:
            assert "name" in group
            assert "rules" in group
            rules.extend(group["rules"])

        for rule in rules:
            assert "alert" in rule, f"Rule missing 'alert' field: {rule}"
            assert "expr" in rule, f"Rule missing 'expr' field: {rule}"
            assert "for" in rule, f"Rule missing 'for' field: {rule}"
            assert "labels" in rule, f"Rule missing 'labels' field: {rule}"
            assert "annotations" in rule, f"Rule missing 'annotations' field: {rule}"

    def test_expected_alert_names(self) -> None:
        data = yaml.safe_load(ALERTS_FILE.read_text())
        alert_names = set()
        for group in data["groups"]:
            for rule in group["rules"]:
                alert_names.add(rule["alert"])

        expected = {
            "HighLLMErrorRate",
            "BudgetExceeded",
            "AgentTaskTimeout",
            "CacheHitRateLow",
        }
        assert expected.issubset(alert_names), (
            f"Missing alerts: {expected - alert_names}"
        )

    def test_alert_severity_labels(self) -> None:
        data = yaml.safe_load(ALERTS_FILE.read_text())
        for group in data["groups"]:
            for rule in group["rules"]:
                assert "severity" in rule["labels"], (
                    f"Alert '{rule['alert']}' missing severity label"
                )


# ── Prometheus Config ──────────────────────────────────────────────────────


class TestPrometheusConfig:
    def test_prometheus_yml_references_alerts(self) -> None:
        data = yaml.safe_load(PROMETHEUS_FILE.read_text())
        assert "rule_files" in data, "prometheus.yml missing 'rule_files'"
        rule_files = data["rule_files"]
        assert any("alerts" in rf for rf in rule_files), (
            "prometheus.yml rule_files does not reference alerts"
        )


# ── Grafana Datasource Provisioning ───────────────────────────────────────


class TestGrafanaDatasource:
    def test_datasource_file_exists(self) -> None:
        assert GRAFANA_DATASOURCE.exists(), f"{GRAFANA_DATASOURCE} does not exist"

    def test_datasource_valid_yaml(self) -> None:
        data = yaml.safe_load(GRAFANA_DATASOURCE.read_text())
        assert "datasources" in data
        ds_list = data["datasources"]
        assert len(ds_list) >= 1

    def test_datasource_prometheus_config(self) -> None:
        data = yaml.safe_load(GRAFANA_DATASOURCE.read_text())
        prom_ds = data["datasources"][0]
        assert prom_ds["type"] == "prometheus"
        assert "url" in prom_ds
        assert "prometheus" in prom_ds["url"] or "9090" in prom_ds["url"]


# ── Grafana Dashboard Provider ─────────────────────────────────────────────


class TestGrafanaDashboardProvider:
    def test_provider_file_exists(self) -> None:
        assert GRAFANA_DASHBOARD_PROVIDER.exists()

    def test_provider_valid_yaml(self) -> None:
        data = yaml.safe_load(GRAFANA_DASHBOARD_PROVIDER.read_text())
        assert "providers" in data
        providers = data["providers"]
        assert len(providers) >= 1

    def test_provider_points_to_dashboards_dir(self) -> None:
        data = yaml.safe_load(GRAFANA_DASHBOARD_PROVIDER.read_text())
        provider = data["providers"][0]
        assert "options" in provider
        path = provider["options"].get("path", "")
        assert "dashboards" in path


# ── Crisis Ops Dashboard JSON ──────────────────────────────────────────────


class TestCrisisOpsDashboard:
    def _load_dashboard(self) -> dict:
        return json.loads(DASHBOARD_JSON.read_text())

    def test_dashboard_json_exists(self) -> None:
        assert DASHBOARD_JSON.exists()

    def test_dashboard_json_valid(self) -> None:
        data = self._load_dashboard()
        assert "title" in data
        assert "panels" in data
        assert len(data["panels"]) > 0

    def test_dashboard_has_required_rows(self) -> None:
        """Dashboard should have row panels for the 4 sections."""
        data = self._load_dashboard()
        row_titles = []
        for panel in data["panels"]:
            if panel.get("type") == "row":
                row_titles.append(panel["title"].lower())

        required_keywords = ["llm", "latency", "agent", "cache"]
        for keyword in required_keywords:
            assert any(keyword in t for t in row_titles), (
                f"No row containing '{keyword}' found. Rows: {row_titles}"
            )

    def test_dashboard_panels_cover_metrics(self) -> None:
        """All key Prometheus metrics from telemetry.py should appear in panels."""
        data = self._load_dashboard()
        dashboard_text = json.dumps(data)

        required_metrics = [
            "crisis_llm_requests_total",
            "crisis_llm_tokens_total",
            "crisis_llm_latency_seconds",
            "crisis_llm_cost_dollars",
            "crisis_agent_tasks_total",
            "crisis_agent_task_duration_seconds",
            "crisis_cache_operations_total",
            "crisis_errors_total",
        ]

        for metric in required_metrics:
            assert metric in dashboard_text, (
                f"Metric '{metric}' not found in any dashboard panel"
            )

    def test_dashboard_has_budget_panel(self) -> None:
        """Dashboard should have a budget gauge panel."""
        data = self._load_dashboard()
        dashboard_text = json.dumps(data).lower()
        assert "budget" in dashboard_text


# ── Docker Compose Grafana Volumes ─────────────────────────────────────────


class TestDockerComposeGrafana:
    def test_grafana_provisioning_volumes(self) -> None:
        data = yaml.safe_load(DOCKER_COMPOSE.read_text())
        grafana = data["services"]["grafana"]
        volumes = grafana.get("volumes", [])
        volume_strs = [str(v) for v in volumes]

        has_provisioning = any("provisioning" in v for v in volume_strs)
        assert has_provisioning, (
            f"Grafana service missing provisioning volume mount. Volumes: {volume_strs}"
        )

    def test_grafana_dashboard_volume(self) -> None:
        data = yaml.safe_load(DOCKER_COMPOSE.read_text())
        grafana = data["services"]["grafana"]
        volumes = grafana.get("volumes", [])
        volume_strs = [str(v) for v in volumes]

        has_dashboards = any("dashboards" in v for v in volume_strs)
        assert has_dashboards, (
            f"Grafana service missing dashboards volume mount. Volumes: {volume_strs}"
        )
