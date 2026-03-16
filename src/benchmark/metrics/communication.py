"""Communication Appropriateness metric for CRISIS-BENCH (spec S8.9).

Evaluates how well agents generate crisis communications by scoring
five sub-dimensions: language match, NDMA adherence, audience fit,
actionable content, and channel formatting.

Maps a weighted composite to a 1.0-5.0 score for integration with
the aggregate Disaster Response Score (DRS).
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


class CommunicationEntry(BaseModel):
    """A single crisis communication produced by an agent."""

    language: str
    audience: str
    channel: str
    content: str
    helplines_included: list[str] = Field(default_factory=list)
    shelter_info: bool = False
    evacuation_routes: bool = False


class SubDimensionScore(BaseModel):
    """Score for one communication sub-dimension."""

    name: str
    score: float = Field(..., ge=1.0, le=5.0)
    coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    details: list[str] = Field(default_factory=list)


class CommunicationAppropriatenessResult(BaseModel):
    """Complete communication appropriateness evaluation result."""

    sub_scores: dict[str, SubDimensionScore] = Field(default_factory=dict)
    score: float = Field(..., ge=1.0, le=5.0)
    languages_expected: list[str] = Field(default_factory=list)
    languages_found: list[str] = Field(default_factory=list)
    communications_count: int = Field(default=0, ge=0)


# =============================================================================
# Weights
# =============================================================================

_WEIGHTS = {
    "language_match": 0.25,
    "ndma_adherence": 0.25,
    "audience_fit": 0.20,
    "actionable_content": 0.20,
    "channel_format": 0.10,
}

# =============================================================================
# Extraction
# =============================================================================

_KV_RE = re.compile(r"^(\w+)=(.+)$")


def extract_communication_expectations(
    ground_truth: GroundTruthDecisions,
) -> dict[str, list[str]]:
    """Extract communication expectations from ground truth key_observations.

    Parses key=value pairs like 'expected_languages=hindi,odia'.
    """
    result: dict[str, list[str]] = {
        "expected_languages": [],
        "expected_audiences": [],
        "expected_channels": [],
        "expected_helplines": [],
        "ndma_guidelines": [],
    }

    comms_exp = ground_truth.agent_expectations.get("community_comms")
    if comms_exp is None:
        return result

    for obs in comms_exp.key_observations:
        match = _KV_RE.match(obs.strip())
        if match:
            key, val = match.group(1), match.group(2)
            if key in result:
                result[key] = [v.strip() for v in val.split(",") if v.strip()]

    return result


def extract_communications_from_decisions(
    decisions: list[dict[str, Any]],
) -> tuple[list[CommunicationEntry], dict[str, list[str]]]:
    """Extract communications and metadata from agent decisions.

    Returns (communications, meta) where meta contains languages_used,
    audiences_addressed, channels_formatted, ndma_references.
    """
    default_meta: dict[str, list[str]] = {
        "languages_used": [],
        "audiences_addressed": [],
        "channels_formatted": [],
        "ndma_references": [],
    }

    for decision in decisions:
        if decision.get("agent_id") != "community_comms":
            continue

        comms_data = decision.get("communications", [])
        entries: list[CommunicationEntry] = []
        for item in comms_data:
            try:
                entries.append(CommunicationEntry(**item))
            except (TypeError, ValueError):
                continue

        meta: dict[str, list[str]] = {
            "languages_used": decision.get("languages_used", []),
            "audiences_addressed": decision.get("audiences_addressed", []),
            "channels_formatted": decision.get("channels_formatted", []),
            "ndma_references": decision.get("ndma_references", []),
        }
        return entries, meta

    return [], default_meta


# =============================================================================
# Sub-Dimension Scoring
# =============================================================================


def _coverage_to_score(coverage: float) -> float:
    """Map coverage (0.0-1.0) to score (1.0-5.0) linearly."""
    return round(1.0 + coverage * 4.0, 2)


def score_language_match(
    expected: list[str],
    actual: list[str],
) -> SubDimensionScore:
    """Score language coverage."""
    if not expected:
        return SubDimensionScore(
            name="language_match", score=3.0, coverage=0.0,
            details=["No expected languages specified"],
        )

    if not actual:
        return SubDimensionScore(
            name="language_match", score=1.0, coverage=0.0,
            details=["No languages produced"],
        )

    expected_set = {lang.lower() for lang in expected}
    actual_set = {lang.lower() for lang in actual}
    covered = expected_set & actual_set
    coverage = len(covered) / len(expected_set)

    details = [f"{lang} covered" for lang in sorted(covered)]
    missing = expected_set - actual_set
    if missing:
        details.extend(f"{lang} missing" for lang in sorted(missing))

    return SubDimensionScore(
        name="language_match",
        score=_coverage_to_score(coverage),
        coverage=round(coverage, 4),
        details=details,
    )


def score_ndma_adherence(
    expected_refs: list[str],
    actual_refs: list[str],
) -> SubDimensionScore:
    """Score NDMA guideline adherence."""
    if not expected_refs:
        return SubDimensionScore(
            name="ndma_adherence", score=3.0, coverage=0.0,
            details=["No expected NDMA references"],
        )

    if not actual_refs:
        return SubDimensionScore(
            name="ndma_adherence", score=1.0, coverage=0.0,
            details=["No NDMA references found"],
        )

    expected_set = {r.upper() for r in expected_refs}
    actual_set = {r.upper() for r in actual_refs}
    covered = expected_set & actual_set
    coverage = len(covered) / len(expected_set)

    return SubDimensionScore(
        name="ndma_adherence",
        score=_coverage_to_score(coverage),
        coverage=round(coverage, 4),
        details=[f"{ref} referenced" for ref in sorted(covered)],
    )


def score_audience_fit(
    expected: list[str],
    actual: list[str],
) -> SubDimensionScore:
    """Score audience coverage."""
    if not expected:
        return SubDimensionScore(
            name="audience_fit", score=3.0, coverage=0.0,
            details=["No expected audiences specified"],
        )

    if not actual:
        return SubDimensionScore(
            name="audience_fit", score=1.0, coverage=0.0,
            details=["No audiences addressed"],
        )

    expected_set = {a.lower() for a in expected}
    actual_set = {a.lower() for a in actual}
    covered = expected_set & actual_set
    coverage = len(covered) / len(expected_set)

    return SubDimensionScore(
        name="audience_fit",
        score=_coverage_to_score(coverage),
        coverage=round(coverage, 4),
        details=[f"{aud} addressed" for aud in sorted(covered)],
    )


def score_actionable_content(
    communications: list[CommunicationEntry],
    expected_helplines: list[str],
) -> SubDimensionScore:
    """Score actionable content (helplines, shelter info, evacuation routes)."""
    if not communications:
        return SubDimensionScore(
            name="actionable_content", score=1.0, coverage=0.0,
            details=["No communications to evaluate"],
        )

    # Collect across all communications
    all_helplines: set[str] = set()
    has_shelter = False
    has_routes = False
    for comm in communications:
        all_helplines.update(comm.helplines_included)
        if comm.shelter_info:
            has_shelter = True
        if comm.evacuation_routes:
            has_routes = True

    # Score components (3 components: helplines, shelter, routes)
    components: list[float] = []

    # Helplines coverage
    if expected_helplines:
        expected_set = set(expected_helplines)
        helpline_coverage = len(all_helplines & expected_set) / len(expected_set)
        components.append(helpline_coverage)
    # If no expected helplines, only evaluate shelter + routes

    # Shelter info
    components.append(1.0 if has_shelter else 0.0)

    # Evacuation routes
    components.append(1.0 if has_routes else 0.0)

    if not components:
        return SubDimensionScore(
            name="actionable_content", score=1.0, coverage=0.0,
        )

    coverage = sum(components) / len(components)
    return SubDimensionScore(
        name="actionable_content",
        score=_coverage_to_score(coverage),
        coverage=round(coverage, 4),
    )


def score_channel_format(
    expected: list[str],
    actual: list[str],
) -> SubDimensionScore:
    """Score channel format coverage."""
    if not expected:
        return SubDimensionScore(
            name="channel_format", score=3.0, coverage=0.0,
            details=["No expected channels specified"],
        )

    if not actual:
        return SubDimensionScore(
            name="channel_format", score=1.0, coverage=0.0,
            details=["No channels formatted"],
        )

    expected_set = {c.lower() for c in expected}
    actual_set = {c.lower() for c in actual}
    covered = expected_set & actual_set
    coverage = len(covered) / len(expected_set)

    return SubDimensionScore(
        name="channel_format",
        score=_coverage_to_score(coverage),
        coverage=round(coverage, 4),
        details=[f"{ch} formatted" for ch in sorted(covered)],
    )


# =============================================================================
# Composite Score
# =============================================================================


def compute_communication_score(
    sub_scores: dict[str, SubDimensionScore],
) -> float:
    """Compute weighted composite from sub-dimension scores."""
    weighted_sum = 0.0
    for name, weight in _WEIGHTS.items():
        sub = sub_scores.get(name)
        if sub:
            weighted_sum += sub.score * weight

    return round(max(1.0, min(5.0, weighted_sum)), 2)


# =============================================================================
# Metric Class
# =============================================================================


class CommunicationAppropriatenessMetric:
    """Computes communication appropriateness across 5 sub-dimensions.

    Evaluates language match, NDMA adherence, audience fit,
    actionable content, and channel formatting.
    """

    async def compute(
        self,
        scenario: BenchmarkScenario,
        evaluation_run: EvaluationRun,
    ) -> CommunicationAppropriatenessResult:
        """Compute communication appropriateness for a benchmark run."""
        expectations = extract_communication_expectations(
            scenario.ground_truth_decisions,
        )
        communications, meta = extract_communications_from_decisions(
            evaluation_run.agent_decisions,
        )

        # Score each sub-dimension
        lang_score = score_language_match(
            expected=expectations["expected_languages"],
            actual=meta["languages_used"],
        )

        ndma_score = score_ndma_adherence(
            expected_refs=expectations["ndma_guidelines"],
            actual_refs=meta["ndma_references"],
        )

        audience_score = score_audience_fit(
            expected=expectations["expected_audiences"],
            actual=meta["audiences_addressed"],
        )

        actionable_score = score_actionable_content(
            communications=communications,
            expected_helplines=expectations["expected_helplines"],
        )

        channel_score = score_channel_format(
            expected=expectations["expected_channels"],
            actual=meta["channels_formatted"],
        )

        sub_scores = {
            "language_match": lang_score,
            "ndma_adherence": ndma_score,
            "audience_fit": audience_score,
            "actionable_content": actionable_score,
            "channel_format": channel_score,
        }

        composite = compute_communication_score(sub_scores)

        return CommunicationAppropriatenessResult(
            sub_scores=sub_scores,
            score=composite,
            languages_expected=expectations["expected_languages"],
            languages_found=meta["languages_used"],
            communications_count=len(communications),
        )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "CommunicationAppropriatenessMetric",
    "CommunicationAppropriatenessResult",
    "CommunicationEntry",
    "SubDimensionScore",
    "compute_communication_score",
    "extract_communication_expectations",
    "extract_communications_from_decisions",
    "score_actionable_content",
    "score_audience_fit",
    "score_channel_format",
    "score_language_match",
    "score_ndma_adherence",
]
