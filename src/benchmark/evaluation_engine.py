"""Evaluation engine (LLM-as-judge) for CRISIS-BENCH (spec S8.4).

Uses an LLM-as-judge pattern to evaluate agent decisions from benchmark
scenario runs against ground truth and structured scoring rubrics. Scores
across 5 dimensions and produces an aggregate Disaster Response Score (DRS).

All LLM calls are routed through the LLM Router at the 'critical' tier
(DeepSeek Reasoner as primary judge).
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from src.benchmark.models import (
    BenchmarkScenario,
    DimensionCriteria,
    EvaluationRubric,
    EvaluationRun,
)
from src.shared.telemetry import get_logger

logger = get_logger("benchmark.evaluation_engine")

# =============================================================================
# Constants
# =============================================================================

DIMENSIONS = [
    "situational_accuracy",
    "decision_timeliness",
    "resource_efficiency",
    "coordination_quality",
    "communication_appropriateness",
]

DEFAULT_RUBRIC = EvaluationRubric(
    situational_accuracy=DimensionCriteria(
        weight=0.20,
        criteria={"accuracy": "Match ground truth observations"},
        key_factors=["data coverage", "correctness"],
    ),
    decision_timeliness=DimensionCriteria(
        weight=0.20,
        criteria={"speed": "Decisions within expected time windows"},
        key_factors=["response time"],
    ),
    resource_efficiency=DimensionCriteria(
        weight=0.20,
        criteria={"optimization": "Efficient resource allocation"},
        key_factors=["resource utilization"],
    ),
    coordination_quality=DimensionCriteria(
        weight=0.20,
        criteria={"collaboration": "Effective inter-agent coordination"},
        key_factors=["information sharing"],
    ),
    communication_appropriateness=DimensionCriteria(
        weight=0.20,
        criteria={"clarity": "Clear and appropriate communications"},
        key_factors=["language quality"],
    ),
)

# =============================================================================
# Models
# =============================================================================


class DimensionScore(BaseModel):
    """Score for a single evaluation dimension."""

    dimension: str
    score: float = Field(..., ge=1.0, le=5.0)
    justification: str
    key_factors: list[str] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    """Complete evaluation result across all dimensions."""

    run_id: uuid.UUID
    scenario_id: uuid.UUID
    dimension_scores: dict[str, DimensionScore]
    aggregate_drs: float = Field(..., ge=0.0, le=1.0)
    total_eval_tokens: int = 0
    total_eval_cost_usd: float = 0.0
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC)
    )


# =============================================================================
# Prompt Building
# =============================================================================


def build_evaluation_prompt(
    dimension: str,
    scenario: BenchmarkScenario,
    evaluation_run: EvaluationRun,
) -> list[dict[str, str]]:
    """Build LLM prompt for evaluating one dimension.

    Returns a list of message dicts (system + user) for the LLM.
    """
    rubric = scenario.evaluation_rubric or DEFAULT_RUBRIC
    dim_criteria: DimensionCriteria = getattr(rubric, dimension)

    gt = scenario.ground_truth_decisions

    system_msg = (
        "You are an expert disaster response evaluator for Indian crisis "
        "scenarios. You evaluate agent decisions against NDMA (National "
        "Disaster Management Authority) guidelines and ground truth data.\n\n"
        "You must respond with ONLY a JSON object in this exact format:\n"
        '{"score": <float 1.0-5.0>, "justification": "<string>", '
        '"key_factors": ["<factor1>", "<factor2>"]}\n\n'
        "Score scale:\n"
        "1.0 = Completely inadequate\n"
        "2.0 = Below expectations\n"
        "3.0 = Meets minimum requirements\n"
        "4.0 = Good performance\n"
        "5.0 = Excellent, exceeds expectations"
    )

    criteria_text = "\n".join(
        f"- {k}: {v}" for k, v in dim_criteria.criteria.items()
    )
    factors_text = ", ".join(dim_criteria.key_factors)

    gt_expectations = json.dumps(
        {
            agent: {
                "key_observations": exp.key_observations,
                "expected_actions": exp.expected_actions,
                "time_window_minutes": list(exp.time_window_minutes),
            }
            for agent, exp in gt.agent_expectations.items()
        },
        indent=2,
    )

    gt_timeline = json.dumps(gt.decision_timeline, indent=2)
    ndma_refs = ", ".join(gt.ndma_references) if gt.ndma_references else "None"

    decisions_text = json.dumps(evaluation_run.agent_decisions, indent=2)

    user_msg = (
        f"## Evaluation Dimension: {dimension}\n\n"
        f"### Scenario\n"
        f"Category: {scenario.category}\n"
        f"Complexity: {scenario.complexity}\n"
        f"Affected states: {', '.join(scenario.affected_states)}\n\n"
        f"### Scoring Criteria\n{criteria_text}\n\n"
        f"### Key Factors to Evaluate\n{factors_text}\n\n"
        f"### Ground Truth (Expected Agent Behavior)\n"
        f"Agent expectations:\n{gt_expectations}\n\n"
        f"Decision timeline:\n{gt_timeline}\n\n"
        f"NDMA references: {ndma_refs}\n\n"
        f"### Actual Agent Decisions\n{decisions_text}\n\n"
        f"Evaluate the agent decisions for the **{dimension}** dimension. "
        f"Respond with JSON only."
    )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


# =============================================================================
# Response Parsing
# =============================================================================

_JSON_BLOCK_RE = re.compile(
    r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL
)


def parse_score_response(raw: str, dimension: str) -> DimensionScore:
    """Parse an LLM evaluation response into a DimensionScore.

    Handles:
    - Clean JSON
    - JSON embedded in markdown code blocks
    - Malformed/missing responses (returns score=1.0)
    """
    json_str = raw.strip()

    # Try extracting from code block first
    match = _JSON_BLOCK_RE.search(json_str)
    if match:
        json_str = match.group(1).strip()

    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        logger.warning(
            "score_parse_failed",
            dimension=dimension,
            raw_length=len(raw),
        )
        return DimensionScore(
            dimension=dimension,
            score=1.0,
            justification="Failed to parse LLM response",
            key_factors=[],
        )

    if "score" not in data:
        return DimensionScore(
            dimension=dimension,
            score=1.0,
            justification="LLM response missing 'score' field",
            key_factors=[],
        )

    score = float(data["score"])
    score = max(1.0, min(5.0, score))  # Clamp to valid range

    return DimensionScore(
        dimension=dimension,
        score=score,
        justification=str(data.get("justification", "")),
        key_factors=data.get("key_factors", []),
    )


# =============================================================================
# Evaluation Engine
# =============================================================================


class EvaluationEngine:
    """LLM-as-judge evaluation engine for benchmark runs.

    Evaluates agent decisions across 5 dimensions using the LLM Router
    and produces an aggregate Disaster Response Score (DRS).
    """

    def __init__(self, router: Any) -> None:
        self._router = router

    async def evaluate_dimension(
        self,
        dimension: str,
        scenario: BenchmarkScenario,
        evaluation_run: EvaluationRun,
    ) -> DimensionScore:
        """Evaluate a single dimension using LLM-as-judge."""
        messages = build_evaluation_prompt(dimension, scenario, evaluation_run)

        try:
            response = await self._router.call(
                "critical", messages, max_tokens=1024,
            )
            return parse_score_response(response.content, dimension)
        except Exception as exc:
            logger.warning(
                "dimension_eval_failed",
                dimension=dimension,
                error=str(exc),
            )
            return DimensionScore(
                dimension=dimension,
                score=1.0,
                justification=f"Evaluation failed: {exc}",
                key_factors=[],
            )

    async def evaluate(
        self,
        scenario: BenchmarkScenario,
        evaluation_run: EvaluationRun,
    ) -> EvaluationResult:
        """Evaluate all 5 dimensions and compute aggregate DRS."""
        rubric = scenario.evaluation_rubric or DEFAULT_RUBRIC
        dimension_scores: dict[str, DimensionScore] = {}
        total_tokens = 0
        total_cost = 0.0

        for dimension in DIMENSIONS:
            messages = build_evaluation_prompt(
                dimension, scenario, evaluation_run,
            )
            try:
                response = await self._router.call(
                    "critical", messages, max_tokens=1024,
                )
                score = parse_score_response(response.content, dimension)
                total_tokens += response.input_tokens + response.output_tokens
                total_cost += response.cost_usd
            except Exception as exc:
                logger.warning(
                    "dimension_eval_failed",
                    dimension=dimension,
                    error=str(exc),
                )
                score = DimensionScore(
                    dimension=dimension,
                    score=1.0,
                    justification=f"Evaluation failed: {exc}",
                    key_factors=[],
                )

            dimension_scores[dimension] = score

        aggregate_drs = self._compute_drs(dimension_scores, rubric)

        return EvaluationResult(
            run_id=evaluation_run.id,
            scenario_id=evaluation_run.scenario_id,
            dimension_scores=dimension_scores,
            aggregate_drs=aggregate_drs,
            total_eval_tokens=total_tokens,
            total_eval_cost_usd=total_cost,
        )

    async def batch_evaluate(
        self,
        scenario: BenchmarkScenario,
        runs: list[EvaluationRun],
    ) -> list[EvaluationResult]:
        """Evaluate multiple runs for the same scenario."""
        results = []
        for run in runs:
            result = await self.evaluate(scenario, run)
            results.append(result)
        return results

    @staticmethod
    def _compute_drs(
        scores: dict[str, DimensionScore],
        rubric: EvaluationRubric,
    ) -> float:
        """Compute aggregate DRS as weighted sum normalized to 0-1.

        DRS = sum(score_i * weight_i) / 5.0
        where scores are 1-5 and weights sum to 1.0.
        """
        weighted_sum = 0.0
        for dimension in DIMENSIONS:
            dim_criteria: DimensionCriteria = getattr(rubric, dimension)
            dim_score = scores.get(dimension)
            if dim_score:
                weighted_sum += dim_score.score * dim_criteria.weight

        return round(min(1.0, max(0.0, weighted_sum / 5.0)), 4)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "DIMENSIONS",
    "DimensionScore",
    "EvaluationEngine",
    "EvaluationResult",
    "build_evaluation_prompt",
    "parse_score_response",
]
