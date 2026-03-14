# Spec S1.3: Pydantic Settings Environment Configuration

**Phase**: 1 — Project Bootstrap
**Status**: spec-written
**Depends On**: S1.1 (project structure, `.env.example`)
**Outputs**: `src/shared/config.py`

---

## 1. Purpose

Provide a single, type-safe, validated configuration module for the entire CRISIS-BENCH system. All environment variables defined in `.env.example` are read, validated, and exposed as typed Python attributes via `pydantic-settings`. If any required config is missing or malformed, the application fails fast at import time with a clear error — not at 3am when a connection first fires.

### Interview Context

**Q: Why Pydantic Settings instead of `os.getenv()` calls everywhere?**
A: Type safety + validation at startup. If `REDIS_URL` is missing or `POSTGRES_PORT` is not an integer, Pydantic fails fast at import time with a clear error. It also provides IDE autocomplete and a single source of truth for all config.

---

## 2. Requirements

### 2.1 Settings Class (`CrisisSettings`)

A single `pydantic_settings.BaseSettings` subclass with nested grouping via inner classes or flat attributes:

#### LLM API Keys (all optional — system works on free tiers + Ollama)
- `DEEPSEEK_API_KEY: str = ""` — DeepSeek V3.2 (critical + standard tier)
- `QWEN_API_KEY: str = ""` — Qwen3.5-Flash (routine tier)
- `KIMI_API_KEY: str = ""` — Kimi K2.5 (fallback for critical tier)
- `GROQ_API_KEY: str = ""` — Groq free tier (overflow)
- `GOOGLE_API_KEY: str = ""` — Gemini 2.0 Flash (free overflow 2)

#### LLM API Base URLs (with sensible defaults)
- `DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"`
- `QWEN_BASE_URL: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"`
- `KIMI_BASE_URL: str = "https://api.moonshot.cn/v1"`
- `GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"`
- `GOOGLE_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"`

#### LLM Model Names (with defaults, overridable)
- `DEEPSEEK_REASONER_MODEL: str = "deepseek-reasoner"`
- `DEEPSEEK_CHAT_MODEL: str = "deepseek-chat"`
- `QWEN_FLASH_MODEL: str = "qwen-plus"`
- `QWEN_VL_MODEL: str = "qwen-vl-plus"`
- `GROQ_MODEL: str = "llama-3.1-70b-versatile"`
- `GOOGLE_MODEL: str = "gemini-2.0-flash"`
- `OLLAMA_MODEL: str = "qwen2.5:7b"`
- `OLLAMA_EMBED_MODEL: str = "nomic-embed-text"`

#### Indian Government APIs
- `BHUVAN_TOKEN: str = ""` — ISRO Bhuvan (free registration)
- `NASA_FIRMS_KEY: str = ""` — NASA FIRMS fire data (free API key)
- `DATA_GOV_IN_KEY: str = ""` — data.gov.in API key

#### Bhashini Translation
- `BHASHINI_USER_ID: str = ""`
- `BHASHINI_ULCA_API_KEY: str = ""`
- `BHASHINI_INFERENCE_API_KEY: str = ""`

#### Ollama
- `OLLAMA_HOST: str = "http://localhost:11434"`

#### Database Configuration
- `POSTGRES_HOST: str = "localhost"`
- `POSTGRES_PORT: int = 5432`
- `POSTGRES_USER: str = "crisis"`
- `POSTGRES_PASSWORD: str = "crisis_dev"`
- `POSTGRES_DB: str = "crisis_bench"`

#### Redis
- `REDIS_HOST: str = "localhost"`
- `REDIS_PORT: int = 6379`
- `REDIS_DB: int = 0`

#### Neo4j
- `NEO4J_URI: str = "bolt://localhost:7687"`
- `NEO4J_USER: str = "neo4j"`
- `NEO4J_PASSWORD: str = "crisis_dev"`

#### ChromaDB
- `CHROMA_HOST: str = "localhost"`
- `CHROMA_PORT: int = 8100`

#### Langfuse
- `LANGFUSE_HOST: str = "http://localhost:4000"`
- `LANGFUSE_SECRET: str = "crisis-bench-dev"`
- `LANGFUSE_SALT: str = "crisis-bench-salt"`

#### Application Settings
- `LOG_LEVEL: str = "INFO"` — validated to be one of DEBUG/INFO/WARNING/ERROR/CRITICAL
- `ENVIRONMENT: str = "development"` — one of development/staging/production
- `API_HOST: str = "0.0.0.0"`
- `API_PORT: int = 8000`
- `BUDGET_LIMIT_PER_SCENARIO: float = 0.05` — max $ per benchmark scenario
- `AGENT_TIMEOUT_SECONDS: int = 120` — global agent task timeout
- `AGENT_MAX_DELEGATION_DEPTH: int = 5` — loop prevention depth limit

### 2.2 Computed Properties

- `postgres_dsn` → `postgresql+asyncpg://user:pass@host:port/db`
- `redis_url` → `redis://host:port/db`

### 2.3 Settings Singleton

- `get_settings() -> CrisisSettings` — cached singleton (using `@lru_cache`)
- Loads from `.env` file if present, else from environment variables
- `model_config` with `env_file=".env"`, `env_file_encoding="utf-8"`, `case_sensitive=True`

### 2.4 Validation Rules

- `POSTGRES_PORT` and `REDIS_PORT` must be valid port numbers (1-65535)
- `LOG_LEVEL` must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL
- `ENVIRONMENT` must be one of: development, staging, production
- `BUDGET_LIMIT_PER_SCENARIO` must be > 0
- `AGENT_TIMEOUT_SECONDS` must be > 0
- `AGENT_MAX_DELEGATION_DEPTH` must be > 0

---

## 3. TDD Plan

### Test File: `tests/unit/test_config.py`

#### Red Phase — Tests to write first:

1. **test_default_settings_load** — CrisisSettings loads with all defaults when no env vars set
2. **test_postgres_dsn_computed** — `postgres_dsn` returns correct connection string
3. **test_redis_url_computed** — `redis_url` returns correct URL
4. **test_env_override** — Setting `POSTGRES_PORT=5433` via env overrides default
5. **test_invalid_log_level_rejected** — `LOG_LEVEL=TRACE` raises ValidationError
6. **test_invalid_environment_rejected** — `ENVIRONMENT=prod` raises ValidationError
7. **test_invalid_port_rejected** — `POSTGRES_PORT=99999` raises ValidationError
8. **test_budget_must_be_positive** — `BUDGET_LIMIT_PER_SCENARIO=-1` raises ValidationError
9. **test_timeout_must_be_positive** — `AGENT_TIMEOUT_SECONDS=0` raises ValidationError
10. **test_get_settings_singleton** — `get_settings()` returns same instance on repeated calls
11. **test_api_keys_default_empty** — All API keys default to empty string (system works without them)
12. **test_ollama_host_default** — Defaults to `http://localhost:11434`
13. **test_all_llm_base_urls_have_defaults** — All base URLs have sensible defaults
14. **test_all_model_names_have_defaults** — All model name fields have defaults

---

## 4. Outcomes

- [ ] `src/shared/config.py` exists with `CrisisSettings` class
- [ ] All 14+ tests pass
- [ ] `ruff check` and `ruff format --check` pass
- [ ] No hardcoded secrets — all config via env vars with safe defaults
- [ ] System can start with zero env vars set (all defaults work for local dev)
- [ ] Computed properties return correct DSN/URL strings
