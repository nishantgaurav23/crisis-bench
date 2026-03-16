# Spec S1.5: Makefile

**Status**: done
**Phase**: 1 — Project Bootstrap
**Depends On**: S1.2 (Docker Compose) ✅ done
**Location**: `Makefile`

---

## 1. Overview

Create a Makefile that provides convenient shortcuts for all common development operations: setting up the environment, starting services, running tests, linting, benchmarking, and cleaning up.

### Why This Matters

- **Interview**: Makefiles demonstrate understanding of build automation, developer experience (DX), and reproducible workflows. Shows you think about the full development lifecycle, not just writing code.
- **Project**: Every developer (and CI/CD in S9.5) needs a single entry point for common tasks. `make setup && make run` is the fastest path from clone to running system.

---

## 2. Make Targets

| Target | Command | Description |
|--------|---------|-------------|
| `help` (default) | — | Print all available targets with descriptions |
| `setup` | Install deps + copy .env + pull Docker images | One-command project setup |
| `install` | `uv sync` | Install Python dependencies via uv |
| `env` | Copy `.env.example` to `.env` if not exists | Initialize environment config |
| `docker-pull` | `docker-compose pull` | Pull all Docker images |
| `run` | `docker-compose up -d` | Start all infrastructure services |
| `run-cpu` | `docker-compose -f docker-compose.yml -f docker-compose.cpu.yml up -d` | Start services (CPU-only mode) |
| `stop` | `docker-compose down` | Stop all services |
| `restart` | `make stop && make run` | Restart all services |
| `logs` | `docker-compose logs -f` | Tail service logs |
| `status` | `docker-compose ps` | Show service status |
| `test` | `pytest tests/` | Run all tests |
| `test-unit` | `pytest tests/unit/` | Run unit tests only |
| `test-integration` | `pytest tests/integration/` | Run integration tests only |
| `test-cov` | `pytest --cov=src --cov-report=term-missing tests/` | Run tests with coverage report |
| `lint` | `ruff check src/ tests/` | Run ruff linter |
| `lint-fix` | `ruff check --fix src/ tests/` | Auto-fix lint issues |
| `format` | `ruff format src/ tests/` | Format code with ruff |
| `format-check` | `ruff format --check src/ tests/` | Check formatting without changes |
| `check` | `make lint && make format-check && make test` | Run all checks (lint + format + tests) |
| `benchmark` | `python scripts/run_benchmark.py` | Run benchmark suite |
| `db-init` | `psql` with `scripts/init_db.sql` | Initialize database schema |
| `db-reset` | Drop + recreate crisis_bench DB + re-init | Reset database to clean state |
| `clean` | Remove caches, build artifacts, Docker volumes | Full cleanup |
| `clean-docker` | `docker-compose down -v` | Stop services + remove volumes |
| `clean-py` | Remove `__pycache__`, `.pytest_cache`, `.ruff_cache`, `*.pyc` | Clean Python artifacts |

---

## 3. Target Details

### 3.1 `help` (default target)
- Parses Makefile comments (lines with `## `) and prints formatted help
- Uses `grep` + `awk` pattern for self-documenting targets
- Runs when you type `make` with no arguments

### 3.2 `setup`
- Runs `install`, `env`, `docker-pull` in sequence
- Prints a summary message with next steps
- Idempotent — safe to run multiple times

### 3.3 `run` / `run-cpu`
- Detached mode (`-d`) so terminal is freed
- `run-cpu` uses the override file for CPU-only environments
- Both print a message showing how to check status (`make status`)

### 3.4 `test` variants
- All use `pytest` with settings from `pyproject.toml`
- `test-cov` uses `--cov=src --cov-report=term-missing`
- Tests run against local environment (Docker services must be up for integration tests)

### 3.5 `lint` / `format`
- Uses `ruff` configured in `pyproject.toml` (line-length: 100, Python 3.11)
- `lint-fix` auto-fixes safe issues
- `format` uses ruff's formatter (replaces black)

### 3.6 `check`
- Runs lint + format-check + tests in sequence
- Fails fast on first error
- This is what CI (S9.5) will call

### 3.7 `db-init` / `db-reset`
- Uses `POSTGRES_PASSWORD` from `.env`
- `db-init` runs `scripts/init_db.sql` against PostgreSQL
- `db-reset` drops and recreates the database first
- Requires PostgreSQL to be running (`make run` first)

### 3.8 `clean` variants
- `clean` = `clean-py` + `clean-docker`
- `clean-py` removes all Python cache files recursively
- `clean-docker` stops services AND removes volumes (destructive — data loss)

---

## 4. Makefile Standards

1. `.PHONY` declaration for all targets (none create files)
2. Use `?=` for overridable variables (e.g., `DOCKER_COMPOSE ?= docker-compose`)
3. Use `.env` include with `-include .env` for database credentials
4. Self-documenting with `## ` comments after target names
5. No hardcoded secrets — all from environment or `.env`
6. Compatible with GNU Make (macOS + Linux)

---

## 5. Outcomes / Acceptance Criteria

1. `make` (no args) prints help with all targets listed
2. `make setup` installs deps, copies .env, pulls Docker images
3. `make run` starts all Docker services in detached mode
4. `make run-cpu` starts services with CPU-only override
5. `make stop` stops all services
6. `make test` runs pytest
7. `make test-cov` runs pytest with coverage
8. `make lint` runs ruff check
9. `make format` runs ruff format
10. `make check` runs lint + format-check + tests
11. `make clean` removes caches and Docker volumes
12. `make db-init` runs init_db.sql
13. All targets are `.PHONY`
14. No secrets hardcoded in Makefile

---

## 6. TDD Notes

### What to Test

Since the Makefile is a configuration/automation file (not Python code), we test it by:

1. **File existence**: Makefile exists at project root
2. **Target presence**: All required targets are defined
3. **PHONY declarations**: All targets are declared .PHONY
4. **Self-documenting**: `make help` / `make` output includes all target descriptions
5. **No hardcoded secrets**: No passwords/keys in Makefile content
6. **Variable defaults**: Overridable variables use `?=` syntax
7. **Docker commands**: `run` target uses `docker-compose up -d`, `run-cpu` uses both compose files
8. **Test commands**: `test` target invokes `pytest`
9. **Lint commands**: `lint` target invokes `ruff`
10. **Clean targets**: `clean-py` removes `__pycache__`, `clean-docker` uses `docker-compose down -v`

### Test File
`tests/unit/test_makefile.py`

### How to Test
- Read the Makefile as text and parse target definitions
- Use regex to validate target names, commands, and PHONY declarations
- Verify no secret values (API keys, passwords) are hardcoded
- Run `make help` via subprocess and validate output contains all targets
- No Docker daemon required for unit tests
