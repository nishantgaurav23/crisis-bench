"""Metrics summary API endpoint.

Returns current LLM cost/token/latency summary by provider.
Uses in-memory data — will connect to cost_tracker when S2.8 is done.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])

# Default provider metrics — reflects the LLM Router tiers from design
_DEFAULT_PROVIDERS = [
    {
        "provider": "DeepSeek Reasoner",
        "tier": "critical",
        "total_cost": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "requests": 0,
        "avg_latency_ms": 0,
        "p50_latency_ms": 0,
        "p95_latency_ms": 0,
        "p99_latency_ms": 0,
    },
    {
        "provider": "DeepSeek Chat",
        "tier": "standard",
        "total_cost": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "requests": 0,
        "avg_latency_ms": 0,
        "p50_latency_ms": 0,
        "p95_latency_ms": 0,
        "p99_latency_ms": 0,
    },
    {
        "provider": "Qwen Flash",
        "tier": "routine",
        "total_cost": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "requests": 0,
        "avg_latency_ms": 0,
        "p50_latency_ms": 0,
        "p95_latency_ms": 0,
        "p99_latency_ms": 0,
    },
    {
        "provider": "Groq",
        "tier": "free",
        "total_cost": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "requests": 0,
        "avg_latency_ms": 0,
        "p50_latency_ms": 0,
        "p95_latency_ms": 0,
        "p99_latency_ms": 0,
    },
    {
        "provider": "Ollama",
        "tier": "free",
        "total_cost": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "requests": 0,
        "avg_latency_ms": 0,
        "p50_latency_ms": 0,
        "p95_latency_ms": 0,
        "p99_latency_ms": 0,
    },
]


@router.get("/summary")
async def get_metrics_summary() -> dict[str, Any]:
    """Return current cost/token/latency summary by provider."""
    now = datetime.now(tz=UTC)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    providers = _DEFAULT_PROVIDERS
    total_cost = sum(p["total_cost"] for p in providers)
    total_input = sum(p["input_tokens"] for p in providers)
    total_output = sum(p["output_tokens"] for p in providers)
    total_reqs = sum(p["requests"] for p in providers)

    return {
        "providers": providers,
        "total_cost": total_cost,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_requests": total_reqs,
        "period_start": period_start.isoformat(),
        "period_end": now.isoformat(),
    }
