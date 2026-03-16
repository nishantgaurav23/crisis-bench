# Spec S9.5 — CI/CD (GitHub Actions)

**Phase**: 9 (Optimization & Polish)
**Depends On**: S1.5 (Makefile)
**Location**: `.github/workflows/`
**Status**: spec-written

---

## Overview

Set up GitHub Actions CI/CD pipelines that automatically lint, test, and validate code on every pull request and push to main. Includes a benchmark regression detection workflow that alerts when benchmark scores drop.

## Outcomes

1. **`ci.yml`** — Runs on every PR and push to main:
   - Lint with `ruff check` and `ruff format --check`
   - Run unit tests with `pytest tests/unit/`
   - Generate coverage report
   - Python 3.11 + 3.12 matrix

2. **`benchmark_regression.yml`** — Runs on PR (manual trigger also):
   - Run benchmark score comparison
   - Post PR comment if scores regress >5%
   - Store benchmark results as artifacts

3. **`docker.yml`** — Runs on push to main:
   - Build Docker images (API gateway, dashboard)
   - Validate docker-compose.yml syntax
   - No push to registry (self-hosted)

## Non-Goals

- No deployment to Oracle Cloud (that's S9.6)
- No paid CI/CD services
- No GPU-dependent jobs
- No integration tests in CI (they need Docker services running)

## Design Decisions

### Why GitHub Actions?
Free for public repos, YAML-based, first-class GitHub integration. No vendor lock-in — workflows are standard YAML + shell scripts.

### Why skip integration tests in CI?
Integration tests require PostgreSQL, Redis, Neo4j, ChromaDB, etc. Running all those via `docker-compose` in CI would take 5-10 min to start and cost CI minutes. Unit tests with mocks cover 80%+ of code. Integration tests run locally via `make test-integration`.

### Why matrix test on 3.11 + 3.12?
Project targets `>=3.11`. Testing both versions catches Python version-specific bugs early. 3.12 has significant performance improvements we may leverage.

### Benchmark Regression Strategy
Store baseline scores in `benchmark/baseline.json`. On PR, run a lightweight benchmark subset (10 scenarios) and compare. If any dimension drops >5%, post a warning comment on the PR. Full 100-scenario benchmark runs manually.

## TDD Notes

### Test File: `tests/unit/test_ci_cd.py`

Tests validate:
1. Workflow YAML files are valid YAML
2. Workflow files reference correct paths (src/, tests/, etc.)
3. Required workflow triggers exist (push, pull_request)
4. Python version matrix includes 3.11 and 3.12
5. All Make targets referenced in workflows exist in Makefile
6. Benchmark baseline schema is valid
7. Docker Compose validation command works
8. Ruff config in pyproject.toml matches CI expectations

### Implementation Order
1. Write tests (Red)
2. Create `ci.yml` workflow
3. Create `benchmark_regression.yml` workflow
4. Create `docker.yml` workflow
5. Create `benchmark/baseline.json` schema
6. All tests pass (Green)
7. Refactor + lint (Refactor)
