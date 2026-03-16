"""Per-provider cost tracker for LLM calls.

Tracks tokens, cost (USD), and latency per provider and tier.
Provides budget monitoring with warning/exceeded thresholds.

Usage:
    from src.routing.cost_tracker import CostTracker

    tracker = CostTracker()
    tracker.record(llm_response)
    summary = tracker.get_summary()
    status = tracker.check_budget(limit=5.0)
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum

from src.routing.llm_router import LLMResponse


class BudgetStatus(str, Enum):
    """Budget check result."""

    UNDER_BUDGET = "under_budget"
    WARNING = "warning"
    EXCEEDED = "exceeded"


@dataclass(frozen=True)
class CostRecord:
    """Immutable record of a single LLM call's cost."""

    provider: str
    tier: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_s: float
    timestamp: float

    @classmethod
    def from_response(cls, response: LLMResponse) -> CostRecord:
        """Create a CostRecord from an LLMResponse."""
        return cls(
            provider=response.provider,
            tier=response.tier,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=response.cost_usd,
            latency_s=response.latency_s,
            timestamp=time.time(),
        )


class CostTracker:
    """Thread-safe in-memory cost tracker for LLM calls."""

    WARNING_THRESHOLD = 0.80

    def __init__(self) -> None:
        self._records: list[CostRecord] = []
        self._lock = threading.Lock()

    def record(self, response: LLMResponse) -> None:
        """Record a completed LLM call."""
        rec = CostRecord.from_response(response)
        with self._lock:
            self._records.append(rec)

    def get_total_cost(self) -> float:
        """Total USD spent across all providers."""
        with self._lock:
            return sum(r.cost_usd for r in self._records)

    def get_cost_by_provider(self) -> dict[str, float]:
        """Cost breakdown by provider name."""
        with self._lock:
            result: dict[str, float] = {}
            for r in self._records:
                result[r.provider] = result.get(r.provider, 0.0) + r.cost_usd
            return result

    def get_cost_by_tier(self) -> dict[str, float]:
        """Cost breakdown by LLM tier."""
        with self._lock:
            result: dict[str, float] = {}
            for r in self._records:
                result[r.tier] = result.get(r.tier, 0.0) + r.cost_usd
            return result

    def get_token_summary(self) -> dict[str, int]:
        """Total input, output, and combined token counts."""
        with self._lock:
            total_in = sum(r.input_tokens for r in self._records)
            total_out = sum(r.output_tokens for r in self._records)
            return {
                "total_input_tokens": total_in,
                "total_output_tokens": total_out,
                "total_tokens": total_in + total_out,
            }

    def get_summary(self) -> dict:
        """Full cost summary with all breakdowns."""
        with self._lock:
            total_cost = sum(r.cost_usd for r in self._records)
            total_in = sum(r.input_tokens for r in self._records)
            total_out = sum(r.output_tokens for r in self._records)

            by_provider: dict[str, float] = {}
            for r in self._records:
                by_provider[r.provider] = by_provider.get(r.provider, 0.0) + r.cost_usd

            by_tier: dict[str, float] = {}
            for r in self._records:
                by_tier[r.tier] = by_tier.get(r.tier, 0.0) + r.cost_usd

            return {
                "total_cost_usd": total_cost,
                "total_records": len(self._records),
                "total_input_tokens": total_in,
                "total_output_tokens": total_out,
                "by_provider": by_provider,
                "by_tier": by_tier,
            }

    def check_budget(self, limit: float) -> BudgetStatus:
        """Check spending against a budget limit.

        Returns WARNING at 80% of limit, EXCEEDED at 100%.
        """
        total = self.get_total_cost()
        if total >= limit:
            return BudgetStatus.EXCEEDED
        if total >= limit * self.WARNING_THRESHOLD:
            return BudgetStatus.WARNING
        return BudgetStatus.UNDER_BUDGET

    def reset(self) -> None:
        """Clear all records."""
        with self._lock:
            self._records.clear()
