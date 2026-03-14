# CRISIS-BENCH Makefile
# Run `make` or `make help` to see all available targets.

.DEFAULT_GOAL := help

# --- Variables (overridable) ---
DOCKER_COMPOSE ?= docker-compose
PYTHON         ?= uv run python
PYTEST         ?= uv run pytest
RUFF           ?= uv run ruff
UV             ?= uv

# Include .env for database credentials (optional, non-fatal if missing)
-include .env
export

# =============================================================================
# Help
# =============================================================================

.PHONY: help
help: ## Show this help message
	@echo "CRISIS-BENCH — Multi-agent disaster response coordination system"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

# =============================================================================
# Setup
# =============================================================================

.PHONY: setup install env docker-pull
setup: install env docker-pull ## One-command project setup
	@echo ""
	@echo "Setup complete! Next steps:"
	@echo "  1. Edit .env with your API keys"
	@echo "  2. make run       — start Docker services"
	@echo "  3. make test      — run tests"

install: ## Install Python dependencies via uv
	$(UV) sync

env: ## Copy .env.example to .env (if .env doesn't exist)
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example — edit it with your API keys"; \
	else \
		echo ".env already exists, skipping"; \
	fi

docker-pull: ## Pull all Docker images
	$(DOCKER_COMPOSE) pull

# =============================================================================
# Services
# =============================================================================

.PHONY: run run-cpu stop restart logs status
run: ## Start all infrastructure services (detached)
	$(DOCKER_COMPOSE) up -d
	@echo "Services started. Run 'make status' to check."

run-cpu: ## Start services in CPU-only mode (no GPU)
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.cpu.yml up -d
	@echo "Services started (CPU mode). Run 'make status' to check."

stop: ## Stop all services
	$(DOCKER_COMPOSE) down

restart: stop run ## Restart all services

logs: ## Tail service logs (Ctrl+C to stop)
	$(DOCKER_COMPOSE) logs -f

status: ## Show service status
	$(DOCKER_COMPOSE) ps

# =============================================================================
# Testing
# =============================================================================

.PHONY: test test-unit test-integration test-cov
test: ## Run all tests
	$(PYTEST) tests/

test-unit: ## Run unit tests only
	$(PYTEST) tests/unit/

test-integration: ## Run integration tests only
	$(PYTEST) tests/integration/

test-cov: ## Run tests with coverage report
	$(PYTEST) --cov=src --cov-report=term-missing tests/

# =============================================================================
# Linting & Formatting
# =============================================================================

.PHONY: lint lint-fix format format-check check
lint: ## Run ruff linter
	$(RUFF) check src/ tests/

lint-fix: ## Auto-fix lint issues
	$(RUFF) check --fix src/ tests/

format: ## Format code with ruff
	$(RUFF) format src/ tests/

format-check: ## Check formatting without changes
	$(RUFF) format --check src/ tests/

check: lint format-check test ## Run all checks (lint + format + tests)

# =============================================================================
# Database
# =============================================================================

.PHONY: db-init db-reset
db-init: ## Initialize database schema
	PGPASSWORD=$(POSTGRES_PASSWORD) psql -h localhost -U crisis -d crisis_bench \
		-f scripts/init_db.sql

db-reset: ## Reset database to clean state (DESTRUCTIVE)
	PGPASSWORD=$(POSTGRES_PASSWORD) psql -h localhost -U crisis -d postgres \
		-c "DROP DATABASE IF EXISTS crisis_bench;"
	PGPASSWORD=$(POSTGRES_PASSWORD) psql -h localhost -U crisis -d postgres \
		-c "CREATE DATABASE crisis_bench;"
	$(MAKE) db-init

# =============================================================================
# Benchmark
# =============================================================================

.PHONY: benchmark
benchmark: ## Run benchmark suite
	$(PYTHON) scripts/run_benchmark.py

# =============================================================================
# Cleanup
# =============================================================================

.PHONY: clean clean-docker clean-py
clean: clean-py clean-docker ## Full cleanup (Python artifacts + Docker volumes)

clean-docker: ## Stop services and remove volumes (DESTRUCTIVE)
	$(DOCKER_COMPOSE) down -v

clean-py: ## Remove Python cache files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
