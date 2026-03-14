"""Tests for S1.5: Makefile.

Validates the Makefile at the project root has all required targets,
proper PHONY declarations, no hardcoded secrets, and correct commands.
"""

import re
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def makefile_path() -> Path:
    return PROJECT_ROOT / "Makefile"


@pytest.fixture
def makefile_content(makefile_path: Path) -> str:
    """Read the Makefile content."""
    assert makefile_path.exists(), "Makefile does not exist at project root"
    return makefile_path.read_text()


# All targets that must be present in the Makefile
REQUIRED_TARGETS = [
    "help",
    "setup",
    "install",
    "env",
    "docker-pull",
    "run",
    "run-cpu",
    "stop",
    "restart",
    "logs",
    "status",
    "test",
    "test-unit",
    "test-integration",
    "test-cov",
    "lint",
    "lint-fix",
    "format",
    "format-check",
    "check",
    "benchmark",
    "db-init",
    "db-reset",
    "clean",
    "clean-docker",
    "clean-py",
]

# Secrets that must NOT appear as literal values in the Makefile
SECRET_PATTERNS = [
    r"(?i)(api[_-]?key|password|secret|token)\s*[:=]\s*['\"]?[a-zA-Z0-9]{8,}",
    r"sk-[a-zA-Z0-9]{20,}",
    r"ghp_[a-zA-Z0-9]{20,}",
]


# --- File Existence ---


class TestMakefileExists:
    def test_makefile_exists(self, makefile_path: Path):
        assert makefile_path.exists(), "Makefile must exist at project root"

    def test_makefile_is_not_empty(self, makefile_content: str):
        assert len(makefile_content.strip()) > 0, "Makefile must not be empty"


# --- Target Presence ---


class TestTargetPresence:
    """Every required target must be defined as a Makefile rule."""

    @pytest.mark.parametrize("target", REQUIRED_TARGETS)
    def test_target_defined(self, makefile_content: str, target: str):
        # Match target name at start of line followed by colon
        pattern = rf"^{re.escape(target)}\s*:"
        assert re.search(pattern, makefile_content, re.MULTILINE), (
            f"Target '{target}' not found in Makefile"
        )


# --- PHONY Declarations ---


class TestPhonyDeclarations:
    """All targets must be declared .PHONY (none produce files)."""

    def test_phony_exists(self, makefile_content: str):
        assert ".PHONY" in makefile_content, "Makefile must have .PHONY declarations"

    @pytest.mark.parametrize("target", REQUIRED_TARGETS)
    def test_target_is_phony(self, makefile_content: str, target: str):
        # Find all .PHONY lines and collect declared targets
        phony_targets: set[str] = set()
        for match in re.finditer(r"^\.PHONY\s*:\s*(.+)$", makefile_content, re.MULTILINE):
            phony_targets.update(match.group(1).split())
        assert target in phony_targets, f"Target '{target}' must be declared .PHONY"


# --- No Hardcoded Secrets ---


class TestNoSecrets:
    @pytest.mark.parametrize("pattern", SECRET_PATTERNS)
    def test_no_secret_patterns(self, makefile_content: str, pattern: str):
        matches = re.findall(pattern, makefile_content)
        assert not matches, f"Possible hardcoded secret found in Makefile: {matches}"

    def test_no_literal_passwords(self, makefile_content: str):
        # Passwords should use $(POSTGRES_PASSWORD) or env vars, not literals
        lines = makefile_content.splitlines()
        for i, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith("#"):
                continue
            assert "password=" not in line.lower() or "$(" in line or "${" in line, (
                f"Line {i} may contain a hardcoded password"
            )


# --- Command Validation ---


