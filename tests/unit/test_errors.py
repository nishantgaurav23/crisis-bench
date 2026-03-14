"""Tests for CrisisError exception hierarchy (src/shared/errors.py).

TDD Red phase: all tests written before implementation.
"""

import re

import pytest

from src.shared.errors import (
    A2AError,
    AgentDelegationError,
    AgentError,
    AgentLoopError,
    AgentTimeoutError,
    AllProvidersFailedError,
    APIRateLimitError,
    BenchmarkError,
    BudgetExceededError,
    CrisisError,
    CrisisValidationError,
    DatabaseConnectionError,
    DataError,
    ExternalAPIError,
    GraphDBError,
    MCPError,
    ProtocolError,
    RateLimitError,
    RedisConnectionError,
    RouterError,
    VectorStoreError,
)

# ============================================================================
# All error classes for parametrized tests
# ============================================================================

ALL_ERROR_CLASSES = [
    CrisisError,
    AgentError,
    AgentTimeoutError,
    AgentDelegationError,
    AgentLoopError,
    RouterError,
    AllProvidersFailedError,
    RateLimitError,
    BudgetExceededError,
    DataError,
    DatabaseConnectionError,
    RedisConnectionError,
    VectorStoreError,
    GraphDBError,
    ProtocolError,
    A2AError,
    MCPError,
    ExternalAPIError,
    APIRateLimitError,
    CrisisValidationError,
    BenchmarkError,
]

VALID_SEVERITIES = {"low", "medium", "high", "critical"}


# ============================================================================
# 1. Base CrisisError tests
# ============================================================================


class TestCrisisErrorBase:
    """Test CrisisError base class properties."""

    def test_crisis_error_base(self):
        """CrisisError has message, trace_id, error_code, severity, http_status."""
        err = CrisisError("something went wrong")
        assert str(err) == "something went wrong" or "something went wrong" in str(err)
        assert err.error_code == "CRISIS_ERROR"
        assert err.severity in VALID_SEVERITIES
        assert isinstance(err.http_status, int)
        assert 400 <= err.http_status <= 599
        assert err.trace_id is not None

    def test_crisis_error_auto_trace_id(self):
        """trace_id is auto-generated as 8-char hex if not provided."""
        err = CrisisError("test")
        assert len(err.trace_id) == 8
        assert re.match(r"^[0-9a-f]{8}$", err.trace_id)

    def test_crisis_error_custom_trace_id(self):
        """trace_id from context is used if provided."""
        err = CrisisError("test", context={"trace_id": "abcd1234"})
        assert err.trace_id == "abcd1234"

    def test_crisis_error_to_dict(self):
        """to_dict returns correct structure."""
        err = CrisisError("bad thing", context={"agent_id": "orchestrator"})
        d = err.to_dict()
        assert d["error_code"] == "CRISIS_ERROR"
        assert d["message"] == "bad thing"
        assert "trace_id" in d
        assert d["severity"] in VALID_SEVERITIES
        assert d["context"]["agent_id"] == "orchestrator"

    def test_crisis_error_context(self):
        """Arbitrary context is preserved."""
        ctx = {"agent_id": "sit_sense", "provider": "deepseek", "tier": "critical"}
        err = CrisisError("fail", context=ctx)
        assert err.context["agent_id"] == "sit_sense"
        assert err.context["provider"] == "deepseek"
        assert err.context["tier"] == "critical"
        # trace_id should also be in context
        assert "trace_id" in err.context

    def test_crisis_error_is_exception(self):
        """CrisisError is an Exception subclass and can be raised/caught."""
        with pytest.raises(CrisisError):
            raise CrisisError("test error")

    def test_str_repr(self):
        """str(error) includes trace_id and message."""
        err = CrisisError("something broke")
        s = str(err)
        assert err.trace_id in s
        assert "something broke" in s


# ============================================================================
# 2. Agent error hierarchy
# ============================================================================


class TestAgentErrors:
    """Test AgentError and subclasses."""

    def test_agent_error_is_crisis_error(self):
        assert issubclass(AgentError, CrisisError)

    def test_agent_timeout_error(self):
        err = AgentTimeoutError("agent timed out after 120s")
        assert isinstance(err, AgentError)
        assert isinstance(err, CrisisError)
        assert err.error_code == "AGENT_TIMEOUT"
        assert err.http_status == 504

    def test_agent_delegation_error(self):
        err = AgentDelegationError("delegation depth exceeded")
        assert isinstance(err, AgentError)
        assert err.error_code == "AGENT_DELEGATION_FAILED"

    def test_agent_loop_error(self):
        err = AgentLoopError("loop detected")
        assert isinstance(err, AgentError)
        assert err.error_code == "AGENT_LOOP_DETECTED"


# ============================================================================
# 3. Router error hierarchy
# ============================================================================


