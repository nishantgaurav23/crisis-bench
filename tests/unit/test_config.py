"""Tests for src/shared/config.py — Pydantic Settings environment configuration.

TDD Red Phase: All tests written before implementation.
"""

import pytest
from pydantic import ValidationError


class TestCrisisSettingsDefaults:
    """Test that all settings have sensible defaults for local development."""

    def test_default_settings_load(self):
        """CrisisSettings loads with all defaults when no env vars are set."""
        from src.shared.config import CrisisSettings

        # Clear any env vars that might interfere, disable .env file loading
        settings = CrisisSettings(_env_file=None)
        assert settings is not None

    def test_api_keys_default_empty(self):
        """All API keys default to empty string — system works without them."""
        from src.shared.config import CrisisSettings

        settings = CrisisSettings(_env_file=None)
        assert settings.DEEPSEEK_API_KEY == ""
        assert settings.QWEN_API_KEY == ""
        assert settings.KIMI_API_KEY == ""
        assert settings.GROQ_API_KEY == ""
        assert settings.GOOGLE_API_KEY == ""
        assert settings.BHUVAN_TOKEN == ""
        assert settings.NASA_FIRMS_KEY == ""
        assert settings.DATA_GOV_IN_KEY == ""
        assert settings.BHASHINI_USER_ID == ""
        assert settings.BHASHINI_ULCA_API_KEY == ""
        assert settings.BHASHINI_INFERENCE_API_KEY == ""

    def test_ollama_host_default(self):
        """Ollama host defaults to localhost:11434."""
        from src.shared.config import CrisisSettings

        settings = CrisisSettings(_env_file=None)
        assert settings.OLLAMA_HOST == "http://localhost:11434"

    def test_all_llm_base_urls_have_defaults(self):
        """All LLM provider base URLs have sensible defaults."""
        from src.shared.config import CrisisSettings

        settings = CrisisSettings(_env_file=None)
        assert "deepseek" in settings.DEEPSEEK_BASE_URL.lower()
        assert settings.QWEN_BASE_URL != ""
        assert settings.KIMI_BASE_URL != ""
        assert settings.GROQ_BASE_URL != ""
        assert settings.GOOGLE_BASE_URL != ""

    def test_all_model_names_have_defaults(self):
        """All LLM model name fields have defaults."""
        from src.shared.config import CrisisSettings

        settings = CrisisSettings(_env_file=None)
        assert settings.DEEPSEEK_REASONER_MODEL != ""
        assert settings.DEEPSEEK_CHAT_MODEL != ""
        assert settings.QWEN_FLASH_MODEL != ""
        assert settings.QWEN_VL_MODEL != ""
        assert settings.GROQ_MODEL != ""
        assert settings.GOOGLE_MODEL != ""
        assert settings.OLLAMA_MODEL != ""
        assert settings.OLLAMA_EMBED_MODEL != ""

    def test_database_defaults(self):
        """Database settings have local development defaults."""
        from src.shared.config import CrisisSettings

        settings = CrisisSettings(_env_file=None)
        assert settings.POSTGRES_HOST == "localhost"
        assert settings.POSTGRES_PORT == 5432
        assert settings.POSTGRES_USER == "crisis"
        assert settings.POSTGRES_DB == "crisis_bench"
        assert settings.REDIS_HOST == "localhost"
        assert settings.REDIS_PORT == 6379
        assert settings.NEO4J_URI == "bolt://localhost:7687"
        assert settings.CHROMA_HOST == "localhost"
        assert settings.CHROMA_PORT == 8100

    def test_application_defaults(self):
        """Application settings have sensible defaults."""
        from src.shared.config import CrisisSettings

        settings = CrisisSettings(_env_file=None)
        assert settings.LOG_LEVEL == "INFO"
        assert settings.ENVIRONMENT == "development"
        assert settings.API_HOST == "0.0.0.0"
        assert settings.API_PORT == 8000
        assert settings.BUDGET_LIMIT_PER_SCENARIO == 0.05
        assert settings.AGENT_TIMEOUT_SECONDS == 120
        assert settings.AGENT_MAX_DELEGATION_DEPTH == 5