class TestCommandContent:
    def test_run_uses_docker_compose_up(self, makefile_content: str):
        # Find the run target's recipe
        run_match = re.search(
            r"^run\s*:.*?\n((?:\t.+\n)*)", makefile_content, re.MULTILINE
        )
        assert run_match, "run target not found"
        recipe = run_match.group(1)
        assert "up" in recipe and "-d" in recipe, (
            "run target must use 'docker-compose up -d' or equivalent"
        )

    def test_run_cpu_uses_both_compose_files(self, makefile_content: str):
        run_cpu_match = re.search(
            r"^run-cpu\s*:.*?\n((?:\t.+\n)*)", makefile_content, re.MULTILINE
        )
        assert run_cpu_match, "run-cpu target not found"
        recipe = run_cpu_match.group(1)
        assert "docker-compose.cpu.yml" in recipe, (
            "run-cpu must reference docker-compose.cpu.yml"
        )
        assert "docker-compose.yml" in recipe or "-f" in recipe, (
            "run-cpu must reference both compose files"
        )

    def test_test_uses_pytest(self, makefile_content: str):
        test_match = re.search(
            r"^test\s*:.*?\n((?:\t.+\n)*)", makefile_content, re.MULTILINE
        )
        assert test_match, "test target not found"
        recipe = test_match.group(1)
        assert "pytest" in recipe.lower() or "PYTEST" in recipe, (
            "test target must invoke pytest (directly or via variable)"
        )

    def test_lint_uses_ruff(self, makefile_content: str):
        lint_match = re.search(
            r"^lint\s*:.*?\n((?:\t.+\n)*)", makefile_content, re.MULTILINE
        )
        assert lint_match, "lint target not found"
        recipe = lint_match.group(1)
        assert "ruff" in recipe.lower() or "RUFF" in recipe, (
            "lint target must invoke ruff (directly or via variable)"
        )

    def test_clean_docker_removes_volumes(self, makefile_content: str):
        clean_match = re.search(
            r"^clean-docker\s*:.*?\n((?:\t.+\n)*)", makefile_content, re.MULTILINE
        )
        assert clean_match, "clean-docker target not found"
        recipe = clean_match.group(1)
        assert "down" in recipe and "-v" in recipe, (
            "clean-docker must use 'docker-compose down -v'"
        )

    def test_test_cov_has_coverage_flag(self, makefile_content: str):
        match = re.search(
            r"^test-cov\s*:.*?\n((?:\t.+\n)*)", makefile_content, re.MULTILINE
        )
        assert match, "test-cov target not found"
        recipe = match.group(1)
        assert "--cov" in recipe, "test-cov must use --cov flag"

    def test_format_uses_ruff_format(self, makefile_content: str):
        match = re.search(
            r"^format\s*:.*?\n((?:\t.+\n)*)", makefile_content, re.MULTILINE
        )
        assert match, "format target not found"
        recipe = match.group(1)
        has_ruff = "ruff" in recipe.lower() or "RUFF" in recipe
        assert has_ruff and "format" in recipe, (
            "format target must use 'ruff format' (directly or via variable)"
        )


# --- Self-Documenting Help ---


class TestSelfDocumenting:
    def test_help_is_default_target(self, makefile_content: str):
        # help should be the first target OR .DEFAULT_GOAL should be help
        has_default_goal = ".DEFAULT_GOAL" in makefile_content and "help" in makefile_content
        # Or help is the first target defined
        first_target = re.search(r"^([a-zA-Z_-]+)\s*:", makefile_content, re.MULTILINE)
        first_is_help = first_target and first_target.group(1) == "help"
        assert has_default_goal or first_is_help, (
            "help must be the default target (first target or .DEFAULT_GOAL := help)"
        )

    def test_targets_have_help_comments(self, makefile_content: str):
        # At least half of the required targets should have ## comments
        comment_count = 0
        for target in REQUIRED_TARGETS:
            pattern = rf"^{re.escape(target)}\s*:.*##\s*.+"
            if re.search(pattern, makefile_content, re.MULTILINE):
                comment_count += 1
        assert comment_count >= len(REQUIRED_TARGETS) // 2, (
            f"Only {comment_count}/{len(REQUIRED_TARGETS)} targets have ## help comments"
        )


# --- Make Help Output ---


class TestMakeHelp:
    def test_make_help_runs(self, makefile_path: Path):
        """Running 'make help' should succeed and produce output."""
        result = subprocess.run(
            ["make", "-f", str(makefile_path), "help"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, f"make help failed: {result.stderr}"
        assert len(result.stdout.strip()) > 0, "make help produced no output"

    def test_make_help_lists_key_targets(self, makefile_path: Path):
        """make help output should mention key targets."""
        result = subprocess.run(
            ["make", "-f", str(makefile_path), "help"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=PROJECT_ROOT,
        )
        output = result.stdout
        for target in ["setup", "run", "test", "lint", "clean"]:
            assert target in output, f"make help output should mention '{target}'"
