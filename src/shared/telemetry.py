"""Telemetry module for CRISIS-BENCH: structured logging, Prometheus metrics, Langfuse tracing.

Provides a unified observability layer. Every module imports from here —
never use stdlib logging or raw Langfuse directly.

Usage:
    from src.shared.telemetry import get_logger, setup_telemetry, LLM_REQUESTS
    logger = get_logger("my_module", agent_id="orchestrator")
    logger.info("processing", trace_id="abc123")
"""

from __future__ import annotations

import hashlib
import logging
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog
from prometheus_client import Counter, Histogram, make_asgi_app

if TYPE_CHECKING:
    from fastapi import FastAPI

    from src.shared.config import CrisisSettings

# Try importing Langfuse — may not be installed in minimal test environments
try:
    from langfuse import Langfuse
except ImportError:  # pragma: no cover
    Langfuse = None  # type: ignore[assignment, misc]

# =============================================================================
# Structured Logging (structlog)
# =============================================================================

_structlog_configured = False


def _configure_structlog(log_level: str = "INFO") -> None:
    """Configure structlog for JSON output with required fields."""
    global _structlog_configured  # noqa: PLW0603
    if _structlog_configured:
        return

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=False,
    )
    _structlog_configured = True


def get_logger(name: str, **initial_binds: Any) -> structlog.BoundLogger:
    """Return a structlog bound logger with initial context.

    Args:
        name: Logger name (typically module name).
        **initial_binds: Initial context bindings (agent_id, trace_id, etc.).
    """
    if not _structlog_configured:
        _configure_structlog()
    return structlog.get_logger(logger_name=name, **initial_binds)


# =============================================================================
# Prometheus Metrics (module-level singletons)
# =============================================================================

LLM_REQUESTS: Counter = Counter(
    "crisis_llm_requests_total",
    "Total LLM API requests",
    ["provider", "tier", "status"],
)

LLM_TOKENS: Counter = Counter(
    "crisis_llm_tokens_total",
    "Total LLM tokens consumed",
    ["provider", "tier", "direction"],
)

LLM_LATENCY: Histogram = Histogram(
    "crisis_llm_latency_seconds",
    "LLM request latency in seconds",
    ["provider", "tier"],
)

LLM_COST: Counter = Counter(
    "crisis_llm_cost_dollars",
    "Total LLM cost in USD",
    ["provider", "tier"],
)

AGENT_TASKS: Counter = Counter(
    "crisis_agent_tasks_total",
    "Total agent tasks processed",
    ["agent_id", "status"],
)

AGENT_TASK_DURATION: Histogram = Histogram(
    "crisis_agent_task_duration_seconds",
    "Agent task duration in seconds",
    ["agent_id"],
)

CACHE_OPS: Counter = Counter(
    "crisis_cache_operations_total",
    "Cache operations (hit/miss/set)",
    ["operation"],
)

ERRORS: Counter = Counter(
    "crisis_errors_total",
    "Total errors by code and severity",
    ["error_code", "severity"],
)


def setup_metrics_endpoint(app: FastAPI) -> None:
    """Mount Prometheus /metrics endpoint on a FastAPI app."""
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)


# =============================================================================
# Langfuse Tracer
# =============================================================================

# TraceHandle is whatever Langfuse returns, or None when disabled
TraceHandle = Any


class LangfuseTracer:
    """Thin wrapper around Langfuse for LLM observability.

    Degrades gracefully to no-op when Langfuse is unreachable.
    """

    def __init__(self, settings: CrisisSettings) -> None:
        self.enabled = False
        self._client: Any = None
        try:
            if Langfuse is None:
                raise ImportError("langfuse not installed")
            self._client = Langfuse(
                host=settings.LANGFUSE_HOST,
                secret_key=settings.LANGFUSE_SECRET,
                public_key="crisis-bench",
            )
            self.enabled = True
        except Exception:
            logger = get_logger("telemetry.langfuse")
            logger.warning("langfuse_unavailable", host=settings.LANGFUSE_HOST)

    def start_trace(
        self,
        name: str,
        *,
        agent_id: str = "",
        trace_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> TraceHandle:
        """Start a Langfuse trace. Returns handle or None if disabled."""
        if not self.enabled or self._client is None:
            return None
        return self._client.trace(
            name=name,
            metadata={
                "agent_id": agent_id,
                "trace_id": trace_id,
                **(metadata or {}),
            },
        )

    def end_trace(
        self,
        handle: TraceHandle,
        *,
        output: str = "",
        status: str = "ok",
    ) -> None:
        """Complete a trace."""
        if handle is None or not self.enabled:
            return
        handle.update(output=output, metadata={"status": status})

    def log_llm_call(
        self,
        handle: TraceHandle,
        *,
        model: str,
        messages: list[Any],
        response: str,
        tokens_in: int,
        tokens_out: int,
        cost: float,
        latency_s: float,
    ) -> None:
        """Log an LLM generation to the trace."""
        if handle is None or not self.enabled:
            return
        handle.generation(
            name=f"llm:{model}",
            model=model,
            input=messages,
            output=hash_content(response),
            usage={"input": tokens_in, "output": tokens_out, "total": tokens_in + tokens_out},
            metadata={"cost_usd": cost, "latency_s": latency_s},
        )

    def shutdown(self) -> None:
        """Flush and close the Langfuse client."""
        if self._client is not None and self.enabled:
            try:
                self._client.flush()
            except Exception:
                pass


# =============================================================================
# Content Hashing (PII Protection)
# =============================================================================


def hash_content(text: str) -> str:
    """Return a truncated SHA-256 hex digest (16 chars / 8 bytes).

    Use this instead of logging raw LLM responses or PII.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# =============================================================================
# One-Call Setup
# =============================================================================


@dataclass
class TelemetryContext:
    """Container returned by setup_telemetry with all telemetry handles."""

    logger: structlog.BoundLogger
    tracer: LangfuseTracer


def setup_telemetry(settings: CrisisSettings) -> TelemetryContext:
    """Initialize all telemetry subsystems and return a TelemetryContext.

    Call once at application startup.
    """
    _configure_structlog(log_level=settings.LOG_LEVEL)
    logger = get_logger("crisis-bench")
    tracer = LangfuseTracer(settings)
    return TelemetryContext(logger=logger, tracer=tracer)
