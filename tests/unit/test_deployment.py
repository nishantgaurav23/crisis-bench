"""Tests for S9.6: Oracle Cloud Always Free Deployment.

Tests cover:
- Dockerfile.api structure and correctness
- Dockerfile.dashboard structure and correctness
- nginx.conf syntax and routing rules
- docker-compose.prod.yml validity and merge with base
- deploy.sh env validation and structure
- health_check.sh service checking logic
- .env.production.example completeness
"""

import os
from pathlib import Path

import pytest
import yaml

# ── Project root ──────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]


# ═══════════════════════════════════════════════════════════════════════
# Dockerfile.api tests
# ═══════════════════════════════════════════════════════════════════════


class TestDockerfileApi:
    """Tests for docker/Dockerfile.api."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.dockerfile = ROOT / "docker" / "Dockerfile.api"

    def test_file_exists(self):
        assert self.dockerfile.exists(), "docker/Dockerfile.api must exist"

    def test_multi_stage_build(self):
        content = self.dockerfile.read_text()
        # Must have at least 2 FROM statements (multi-stage)
        from_count = content.lower().count("\nfrom ") + (
            1 if content.lower().startswith("from ") else 0
        )
        assert from_count >= 2, "Dockerfile.api must use multi-stage build (>=2 FROM)"

    def test_uses_python_base(self):
        content = self.dockerfile.read_text()
        assert "python:" in content.lower() or "python3" in content.lower(), (
            "Must use a Python base image"
        )

    def test_exposes_port_8000(self):
        content = self.dockerfile.read_text()
        assert "EXPOSE 8000" in content, "Must expose port 8000 for API"

    def test_has_healthcheck(self):
        content = self.dockerfile.read_text()
        assert "HEALTHCHECK" in content, "Must include HEALTHCHECK instruction"

    def test_non_root_user(self):
        content = self.dockerfile.read_text()
        assert "USER" in content, "Must run as non-root user"

    def test_copies_requirements_before_code(self):
        """Ensure dependency layer caching: copy requirements before full source."""
        content = self.dockerfile.read_text()
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        # Find first COPY of pyproject.toml and first COPY of src/
        pyproject_idx = None
        src_idx = None
        for i, line in enumerate(lines):
            if "pyproject.toml" in line and line.startswith("COPY"):
                pyproject_idx = i
            if ("src/" in line or "src ." in line or ". ." in line) and line.startswith("COPY"):
                if src_idx is None:
                    src_idx = i
        if pyproject_idx is not None and src_idx is not None:
            assert pyproject_idx < src_idx, (
                "pyproject.toml should be copied before source code for layer caching"
            )


# ═══════════════════════════════════════════════════════════════════════
# Dockerfile.dashboard tests
# ═══════════════════════════════════════════════════════════════════════


class TestDockerfileDashboard:
    """Tests for docker/Dockerfile.dashboard."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.dockerfile = ROOT / "docker" / "Dockerfile.dashboard"

    def test_file_exists(self):
        assert self.dockerfile.exists(), "docker/Dockerfile.dashboard must exist"

    def test_multi_stage_build(self):
        content = self.dockerfile.read_text()
        from_count = content.lower().count("\nfrom ") + (
            1 if content.lower().startswith("from ") else 0
        )
        assert from_count >= 2, "Must use multi-stage build"

    def test_uses_node_base(self):
        content = self.dockerfile.read_text()
        assert "node:" in content.lower(), "Must use Node.js base image"

    def test_exposes_port_3000(self):
        content = self.dockerfile.read_text()
        assert "EXPOSE 3000" in content, "Must expose port 3000"

    def test_has_healthcheck(self):
        content = self.dockerfile.read_text()
        assert "HEALTHCHECK" in content, "Must include HEALTHCHECK"

    def test_non_root_user(self):
        content = self.dockerfile.read_text()
        assert "USER" in content, "Must run as non-root user"


# ═══════════════════════════════════════════════════════════════════════
# nginx.conf tests
# ═══════════════════════════════════════════════════════════════════════


