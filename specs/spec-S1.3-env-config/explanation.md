# Spec S1.3: Environment Configuration — Explanation

## Why This Spec Exists

Every module in CRISIS-BENCH needs configuration: database URLs, API keys, model names, timeouts. Without a centralized config module, you'd see `os.getenv("POSTGRES_HOST", "localhost")` scattered across dozens of files — untestable, untyped, and guaranteed to cause 3am bugs when someone misspells an env var name.

Pydantic Settings solves this by validating all configuration **at import time**. If `POSTGRES_PORT` is set to "not_a_number" or `LOG_LEVEL` is "TRACE" (not a valid Python log level), the app crashes immediately with a clear error — not when the first database query fires 10 minutes into a benchmark run.

## What It Does

`src/shared/config.py` provides:

1. **`CrisisSettings`** — A Pydantic `BaseSettings` subclass with ~40 typed fields covering:
   - 5 LLM API keys (DeepSeek, Qwen, Kimi, Groq, Google) — all default to `""` so the system works without any paid APIs
   - 5 LLM base URLs with provider-specific defaults
   - 8 LLM model name fields with defaults
   - 3 Indian government API keys (Bhuvan, FIRMS, data.gov.in)
   - 3 Bhashini translation credentials
   - Database connection params (PostgreSQL, Redis, Neo4j, ChromaDB, Langfuse)
   - Application settings (log level, environment, budget limits, agent timeouts)

2. **Computed properties**:
   - `postgres_dsn` → `postgresql+asyncpg://user:pass@host:port/db`
   - `redis_url` → `redis://host:port/db`

3. **`get_settings()`** — `@lru_cache` singleton so the config is parsed once and reused everywhere.

4. **Validation rules**:
   - Ports must be 1-65535
   - `LOG_LEVEL` must be one of DEBUG/INFO/WARNING/ERROR/CRITICAL (via `Literal` type)
   - `ENVIRONMENT` must be development/staging/production
   - Budget, timeout, and delegation depth must be positive

## How It Works

```python
from src.shared.config import get_settings

settings = get_settings()
# Type-safe, IDE-autocomplete access:
dsn = settings.postgres_dsn          # "postgresql+asyncpg://crisis:crisis_dev@localhost:5432/crisis_bench"
model = settings.DEEPSEEK_CHAT_MODEL # "deepseek-chat"
```

Pydantic Settings reads values in this priority order:
1. Constructor arguments (used in tests)
2. Environment variables
3. `.env` file
4. Field defaults

## How It Connects

- **Upstream**: Depends on S1.1 (project structure, `.env.example`)
- **Downstream**: Nearly everything depends on this — S2.1 (domain models), S2.2 (DB connection), S2.3 (Redis), S2.5 (telemetry), S2.6 (LLM Router), S3.1 (API gateway), S4.4 (MCP base), S6.1 (ChromaDB), S6.3 (Neo4j)
- This is the **most depended-upon spec** in the entire project — 15+ specs list S1.3 as a dependency

## Interview Talking Points

- **Why `Literal` types instead of `@field_validator`?** — Literal types are declarative and self-documenting. The valid values are in the type annotation, not hidden in a validator function. Pydantic generates clear error messages automatically.
- **Why `@computed_field` instead of `@property`?** — `@computed_field` makes the DSN visible in `.model_dump()` and JSON serialization, useful for debugging and health check endpoints.
- **Why `@lru_cache` singleton?** — Config should be parsed once. Without caching, every `get_settings()` call would re-read the `.env` file and re-validate. The cache ensures O(1) access after first call.
- **Why all API keys default to `""`?** — The system must work on free tiers only. If DeepSeek key is empty, the LLM Router (S2.6) skips it and falls through to Groq free → Ollama local. Zero-config local development is a hard requirement.
