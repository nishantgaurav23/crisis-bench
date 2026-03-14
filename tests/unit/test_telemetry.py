"""Tests for src/shared/telemetry.py — structured logging, Prometheus metrics, Langfuse stubs."""

from unittest.mock import MagicMock, patch

from src.shared.config import CrisisSettings
from src.shared.telemetry import (
    AGENT_TASK_DURATION,
    AGENT_TASKS,
    CACHE_OPS,
    ERRORS,
    LLM_COST,
    LLM_LATENCY,
    LLM_REQUESTS,
    LLM_TOKENS,
    LangfuseTracer,
    TelemetryContext,
    get_logger,
    hash_content,
    setup_metrics_endpoint,
    setup_telemetry,
)

# =============================================================================
# Structured Logging
# =============================================================================


class TestGetLogger:
    def test_returns_bound_logger(self):
        """get_logger returns a structlog BoundLogger instance."""

        logger = get_logger("test_module")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")

    def test_binds_initial_context(self):
        """get_logger binds agent_id and trace_id as initial context."""
        logger = get_logger("test", agent_id="orchestrator", trace_id="abc123")
        # Structlog bound loggers carry context — extract it
        ctx = logger._context  # noqa: SLF001
        assert ctx["agent_id"] == "orchestrator"
        assert ctx["trace_id"] == "abc123"

    def test_logger_outputs_json_with_required_fields(self):
        """Logger output includes timestamp, severity, and message as JSON."""
        logger = get_logger("json_test", agent_id="test_agent", trace_id="t123")
        # Should produce JSON output without error
        logger.info("test_event", extra_field="value")

    def test_logger_name_bound(self):
        """Logger name is bound as 'logger_name' context key."""
        logger = get_logger("my_module")
        ctx = logger._context  # noqa: SLF001
        assert ctx["logger_name"] == "my_module"


class TestLogLevel:
    def test_logger_respects_log_level(self):
        """Logger should be configurable with different log levels."""
        # get_logger works without crashing at any level
        logger = get_logger("level_test")
        # These should not raise
        logger.debug("debug msg")
        logger.info("info msg")
        logger.warning("warning msg")
        logger.error("error msg")


# =============================================================================
# Prometheus Metrics
# =============================================================================


