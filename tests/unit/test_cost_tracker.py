"""Tests for S2.8: Per-provider cost tracker."""

import time

import pytest

from src.routing.cost_tracker import BudgetStatus, CostRecord, CostTracker
from src.routing.llm_router import LLMResponse

# =============================================================================
# Fixtures
# =============================================================================


def _make_response(
    provider: str = "DeepSeek Chat",
    model: str = "deepseek-chat",
    tier: str = "standard",
    input_tokens: int = 100,
    output_tokens: int = 50,
    cost_usd: float = 0.000049,
    latency_s: float = 1.2,
) -> LLMResponse:
    return LLMResponse(
        content="test",
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        latency_s=latency_s,
        tier=tier,
    )


# =============================================================================
# CostRecord
# =============================================================================


class TestCostRecord:
    def test_from_response(self):
        resp = _make_response()
        record = CostRecord.from_response(resp)
        assert record.provider == "DeepSeek Chat"
        assert record.tier == "standard"
        assert record.model == "deepseek-chat"
        assert record.input_tokens == 100
        assert record.output_tokens == 50
        assert record.cost_usd == pytest.approx(0.000049)
        assert record.latency_s == pytest.approx(1.2)
        assert record.timestamp > 0

    def test_timestamp_is_current(self):
        before = time.time()
        record = CostRecord.from_response(_make_response())
        after = time.time()
        assert before <= record.timestamp <= after


# =============================================================================
# CostTracker — Empty State
# =============================================================================


class TestCostTrackerEmpty:
    def test_total_cost_zero(self):
        tracker = CostTracker()
        assert tracker.get_total_cost() == 0.0

    def test_cost_by_provider_empty(self):
        tracker = CostTracker()
        assert tracker.get_cost_by_provider() == {}

    def test_cost_by_tier_empty(self):
        tracker = CostTracker()
        assert tracker.get_cost_by_tier() == {}

    def test_token_summary_zeroes(self):
        tracker = CostTracker()
        summary = tracker.get_token_summary()
        assert summary["total_input_tokens"] == 0
        assert summary["total_output_tokens"] == 0
        assert summary["total_tokens"] == 0

    def test_budget_under(self):
        tracker = CostTracker()
        assert tracker.check_budget(1.0) == BudgetStatus.UNDER_BUDGET

    def test_summary_empty(self):
        tracker = CostTracker()
        summary = tracker.get_summary()
        assert summary["total_cost_usd"] == 0.0
        assert summary["total_records"] == 0
        assert summary["by_provider"] == {}
        assert summary["by_tier"] == {}


# =============================================================================
# CostTracker — Recording
# =============================================================================


class TestCostTrackerRecording:
    def test_record_single_call(self):
        tracker = CostTracker()
        tracker.record(_make_response(cost_usd=0.001))
        assert tracker.get_total_cost() == pytest.approx(0.001)

    def test_record_multiple_calls_accumulate(self):
        tracker = CostTracker()
        tracker.record(_make_response(cost_usd=0.001))
        tracker.record(_make_response(cost_usd=0.002))
        tracker.record(_make_response(cost_usd=0.003))
        assert tracker.get_total_cost() == pytest.approx(0.006)

    def test_cost_by_provider(self):
        tracker = CostTracker()
        tracker.record(_make_response(provider="DeepSeek Chat", cost_usd=0.01))
        tracker.record(_make_response(provider="DeepSeek Chat", cost_usd=0.02))
        tracker.record(_make_response(provider="Qwen Flash", cost_usd=0.005))
        by_provider = tracker.get_cost_by_provider()
        assert by_provider["DeepSeek Chat"] == pytest.approx(0.03)
        assert by_provider["Qwen Flash"] == pytest.approx(0.005)

    def test_cost_by_tier(self):
        tracker = CostTracker()
        tracker.record(_make_response(tier="critical", cost_usd=0.05))
        tracker.record(_make_response(tier="routine", cost_usd=0.001))
        tracker.record(_make_response(tier="critical", cost_usd=0.03))
        by_tier = tracker.get_cost_by_tier()
        assert by_tier["critical"] == pytest.approx(0.08)
        assert by_tier["routine"] == pytest.approx(0.001)

    def test_token_summary(self):
        tracker = CostTracker()
        tracker.record(_make_response(input_tokens=100, output_tokens=50))
        tracker.record(_make_response(input_tokens=200, output_tokens=100))
        summary = tracker.get_token_summary()
        assert summary["total_input_tokens"] == 300
        assert summary["total_output_tokens"] == 150
        assert summary["total_tokens"] == 450


# =============================================================================
# CostTracker — Budget
# =============================================================================


class TestCostTrackerBudget:
    def test_under_budget(self):
        tracker = CostTracker()
        tracker.record(_make_response(cost_usd=0.01))
        assert tracker.check_budget(1.0) == BudgetStatus.UNDER_BUDGET

    def test_warning_at_80_percent(self):
        tracker = CostTracker()
        tracker.record(_make_response(cost_usd=0.85))
        assert tracker.check_budget(1.0) == BudgetStatus.WARNING

    def test_exceeded_at_100_percent(self):
        tracker = CostTracker()
        tracker.record(_make_response(cost_usd=1.0))
        assert tracker.check_budget(1.0) == BudgetStatus.EXCEEDED

    def test_exceeded_over_limit(self):
        tracker = CostTracker()
        tracker.record(_make_response(cost_usd=1.5))
        assert tracker.check_budget(1.0) == BudgetStatus.EXCEEDED

    def test_exactly_at_warning_threshold(self):
        tracker = CostTracker()
        tracker.record(_make_response(cost_usd=0.80))
        assert tracker.check_budget(1.0) == BudgetStatus.WARNING

    def test_just_below_warning(self):
        tracker = CostTracker()
        tracker.record(_make_response(cost_usd=0.79))
        assert tracker.check_budget(1.0) == BudgetStatus.UNDER_BUDGET


# =============================================================================
# CostTracker — Summary & Reset
# =============================================================================


class TestCostTrackerSummaryAndReset:
    def test_full_summary_structure(self):
        tracker = CostTracker()
        tracker.record(_make_response(
            provider="DeepSeek Chat", tier="standard",
            input_tokens=100, output_tokens=50, cost_usd=0.01,
        ))
        tracker.record(_make_response(
            provider="Qwen Flash", tier="routine",
            input_tokens=200, output_tokens=100, cost_usd=0.002,
        ))
        summary = tracker.get_summary()
        assert summary["total_cost_usd"] == pytest.approx(0.012)
        assert summary["total_records"] == 2
        assert summary["total_input_tokens"] == 300
        assert summary["total_output_tokens"] == 150
        assert "DeepSeek Chat" in summary["by_provider"]
        assert "Qwen Flash" in summary["by_provider"]
        assert "standard" in summary["by_tier"]
        assert "routine" in summary["by_tier"]

    def test_reset_clears_all(self):
        tracker = CostTracker()
        tracker.record(_make_response(cost_usd=0.01))
        tracker.record(_make_response(cost_usd=0.02))
        tracker.reset()
        assert tracker.get_total_cost() == 0.0
        assert tracker.get_cost_by_provider() == {}
        assert tracker.get_cost_by_tier() == {}
        assert tracker.get_token_summary()["total_tokens"] == 0
        assert tracker.get_summary()["total_records"] == 0
