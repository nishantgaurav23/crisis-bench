"""Tests for S1.1: Verify pyproject.toml configuration."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_pyproject() -> dict:
    with open(ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)


class TestProjectMetadata:
    def test_name(self):
        cfg = _load_pyproject()
        assert cfg["project"]["name"] == "crisis-bench"

    def test_python_version(self):
        cfg = _load_pyproject()
        assert "3.11" in cfg["project"]["requires-python"]

    def test_license(self):
        cfg = _load_pyproject()
        license_val = cfg["project"].get("license")
        assert license_val is not None
        # Accept either string or dict format
        if isinstance(license_val, dict):
            assert "Apache" in license_val.get("text", "")
        else:
            assert "Apache" in str(license_val)


class TestCoreDependencies:
    """Key dependencies must be declared."""

    REQUIRED_DEPS = [
        "fastapi",
        "uvicorn",
        "asyncpg",
        "redis",
        "openai",
        "langgraph",
        "httpx",
        "pydantic",
        "pydantic-settings",
        "structlog",
        "prometheus-client",
    ]

    def test_required_deps_present(self):
        cfg = _load_pyproject()
        deps = cfg["project"]["dependencies"]
        dep_names = [d.split("[")[0].split(">")[0].split("=")[0].strip() for d in deps]
        for req in self.REQUIRED_DEPS:
            assert req in dep_names, f"Missing dependency: {req}"


class TestDevDependencies:
    """Dev/test dependencies must be declared."""

    REQUIRED_DEV = ["pytest", "pytest-asyncio", "pytest-cov", "ruff", "hypothesis"]

    def test_dev_deps_present(self):
        cfg = _load_pyproject()
        dev_deps = cfg["project"]["optional-dependencies"]["dev"]
        dep_names = [d.split("[")[0].split(">")[0].split("=")[0].strip() for d in dev_deps]
        for req in self.REQUIRED_DEV:
            assert req in dep_names, f"Missing dev dependency: {req}"


class TestRuffConfig:
    def test_line_length(self):
        cfg = _load_pyproject()
        assert cfg["tool"]["ruff"]["line-length"] == 100

    def test_target_version(self):
        cfg = _load_pyproject()
        assert cfg["tool"]["ruff"]["target-version"] == "py311"


class TestPytestConfig:
    def test_asyncio_mode(self):
        cfg = _load_pyproject()
        assert cfg["tool"]["pytest"]["ini_options"]["asyncio_mode"] == "auto"

    def test_testpaths(self):
        cfg = _load_pyproject()
        assert "tests" in cfg["tool"]["pytest"]["ini_options"]["testpaths"]
