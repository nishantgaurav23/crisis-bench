# Spec S1.1: Project Structure + Dependency Declaration

**Phase**: 1 — Project Bootstrap
**Status**: done
**Depends On**: None
**Outputs**: `pyproject.toml`, `.gitignore`, `.env.example`, `src/**/__init__.py`, `tests/conftest.py`

---

## 1. Purpose

Establish the foundational project skeleton for CRISIS-BENCH: a properly configured Python project with all dependencies pinned, linting configured, test infrastructure ready, and environment template provided. After this spec, `uv sync` installs everything and `uv run pytest` runs (with zero tests initially).

## 2. Requirements

### 2.1 `pyproject.toml`

- **Build system**: hatchling (PEP 621 compliant)
- **Python**: requires-python >= 3.11
- **Project metadata**: name, version, description, author, license (Apache-2.0)
- **Dependencies** (all free/open-source, pinned with `>=` minimum versions):
  - **Web**: fastapi, uvicorn[standard], websockets
  - **Database**: asyncpg, redis[hiredis], neo4j, chromadb
  - **LLM**: openai (AsyncOpenAI for all providers), langgraph, langfuse
  - **Data**: httpx, feedparser, pydantic, pydantic-settings
  - **NLP**: transformers, torch (CPU), sentence-transformers
  - **Spatial**: geopandas, shapely, pyproj
  - **Optimization**: ortools, pulp
  - **Monitoring**: structlog, prometheus-client
  - **Translation**: (Bhashini via httpx, IndicTrans2 via transformers)
  - **Data Processing**: pandas, numpy, xarray, netCDF4, imdlib
  - **PDF**: pymupdf (fitz)
  - **MCP**: mcp
- **Dev dependencies** (`[project.optional-dependencies]` dev group):
  - pytest, pytest-asyncio, pytest-cov, hypothesis, ruff, pre-commit
- **Tool configs in pyproject.toml**:
  - `[tool.ruff]`: line-length = 100, target-version = "py311"
  - `[tool.ruff.lint]`: select = ["E", "F", "I", "W"], ignore = ["E501"] (handled by formatter)
  - `[tool.ruff.format]`: quote-style = "double"
  - `[tool.pytest.ini_options]`: asyncio_mode = "auto", testpaths = ["tests"]
  - `[tool.coverage.run]`: source = ["src"], omit = ["tests/*"]

### 2.2 `.gitignore`

Standard Python gitignore plus:
- `.env` (secrets)
- `data/` (large data files, ~17GB)
- Docker volumes
- IDE files
- Ollama models
- `__pycache__`, `.pytest_cache`, `.ruff_cache`
- `*.egg-info`, `dist/`, `build/`
- `.coverage`, `htmlcov/`

### 2.3 `.env.example`

Template with all required environment variables (no real values):
- Chinese LLM API keys (DeepSeek, Qwen, Kimi, Groq, Google)
- Indian govt API keys (Bhuvan, NASA FIRMS, data.gov.in)
- Bhashini translation keys
- Ollama host URL
- Database passwords (with dev defaults)
- Langfuse secrets

### 2.4 Python Package Structure

- `src/__init__.py` (empty, makes src a package)
- `src/{agents,routing,protocols,protocols/a2a,protocols/mcp,benchmark,benchmark/metrics,data,data/ingest,data/synthetic,data/processing,caching,api,api/routes,shared}/__init__.py`
- `tests/__init__.py`
- `tests/unit/__init__.py`
- `tests/integration/__init__.py`
- `tests/conftest.py` (shared fixtures placeholder)

### 2.5 Validation Criteria

- `uv sync` completes without errors
- `uv run python -c "import src"` succeeds
- `uv run pytest` runs (0 tests collected, no errors)
- `uv run ruff check src/ tests/` returns clean
- `uv run ruff format --check src/ tests/` returns clean
- `.env.example` contains all variables referenced in design.md
- No real API keys or secrets in any file

## 3. TDD Notes

### Tests to Write First

1. **test_project_structure.py**: Verify all expected directories and `__init__.py` files exist
2. **test_pyproject_config.py**: Parse `pyproject.toml`, verify key dependencies present, ruff config correct, pytest config correct
3. **test_env_example.py**: Verify `.env.example` contains all required variable names
4. **test_gitignore.py**: Verify `.gitignore` contains critical patterns (.env, data/, __pycache__)

### What NOT to Test

- Actual package imports (dependencies may not be installed in CI without Docker)
- Network connectivity to LLM providers
- Docker services
