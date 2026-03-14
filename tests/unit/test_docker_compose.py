"""Tests for S1.2: Docker Compose configuration.

Validates docker-compose.yml and docker-compose.cpu.yml without
requiring a running Docker daemon — pure YAML parsing + structure checks.
"""

from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def compose_path() -> Path:
    return PROJECT_ROOT / "docker-compose.yml"


@pytest.fixture
def cpu_override_path() -> Path:
    return PROJECT_ROOT / "docker-compose.cpu.yml"


@pytest.fixture
def compose(compose_path: Path) -> dict:
    """Parse the main docker-compose.yml."""
    assert compose_path.exists(), "docker-compose.yml does not exist"
    return yaml.safe_load(compose_path.read_text())


@pytest.fixture
def cpu_override(cpu_override_path: Path) -> dict:
    """Parse the CPU override compose file."""
    assert cpu_override_path.exists(), "docker-compose.cpu.yml does not exist"
    return yaml.safe_load(cpu_override_path.read_text())


# --- YAML Validity ---


class TestYAMLValidity:
    def test_compose_is_valid_yaml(self, compose: dict):
        assert isinstance(compose, dict)

    def test_cpu_override_is_valid_yaml(self, cpu_override: dict):
        assert isinstance(cpu_override, dict)


# --- Service Presence ---

EXPECTED_SERVICES = ["postgres", "redis", "neo4j", "chromadb", "langfuse", "prometheus", "grafana"]


class TestServicePresence:
    def test_all_services_defined(self, compose: dict):
        services = compose.get("services", {})
        for svc in EXPECTED_SERVICES:
            assert svc in services, f"Service '{svc}' missing from docker-compose.yml"

    def test_exactly_seven_services(self, compose: dict):
        services = compose.get("services", {})
        assert len(services) == 7, f"Expected 7 services, got {len(services)}"


# --- Port Mappings ---

EXPECTED_PORTS = {
    "postgres": "5432:5432",
    "redis": "6379:6379",
    "neo4j": ["7474:7474", "7687:7687"],
    "chromadb": "8100:8000",
    "langfuse": "4000:3000",
    "prometheus": "9090:9090",
    "grafana": "4001:3000",
}


class TestPortMappings:
    @pytest.mark.parametrize("service,expected", EXPECTED_PORTS.items())
    def test_port_mapping(self, compose: dict, service: str, expected):
        ports = compose["services"][service].get("ports", [])
        if isinstance(expected, list):
            for port in expected:
                assert port in ports, f"{service} missing port {port}"
        else:
            assert expected in ports, f"{service} missing port {expected}"


# --- Named Volumes ---

EXPECTED_VOLUMES = [
    "postgres_data",
    "redis_data",
    "neo4j_data",
    "chroma_data",
    "prometheus_data",
    "grafana_data",
]


class TestVolumes:
    def test_named_volumes_declared(self, compose: dict):
        volumes = compose.get("volumes", {})
        for vol in EXPECTED_VOLUMES:
            assert vol in volumes, f"Named volume '{vol}' not declared"

    def test_postgres_volume_mount(self, compose: dict):
        svc = compose["services"]["postgres"]
        volumes = svc.get("volumes", [])
        assert any("postgres_data" in str(v) for v in volumes)

    def test_redis_volume_mount(self, compose: dict):
        svc = compose["services"]["redis"]
        volumes = svc.get("volumes", [])
        assert any("redis_data" in str(v) for v in volumes)


# --- Health Checks ---


class TestHealthChecks:
    @pytest.mark.parametrize("service", EXPECTED_SERVICES)
    def test_service_has_healthcheck(self, compose: dict, service: str):
        svc = compose["services"][service]
        assert "healthcheck" in svc, f"Service '{service}' missing healthcheck"

    def test_postgres_healthcheck_uses_pg_isready(self, compose: dict):
        hc = compose["services"]["postgres"]["healthcheck"]
        test_cmd = hc.get("test", "")
        if isinstance(test_cmd, list):
            test_cmd = " ".join(test_cmd)
        assert "pg_isready" in test_cmd

    def test_redis_healthcheck_uses_ping(self, compose: dict):
        hc = compose["services"]["redis"]["healthcheck"]
        test_cmd = hc.get("test", "")
        if isinstance(test_cmd, list):
            test_cmd = " ".join(test_cmd)
        assert "redis-cli" in test_cmd and "ping" in test_cmd


# --- Network ---


