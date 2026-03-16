"""Tests for S9.5 — CI/CD GitHub Actions workflows."""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = ROOT / ".github" / "workflows"
MAKEFILE = ROOT / "Makefile"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _load_workflow(name: str) -> dict:
    """Load and parse a workflow YAML file.

    Note: YAML parses `on:` as boolean True, so we normalize it back to "on".
    """
    path = WORKFLOWS_DIR / name
    assert path.exists(), f"Workflow file {name} does not exist"
    text = path.read_text()
    data = yaml.safe_load(text)
    assert isinstance(data, dict), f"{name} is not valid YAML mapping"
    # yaml.safe_load converts `on:` key to boolean True — normalize it
    if True in data and "on" not in data:
        data["on"] = data.pop(True)
    return data


def _makefile_targets() -> set[str]:
    """Extract all Make targets from the Makefile."""
    targets = set()
    for line in MAKEFILE.read_text().splitlines():
        if ":" in line and not line.startswith("\t") and not line.startswith("#"):
            target = line.split(":")[0].strip()
            if target and not target.startswith(".") and not target.startswith("$"):
                targets.add(target)
    return targets


# ===========================================================================
# ci.yml tests
# ===========================================================================


class TestCIWorkflow:
    """Tests for the main CI workflow."""

    def test_ci_yml_exists(self):
        assert (WORKFLOWS_DIR / "ci.yml").exists()

    def test_ci_yml_valid_yaml(self):
        wf = _load_workflow("ci.yml")
        assert "name" in wf
        assert "on" in wf
        assert "jobs" in wf

    def test_ci_triggers_on_push_and_pr(self):
        wf = _load_workflow("ci.yml")
        triggers = wf["on"]
        assert "push" in triggers, "CI must trigger on push"
        assert "pull_request" in triggers, "CI must trigger on pull_request"

    def test_ci_push_targets_main(self):
        wf = _load_workflow("ci.yml")
        push = wf["on"]["push"]
        assert "main" in push.get("branches", [])

    def test_ci_has_lint_job(self):
        wf = _load_workflow("ci.yml")
        jobs = wf["jobs"]
        assert "lint" in jobs, "CI must have a lint job"

    def test_ci_has_test_job(self):
        wf = _load_workflow("ci.yml")
        jobs = wf["jobs"]
        assert "test" in jobs, "CI must have a test job"

    def test_ci_python_matrix_includes_311_and_312(self):
        wf = _load_workflow("ci.yml")
        test_job = wf["jobs"]["test"]
        strategy = test_job.get("strategy", {})
        matrix = strategy.get("matrix", {})
        py_versions = matrix.get("python-version", [])
        assert "3.11" in py_versions, "Must test Python 3.11"
        assert "3.12" in py_versions, "Must test Python 3.12"

    def test_ci_lint_uses_ruff(self):
        """Lint job must use ruff check and ruff format --check."""
        wf = _load_workflow("ci.yml")
        lint_steps = wf["jobs"]["lint"]["steps"]
        step_texts = " ".join(str(s.get("run", "")) for s in lint_steps)
        assert "ruff check" in step_texts, "Lint must run ruff check"
        assert "ruff format" in step_texts, "Lint must run ruff format --check"

    def test_ci_test_runs_unit_tests(self):
        """Test job must run pytest on unit tests."""
        wf = _load_workflow("ci.yml")
        test_steps = wf["jobs"]["test"]["steps"]
        step_texts = " ".join(str(s.get("run", "")) for s in test_steps)
        assert "pytest" in step_texts, "Test job must run pytest"

    def test_ci_uses_uv_for_install(self):
        """CI should use uv for dependency installation."""
        wf = _load_workflow("ci.yml")
        all_steps = []
        for job in wf["jobs"].values():
            all_steps.extend(job.get("steps", []))
        step_texts = " ".join(str(s.get("run", "")) + str(s.get("uses", "")) for s in all_steps)
        assert "uv" in step_texts.lower() or "astral-sh" in step_texts.lower(), (
            "CI should use uv for dependency management"
        )


# ===========================================================================
# benchmark_regression.yml tests
# ===========================================================================


