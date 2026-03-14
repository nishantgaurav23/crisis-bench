"""CrisisError exception hierarchy for CRISIS-BENCH.

Custom exception hierarchy with trace IDs, error codes, severity levels,
and HTTP status mapping. Every module raises and catches these errors.
"""

import uuid
from typing import Any


class CrisisError(Exception):
    """Base exception for all CRISIS-BENCH errors.

    Attributes:
        message: Human-readable error description.
        context: Arbitrary metadata (agent_id, provider, tier, etc.).
        trace_id: 8-char hex ID for distributed tracing.
        error_code: Unique UPPER_SNAKE_CASE error identifier.
        severity: low | medium | high | critical.
        http_status: HTTP status code for API responses.
    """

    error_code: str = "CRISIS_ERROR"
    severity: str = "medium"
    http_status: int = 500

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        self.message = message
        self.context = dict(context) if context else {}
        # Use provided trace_id or auto-generate 8-char hex
        if "trace_id" in self.context:
            self.trace_id = self.context["trace_id"]
        else:
            self.trace_id = uuid.uuid4().hex[:8]
            self.context["trace_id"] = self.trace_id
        super().__init__(str(self))

    def __str__(self) -> str:
        return f"[{self.trace_id}] {self.error_code}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """Structured error data for JSON logging and API responses."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "trace_id": self.trace_id,
            "severity": self.severity,
            "context": self.context,
        }


# =============================================================================
# Agent Errors
# =============================================================================


class AgentError(CrisisError):
    """Base for all agent-related errors."""

    error_code = "AGENT_ERROR"
    severity = "high"
    http_status = 500


class AgentTimeoutError(AgentError):
    """Agent exceeded AGENT_TIMEOUT_SECONDS (default 120s)."""

    error_code = "AGENT_TIMEOUT"
    severity = "high"
    http_status = 504


class AgentDelegationError(AgentError):
    """Delegation depth exceeded or target agent unavailable."""

    error_code = "AGENT_DELEGATION_FAILED"
    severity = "high"
    http_status = 502


class AgentLoopError(AgentError):
    """Loop detection triggered — agents cycling without progress."""

    error_code = "AGENT_LOOP_DETECTED"
    severity = "high"
    http_status = 508


# =============================================================================
# Router Errors
# =============================================================================


class RouterError(CrisisError):
    """Base for all LLM Router errors."""

    error_code = "ROUTER_ERROR"
    severity = "high"
    http_status = 503


class AllProvidersFailedError(RouterError):
    """All providers in the fallback chain exhausted."""

    error_code = "ALL_PROVIDERS_FAILED"
    severity = "high"
    http_status = 503


class RateLimitError(RouterError):
    """Provider rate limit hit — back off and retry or failover."""

    error_code = "RATE_LIMIT"
    severity = "medium"
    http_status = 429


class BudgetExceededError(RouterError):
    """Per-scenario budget ceiling breached."""

    error_code = "BUDGET_EXCEEDED"
    severity = "medium"
    http_status = 429


# =============================================================================
# Data Errors
# =============================================================================


class DataError(CrisisError):
    """Base for all data layer errors."""

    error_code = "DATA_ERROR"
    severity = "high"
    http_status = 503


class DatabaseConnectionError(DataError):
    """PostgreSQL/PostGIS connection failure."""

    error_code = "DATABASE_CONNECTION"
    severity = "critical"
    http_status = 503


class RedisConnectionError(DataError):
    """Redis connection failure."""

    error_code = "REDIS_CONNECTION"
    severity = "critical"
    http_status = 503


class VectorStoreError(DataError):
    """ChromaDB operation failure."""

    error_code = "VECTOR_STORE"
    severity = "high"
    http_status = 503


class GraphDBError(DataError):
    """Neo4j operation failure."""

    error_code = "GRAPH_DB"
    severity = "high"
    http_status = 503


# =============================================================================
# Protocol Errors
# =============================================================================


class ProtocolError(CrisisError):
    """Base for all communication protocol errors."""

    error_code = "PROTOCOL_ERROR"
    severity = "high"
    http_status = 502


class A2AError(ProtocolError):
    """A2A message serialization or delivery failure."""

    error_code = "A2A_ERROR"
    severity = "high"
    http_status = 502


class MCPError(ProtocolError):
    """MCP server or tool invocation failure."""

    error_code = "MCP_ERROR"
    severity = "medium"
    http_status = 502


# =============================================================================
# External API Errors
# =============================================================================


class ExternalAPIError(CrisisError):
    """External API (IMD, SACHET, USGS, Bhuvan, FIRMS) failure."""

    error_code = "EXTERNAL_API"
    severity = "medium"
    http_status = 502


class APIRateLimitError(ExternalAPIError):
    """External API rate limit exceeded."""

    error_code = "API_RATE_LIMIT"
    severity = "low"
    http_status = 429


# =============================================================================
# Validation & Benchmark Errors
# =============================================================================


class CrisisValidationError(CrisisError):
    """Data validation failure (distinct from Pydantic's ValidationError)."""

    error_code = "VALIDATION_ERROR"
    severity = "low"
    http_status = 422


class BenchmarkError(CrisisError):
    """Benchmark runner or evaluation error."""

    error_code = "BENCHMARK_ERROR"
    severity = "medium"
    http_status = 500


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "CrisisError",
    "AgentError",
    "AgentTimeoutError",
    "AgentDelegationError",
    "AgentLoopError",
    "RouterError",
    "AllProvidersFailedError",
    "RateLimitError",
    "BudgetExceededError",
    "DataError",
    "DatabaseConnectionError",
    "RedisConnectionError",
    "VectorStoreError",
    "GraphDBError",
    "ProtocolError",
    "A2AError",
    "MCPError",
    "ExternalAPIError",
    "APIRateLimitError",
    "CrisisValidationError",
    "BenchmarkError",
]
