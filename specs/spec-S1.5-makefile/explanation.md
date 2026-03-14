# S1.5 Makefile — Explanation

## Why This Spec Exists

Every development workflow needs a single, consistent entry point. Without a Makefile, developers must remember individual commands (`uv sync`, `docker-compose -f docker-compose.yml -f docker-compose.cpu.yml up -d`, `uv run pytest --cov=src --cov-report=term-missing tests/`). The Makefile reduces cognitive load to `make setup`, `make run`, `make test`. It also serves as the foundation for CI/CD (S9.5) — GitHub Actions will call `make check`.

## What It Does

Provides 26 Make targets organized into 7 categories:

| Category | Targets | Purpose |
|----------|---------|---------|
| Help | `help` | Self-documenting target list (default) |
| Setup | `setup`, `install`, `env`, `docker-pull` | Clone-to-running in one command |
| Services | `run`, `run-cpu`, `stop`, `restart`, `logs`, `status` | Docker Compose lifecycle |
| Testing | `test`, `test-unit`, `test-integration`, `test-cov` | pytest with coverage |
| Linting | `lint`, `lint-fix`, `format`, `format-check`, `check` | ruff linting + formatting |
| Database | `db-init`, `db-reset`, `benchmark` | Schema management |
| Cleanup | `clean`, `clean-docker`, `clean-py` | Artifact and volume removal |

## How It Works

1. **Self-documenting help**: Uses `grep` + `awk` to parse `## ` comments after target names, producing a formatted help display. This is a standard Makefile pattern — no external tools needed.

2. **Variable overrides**: All tool paths use `?=` (conditional assignment), so `DOCKER_COMPOSE=podman-compose make run` works without modifying the file.

3. **Environment loading**: `-include .env` loads database credentials for `db-init`/`db-reset` targets. The `-` prefix means "don't error if .env doesn't exist."

4. **All targets are `.PHONY`**: Since no target produces a file, all are declared `.PHONY` to ensure Make always runs the recipe (doesn't skip based on file timestamps).

## Key Concepts

### Self-Documenting Makefiles
The `help` target uses this pattern:
```makefile
@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-20s %s\n", $$1, $$2}'
```
It finds lines matching `target: ... ## description` and formats them as a table. This means adding a new target with `## comment` automatically appears in `make help`.

### .PHONY
In Make, targets are assumed to be files. If a file named `test` existed, `make test` would check its timestamp and potentially skip the recipe. `.PHONY` tells Make "this target is not a file — always run the recipe."

### Conditional Assignment (?=)
`DOCKER_COMPOSE ?= docker-compose` means "set DOCKER_COMPOSE to 'docker-compose' only if it's not already set." This allows overriding from the command line or environment without editing the Makefile.

## Connections

| Spec | Relationship |
|------|-------------|
| S1.1 (Project Structure) | `make install` runs `uv sync` against `pyproject.toml` |
| S1.2 (Docker Compose) | `make run` wraps `docker-compose up -d`; `make run-cpu` uses both compose files |
| S1.3 (Env Config) | `make env` copies `.env.example` to `.env` |
| S1.4 (DB Schema) | `make db-init` runs `scripts/init_db.sql` |
| S9.5 (CI/CD) | GitHub Actions will call `make check` (lint + format-check + test) |

## Interview Talking Points

**Q: Why use Make instead of a shell script or npm-style scripts?**
A: Make provides: (1) dependency tracking between targets (e.g., `setup: install env docker-pull`), (2) parallel execution with `make -j`, (3) self-documenting help via comment parsing, (4) conditional execution (only runs if needed), (5) it's universally available on Unix systems. Shell scripts lack dependency graphs. npm scripts are JavaScript-specific. Task runners like `just` or `task` require extra installs. Make is the lowest-common-denominator that works everywhere.

**Q: Why `.PHONY` for every target?**
A: All our targets are commands, not file-producing build rules. Without `.PHONY`, if someone creates a file named `test` or `clean`, Make would check its timestamp and potentially skip the recipe — a subtle, confusing bug. Declaring all targets `.PHONY` prevents this class of bugs entirely.

**Q: How does the self-documenting help pattern work?**
A: Each target has a `## description` comment on the same line as the rule. The `help` target greps for this pattern, splits on `:.*## ` to separate target name from description, and formats the output. Adding a new target with `##` automatically includes it in `make help` — zero maintenance cost.