class TestRouterErrors:
    """Test RouterError and subclasses."""

    def test_router_error_is_crisis_error(self):
        assert issubclass(RouterError, CrisisError)

    def test_all_providers_failed(self):
        err = AllProvidersFailedError("no providers available for tier critical")
        assert isinstance(err, RouterError)
        assert err.error_code == "ALL_PROVIDERS_FAILED"
        assert err.http_status == 503
        assert err.severity == "high"

    def test_rate_limit_error(self):
        err = RateLimitError("groq rate limit hit", context={"provider": "groq"})
        assert isinstance(err, RouterError)
        assert err.error_code == "RATE_LIMIT"
        assert err.http_status == 429

    def test_budget_exceeded_error(self):
        err = BudgetExceededError("$0.05 ceiling breached")
        assert isinstance(err, RouterError)
        assert err.error_code == "BUDGET_EXCEEDED"
        assert err.http_status == 429


# ============================================================================
# 4. Data error hierarchy
# ============================================================================


class TestDataErrors:
    """Test DataError and subclasses."""

    def test_data_error_is_crisis_error(self):
        assert issubclass(DataError, CrisisError)

    def test_database_connection_error(self):
        err = DatabaseConnectionError("pg pool exhausted")
        assert isinstance(err, DataError)
        assert err.error_code == "DATABASE_CONNECTION"
        assert err.severity == "critical"
        assert err.http_status == 503

    def test_redis_connection_error(self):
        err = RedisConnectionError("redis refused connection")
        assert isinstance(err, DataError)
        assert err.error_code == "REDIS_CONNECTION"
        assert err.severity == "critical"

    def test_vector_store_error(self):
        err = VectorStoreError("chromadb query failed")
        assert isinstance(err, DataError)
        assert err.error_code == "VECTOR_STORE"

    def test_graph_db_error(self):
        err = GraphDBError("neo4j connection lost")
        assert isinstance(err, DataError)
        assert err.error_code == "GRAPH_DB"


# ============================================================================
# 5. Protocol error hierarchy
# ============================================================================


class TestProtocolErrors:
    """Test ProtocolError and subclasses."""

    def test_protocol_error_is_crisis_error(self):
        assert issubclass(ProtocolError, CrisisError)

    def test_a2a_error(self):
        err = A2AError("message serialization failed")
        assert isinstance(err, ProtocolError)
        assert err.error_code == "A2A_ERROR"

    def test_mcp_error(self):
        err = MCPError("tool invocation failed")
        assert isinstance(err, ProtocolError)
        assert err.error_code == "MCP_ERROR"


# ============================================================================
# 6. External API error
# ============================================================================


class TestExternalAPIError:
    """Test ExternalAPIError and APIRateLimitError."""

    def test_external_api_error(self):
        err = ExternalAPIError("IMD API returned 500")
        assert isinstance(err, CrisisError)
        assert err.error_code == "EXTERNAL_API"

    def test_api_rate_limit_error(self):
        err = APIRateLimitError("USGS rate limit exceeded")
        assert isinstance(err, ExternalAPIError)
        assert err.error_code == "API_RATE_LIMIT"
        assert err.http_status == 429


# ============================================================================
# 7. Validation error
# ============================================================================


class TestCrisisValidationError:
    """Test CrisisValidationError (distinct from Pydantic's)."""

    def test_validation_error(self):
        err = CrisisValidationError("invalid severity value")
        assert isinstance(err, CrisisError)
        assert err.error_code == "VALIDATION_ERROR"
        assert err.http_status == 422


# ============================================================================
# 8. Benchmark error
# ============================================================================


class TestBenchmarkError:
    """Test BenchmarkError."""

    def test_benchmark_error(self):
        err = BenchmarkError("scenario runner failed")
        assert isinstance(err, CrisisError)
        assert err.error_code == "BENCHMARK_ERROR"


# ============================================================================
# 9. Cross-cutting tests
# ============================================================================


class TestCrossCutting:
    """Tests that verify properties across all error classes."""

    def test_error_codes_unique(self):
        """All error classes have unique error_code values."""
        codes = set()
        for cls in ALL_ERROR_CLASSES:
            err = cls("test")
            assert err.error_code not in codes, (
                f"Duplicate error_code: {err.error_code} in {cls.__name__}"
            )
            codes.add(err.error_code)

    def test_all_have_valid_severity(self):
        """Every error class has a valid severity level."""
        for cls in ALL_ERROR_CLASSES:
            err = cls("test")
            assert err.severity in VALID_SEVERITIES, (
                f"{cls.__name__} has invalid severity: {err.severity}"
            )

    def test_all_have_valid_http_status(self):
        """Every error class has an HTTP status in 4xx-5xx range."""
        for cls in ALL_ERROR_CLASSES:
            err = cls("test")
            assert 400 <= err.http_status <= 599, (
                f"{cls.__name__} has invalid http_status: {err.http_status}"
            )

    def test_inheritance_catch(self):
        """Catching CrisisError catches all subclasses."""
        for cls in ALL_ERROR_CLASSES:
            with pytest.raises(CrisisError):
                raise cls("test")

    def test_all_have_trace_id(self):
        """Every error instance has a trace_id."""
        for cls in ALL_ERROR_CLASSES:
            err = cls("test")
            assert err.trace_id is not None
            assert len(err.trace_id) == 8

    def test_to_dict_all_classes(self):
        """to_dict works for all error classes."""
        for cls in ALL_ERROR_CLASSES:
            err = cls("test message")
            d = err.to_dict()
            assert "error_code" in d
            assert "message" in d
            assert "trace_id" in d
            assert "severity" in d
            assert "context" in d
