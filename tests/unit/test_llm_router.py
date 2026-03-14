"""Tests for LLM Router — 5-tier multi-provider routing.

Tests cover: initialization, tier routing, failover, rate limiting,
circuit breaker, cost tracking, Prometheus metrics, timeout handling.
All external LLM APIs are mocked — no real calls.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.routing.llm_router import (
    CircuitBreaker,
    CircuitState,
    LLMProvider,
    LLMResponse,
    LLMRouter,
    LLMTier,
    SlidingWindowRateLimiter,
)
from src.shared.config import CrisisSettings
from src.shared.errors import AllProvidersFailedError

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def settings() -> CrisisSettings:
    """CrisisSettings with test values (no real API keys)."""
    return CrisisSettings(
        DEEPSEEK_API_KEY="test-deepseek-key",
        QWEN_API_KEY="test-qwen-key",
        KIMI_API_KEY="test-kimi-key",
        GROQ_API_KEY="test-groq-key",
        GOOGLE_API_KEY="test-google-key",
        OLLAMA_HOST="http://localhost:11434",
        _env_file=None,
    )


@pytest.fixture
def settings_no_keys() -> CrisisSettings:
    """CrisisSettings with no API keys — only Ollama should work."""
    return CrisisSettings(
        DEEPSEEK_API_KEY="",
        QWEN_API_KEY="",
        KIMI_API_KEY="",
        GROQ_API_KEY="",
        GOOGLE_API_KEY="",
        _env_file=None,
    )


def _mock_completion(content: str = "test response", input_tokens: int = 10, output_tokens: int = 5):
    """Create a mock OpenAI ChatCompletion response."""
    mock = MagicMock()
    mock.choices = [MagicMock()]
    mock.choices[0].message.content = content
    mock.usage.prompt_tokens = input_tokens
    mock.usage.completion_tokens = output_tokens
    return mock


@pytest.fixture
def router(settings: CrisisSettings) -> LLMRouter:
    """LLMRouter with mocked AsyncOpenAI clients."""
    r = LLMRouter(settings)
    # Mock all provider clients
    for provider in r._providers.values():
        provider.client = MagicMock()
        provider.client.chat.completions.create = AsyncMock(
            return_value=_mock_completion()
        )
    return r


# =============================================================================
# Data Model Tests
# =============================================================================


class TestLLMTier:
    def test_tier_values(self):
        assert LLMTier.CRITICAL == "critical"
        assert LLMTier.STANDARD == "standard"
        assert LLMTier.ROUTINE == "routine"
        assert LLMTier.VISION == "vision"

    def test_tier_from_string(self):
        assert LLMTier("critical") == LLMTier.CRITICAL
        assert LLMTier("routine") == LLMTier.ROUTINE


class TestLLMResponse:
    def test_response_fields(self):
        resp = LLMResponse(
            content="hello",
            provider="DeepSeek Reasoner",
            model="deepseek-reasoner",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.00016,
            latency_s=1.5,
            tier="critical",
        )
        assert resp.content == "hello"
        assert resp.provider == "DeepSeek Reasoner"
        assert resp.cost_usd == pytest.approx(0.00016)
        assert resp.tier == "critical"


class TestLLMProvider:
    def test_provider_fields(self):
        provider = LLMProvider(
            name="Test",
            key="test",
            client=MagicMock(),
            model="test-model",
            input_cost_per_m=0.50,
            output_cost_per_m=2.18,
            max_rpm=60,
            is_free=False,
        )
        assert provider.name == "Test"
        assert provider.max_rpm == 60
        assert not provider.is_free


# =============================================================================
# SlidingWindowRateLimiter Tests
# =============================================================================


class TestSlidingWindowRateLimiter:
    def test_allows_within_limit(self):
        limiter = SlidingWindowRateLimiter(max_rpm=5)
        for _ in range(5):
            assert limiter.allow()

    def test_blocks_over_limit(self):
        limiter = SlidingWindowRateLimiter(max_rpm=2)
        assert limiter.allow()
        assert limiter.allow()
        assert not limiter.allow()

    def test_window_expires(self):
        limiter = SlidingWindowRateLimiter(max_rpm=1)
        assert limiter.allow()
        assert not limiter.allow()
        # Simulate time passing by clearing timestamps
        limiter._timestamps.clear()
        assert limiter.allow()

    def test_remaining_capacity(self):
        limiter = SlidingWindowRateLimiter(max_rpm=5)
        assert limiter.remaining() == 5
        limiter.allow()
        assert limiter.remaining() == 4


# =============================================================================
# CircuitBreaker Tests
# =============================================================================


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        assert cb.state == CircuitState.CLOSED

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_open_rejects_calls(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        for _ in range(3):
            cb.record_failure()
        assert not cb.allow_request()

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.allow_request()  # Should allow one test request
        assert cb.state == CircuitState.HALF_OPEN

    def test_success_closes_from_half_open(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)
        for _ in range(3):
            cb.record_failure()
        time.sleep(0.15)
        cb.allow_request()  # Transition to half-open
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_failure_in_half_open_reopens(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)
        for _ in range(3):
            cb.record_failure()
        time.sleep(0.15)
        cb.allow_request()  # half-open
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb._failure_count == 0
        assert cb.state == CircuitState.CLOSED


# =============================================================================
# LLMRouter Initialization Tests
# =============================================================================


class TestLLMRouterInit:
    def test_creates_all_providers(self, settings: CrisisSettings):
        router = LLMRouter(settings)
        expected = {
            "deepseek_reasoner", "deepseek_chat",
            "qwen_flash", "qwen_vl",
            "kimi",
            "groq_free", "gemini_free",
            "ollama_local",
        }
        assert set(router._providers.keys()) == expected

    def test_tier_chains_defined(self, settings: CrisisSettings):
        router = LLMRouter(settings)
        assert "critical" in router._tier_chains
        assert "standard" in router._tier_chains
        assert "routine" in router._tier_chains
        assert "vision" in router._tier_chains

    def test_critical_chain_order(self, settings: CrisisSettings):
        router = LLMRouter(settings)
        assert router._tier_chains["critical"] == [
            "deepseek_reasoner", "kimi", "groq_free", "ollama_local",
        ]

    def test_standard_chain_order(self, settings: CrisisSettings):
        router = LLMRouter(settings)
        assert router._tier_chains["standard"] == [
            "deepseek_chat", "qwen_flash", "groq_free", "ollama_local",
        ]

    def test_routine_chain_order(self, settings: CrisisSettings):
        router = LLMRouter(settings)
        assert router._tier_chains["routine"] == [
            "qwen_flash", "groq_free", "gemini_free", "ollama_local",
        ]

    def test_vision_chain_order(self, settings: CrisisSettings):
        router = LLMRouter(settings)
        assert router._tier_chains["vision"] == [
            "qwen_vl", "ollama_local",
        ]

    def test_no_keys_still_has_ollama(self, settings_no_keys: CrisisSettings):
        router = LLMRouter(settings_no_keys)
        assert "ollama_local" in router._providers
        # Providers with empty keys should be marked as unavailable
        assert not router._providers["deepseek_reasoner"].has_key
        assert router._providers["ollama_local"].has_key


# =============================================================================
# LLMRouter.call() Tests
# =============================================================================


class TestLLMRouterCall:
    @pytest.mark.asyncio
    async def test_routes_to_primary_provider(self, router: LLMRouter):
        messages = [{"role": "user", "content": "hello"}]
        result = await router.call("critical", messages)
        assert isinstance(result, LLMResponse)
        assert result.content == "test response"
        # Primary for critical is deepseek_reasoner
        assert result.provider == "DeepSeek Reasoner"

    @pytest.mark.asyncio
    async def test_routes_routine_to_qwen(self, router: LLMRouter):
        messages = [{"role": "user", "content": "classify this"}]
        result = await router.call("routine", messages)
        assert result.provider == "Qwen Flash"

    @pytest.mark.asyncio
    async def test_accepts_tier_enum(self, router: LLMRouter):
        messages = [{"role": "user", "content": "test"}]
        result = await router.call(LLMTier.STANDARD, messages)
        assert result.provider == "DeepSeek Chat"

    @pytest.mark.asyncio
    async def test_failover_on_primary_failure(self, router: LLMRouter):
        messages = [{"role": "user", "content": "test"}]
        # Make deepseek_reasoner fail
        router._providers["deepseek_reasoner"].client.chat.completions.create = AsyncMock(
            side_effect=Exception("API down")
        )
        result = await router.call("critical", messages)
        # Should fall through to kimi
        assert result.provider == "Kimi K2.5"

    @pytest.mark.asyncio
    async def test_failover_chain_exhausted(self, router: LLMRouter):
        messages = [{"role": "user", "content": "test"}]
        # Make ALL providers in critical chain fail
        for key in ["deepseek_reasoner", "kimi", "groq_free", "ollama_local"]:
            router._providers[key].client.chat.completions.create = AsyncMock(
                side_effect=Exception("down")
            )
        with pytest.raises(AllProvidersFailedError):
            await router.call("critical", messages)

    @pytest.mark.asyncio
    async def test_skips_providers_with_no_key(self, settings_no_keys: CrisisSettings):
        router = LLMRouter(settings_no_keys)
        # Mock ollama client (the only one with a key)
        router._providers["ollama_local"].client = MagicMock()
        router._providers["ollama_local"].client.chat.completions.create = AsyncMock(
            return_value=_mock_completion()
        )
        messages = [{"role": "user", "content": "test"}]
        result = await router.call("critical", messages)
        assert result.provider == "Ollama Local"

    @pytest.mark.asyncio
    async def test_passes_max_tokens(self, router: LLMRouter):
        messages = [{"role": "user", "content": "test"}]
        await router.call("routine", messages, max_tokens=100)
        call_kwargs = (
            router._providers["qwen_flash"]
            .client.chat.completions.create.call_args
        )
        assert call_kwargs.kwargs.get("max_tokens") == 100

    @pytest.mark.asyncio
    async def test_passes_temperature(self, router: LLMRouter):
        messages = [{"role": "user", "content": "test"}]
        await router.call("routine", messages, temperature=0.7)
        call_kwargs = (
            router._providers["qwen_flash"]
            .client.chat.completions.create.call_args
        )
        assert call_kwargs.kwargs.get("temperature") == 0.7

    @pytest.mark.asyncio
    async def test_timeout_triggers_failover(self, router: LLMRouter):
        messages = [{"role": "user", "content": "test"}]

        async def slow_call(**kwargs):
            await asyncio.sleep(5)

        router._providers["deepseek_reasoner"].client.chat.completions.create = AsyncMock(
            side_effect=slow_call
        )
        result = await router.call("critical", messages, timeout=0.1)
        # Should failover to kimi
        assert result.provider == "Kimi K2.5"

    @pytest.mark.asyncio
    async def test_invalid_tier_uses_standard(self, router: LLMRouter):
        messages = [{"role": "user", "content": "test"}]
        result = await router.call("nonexistent", messages)
        # Should fall back to standard chain
        assert result.provider == "DeepSeek Chat"


# =============================================================================
# Rate Limiter Integration Tests
# =============================================================================


class TestRateLimiterIntegration:
    @pytest.mark.asyncio
    async def test_rate_limited_provider_skipped(self, router: LLMRouter):
        messages = [{"role": "user", "content": "test"}]
        # Exhaust qwen_flash rate limiter
        qwen_limiter = router._rate_limiters["qwen_flash"]
        for _ in range(router._providers["qwen_flash"].max_rpm):
            qwen_limiter.allow()
        # Routine tier: qwen_flash should be skipped, groq_free used
        result = await router.call("routine", messages)
        assert result.provider != "Qwen Flash"


# =============================================================================
# Circuit Breaker Integration Tests
# =============================================================================


class TestCircuitBreakerIntegration:
    @pytest.mark.asyncio
    async def test_circuit_open_skips_provider(self, router: LLMRouter):
        messages = [{"role": "user", "content": "test"}]
        # Open the circuit breaker for deepseek_reasoner
        cb = router._circuit_breakers["deepseek_reasoner"]
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

        result = await router.call("critical", messages)
        # Should skip deepseek_reasoner (circuit open) → use kimi
        assert result.provider == "Kimi K2.5"


# =============================================================================
# Cost Tracking Tests
# =============================================================================


class TestCostTracking:
    @pytest.mark.asyncio
    async def test_cost_calculated_correctly(self, router: LLMRouter):
        messages = [{"role": "user", "content": "test"}]
        # deepseek_reasoner: input=0.50/M, output=2.18/M
        router._providers["deepseek_reasoner"].client.chat.completions.create = AsyncMock(
            return_value=_mock_completion(input_tokens=1000, output_tokens=500)
        )
        result = await router.call("critical", messages)
        expected_cost = (1000 / 1_000_000 * 0.50) + (500 / 1_000_000 * 2.18)
        assert result.cost_usd == pytest.approx(expected_cost)

    @pytest.mark.asyncio
    async def test_free_provider_zero_cost(self, router: LLMRouter):
        messages = [{"role": "user", "content": "test"}]
        # Force to use groq_free
        for key in ["qwen_flash"]:
            router._providers[key].client.chat.completions.create = AsyncMock(
                side_effect=Exception("down")
            )
        result = await router.call("routine", messages)
        assert result.provider == "Groq (Free)"
        assert result.cost_usd == pytest.approx(0.0)


# =============================================================================
# Prometheus Metrics Tests
# =============================================================================


class TestPrometheusMetrics:
    @pytest.mark.asyncio
    async def test_request_counter_incremented(self, router: LLMRouter):
        from src.shared.telemetry import LLM_REQUESTS

        messages = [{"role": "user", "content": "test"}]
        before = LLM_REQUESTS.labels(
            provider="DeepSeek Reasoner", tier="critical", status="success"
        )._value.get()
        await router.call("critical", messages)
        after = LLM_REQUESTS.labels(
            provider="DeepSeek Reasoner", tier="critical", status="success"
        )._value.get()
        assert after == before + 1

    @pytest.mark.asyncio
    async def test_token_counters_incremented(self, router: LLMRouter):
        from src.shared.telemetry import LLM_TOKENS

        messages = [{"role": "user", "content": "test"}]
        router._providers["deepseek_reasoner"].client.chat.completions.create = AsyncMock(
            return_value=_mock_completion(input_tokens=100, output_tokens=50)
        )
        before_in = LLM_TOKENS.labels(
            provider="DeepSeek Reasoner", tier="critical", direction="input"
        )._value.get()
        await router.call("critical", messages)
        after_in = LLM_TOKENS.labels(
            provider="DeepSeek Reasoner", tier="critical", direction="input"
        )._value.get()
        assert after_in == before_in + 100


# =============================================================================
# Provider Status Tests
# =============================================================================


class TestProviderStatus:
    def test_get_provider_status(self, router: LLMRouter):
        status = router.get_provider_status()
        assert "deepseek_reasoner" in status
        assert "circuit_state" in status["deepseek_reasoner"]
        assert "rate_limit_remaining" in status["deepseek_reasoner"]
        assert "has_key" in status["deepseek_reasoner"]

    def test_status_reflects_circuit_state(self, router: LLMRouter):
        cb = router._circuit_breakers["deepseek_reasoner"]
        for _ in range(3):
            cb.record_failure()
        status = router.get_provider_status()
        assert status["deepseek_reasoner"]["circuit_state"] == "open"