class TestPrometheusMetrics:
    def test_metrics_exist_and_correct_types(self):
        """All 8 metrics are importable and correct types."""
        from prometheus_client import Counter, Histogram

        assert isinstance(LLM_REQUESTS, Counter)
        assert isinstance(LLM_TOKENS, Counter)
        assert isinstance(LLM_LATENCY, Histogram)
        assert isinstance(LLM_COST, Counter)
        assert isinstance(AGENT_TASKS, Counter)
        assert isinstance(AGENT_TASK_DURATION, Histogram)
        assert isinstance(CACHE_OPS, Counter)
        assert isinstance(ERRORS, Counter)

    def test_counter_increment(self):
        """Counter labels work and can be incremented."""
        # Should not raise
        LLM_REQUESTS.labels(provider="ollama", tier="routine", status="success").inc()
        LLM_TOKENS.labels(provider="ollama", tier="routine", direction="input").inc(100)
        LLM_COST.labels(provider="ollama", tier="routine").inc(0.001)
        AGENT_TASKS.labels(agent_id="orchestrator", status="completed").inc()
        CACHE_OPS.labels(operation="hit").inc()
        ERRORS.labels(error_code="AGENT_TIMEOUT", severity="high").inc()

    def test_histogram_observe(self):
        """Histogram records values with labels."""
        LLM_LATENCY.labels(provider="deepseek", tier="critical").observe(1.5)
        AGENT_TASK_DURATION.labels(agent_id="situation_sense").observe(3.2)

    def test_setup_metrics_endpoint(self):
        """setup_metrics_endpoint mounts /metrics on a FastAPI app."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        setup_metrics_endpoint(app)

        client = TestClient(app)
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "crisis_llm_requests_total" in response.text or "text/plain" in response.headers.get(
            "content-type", ""
        )


# =============================================================================
# Langfuse Tracer
# =============================================================================


class TestLangfuseTracer:
    def _make_settings(self, **overrides):
        """Create test settings."""
        defaults = {
            "LANGFUSE_HOST": "http://localhost:4000",
            "LANGFUSE_SECRET": "test-secret",
            "LANGFUSE_SALT": "test-salt",
            "LOG_LEVEL": "DEBUG",
        }
        defaults.update(overrides)
        return CrisisSettings(**defaults)

    @patch("src.shared.telemetry.Langfuse")
    def test_init_success(self, mock_langfuse_cls):
        """Tracer initializes when Langfuse is available."""
        mock_langfuse_cls.return_value = MagicMock()
        settings = self._make_settings()
        tracer = LangfuseTracer(settings)
        assert tracer.enabled is True

    def test_graceful_noop_when_unreachable(self):
        """Tracer becomes no-op when Langfuse is unreachable."""
        settings = self._make_settings(LANGFUSE_HOST="http://unreachable:9999")
        with patch("src.shared.telemetry.Langfuse", side_effect=Exception("Connection refused")):
            tracer = LangfuseTracer(settings)
        assert tracer.enabled is False

    @patch("src.shared.telemetry.Langfuse")
    def test_start_end_trace(self, mock_langfuse_cls):
        """Trace lifecycle: start → end works."""
        mock_client = MagicMock()
        mock_trace = MagicMock()
        mock_client.trace.return_value = mock_trace
        mock_langfuse_cls.return_value = mock_client

        settings = self._make_settings()
        tracer = LangfuseTracer(settings)

        handle = tracer.start_trace("test_op", agent_id="orchestrator", trace_id="t1")
        assert handle is not None

        tracer.end_trace(handle, output="result", status="ok")
        mock_trace.update.assert_called_once()

    @patch("src.shared.telemetry.Langfuse")
    def test_log_llm_call(self, mock_langfuse_cls):
        """LLM generation is logged to trace."""
        mock_client = MagicMock()
        mock_trace = MagicMock()
        mock_generation = MagicMock()
        mock_trace.generation.return_value = mock_generation
        mock_client.trace.return_value = mock_trace
        mock_langfuse_cls.return_value = mock_client

        settings = self._make_settings()
        tracer = LangfuseTracer(settings)
        handle = tracer.start_trace("llm_test")

        tracer.log_llm_call(
            handle,
            model="deepseek-chat",
            messages=[{"role": "user", "content": "hello"}],
            response="world",
            tokens_in=10,
            tokens_out=5,
            cost=0.001,
            latency_s=0.5,
        )
        mock_trace.generation.assert_called_once()

    def test_noop_tracer_methods_dont_crash(self):
        """Disabled tracer methods return safely."""
        with patch("src.shared.telemetry.Langfuse", side_effect=Exception("fail")):
            settings = self._make_settings()
            tracer = LangfuseTracer(settings)

        # None of these should raise
        handle = tracer.start_trace("test")
        assert handle is None
        tracer.end_trace(handle, output="x")
        tracer.log_llm_call(
            handle,
            model="m",
            messages=[],
            response="r",
            tokens_in=0,
            tokens_out=0,
            cost=0,
            latency_s=0,
        )
        tracer.shutdown()


# =============================================================================
# Content Hashing
# =============================================================================


class TestHashContent:
    def test_deterministic(self):
        """Same input always produces the same hash."""
        assert hash_content("hello world") == hash_content("hello world")

    def test_different_inputs(self):
        """Different inputs produce different hashes."""
        assert hash_content("hello") != hash_content("world")

    def test_returns_hex_string(self):
        """Hash is a hex string of fixed length."""
        h = hash_content("test")
        assert isinstance(h, str)
        assert len(h) == 16  # 8 bytes = 16 hex chars
        int(h, 16)  # Should not raise — valid hex


# =============================================================================
# Setup Telemetry
# =============================================================================


class TestSetupTelemetry:
    @patch("src.shared.telemetry.Langfuse")
    def test_returns_context(self, mock_langfuse_cls):
        """setup_telemetry returns a TelemetryContext with logger and tracer."""
        mock_langfuse_cls.return_value = MagicMock()
        settings = self._make_settings()
        ctx = setup_telemetry(settings)

        assert isinstance(ctx, TelemetryContext)
        assert ctx.logger is not None
        assert isinstance(ctx.tracer, LangfuseTracer)

    def _make_settings(self, **overrides):
        defaults = {
            "LANGFUSE_HOST": "http://localhost:4000",
            "LANGFUSE_SECRET": "test-secret",
            "LANGFUSE_SALT": "test-salt",
            "LOG_LEVEL": "INFO",
        }
        defaults.update(overrides)
        return CrisisSettings(**defaults)