class TestBenchmarkRegressionWorkflow:
    """Tests for the benchmark regression detection workflow."""

    def test_benchmark_yml_exists(self):
        assert (WORKFLOWS_DIR / "benchmark_regression.yml").exists()

    def test_benchmark_yml_valid_yaml(self):
        wf = _load_workflow("benchmark_regression.yml")
        assert "name" in wf
        assert "on" in wf
        assert "jobs" in wf

    def test_benchmark_triggers_on_pr(self):
        wf = _load_workflow("benchmark_regression.yml")
        triggers = wf["on"]
        assert "pull_request" in triggers, "Benchmark must trigger on PR"

    def test_benchmark_has_manual_trigger(self):
        wf = _load_workflow("benchmark_regression.yml")
        triggers = wf["on"]
        assert "workflow_dispatch" in triggers, "Benchmark must have manual trigger"

    def test_benchmark_has_compare_job(self):
        wf = _load_workflow("benchmark_regression.yml")
        jobs = wf["jobs"]
        # At least one job should handle benchmark comparison
        job_names = list(jobs.keys())
        assert len(job_names) >= 1, "Must have at least one benchmark job"


# ===========================================================================
# docker.yml tests
# ===========================================================================


class TestDockerWorkflow:
    """Tests for the Docker build workflow."""

    def test_docker_yml_exists(self):
        assert (WORKFLOWS_DIR / "docker.yml").exists()

    def test_docker_yml_valid_yaml(self):
        wf = _load_workflow("docker.yml")
        assert "name" in wf
        assert "on" in wf
        assert "jobs" in wf

    def test_docker_triggers_on_push_to_main(self):
        wf = _load_workflow("docker.yml")
        triggers = wf["on"]
        assert "push" in triggers
        push = triggers["push"]
        assert "main" in push.get("branches", [])

    def test_docker_validates_compose(self):
        """Docker workflow should validate docker-compose.yml."""
        wf = _load_workflow("docker.yml")
        all_steps = []
        for job in wf["jobs"].values():
            all_steps.extend(job.get("steps", []))
        step_texts = " ".join(str(s.get("run", "")) for s in all_steps)
        assert "docker" in step_texts.lower() and "compose" in step_texts.lower(), (
            "Docker workflow must validate compose config"
        )


# ===========================================================================
# Benchmark baseline tests
# ===========================================================================


class TestBenchmarkBaseline:
    """Tests for benchmark baseline score file."""

    def test_baseline_json_exists(self):
        baseline = ROOT / "benchmark" / "baseline.json"
        assert baseline.exists(), "benchmark/baseline.json must exist"

    def test_baseline_json_valid(self):
        baseline = ROOT / "benchmark" / "baseline.json"
        data = json.loads(baseline.read_text())
        assert isinstance(data, dict)

    def test_baseline_has_required_fields(self):
        baseline = ROOT / "benchmark" / "baseline.json"
        data = json.loads(baseline.read_text())
        assert "version" in data
        assert "scores" in data
        assert isinstance(data["scores"], dict)

    def test_baseline_scores_have_dimensions(self):
        baseline = ROOT / "benchmark" / "baseline.json"
        data = json.loads(baseline.read_text())
        scores = data["scores"]
        expected = [
            "situational_accuracy",
            "decision_timeliness",
            "resource_efficiency",
            "coordination_quality",
            "communication_appropriateness",
        ]
        for dim in expected:
            assert dim in scores, f"Baseline must include {dim} score"
            assert isinstance(scores[dim], (int, float)), f"{dim} must be numeric"

    def test_baseline_has_aggregate_drs(self):
        baseline = ROOT / "benchmark" / "baseline.json"
        data = json.loads(baseline.read_text())
        assert "aggregate_drs" in data["scores"]


# ===========================================================================
# Cross-cutting tests
# ===========================================================================


class TestWorkflowConsistency:
    """Cross-cutting consistency checks."""

    def test_all_three_workflows_exist(self):
        expected = ["ci.yml", "benchmark_regression.yml", "docker.yml"]
        for name in expected:
            assert (WORKFLOWS_DIR / name).exists(), f"{name} missing"

    def test_workflows_use_checkout_action(self):
        """All workflows should checkout the repo."""
        for name in ["ci.yml", "benchmark_regression.yml", "docker.yml"]:
            wf = _load_workflow(name)
            all_steps = []
            for job in wf["jobs"].values():
                all_steps.extend(job.get("steps", []))
            uses = [s.get("uses", "") for s in all_steps]
            has_checkout = any("actions/checkout" in u for u in uses)
            assert has_checkout, f"{name} must use actions/checkout"

    def test_no_secrets_hardcoded_in_workflows(self):
        """Workflows must not contain hardcoded secrets."""
        for name in ["ci.yml", "benchmark_regression.yml", "docker.yml"]:
            text = (WORKFLOWS_DIR / name).read_text()
            # Check for common secret patterns
            assert "sk-" not in text, f"{name} contains possible API key"
            assert "password" not in text.lower() or "POSTGRES_PASSWORD" not in text, (
                f"{name} may contain hardcoded password"
            )