class TestComputedProperties:
    """Test computed DSN/URL properties."""

    def test_postgres_dsn_computed(self):
        """postgres_dsn returns correct asyncpg connection string."""
        from src.shared.config import CrisisSettings

        settings = CrisisSettings(_env_file=None)
        dsn = settings.postgres_dsn
        assert dsn == "postgresql+asyncpg://crisis:crisis_dev@localhost:5432/crisis_bench"

    def test_redis_url_computed(self):
        """redis_url returns correct Redis URL."""
        from src.shared.config import CrisisSettings

        settings = CrisisSettings(_env_file=None)
        url = settings.redis_url
        assert url == "redis://localhost:6379/0"

    def test_postgres_dsn_reflects_overrides(self):
        """postgres_dsn uses overridden values."""
        from src.shared.config import CrisisSettings

        settings = CrisisSettings(
            _env_file=None,
            POSTGRES_HOST="db.example.com",
            POSTGRES_PORT=5433,
            POSTGRES_USER="admin",
            POSTGRES_PASSWORD="secret",
            POSTGRES_DB="crisis_prod",
        )
        assert settings.postgres_dsn == (
            "postgresql+asyncpg://admin:secret@db.example.com:5433/crisis_prod"
        )

    def test_redis_url_reflects_overrides(self):
        """redis_url uses overridden values."""
        from src.shared.config import CrisisSettings

        settings = CrisisSettings(
            _env_file=None,
            REDIS_HOST="redis.example.com",
            REDIS_PORT=6380,
            REDIS_DB=2,
        )
        assert settings.redis_url == "redis://redis.example.com:6380/2"


class TestEnvOverride:
    """Test that environment variables override defaults."""

    def test_env_override_postgres_port(self):
        """Setting POSTGRES_PORT via env overrides the default."""
        from src.shared.config import CrisisSettings

        settings = CrisisSettings(_env_file=None, POSTGRES_PORT=5433)
        assert settings.POSTGRES_PORT == 5433

    def test_env_override_log_level(self):
        """Setting LOG_LEVEL via env overrides the default."""
        from src.shared.config import CrisisSettings

        settings = CrisisSettings(_env_file=None, LOG_LEVEL="DEBUG")
        assert settings.LOG_LEVEL == "DEBUG"


class TestValidation:
    """Test validation rules reject invalid values."""

    def test_invalid_log_level_rejected(self):
        """LOG_LEVEL=TRACE should raise ValidationError."""
        from src.shared.config import CrisisSettings

        with pytest.raises(ValidationError):
            CrisisSettings(_env_file=None, LOG_LEVEL="TRACE")

    def test_invalid_environment_rejected(self):
        """ENVIRONMENT=prod (not 'production') should raise ValidationError."""
        from src.shared.config import CrisisSettings

        with pytest.raises(ValidationError):
            CrisisSettings(_env_file=None, ENVIRONMENT="prod")

    def test_invalid_port_rejected(self):
        """POSTGRES_PORT=99999 (out of range) should raise ValidationError."""
        from src.shared.config import CrisisSettings

        with pytest.raises(ValidationError):
            CrisisSettings(_env_file=None, POSTGRES_PORT=99999)

    def test_invalid_redis_port_rejected(self):
        """REDIS_PORT=0 should raise ValidationError."""
        from src.shared.config import CrisisSettings

        with pytest.raises(ValidationError):
            CrisisSettings(_env_file=None, REDIS_PORT=0)

    def test_budget_must_be_positive(self):
        """BUDGET_LIMIT_PER_SCENARIO=-1 should raise ValidationError."""
        from src.shared.config import CrisisSettings

        with pytest.raises(ValidationError):
            CrisisSettings(_env_file=None, BUDGET_LIMIT_PER_SCENARIO=-1)

    def test_timeout_must_be_positive(self):
        """AGENT_TIMEOUT_SECONDS=0 should raise ValidationError."""
        from src.shared.config import CrisisSettings

        with pytest.raises(ValidationError):
            CrisisSettings(_env_file=None, AGENT_TIMEOUT_SECONDS=0)

    def test_delegation_depth_must_be_positive(self):
        """AGENT_MAX_DELEGATION_DEPTH=0 should raise ValidationError."""
        from src.shared.config import CrisisSettings

        with pytest.raises(ValidationError):
            CrisisSettings(_env_file=None, AGENT_MAX_DELEGATION_DEPTH=0)


class TestSingleton:
    """Test get_settings() caching behavior."""

    def test_get_settings_returns_instance(self):
        """get_settings() returns a CrisisSettings instance."""
        from src.shared.config import CrisisSettings, get_settings

        settings = get_settings()
        assert isinstance(settings, CrisisSettings)

    def test_get_settings_singleton(self):
        """get_settings() returns the same instance on repeated calls."""
        from src.shared.config import get_settings

        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