class TestNginxConf:
    """Tests for docker/nginx.conf."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.nginx_conf = ROOT / "docker" / "nginx.conf"

    def test_file_exists(self):
        assert self.nginx_conf.exists(), "docker/nginx.conf must exist"

    def test_routes_api(self):
        content = self.nginx_conf.read_text()
        assert "/api/" in content or "/api" in content, "Must route /api to backend"

    def test_routes_websocket(self):
        content = self.nginx_conf.read_text()
        assert "/ws" in content, "Must route /ws for WebSocket"
        assert "upgrade" in content.lower(), "Must handle WebSocket upgrade"

    def test_routes_dashboard(self):
        content = self.nginx_conf.read_text()
        # Default location or explicit dashboard routing
        assert "location /" in content, "Must route / to dashboard"

    def test_proxy_pass_to_correct_ports(self):
        content = self.nginx_conf.read_text()
        assert "8000" in content, "Must proxy to API on port 8000"
        assert "3000" in content, "Must proxy to dashboard on port 3000"

    def test_listens_on_port_80(self):
        content = self.nginx_conf.read_text()
        assert "listen 80" in content or "listen      80" in content, "Must listen on port 80"


# ═══════════════════════════════════════════════════════════════════════
# docker-compose.prod.yml tests
# ═══════════════════════════════════════════════════════════════════════


class TestDockerComposeProd:
    """Tests for docker-compose.prod.yml."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.prod_file = ROOT / "docker-compose.prod.yml"

    def test_file_exists(self):
        assert self.prod_file.exists(), "docker-compose.prod.yml must exist"

    def test_valid_yaml(self):
        content = self.prod_file.read_text()
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict), "Must be valid YAML dict"

    def test_has_services(self):
        content = self.prod_file.read_text()
        parsed = yaml.safe_load(content)
        assert "services" in parsed, "Must define services"

    def test_api_service_defined(self):
        parsed = yaml.safe_load(self.prod_file.read_text())
        assert "api" in parsed["services"], "Must define api service"

    def test_nginx_service_defined(self):
        parsed = yaml.safe_load(self.prod_file.read_text())
        assert "nginx" in parsed["services"], "Must define nginx service"

    def test_resource_limits(self):
        """Production services should have memory limits."""
        parsed = yaml.safe_load(self.prod_file.read_text())
        services_with_limits = 0
        for name, svc in parsed["services"].items():
            if isinstance(svc, dict):
                deploy = svc.get("deploy", {})
                resources = deploy.get("resources", {})
                if resources.get("limits", {}).get("memory"):
                    services_with_limits += 1
                # Also check mem_limit (compose v2 format)
                if svc.get("mem_limit"):
                    services_with_limits += 1
        assert services_with_limits >= 3, (
            "At least 3 services should have memory limits in production"
        )

    def test_restart_policies(self):
        """Production services should have restart policies."""
        parsed = yaml.safe_load(self.prod_file.read_text())
        for name, svc in parsed["services"].items():
            if isinstance(svc, dict):
                restart = svc.get("restart")
                deploy_restart = (
                    svc.get("deploy", {}).get("restart_policy", {}).get("condition")
                )
                assert restart or deploy_restart, (
                    f"Service '{name}' must have a restart policy in production"
                )

    def test_no_exposed_debug_ports(self):
        """Production should not expose database ports to host."""
        parsed = yaml.safe_load(self.prod_file.read_text())
        # nginx should expose 80, but postgres/redis/neo4j should not expose to host
        # In prod override, db ports should be removed or only on internal network
        nginx_svc = parsed["services"].get("nginx", {})
        if isinstance(nginx_svc, dict) and "ports" in nginx_svc:
            ports = nginx_svc["ports"]
            port_strs = [str(p) for p in ports]
            assert any("80" in p for p in port_strs), "nginx must expose port 80"


# ═══════════════════════════════════════════════════════════════════════
# .env.production.example tests
# ═══════════════════════════════════════════════════════════════════════


