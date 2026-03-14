# Spec S2.6: LLM Router — 5-Tier Multi-Provider Routing

## Overview

The LLM Router is the core abstraction that decouples all agents from specific LLM providers. Every LLM call in the system goes through `LLMRouter.call(tier, messages)` — the router handles provider selection, automatic failover, cost tracking, rate limiting, circuit breaking, and Prometheus/Langfuse observability.

## Location

- `src/routing/llm_router.py`

## Dependencies

- S1.3 (`src/shared/config.py`) — CrisisSettings for API keys, base URLs, model names
- S2.4 (`src/shared/errors.py`) — RouterError, AllProvidersFailedError, RateLimitError, BudgetExceededError
- S2.5 (`src/shared/telemetry.py`) — LLM_REQUESTS, LLM_TOKENS, LLM_LATENCY, LLM_COST counters; LangfuseTracer

## Data Models

### LLMProvider (dataclass)
- `name: str` — human-readable name (e.g., "DeepSeek Reasoner")
- `key: str` — internal key (e.g., "deepseek_reasoner")
- `client: AsyncOpenAI` — OpenAI-compatible async client
- `model: str` — model identifier
- `input_cost_per_m: float` — USD per 1M input tokens
- `output_cost_per_m: float` — USD per 1M output tokens
- `max_rpm: int` — max requests per minute
- `is_free: bool` — whether this provider is free tier

### LLMResponse (dataclass)
- `content: str` — LLM response text
- `provider: str` — provider name that served the request
- `model: str` — model used
- `input_tokens: int` — prompt tokens consumed
- `output_tokens: int` — completion tokens consumed
- `cost_usd: float` — estimated cost
- `latency_s: float` — wall-clock seconds
- `tier: str` — tier that was requested

### LLMTier (str enum)
- `critical` — evacuation decisions, cascading failure analysis
- `standard` — situation reports, infrastructure analysis
- `routine` — classification, summarization, monitoring
- `vision` — satellite imagery analysis

## Tier → Provider Fallback Chains

| Tier | Primary | Fallback 1 | Fallback 2 | Fallback 3 |
|------|---------|------------|------------|------------|
| critical | DeepSeek Reasoner | Kimi K2.5 | Groq free | Ollama local |
| standard | DeepSeek Chat | Qwen Flash | Groq free | Ollama local |
| routine | Qwen Flash | Groq free | Gemini free | Ollama local |
| vision | Qwen VL Flash | Ollama local (LLaVA) | — | — |

## Core API

```python
class LLMRouter:
    def __init__(self, settings: CrisisSettings, tracer: LangfuseTracer | None = None): ...

    async def call(
        self,
        tier: str | LLMTier,
        messages: list[dict[str, str]],
        *,
        trace_id: str = "",
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout: float = 60.0,
    ) -> LLMResponse: ...

    def get_provider_status(self) -> dict[str, dict]: ...
```

## Key Behaviors

1. **Automatic failover**: If the primary provider fails (timeout, API error, rate limit), try the next provider in the chain. If ALL providers fail, raise `AllProvidersFailedError`.

2. **Rate limiting**: Track requests-per-minute per provider using a sliding window. If a provider's RPM is exhausted, skip it (don't wait) and move to the next in the chain.

3. **Circuit breaker**: After 3 consecutive failures for a provider, mark it as "open" (skip for 30 seconds). After cooldown, allow one test request ("half-open"). If it succeeds, close the circuit.

4. **Cost tracking**: Calculate cost per call from token usage and provider pricing. Emit `LLM_COST` Prometheus counter.

5. **Telemetry**: For every call:
   - Increment `LLM_REQUESTS` counter (provider, tier, status)
   - Increment `LLM_TOKENS` counter (provider, tier, direction=input/output)
   - Observe `LLM_LATENCY` histogram (provider, tier)
   - Increment `LLM_COST` counter (provider, tier)
   - Log via structlog (provider, model, latency, tokens, cost — never log response content)
   - Optionally log to Langfuse tracer

6. **Provider initialization**: Read all API keys and base URLs from CrisisSettings. Providers with empty API keys are still created but skipped during routing (except Ollama which needs no key).

7. **Timeout handling**: Each provider call has a configurable timeout (default 60s). Use `asyncio.wait_for`.

## Outcomes

- [ ] `LLMRouter` class with `call()` method
- [ ] 8 providers configured from CrisisSettings
- [ ] 4 tier fallback chains
- [ ] Automatic failover on provider failure
- [ ] Sliding-window rate limiter per provider
- [ ] Circuit breaker (3 failures → 30s open → half-open)
- [ ] Cost calculation per call
- [ ] Prometheus metrics emitted for every call
- [ ] structlog JSON logging for every call
- [ ] Optional Langfuse tracing
- [ ] `AllProvidersFailedError` when chain exhausted
- [ ] Provider status reporting (`get_provider_status`)

## TDD Notes

- Mock `AsyncOpenAI.chat.completions.create` — never hit real APIs in tests
- Test each tier routes to correct primary provider
- Test failover: mock primary failure → verify fallback used
- Test all-providers-failed → AllProvidersFailedError
- Test rate limiter: exhaust RPM → provider skipped
- Test circuit breaker: 3 failures → open → skip → cooldown → half-open → success → closed
- Test cost calculation with known token counts
- Test Prometheus counters are incremented
- Test that providers with empty API keys are skipped (except Ollama)
- Test timeout handling
