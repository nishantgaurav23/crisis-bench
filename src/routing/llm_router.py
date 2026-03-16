"""LLM Router — 5-tier multi-provider routing with automatic failover.

Routes all LLM calls through a unified interface. Every agent calls
`router.call(tier, messages)` — the router handles provider selection,
failover, rate limiting, circuit breaking, cost tracking, and observability.

Usage:
    from src.shared.config import get_settings
    from src.routing.llm_router import LLMRouter

    router = LLMRouter(get_settings())
    result = await router.call("critical", [{"role": "user", "content": "..."}])
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from openai import AsyncOpenAI

from src.shared.config import CrisisSettings
from src.shared.errors import AllProvidersFailedError
from src.shared.telemetry import (
    LLM_COST,
    LLM_LATENCY,
    LLM_REQUESTS,
    LLM_TOKENS,
    LangfuseTracer,
    get_logger,
)

logger = get_logger("llm_router")


# =============================================================================
# Enums & Data Models
# =============================================================================


class LLMTier(str, Enum):
    """LLM routing tier — determines provider chain."""

    CRITICAL = "critical"
    STANDARD = "standard"
    ROUTINE = "routine"
    VISION = "vision"


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class LLMProvider:
    """Configuration for a single LLM provider."""

    name: str
    key: str
    client: AsyncOpenAI
    model: str
    input_cost_per_m: float
    output_cost_per_m: float
    max_rpm: int
    is_free: bool
    has_key: bool = True


@dataclass
class LLMResponse:
    """Result from an LLM call."""

    content: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_s: float
    tier: str


# =============================================================================
# Rate Limiter
# =============================================================================


class SlidingWindowRateLimiter:
    """Sliding-window rate limiter tracking requests per minute."""

    def __init__(self, max_rpm: int) -> None:
        self._max_rpm = max_rpm
        self._timestamps: deque[float] = deque()

    def _cleanup(self) -> None:
        now = time.monotonic()
        while self._timestamps and (now - self._timestamps[0]) > 60.0:
            self._timestamps.popleft()

    def allow(self) -> bool:
        """Return True if a request is allowed, False if rate-limited."""
        self._cleanup()
        if len(self._timestamps) >= self._max_rpm:
            return False
        self._timestamps.append(time.monotonic())
        return True

    def remaining(self) -> int:
        """Return remaining capacity in the current window."""
        self._cleanup()
        return max(0, self._max_rpm - len(self._timestamps))


# =============================================================================
# Circuit Breaker
# =============================================================================


@dataclass
class CircuitBreaker:
    """Circuit breaker to prevent cascading failures.

    After `failure_threshold` consecutive failures, opens the circuit for
    `recovery_timeout` seconds. Then allows one test request (half-open).
    """

    failure_threshold: int = 3
    recovery_timeout: float = 30.0
    state: CircuitState = field(default=CircuitState.CLOSED)
    _failure_count: int = field(default=0, repr=False)
    _last_failure_time: float = field(default=0.0, repr=False)

    def allow_request(self) -> bool:
        """Return True if a request should be attempted."""
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if (time.monotonic() - self._last_failure_time) >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        # HALF_OPEN — already allowed one test request
        return False

    def record_success(self) -> None:
        """Record a successful call — reset failure count, close circuit."""
        self._failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failed call — may open the circuit."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
        elif self._failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN


# =============================================================================
# LLM Router
# =============================================================================


class LLMRouter:
    """Routes LLM calls across providers based on tier with automatic failover."""

    def __init__(
        self,
        settings: CrisisSettings,
        tracer: LangfuseTracer | None = None,
    ) -> None:
        self._settings = settings
        self._tracer = tracer
        self._providers: dict[str, LLMProvider] = {}
        self._rate_limiters: dict[str, SlidingWindowRateLimiter] = {}
        self._circuit_breakers: dict[str, CircuitBreaker] = {}

        self._init_providers()
        self._tier_chains: dict[str, list[str]] = {
            "critical": ["deepseek_reasoner", "kimi", "gemini_free", "groq_free", "ollama_local"],
            "standard": ["deepseek_chat", "qwen_flash", "gemini_free", "groq_free", "ollama_local"],
            "routine": ["qwen_flash", "groq_free", "gemini_free", "ollama_local"],
            "vision": ["qwen_vl", "ollama_local"],
        }

    def _init_providers(self) -> None:
        """Initialize all providers from settings."""
        s = self._settings
        provider_defs = [
            ("deepseek_reasoner", "DeepSeek Reasoner", s.DEEPSEEK_BASE_URL,
             s.DEEPSEEK_API_KEY, s.DEEPSEEK_REASONER_MODEL, 0.50, 2.18, 60, False),
            ("deepseek_chat", "DeepSeek Chat", s.DEEPSEEK_BASE_URL,
             s.DEEPSEEK_API_KEY, s.DEEPSEEK_CHAT_MODEL, 0.28, 0.42, 60, False),
            ("qwen_flash", "Qwen Flash", s.QWEN_BASE_URL,
             s.QWEN_API_KEY, s.QWEN_FLASH_MODEL, 0.04, 0.40, 120, False),
            ("qwen_vl", "Qwen VL Flash", s.QWEN_BASE_URL,
             s.QWEN_API_KEY, s.QWEN_VL_MODEL, 0.10, 0.40, 60, False),
            ("kimi", "Kimi K2.5", s.KIMI_BASE_URL,
             s.KIMI_API_KEY, "kimi-k2.5", 0.45, 2.20, 30, False),
            ("groq_free", "Groq (Free)", s.GROQ_BASE_URL,
             s.GROQ_API_KEY, s.GROQ_MODEL, 0.0, 0.0, 30, True),
            ("gemini_free", "Gemini Flash (Free)", s.GOOGLE_BASE_URL,
             s.GOOGLE_API_KEY, s.GOOGLE_MODEL, 0.0, 0.0, 15, True),
            ("ollama_local", "Ollama Local", f"{s.OLLAMA_HOST}/v1",
             "ollama", s.OLLAMA_MODEL, 0.0, 0.0, 999, True),
        ]

        for (key, name, base_url, api_key, model,
             in_cost, out_cost, max_rpm, is_free) in provider_defs:
            has_key = bool(api_key) or key == "ollama_local"
            client = AsyncOpenAI(base_url=base_url, api_key=api_key or "none")
            provider = LLMProvider(
                name=name,
                key=key,
                client=client,
                model=model,
                input_cost_per_m=in_cost,
                output_cost_per_m=out_cost,
                max_rpm=max_rpm,
                is_free=is_free,
                has_key=has_key,
            )
            self._providers[key] = provider
            self._rate_limiters[key] = SlidingWindowRateLimiter(max_rpm)
            self._circuit_breakers[key] = CircuitBreaker()

    async def call(
        self,
        tier: str | LLMTier,
        messages: list[dict[str, str]],
        *,
        trace_id: str = "",
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout: float = 60.0,
        parent_handle: Any = None,
    ) -> LLMResponse:
        """Route an LLM call through the provider chain for the given tier.

        Tries each provider in the chain until one succeeds. Skips providers
        that are rate-limited, circuit-broken, or missing API keys.

        Raises:
            AllProvidersFailedError: When all providers in the chain fail.
        """
        tier_str = tier.value if isinstance(tier, LLMTier) else str(tier)
        chain = self._tier_chains.get(tier_str, self._tier_chains["standard"])
        errors: list[str] = []

        # For critical/standard tiers falling through to Gemini, add thinking
        # instructions so the model uses its built-in chain-of-thought
        _thinking_tiers = {"critical", "standard"}
        _thinking_providers = {"gemini_free"}

        for provider_key in chain:
            provider = self._providers[provider_key]

            # Skip providers without API keys
            if not provider.has_key:
                errors.append(f"{provider.name}: no API key")
                continue

            # Skip rate-limited providers
            if not self._rate_limiters[provider_key].allow():
                errors.append(f"{provider.name}: rate limited")
                continue

            # Skip circuit-broken providers
            cb = self._circuit_breakers[provider_key]
            if not cb.allow_request():
                errors.append(f"{provider.name}: circuit open")
                continue

            try:
                # Inject thinking instructions for critical/standard on weaker providers
                call_messages = messages
                call_max_tokens = max_tokens
                if (
                    tier_str in _thinking_tiers
                    and provider_key in _thinking_providers
                    and messages
                ):
                    thinking_prefix = (
                        "Think through this step-by-step before answering. "
                        "Consider multiple angles, potential risks, and "
                        "second-order consequences. Be thorough and specific."
                    )
                    # Prepend thinking instruction to the last user message
                    call_messages = list(messages)
                    for i in range(len(call_messages) - 1, -1, -1):
                        if call_messages[i].get("role") == "user":
                            call_messages[i] = {
                                **call_messages[i],
                                "content": (
                                    f"{thinking_prefix}\n\n"
                                    f"{call_messages[i]['content']}"
                                ),
                            }
                            break
                    # Allow more tokens for thinking
                    if call_max_tokens and call_max_tokens < 1024:
                        call_max_tokens = 1024

                result = await self._call_provider(
                    provider, tier_str, call_messages,
                    max_tokens=call_max_tokens,
                    temperature=temperature,
                    timeout=timeout,
                    trace_id=trace_id,
                )
                cb.record_success()

                # Log generation to Langfuse under parent handle
                if self._tracer is not None and parent_handle is not None:
                    self._tracer.log_generation(
                        parent_handle=parent_handle,
                        name=f"llm:{result.model}",
                        model=result.model,
                        messages=messages,
                        response=result.content,
                        tokens_in=result.input_tokens,
                        tokens_out=result.output_tokens,
                        cost=result.cost_usd,
                        latency_s=result.latency_s,
                        metadata={
                            "tier": tier_str,
                            "provider": result.provider,
                        },
                    )

                return result
            except Exception as e:
                cb.record_failure()
                errors.append(f"{provider.name}: {e}")
                logger.warning(
                    "provider_failed",
                    provider=provider.name,
                    tier=tier_str,
                    error=str(e),
                    trace_id=trace_id,
                )

        raise AllProvidersFailedError(
            f"All providers failed for tier '{tier_str}'",
            context={"tier": tier_str, "errors": errors, "trace_id": trace_id},
        )

    async def _call_provider(
        self,
        provider: LLMProvider,
        tier: str,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None,
        temperature: float | None,
        timeout: float,
        trace_id: str,
    ) -> LLMResponse:
        """Make an actual LLM call to a single provider."""
        kwargs: dict = {"model": provider.model, "messages": messages}
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if temperature is not None:
            kwargs["temperature"] = temperature

        start = time.monotonic()
        response = await asyncio.wait_for(
            provider.client.chat.completions.create(**kwargs),
            timeout=timeout,
        )
        latency = time.monotonic() - start

        usage = response.usage
        input_tokens = usage.prompt_tokens
        output_tokens = usage.completion_tokens
        cost = (
            input_tokens / 1_000_000 * provider.input_cost_per_m
            + output_tokens / 1_000_000 * provider.output_cost_per_m
        )

        # Prometheus metrics
        LLM_REQUESTS.labels(provider=provider.name, tier=tier, status="success").inc()
        LLM_TOKENS.labels(provider=provider.name, tier=tier, direction="input").inc(input_tokens)
        LLM_TOKENS.labels(provider=provider.name, tier=tier, direction="output").inc(output_tokens)
        LLM_LATENCY.labels(provider=provider.name, tier=tier).observe(latency)
        LLM_COST.labels(provider=provider.name, tier=tier).inc(cost)

        # Structured logging (never log response content)
        logger.info(
            "llm_call",
            provider=provider.name,
            model=provider.model,
            tier=tier,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost, 6),
            latency_s=round(latency, 3),
            trace_id=trace_id,
        )

        # Optional Langfuse tracing
        if self._tracer is not None:
            handle = self._tracer.start_trace(
                name=f"llm:{provider.model}",
                agent_id="router",
                trace_id=trace_id,
            )
            self._tracer.log_llm_call(
                handle,
                model=provider.model,
                messages=messages,
                response=response.choices[0].message.content or "",
                tokens_in=input_tokens,
                tokens_out=output_tokens,
                cost=cost,
                latency_s=latency,
            )
            self._tracer.end_trace(handle)

        return LLMResponse(
            content=response.choices[0].message.content or "",
            provider=provider.name,
            model=provider.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            latency_s=latency,
            tier=tier,
        )

    def get_provider_status(self) -> dict[str, dict]:
        """Return status for all providers (circuit state, rate limit, etc.)."""
        status = {}
        for key, provider in self._providers.items():
            cb = self._circuit_breakers[key]
            rl = self._rate_limiters[key]
            status[key] = {
                "name": provider.name,
                "model": provider.model,
                "has_key": provider.has_key,
                "is_free": provider.is_free,
                "circuit_state": cb.state.value,
                "rate_limit_remaining": rl.remaining(),
                "max_rpm": provider.max_rpm,
            }
        return status
