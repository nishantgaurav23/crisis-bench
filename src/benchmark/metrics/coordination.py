"""Coordination Quality metric for CRISIS-BENCH (spec S8.8).

Measures inter-agent information sharing, milestone achievement,
response coverage, and redundancy avoidance. Evaluates how effectively
agents coordinate during disaster response.

Maps a composite score to 1.0-5.0 using weighted component scores.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from src.benchmark.models import (
    BenchmarkScenario,
    EvaluationRun,
    GroundTruthDecisions,
)

# =============================================================================
# Models
# =============================================================================


class MessageRecord(BaseModel):
    """A single inter-agent message."""

    from_agent: str
    to_agent: str
    message_type: str = "unknown"


class MilestoneRecord(BaseModel):
    """A coordination milestone reached during a run."""

    milestone_id: str
    agent_id: str
    timestamp_minutes: float = Field(..., ge=0.0)


class CoordinationQualityResult(BaseModel):
    """Complete coordination quality evaluation result."""

    info_sharing_ratio: float = Field(..., ge=0.0, le=1.0)
    milestone_ratio: float = Field(..., ge=0.0, le=1.0)
    coverage_ratio: float = Field(..., ge=0.0, le=1.0)
    redundancy_ratio: float = Field(..., ge=0.0, le=1.0)
    component_scores: dict[str, float] = Field(default_factory=dict)
    score: float = Field(..., ge=1.0, le=5.0)


# =============================================================================
# Extraction — Messages
# =============================================================================


def extract_messages(decisions: list[dict[str, Any]]) -> list[MessageRecord]:
    """Extract inter-agent messages from agent decision records.

    Looks for a 'messages_sent' list in each decision. Skips
    malformed entries.
    """
    result: list[MessageRecord] = []
    for decision in decisions:
        messages_data = decision.get("messages_sent", [])
        for msg in messages_data:
            try:
                result.append(MessageRecord(**msg))
            except (TypeError, ValueError):
                continue
    return result


# =============================================================================
# Extraction — Milestones
# =============================================================================


def extract_milestones(
    decisions: list[dict[str, Any]],
) -> list[MilestoneRecord]:
    """Extract coordination milestones from agent decision records.

    Looks for a 'milestones_reached' list in each decision.
    """
    result: list[MilestoneRecord] = []
    for decision in decisions:
        milestones_data = decision.get("milestones_reached", [])
        for ms in milestones_data:
            try:
                result.append(MilestoneRecord(**ms))
            except (TypeError, ValueError):
                continue
    return result


# =============================================================================
# Extraction — Expected Coordination from Ground Truth
# =============================================================================

_SHARE_RE = re.compile(
    r"share\s+.+\s+with\s+(\w+)", re.IGNORECASE,
)


def extract_expected_coordination(
    ground_truth: GroundTruthDecisions,
) -> tuple[list[tuple[str, str]], dict[str, int], set[str]]:
    """Extract expected coordination data from ground truth.

    Returns:
        - expected_messages: list of (from_agent, to_agent) tuples
        - expected_milestones: dict of {milestone_id: deadline_minutes}
        - expected_agents: set of agent IDs that should participate
    """
    expected_messages: list[tuple[str, str]] = []
    expected_agents: set[str] = set()

    for agent_id, expectation in ground_truth.agent_expectations.items():
        expected_agents.add(agent_id)
        for action in expectation.expected_actions:
            match = _SHARE_RE.search(action)
            if match:
                target_agent = match.group(1)
                expected_messages.append((agent_id, target_agent))

    # Parse milestones from decision_timeline
    expected_milestones: dict[str, int] = {}
    for milestone_id, deadline_str in ground_truth.decision_timeline.items():
        try:
            expected_milestones[milestone_id] = int(deadline_str)
        except (ValueError, TypeError):
            continue

    return expected_messages, expected_milestones, expected_agents


# =============================================================================
# Component Scoring — Information Sharing
# =============================================================================


def compute_info_sharing_score(
    expected: list[tuple[str, str]],
    actual: list[MessageRecord],
) -> float:
    """Compute information sharing ratio.

    Returns the fraction of expected (from, to) pairs that appear
    in the actual messages. Returns 1.0 if no expected messages.
    """
    if not expected:
        return 1.0

    actual_pairs = {(m.from_agent, m.to_agent) for m in actual}
    matched = sum(1 for pair in expected if pair in actual_pairs)
    return matched / len(expected)


# =============================================================================
# Component Scoring — Milestone Achievement
# =============================================================================


def compute_milestone_score(
    expected: dict[str, int],
    actual: list[MilestoneRecord],
) -> float:
    """Compute milestone achievement ratio.

    Milestones reached on or before deadline get full credit (1.0).
    Late milestones get partial credit based on how late they are.
    Missing milestones get 0.0. Returns 1.0 if no expected milestones.
    """
    if not expected:
        return 1.0

    actual_map: dict[str, float] = {}
    for ms in actual:
        if ms.milestone_id not in actual_map:
            actual_map[ms.milestone_id] = ms.timestamp_minutes

    total_credit = 0.0
    for milestone_id, deadline in expected.items():
        actual_time = actual_map.get(milestone_id)
        if actual_time is None:
            continue  # Missing → 0 credit
        if actual_time <= deadline:
            total_credit += 1.0  # On time → full credit
        else:
            # Late → partial credit with exponential decay
            lateness = (actual_time - deadline) / max(deadline, 1)
            import math

            credit = math.exp(-2.0 * lateness)
            total_credit += max(0.0, credit)

    return total_credit / len(expected)


# =============================================================================
# Component Scoring — Response Coverage
# =============================================================================


def compute_coverage_score(
    expected_agents: set[str],
    actual_agents: set[str],
) -> float:
    """Compute response coverage as fraction of expected agents present.

    Returns 1.0 if no expected agents.
    """
    if not expected_agents:
        return 1.0

    present = expected_agents & actual_agents
    return len(present) / len(expected_agents)


# =============================================================================
# Component Scoring — Redundancy Avoidance
# =============================================================================


def compute_redundancy_score(messages: list[MessageRecord]) -> float:
    """Compute redundancy avoidance score.

    Measures the ratio of unique messages to total messages.
    Returns 1.0 if no messages (no redundancy possible).
    """
    if not messages:
        return 1.0

    total = len(messages)
    unique = len({(m.from_agent, m.to_agent, m.message_type) for m in messages})
    return unique / total


# =============================================================================
# Score Mapping
# =============================================================================


def ratio_to_score(ratio: float) -> float:
    """Map ratio (0.0-1.0) to score (1.0-5.0) linearly."""
    ratio = max(0.0, min(1.0, ratio))
    return round(1.0 + ratio * 4.0, 2)


# =============================================================================
# Composite Score
# =============================================================================

_WEIGHTS = {
    "info_sharing": 0.30,
    "milestone": 0.30,
    "coverage": 0.25,
    "redundancy": 0.15,
}


def compute_composite_score(
    info_sharing: float,
    milestone: float,
    coverage: float,
    redundancy: float,
) -> float:
    """Compute weighted composite score from component ratios.

    Each ratio (0.0-1.0) is mapped to a 1.0-5.0 sub-score, then
    combined with weights.
    """
    composite = (
        _WEIGHTS["info_sharing"] * ratio_to_score(info_sharing)
        + _WEIGHTS["milestone"] * ratio_to_score(milestone)
        + _WEIGHTS["coverage"] * ratio_to_score(coverage)
        + _WEIGHTS["redundancy"] * ratio_to_score(redundancy)
    )
    return round(max(1.0, min(5.0, composite)), 2)


# =============================================================================
# Metric Class
# =============================================================================


class CoordinationQualityMetric:
    """Computes coordination quality across 4 components.

    Evaluates inter-agent information sharing, milestone achievement,
    response coverage, and redundancy avoidance.
    """

    async def compute(
        self,
        scenario: BenchmarkScenario,
        evaluation_run: EvaluationRun,
    ) -> CoordinationQualityResult:
        """Compute coordination quality for a benchmark run."""
        gt = scenario.ground_truth_decisions

        # Extract expected coordination
        expected_msgs, expected_milestones, expected_agents = (
            extract_expected_coordination(gt)
        )

        # Extract actual coordination data
        actual_messages = extract_messages(evaluation_run.agent_decisions)
        actual_milestones = extract_milestones(evaluation_run.agent_decisions)
        actual_agents = {
            d.get("agent_id", "unknown")
            for d in evaluation_run.agent_decisions
            if d.get("agent_id")
        }

        # Compute components
        info_ratio = compute_info_sharing_score(expected_msgs, actual_messages)
        ms_ratio = compute_milestone_score(expected_milestones, actual_milestones)
        cov_ratio = compute_coverage_score(expected_agents, actual_agents)
        red_ratio = compute_redundancy_score(actual_messages)

        # Composite score
        score = compute_composite_score(info_ratio, ms_ratio, cov_ratio, red_ratio)

        component_scores = {
            "info_sharing": ratio_to_score(info_ratio),
            "milestone": ratio_to_score(ms_ratio),
            "coverage": ratio_to_score(cov_ratio),
            "redundancy": ratio_to_score(red_ratio),
        }

        return CoordinationQualityResult(
            info_sharing_ratio=round(info_ratio, 4),
            milestone_ratio=round(ms_ratio, 4),
            coverage_ratio=round(cov_ratio, 4),
            redundancy_ratio=round(red_ratio, 4),
            component_scores=component_scores,
            score=score,
        )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "CoordinationQualityMetric",
    "CoordinationQualityResult",
    "MessageRecord",
    "MilestoneRecord",
    "compute_composite_score",
    "compute_coverage_score",
    "compute_info_sharing_score",
    "compute_milestone_score",
    "compute_redundancy_score",
    "extract_expected_coordination",
    "extract_messages",
    "extract_milestones",
    "ratio_to_score",
]