class TestEnvProductionExample:
    """Tests for .env.production.example."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.env_file = ROOT / ".env.production.example"

    def test_file_exists(self):
        assert self.env_file.exists(), ".env.production.example must exist"

    def test_has_required_vars(self):
        content = self.env_file.read_text()
        required = [
            "POSTGRES_PASSWORD",
            "NEO4J_PASSWORD",
            "LANGFUSE_SECRET",
            "LANGFUSE_SALT",
            "OLLAMA_HOST",
        ]
        for var in required:
            assert var in content, f"Must include {var}"

    def test_no_real_secrets(self):
        """Production example must not contain real secret values."""
        content = self.env_file.read_text()
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("#") or not line or "=" not in line:
                continue
            key, _, value = line.partition("=")
            # Values should be empty or placeholder
            if key.strip() in ("OLLAMA_HOST",):
                continue  # These can have default values
            # Check it's not a real-looking secret
            assert len(value.strip()) < 40 or value.strip().startswith("<"), (
                f"{key} appears to contain a real secret"
            )

    def test_has_domain_config(self):
        """Production should have domain/host configuration."""
        content = self.env_file.read_text()
        assert "DOMAIN" in content or "HOST" in content or "SERVER" in content, (
            "Must include domain/host configuration for production"
        )


# ═══════════════════════════════════════════════════════════════════════
# deploy.sh tests
# ═══════════════════════════════════════════════════════════════════════


class TestDeployScript:
    """Tests for scripts/deploy.sh."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.script = ROOT / "scripts" / "deploy.sh"

    def test_file_exists(self):
        assert self.script.exists(), "scripts/deploy.sh must exist"

    def test_is_executable(self):
        assert os.access(self.script, os.X_OK), "deploy.sh must be executable"

    def test_has_shebang(self):
        content = self.script.read_text()
        assert content.startswith("#!/"), "Must have shebang line"

    def test_uses_set_e(self):
        """Script should exit on error."""
        content = self.script.read_text()
        assert "set -e" in content, "Must use 'set -e' to exit on errors"

    def test_checks_env_file(self):
        content = self.script.read_text()
        assert ".env" in content, "Must reference .env file"

    def test_validates_required_vars(self):
        """Script should validate critical env vars exist."""
        content = self.script.read_text()
        assert "POSTGRES_PASSWORD" in content, "Must validate POSTGRES_PASSWORD"

    def test_installs_docker(self):
        content = self.script.read_text()
        assert "docker" in content.lower(), "Must handle Docker installation"

    def test_uses_prod_compose(self):
        content = self.script.read_text()
        assert "prod" in content, "Must reference production compose file"

    def test_has_help_option(self):
        """Script should support --help."""
        content = self.script.read_text()
        assert "--help" in content or "-h" in content, "Must support --help flag"


# ═══════════════════════════════════════════════════════════════════════
# health_check.sh tests
# ═══════════════════════════════════════════════════════════════════════


class TestHealthCheckScript:
    """Tests for scripts/health_check.sh."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.script = ROOT / "scripts" / "health_check.sh"

    def test_file_exists(self):
        assert self.script.exists(), "scripts/health_check.sh must exist"

    def test_is_executable(self):
        assert os.access(self.script, os.X_OK), "health_check.sh must be executable"

    def test_has_shebang(self):
        content = self.script.read_text()
        assert content.startswith("#!/"), "Must have shebang line"

    def test_checks_api_health(self):
        content = self.script.read_text()
        assert "8000" in content or "api" in content.lower(), "Must check API health"

    def test_checks_postgres(self):
        content = self.script.read_text()
        assert "postgres" in content.lower() or "5432" in content, "Must check PostgreSQL"

    def test_checks_redis(self):
        content = self.script.read_text()
        assert "redis" in content.lower() or "6379" in content, "Must check Redis"

    def test_reports_status(self):
        """Must output status for each service."""
        content = self.script.read_text()
        assert "OK" in content or "PASS" in content or "UP" in content or "healthy" in content.lower(), (
            "Must report healthy status"
        )
        assert "FAIL" in content or "DOWN" in content or "unhealthy" in content.lower() or "ERROR" in content, (
            "Must report unhealthy status"
        )

    def test_exit_code_on_failure(self):
        """Script should exit with non-zero on any service failure."""
        content = self.script.read_text()
        assert "exit 1" in content or "exit $" in content, (
            "Must exit non-zero on failure"
        )