class TestNetwork:
    def test_crisis_net_defined(self, compose: dict):
        networks = compose.get("networks", {})
        assert "crisis-net" in networks, "Network 'crisis-net' not defined"

    @pytest.mark.parametrize("service", EXPECTED_SERVICES)
    def test_service_on_crisis_net(self, compose: dict, service: str):
        svc = compose["services"][service]
        networks = svc.get("networks", [])
        assert "crisis-net" in networks, f"'{service}' not on crisis-net"


# --- No Hardcoded Secrets ---


class TestNoHardcodedSecrets:
    def test_postgres_password_from_env(self, compose: dict):
        env = compose["services"]["postgres"].get("environment", {})
        # Environment can be a list of "KEY=VAL" or a dict
        if isinstance(env, list):
            pw_entries = [e for e in env if "POSTGRES_PASSWORD" in e]
            assert pw_entries, "POSTGRES_PASSWORD not set"
            for entry in pw_entries:
                assert "${" in entry, "POSTGRES_PASSWORD is hardcoded, should use ${VAR}"
        else:
            pw = env.get("POSTGRES_PASSWORD", "")
            assert "${" in str(pw) or pw == "", "POSTGRES_PASSWORD is hardcoded"

    def test_neo4j_password_from_env(self, compose: dict):
        env = compose["services"]["neo4j"].get("environment", {})
        if isinstance(env, list):
            auth_entries = [e for e in env if "NEO4J_AUTH" in e]
            assert auth_entries, "NEO4J_AUTH not set"
            for entry in auth_entries:
                assert "${" in entry, "NEO4J_AUTH contains hardcoded password"
        else:
            auth = env.get("NEO4J_AUTH", "")
            assert "${" in str(auth), "NEO4J_AUTH contains hardcoded password"

    def test_langfuse_secret_from_env(self, compose: dict):
        env = compose["services"]["langfuse"].get("environment", {})
        if isinstance(env, list):
            secret_entries = [e for e in env if "NEXTAUTH_SECRET" in e]
            assert secret_entries, "NEXTAUTH_SECRET not set"
            for entry in secret_entries:
                assert "${" in entry, "NEXTAUTH_SECRET is hardcoded"
        else:
            secret = env.get("NEXTAUTH_SECRET", "")
            assert "${" in str(secret), "NEXTAUTH_SECRET is hardcoded"


# --- Dependency Ordering ---


class TestDependencyOrdering:
    def test_langfuse_depends_on_postgres(self, compose: dict):
        deps = compose["services"]["langfuse"].get("depends_on", {})
        if isinstance(deps, list):
            assert "postgres" in deps
        else:
            assert "postgres" in deps

    def test_langfuse_waits_for_postgres_healthy(self, compose: dict):
        deps = compose["services"]["langfuse"].get("depends_on", {})
        if isinstance(deps, dict):
            pg_dep = deps.get("postgres", {})
            assert pg_dep.get("condition") == "service_healthy"

    def test_grafana_depends_on_prometheus(self, compose: dict):
        deps = compose["services"]["grafana"].get("depends_on", {})
        if isinstance(deps, list):
            assert "prometheus" in deps
        else:
            assert "prometheus" in deps


# --- Init Script Mount ---


class TestInitScript:
    def test_postgres_mounts_init_script(self, compose: dict):
        volumes = compose["services"]["postgres"].get("volumes", [])
        assert any("init_langfuse_db" in str(v) for v in volumes)

    def test_init_script_exists(self):
        script = PROJECT_ROOT / "scripts" / "init_langfuse_db.sh"
        assert script.exists(), "scripts/init_langfuse_db.sh does not exist"

    def test_init_script_is_executable_content(self):
        script = PROJECT_ROOT / "scripts" / "init_langfuse_db.sh"
        content = script.read_text()
        assert "CREATE DATABASE" in content or "createdb" in content


# --- Prometheus Config ---


class TestPrometheusConfig:
    def test_prometheus_config_mounted(self, compose: dict):
        volumes = compose["services"]["prometheus"].get("volumes", [])
        assert any("prometheus.yml" in str(v) for v in volumes)

    def test_prometheus_config_exists(self):
        config = PROJECT_ROOT / "monitoring" / "prometheus.yml"
        assert config.exists(), "monitoring/prometheus.yml does not exist"

    def test_prometheus_config_valid_yaml(self):
        config = PROJECT_ROOT / "monitoring" / "prometheus.yml"
        data = yaml.safe_load(config.read_text())
        assert "scrape_configs" in data


# --- CPU Override ---


class TestCPUOverride:
    def test_override_has_services_key(self, cpu_override: dict):
        assert "services" in cpu_override
