# Spec S2.6: LLM Router — Explanation

## Why This Spec Exists

Every agent in the system needs to make LLM calls, but no agent should know or care which specific provider (DeepSeek, Qwen, Groq, Ollama) serves the request. The LLM Router is the **strategy pattern with automatic failover** — it decouples agents from providers and enables the hybrid Chinese API + local Ollama cost model ($3-8/month instead of $100+/month).

Without this, each agent would need provider-specific code, error handling, and fallback logic — duplicated 7+ times.

## What It Does

The `LLMRouter` class provides a single async method: `call(tier, messages)`. Internally it:

1. **Selects a provider chain** based on the tier (critical/standard/routine/vision)
2. **Tries each provider** in order, skipping those that are rate-limited, circuit-broken, or missing API keys
3. **Makes the API call** via `AsyncOpenAI` (all providers are OpenAI-compatible)
4. **Tracks cost** from token usage × provider pricing
5. **Emits telemetry** — Prometheus counters, structlog JSON, optional Langfuse traces
6. **Falls over automatically** if a provider fails — agents never see the failure

### Key Components

- **LLMTier** — enum mapping urgency to provider chain
- **LLMProvider** — dataclass holding client, model, pricing, rate limit config
- **LLMResponse** — dataclass returned to callers with content + metadata
- **SlidingWindowRateLimiter** — per-provider RPM tracking using a deque of timestamps
- **CircuitBreaker** — 3-state machine (closed → open → half-open) preventing cascading failures

### Provider Chain Configuration

| Tier | Chain |
|------|-------|
| critical | DeepSeek Reasoner → Kimi K2.5 → Groq free → Ollama local |
| standard | DeepSeek Chat → Qwen Flash → Groq free → Ollama local |
| routine | Qwen Flash → Groq free → Gemini free → Ollama local |
| vision | Qwen VL Flash → Ollama local |

## How It Works

```
Agent calls router.call("critical", messages)
  │
  ├─ Get chain: [deepseek_reasoner, kimi, groq_free, ollama_local]
  │
  ├─ For each provider in chain:
  │   ├─ Skip if no API key (except Ollama)
  │   ├─ Skip if rate limiter says no
  │   ├─ Skip if circuit breaker is open
  │   ├─ Try the call with asyncio.wait_for(timeout)
  │   │   ├─ Success → record success, emit metrics, return LLMResponse
  │   │   └─ Failure → record failure, log warning, try next
  │
  └─ All failed → raise AllProvidersFailedError
```

### Circuit Breaker State Machine

```
CLOSED ──[3 failures]──→ OPEN ──[30s timeout]──→ HALF_OPEN
  ↑                                                   │
  └──────────[success]─────────────────────────────────┘
  HALF_OPEN ──[failure]──→ OPEN
```

## How It Connects

### Upstream (depends on)
- **S1.3 config.py** — API keys, base URLs, model names, budget limits
- **S2.4 errors.py** — `AllProvidersFailedError`, `RouterError` hierarchy
- **S2.5 telemetry.py** — `LLM_REQUESTS`, `LLM_TOKENS`, `LLM_LATENCY`, `LLM_COST` counters; `LangfuseTracer`

### Downstream (used by)
- **S2.7 urgency_classifier.py** — Maps disaster data to tiers, then calls router
- **S2.8 cost_tracker.py** — Reads cost data from router responses
- **S7.1 base_agent.py** — Every agent's `reason()` method calls `router.call()`
- **S6.6 scenario_gen.py** — Uses router for LLM-powered scenario generation
- **S6.7 social_media_gen.py** — Uses router for synthetic tweet generation
- **S8.4 evaluation_engine.py** — Uses critical tier for LLM-as-judge

## Interview Q&A

**Q: Why use the Strategy pattern here instead of a simple if-else?**
A: The Strategy pattern (provider chains per tier) separates the "what tier to use" decision from the "which provider to try" logic. Adding a new provider means adding one entry to `_init_providers()` and inserting it in the right chain position — zero changes to `call()`. An if-else would grow linearly with providers × tiers.

**Q: Why a sliding window rate limiter instead of a token bucket?**
A: Sliding window is simpler to implement correctly (just a deque of timestamps) and more intuitive — "N requests in the last 60 seconds." Token bucket is better for smoothing bursts, but our providers have strict RPM limits, not burst allowances. The deque approach is O(1) amortized (we only clean old entries when checking).

**Q: What happens if Ollama is also down?**
A: `AllProvidersFailedError` is raised. The agent's circuit breaker (in S7.1) catches this and enters degraded mode — it returns a cached/partial response or escalates to the Orchestrator. The system is designed so that no single failure is unrecoverable.

**Q: Why not use httpx directly instead of AsyncOpenAI?**
A: All our providers (DeepSeek, Qwen, Kimi, Groq, Ollama) expose OpenAI-compatible APIs. Using `AsyncOpenAI` with different `base_url` + `api_key` means the same client code works for all providers. If we used httpx, we'd need to handle request/response serialization, streaming, token counting, and error parsing ourselves.
