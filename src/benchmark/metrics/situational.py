"""Situational Accuracy metric for CRISIS-BENCH (spec S8.5).

Computes precision/recall/F1 by comparing agent-reported observations
against ground truth key observations from IMD/CWC bulletins. Uses
keyword-based Jaccard similarity for matching (optionally LLM-based).

Maps F1 to a 1.0-5.0 score with linear interpolation between bands.
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


class ObservationMatch(BaseModel):
    """A matched pair of expected and actual observations."""

    expected: str
    actual: str
    similarity: float = Field(..., ge=0.0, le=1.0)


class AgentAccuracyScore(BaseModel):
    """Precision/recall/F1 for a single agent."""

    agent_id: str
    precision: float = Field(..., ge=0.0, le=1.0)
    recall: float = Field(..., ge=0.0, le=1.0)
    f1: float = Field(..., ge=0.0, le=1.0)
    matched: int = Field(..., ge=0)
    expected_total: int = Field(..., ge=0)
    actual_total: int = Field(..., ge=0)


class SituationalAccuracyResult(BaseModel):
    """Complete situational accuracy result."""

    precision: float = Field(..., ge=0.0, le=1.0)
    recall: float = Field(..., ge=0.0, le=1.0)
    f1: float = Field(..., ge=0.0, le=1.0)
    score: float = Field(..., ge=1.0, le=5.0)
    matched_observations: list[ObservationMatch] = Field(default_factory=list)
    unmatched_expected: list[str] = Field(default_factory=list)
    unmatched_actual: list[str] = Field(default_factory=list)
    per_agent_scores: dict[str, AgentAccuracyScore] = Field(default_factory=dict)


class MatchResult:
    """Internal result from match_observations."""

    __slots__ = ("matched", "unmatched_expected", "unmatched_actual")

    def __init__(
        self,
        matched: list[ObservationMatch],
        unmatched_expected: list[str],
        unmatched_actual: list[str],
    ) -> None:
        self.matched = matched
        self.unmatched_expected = unmatched_expected
        self.unmatched_actual = unmatched_actual


# =============================================================================
# Keyword Similarity
# =============================================================================

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    """Lowercase and extract alphanumeric tokens."""
    return set(_WORD_RE.findall(text.lower()))


def keyword_similarity(a: str, b: str) -> float:
    """Compute Jaccard similarity between two strings based on keyword overlap.

    Returns 0.0 for empty strings, 1.0 for identical token sets.
    """
    tokens_a = _tokenize(a)
    tokens_b = _tokenize(b)

    if not tokens_a or not tokens_b:
        return 0.0

    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b

    return len(intersection) / len(union) if union else 0.0


# =============================================================================
# Observation Extraction
# =============================================================================


def extract_expected_observations(
    ground_truth: GroundTruthDecisions,
) -> dict[str, list[str]]:
    """Extract per-agent expected observations from ground truth."""
    result: dict[str, list[str]] = {}
    for agent_id, expectation in ground_truth.agent_expectations.items():
        if expectation.key_observations:
            result[agent_id] = list(expectation.key_observations)
    return result


def extract_observations_from_decisions(
    decisions: list[dict[str, Any]],
) -> dict[str, list[str]]:
    """Extract per-agent observations from agent decision records.

    Looks for an 'observations' field first; falls back to using
    the 'reasoning' field as a single observation.
    """
    result: dict[str, list[str]] = {}
    for decision in decisions:
        agent_id = decision.get("agent_id", "unknown")
        obs = decision.get("observations")
        if obs and isinstance(obs, list):
            result.setdefault(agent_id, []).extend(obs)
        elif "reasoning" in decision and decision["reasoning"]:
            result.setdefault(agent_id, []).append(decision["reasoning"])
    return result


# =============================================================================
# Observation Matching
# =============================================================================


def match_observations(
    expected: list[str],
    actual: list[str],
    threshold: float = 0.5,
) -> MatchResult:
    """Match actual observations against expected using keyword similarity.

    Uses greedy best-first matching: finds the highest-similarity pair,
    matches them, removes both from consideration, repeats. Each observation
    can match at most once (no double counting).
    """
    if not expected or not actual:
        return MatchResult(
            matched=[],
            unmatched_expected=list(expected),
            unmatched_actual=list(actual),
        )

    # Compute all pairwise similarities
    pairs: list[tuple[float, int, int]] = []
    for i, exp in enumerate(expected):
        for j, act in enumerate(actual):
            sim = keyword_similarity(exp, act)
            if sim >= threshold:
                pairs.append((sim, i, j))

    # Sort by similarity descending (greedy best-first)
    pairs.sort(key=lambda x: x[0], reverse=True)

    matched_exp: set[int] = set()
    matched_act: set[int] = set()
    matches: list[ObservationMatch] = []

    for sim, i, j in pairs:
        if i in matched_exp or j in matched_act:
            continue
        matches.append(ObservationMatch(
            expected=expected[i],
            actual=actual[j],
            similarity=round(sim, 4),
        ))
        matched_exp.add(i)
        matched_act.add(j)

    unmatched_expected = [expected[i] for i in range(len(expected)) if i not in matched_exp]
    unmatched_actual = [actual[j] for j in range(len(actual)) if j not in matched_act]

    return MatchResult(
        matched=matches,
        unmatched_expected=unmatched_expected,
        unmatched_actual=unmatched_actual,
    )


# =============================================================================
# Precision / Recall / F1
# =============================================================================


def compute_precision_recall_f1(
    matched: int,
    expected_total: int,
    actual_total: int,
) -> tuple[float, float, float]:
    """Compute precision, recall, and F1.

    Returns (0.0, 0.0, 0.0) when denominators are zero.
    """
    precision = matched / actual_total if actual_total > 0 else 0.0
    recall = matched / expected_total if expected_total > 0 else 0.0

    if precision + recall > 0:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = 0.0

    return (round(precision, 4), round(recall, 4), round(f1, 4))


# =============================================================================
# F1 → Score Mapping
# =============================================================================

# Bands: (f1_lower, f1_upper, score_lower, score_upper)
_SCORE_BANDS: list[tuple[float, float, float, float]] = [
    (0.9, 1.0, 5.0, 5.0),
    (0.7, 0.9, 4.0, 5.0),
    (0.5, 0.7, 3.0, 4.0),
    (0.3, 0.5, 2.0, 3.0),
    (0.0, 0.3, 1.0, 2.0),
]


def f1_to_score(f1: float) -> float:
    """Map F1 (0.0-1.0) to score (1.0-5.0) with linear interpolation."""
    f1 = max(0.0, min(1.0, f1))

    for f1_lo, f1_hi, score_lo, score_hi in _SCORE_BANDS:
        if f1 >= f1_lo:
            if f1_hi == f1_lo:
                return score_hi
            t = (f1 - f1_lo) / (f1_hi - f1_lo)
            return round(score_lo + t * (score_hi - score_lo), 2)

    return 1.0


# =============================================================================
# Metric Class
# =============================================================================


class SituationalAccuracyMetric:
    """Computes situational accuracy as precision/recall/F1.

    Compares agent-reported observations against ground truth
    expected observations using keyword-based Jaccard similarity.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.5,
        router: Any = None,
    ) -> None:
        self._threshold = similarity_threshold
        self._router = router  # Reserved for future LLM-based matching

    async def compute(
        self,
        scenario: BenchmarkScenario,
        evaluation_run: EvaluationRun,
    ) -> SituationalAccuracyResult:
        """Compute situational accuracy for a benchmark run."""
        expected_by_agent = extract_expected_observations(
            scenario.ground_truth_decisions,
        )
        actual_by_agent = extract_observations_from_decisions(
            evaluation_run.agent_decisions,
        )

        # Flatten for global precision/recall/F1
        all_expected: list[str] = []
        all_actual: list[str] = []
        for obs_list in expected_by_agent.values():
            all_expected.extend(obs_list)
        for obs_list in actual_by_agent.values():
            all_actual.extend(obs_list)

        # Global matching
        global_match = match_observations(all_expected, all_actual, self._threshold)
        precision, recall, f1 = compute_precision_recall_f1(
            matched=len(global_match.matched),
            expected_total=len(all_expected),
            actual_total=len(all_actual),
        )

        # Per-agent breakdown
        per_agent: dict[str, AgentAccuracyScore] = {}
        all_agents = set(expected_by_agent.keys()) | set(actual_by_agent.keys())
        for agent_id in all_agents:
            agent_expected = expected_by_agent.get(agent_id, [])
            agent_actual = actual_by_agent.get(agent_id, [])
            agent_match = match_observations(
                agent_expected, agent_actual, self._threshold,
            )
            ap, ar, af = compute_precision_recall_f1(
                matched=len(agent_match.matched),
                expected_total=len(agent_expected),
                actual_total=len(agent_actual),
            )
            per_agent[agent_id] = AgentAccuracyScore(
                agent_id=agent_id,
                precision=ap,
                recall=ar,
                f1=af,
                matched=len(agent_match.matched),
                expected_total=len(agent_expected),
                actual_total=len(agent_actual),
            )

        score = f1_to_score(f1)

        return SituationalAccuracyResult(
            precision=precision,
            recall=recall,
            f1=f1,
            score=score,
            matched_observations=global_match.matched,
            unmatched_expected=global_match.unmatched_expected,
            unmatched_actual=global_match.unmatched_actual,
            per_agent_scores=per_agent,
        )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "AgentAccuracyScore",
    "MatchResult",
    "ObservationMatch",
    "SituationalAccuracyMetric",
    "SituationalAccuracyResult",
    "compute_precision_recall_f1",
    "extract_expected_observations",
    "extract_observations_from_decisions",
    "f1_to_score",
    "keyword_similarity",
    "match_observations",
]
