"""Tests for S1.1: Verify project structure and package layout."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class TestDirectoriesExist:
    """All expected source directories must exist."""

    EXPECTED_DIRS = [
        "src",
        "src/agents",
        "src/routing",
        "src/protocols",
        "src/protocols/a2a",
        "src/protocols/mcp",
        "src/benchmark",
        "src/benchmark/metrics",
        "src/data",
        "src/data/ingest",
        "src/data/synthetic",
        "src/data/processing",
        "src/caching",
        "src/api",
        "src/api/routes",
        "src/shared",
        "tests",
        "tests/unit",
        "tests/integration",
        "docker",
        "scripts",
        "monitoring",
        "specs",
        "dashboard",
    ]

    def test_directories_exist(self):
        for d in self.EXPECTED_DIRS:
            assert (ROOT / d).is_dir(), f"Directory missing: {d}"


class TestInitFiles:
    """All Python packages must have __init__.py."""

    PYTHON_PACKAGES = [
        "src",
        "src/agents",
        "src/routing",
        "src/protocols",
        "src/protocols/a2a",
        "src/protocols/mcp",
        "src/benchmark",
        "src/benchmark/metrics",
        "src/data",
        "src/data/ingest",
        "src/data/synthetic",
        "src/data/processing",
        "src/caching",
        "src/api",
        "src/api/routes",
        "src/shared",
        "tests",
        "tests/unit",
        "tests/integration",
    ]

    def test_init_files_exist(self):
        for pkg in self.PYTHON_PACKAGES:
            init_file = ROOT / pkg / "__init__.py"
            assert init_file.is_file(), f"Missing __init__.py in {pkg}"


class TestConftest:
    """tests/conftest.py must exist."""

    def test_conftest_exists(self):
        assert (ROOT / "tests" / "conftest.py").is_file()


class TestTopLevelFiles:
    """Critical top-level files must exist."""

    def test_pyproject_toml_exists(self):
        assert (ROOT / "pyproject.toml").is_file()

    def test_gitignore_exists(self):
        assert (ROOT / ".gitignore").is_file()

    def test_env_example_exists(self):
        assert (ROOT / ".env.example").is_file()
