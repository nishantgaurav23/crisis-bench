# Spec S9.5 — CI/CD (GitHub Actions) — Explanation

## Why This Spec Exists

Every professional software project needs automated quality gates. Without CI/CD, code quality relies entirely on developer discipline — lint errors slip through, tests break silently, and Docker builds fail in production. GitHub Actions provides free CI/CD for public repos, making it the natural choice for crisis-bench.

This spec is the second-to-last in Phase 9 (Optimization & Polish) because it codifies all the quality checks that previous phases established (ruff linting, pytest unit tests, Docker builds) into automated pipelines.

## What It Does

Three GitHub Actions workflows:

### 1. `ci.yml` — Code Quality Gate
- **Triggers**: Every push to `main` and every pull request
- **Lint job**: Runs `ruff check` and `ruff format --check` to enforce code style
- **Test job**: Runs `pytest tests/unit/` on a Python 3.11 + 3.12 matrix
- **Coverage**: Generates coverage report and uploads as artifact
- **Dependency install**: Uses `uv` (via `astral-sh/setup-uv`) for fast, reproducible installs
- **Concurrency**: Cancels in-progress runs on the same branch to save CI minutes

### 2. `benchmark_regression.yml` — Benchmark Score Protection
- **Triggers**: PRs that touch `src/benchmark/`, `src/agents/`, `src/routing/`, or `benchmark/baseline.json`; also manual via `workflow_dispatch`
- **Validates**: `benchmark/baseline.json` exists and is valid JSON
- **Compares**: Runs baseline score validation (future: full regression comparison)
- **Artifacts**: Uploads benchmark results for historical tracking

### 3. `docker.yml` — Container Build Validation
- **Triggers**: Pushes to `main` that touch `docker/`, `docker-compose.yml`, `dashboard/Dockerfile`, or `src/`
- **Validates**: `docker compose config` to catch YAML syntax errors
- **Builds**: Dashboard Docker image with BuildKit layer caching (no push to registry — self-hosted)

### 4. `benchmark/baseline.json` — Score Baseline
- Stores baseline scores for all 6 benchmark dimensions (5 metrics + aggregate DRS)
- Initial scores are 0.0 — populated after first full benchmark run
- Schema validated by tests to prevent silent corruption

## How It Works

### Workflow Architecture
```
Push to main ──→ ci.yml (lint + test)
              ──→ docker.yml (build)

Pull Request ──→ ci.yml (lint + test)
             ──→ benchmark_regression.yml (if benchmark paths changed)

Manual       ──→ benchmark_regression.yml (workflow_dispatch)
```

### Key Design Decisions

1. **Unit tests only in CI** — Integration tests need PostgreSQL, Redis, Neo4j, ChromaDB (5+ Docker services). Starting these in CI adds 5-10 min and burns CI minutes. Unit tests with mocks cover 80%+ of logic. Integration tests run locally via `make test-integration`.

2. **Python matrix (3.11 + 3.12)** — Project targets `>=3.11`. Testing both catches version-specific bugs. 3.12 has 10-15% performance improvements we may leverage.

3. **uv instead of pip** — `uv sync --frozen` is 10-100x faster than `pip install`. Combined with `astral-sh/setup-uv`, dependency install drops from ~60s to ~5s.

4. **Concurrency groups** — Prevents wasted CI minutes. If you push 3 commits in quick succession, only the latest runs.

5. **Path filters on docker.yml and benchmark_regression.yml** — No point building Docker images on a docs-only PR. Path filters keep CI focused and fast.

6. **No registry push** — crisis-bench is self-hosted on Oracle Cloud Always Free (S9.6). Images are built locally via `docker compose build`. CI validates they build correctly, but doesn't push.

## How It Connects

### Dependencies (upstream)
- **S1.5 (Makefile)** — CI workflows mirror Make targets (`make lint`, `make test-unit`)
- **S8.10 (Aggregate DRS)** — Benchmark baseline scores correspond to the 5 evaluation dimensions + aggregate DRS from Phase 8

### Dependents (downstream)
- **S9.6 (Deployment)** — Deployment scripts can trigger CI workflows for pre-deploy validation

### Related Specs
- **S2.5 (Telemetry)** — CI validates that telemetry code passes lint/tests
- **S1.2 (Docker Compose)** — `docker.yml` validates the compose config from S1.2

## Interview Q&A

**Q: Why separate workflows instead of one monolithic CI file?**
A: Separation of concerns + performance. A lint failure shouldn't block Docker build checks. Path filters on `benchmark_regression.yml` and `docker.yml` mean they only run when relevant files change. A monolithic workflow would run everything on every PR, wasting CI minutes.

**Q: Why not run integration tests in CI?**
A: Cost-benefit analysis. Integration tests need 5+ Docker services (PostgreSQL, Redis, Neo4j, ChromaDB, Langfuse) — starting them in CI adds ~5 min overhead and ~$0 cost on GitHub Actions free tier (but uses limited minutes). Unit tests with mocked externals cover 80%+ of code paths. Integration tests run locally before merge via `make test-integration`.

**Q: What is `uv sync --frozen` and why use it?**
A: `uv sync` installs all dependencies from `pyproject.toml`. The `--frozen` flag ensures the lockfile is used exactly as-is — if someone forgot to update the lockfile, CI fails rather than silently installing different versions. This prevents "works on my machine" problems from dependency drift.

**Q: How does benchmark regression detection work?**
A: `benchmark/baseline.json` stores expected scores for all 6 dimensions. On PRs that touch agent/benchmark code, the workflow validates the baseline exists and is valid. Future enhancement: run a 10-scenario subset, compare scores, and post a PR comment if any dimension drops >5%. This prevents performance regressions from slipping through code review.
