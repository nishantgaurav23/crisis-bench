"""Pydantic Settings environment configuration for CRISIS-BENCH.

Single source of truth for all configuration. Reads from .env file or
environment variables. Fails fast at import time if config is invalid.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings


class CrisisSettings(BaseSettings):
    """Typed, validated configuration for the entire CRISIS-BENCH system."""

    # --- LLM API Keys (all optional — system works on free tiers + Ollama) ---
    DEEPSEEK_API_KEY: str = ""
    QWEN_API_KEY: str = ""
    KIMI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""

    # --- LLM API Base URLs ---
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    QWEN_BASE_URL: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    KIMI_BASE_URL: str = "https://api.moonshot.cn/v1"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GOOGLE_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    # --- LLM Model Names ---
    DEEPSEEK_REASONER_MODEL: str = "deepseek-reasoner"
    DEEPSEEK_CHAT_MODEL: str = "deepseek-chat"
    QWEN_FLASH_MODEL: str = "qwen-plus"
    QWEN_VL_MODEL: str = "qwen-vl-plus"
    GROQ_MODEL: str = "llama-3.1-70b-versatile"
    GOOGLE_MODEL: str = "gemini-2.0-flash"
    OLLAMA_MODEL: str = "qwen2.5:7b"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"

    # --- Indian Government APIs ---
    BHUVAN_TOKEN: str = ""
    NASA_FIRMS_KEY: str = ""
    DATA_GOV_IN_KEY: str = ""

    # --- Bhashini Translation ---
    BHASHINI_USER_ID: str = ""
    BHASHINI_ULCA_API_KEY: str = ""
    BHASHINI_INFERENCE_API_KEY: str = ""

    # --- Ollama ---
    OLLAMA_HOST: str = "http://localhost:11434"

    # --- PostgreSQL/PostGIS ---
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = Field(default=5432, gt=0, le=65535)
    POSTGRES_USER: str = "crisis"
    POSTGRES_PASSWORD: str = "crisis_dev"
    POSTGRES_DB: str = "crisis_bench"

    # --- Redis ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = Field(default=6379, gt=0, le=65535)
    REDIS_DB: int = 0

    # --- Neo4j ---
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "crisis_dev"

    # --- ChromaDB ---
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = Field(default=8100, gt=0, le=65535)

    # --- Langfuse ---
    LANGFUSE_HOST: str = "http://localhost:4000"
    LANGFUSE_SECRET: str = "crisis-bench-dev"
    LANGFUSE_SALT: str = "crisis-bench-salt"

    # --- Application Settings ---
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = Field(default=8000, gt=0, le=65535)
    BUDGET_LIMIT_PER_SCENARIO: float = Field(default=0.05, gt=0)
    AGENT_TIMEOUT_SECONDS: int = Field(default=120, gt=0)
    AGENT_MAX_DELEGATION_DEPTH: int = Field(default=5, gt=0)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def postgres_dsn(self) -> str:
        """Async PostgreSQL connection string."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redis_url(self) -> str:
        """Redis connection URL."""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


@lru_cache
def get_settings() -> CrisisSettings:
    """Return cached CrisisSettings singleton."""
    return CrisisSettings()
