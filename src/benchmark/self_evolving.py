"""Self-evolving benchmark generator for CRISIS-BENCH (spec S8.11).

Auto-generates new scenario variants using perturbation operations (COLING 2025),
detects data contamination via performance anomaly analysis, and creates
scenarios from historical Indian disaster data.

Downstream consumers: benchmark runner, evaluation engine.
"""

from __future__ import annotations

import math
import random
import uuid
from datetime import UTC, datetime
from typing import Any

from src.benchmark.models import BenchmarkScenario, ScenarioEvent
from src.shared.models import DisasterPhase
from src.shared.telemetry import get_logger

logger = get_logger("benchmark.self_evolving")

# =============================================================================
# Constants
# =============================================================================

PERTURBATION_OPS = (
    "geographic_swap",
    "temporal_shift",
    "resource_constraint",
    "cascading_injection",
    "communication_degradation",
)

# Resource keys that can be reduced
_RESOURCE_KEYS = ("ndrf_battalions", "shelters_available", "medical_teams", "boats")

# Minimum number of evaluation runs needed for contamination detection
_MIN_RUNS_FOR_DETECTION = 3

# Z-score threshold for flagging contamination (2 std devs)
_CONTAMINATION_Z_THRESHOLD = 2.0

# Historical disaster contexts for generation
HISTORICAL_CONTEXTS: list[dict[str, str]] = [
    {
        "category": "cyclone",
        "context": "Cyclone Fani hit Odisha in May 2019, Category 4, 1.2M evacuated",
    },
    {
        "category": "monsoon_flood",
        "context": "Kerala floods August 2018, worst in 100 years, 483 deaths",
    },
    {
        "category": "earthquake",
        "context": "Gujarat earthquake January 2001, M7.7, Bhuj epicenter, 20K deaths",
    },
    {
        "category": "heatwave",
        "context": "Andhra Pradesh heatwave May 2015, 2500+ deaths, 48C temperatures",
    },
    {
        "category": "landslide",
        "context": "Wayanad landslide July 2024, Kerala, 400+ missing, heavy monsoon",
    },
]


# =============================================================================
# Perturbation Operations
# =============================================================================


def _clone_scenario(scenario: BenchmarkScenario) -> BenchmarkScenario:
    """Deep copy a scenario with a new ID, version=1, source=perturbation."""
    data = scenario.model_dump(mode="json")
    data["id"] = str(uuid.uuid4())
    data["version"] = 1
    data["source"] = "perturbation"
    data["created_at"] = datetime.now(tz=UTC).isoformat()
    return BenchmarkScenario.model_validate(data)


async def perturb_geographic_swap(
    scenario: BenchmarkScenario,
    target_states: list[str],
    target_language: str | None = None,
) -> BenchmarkScenario:
    """Swap geography: change affected states and language.

    Preserves: category, severity, event structure, complexity.
    Changes: affected_states, primary_language.
    """
    result = _clone_scenario(scenario)
    result.affected_states = list(target_states)
    if target_language:
        result.primary_language = target_language

    logger.info(
        "perturbation_geographic_swap",
        original_states=scenario.affected_states,
        target_states=target_states,
    )
    return result


async def perturb_temporal_shift(
    scenario: BenchmarkScenario,
    target_season: str,
    target_time: str | None = None,
) -> BenchmarkScenario:
    """Shift temporal context: change season and/or time of day.

    Preserves: geography, disaster type, event structure.
    Changes: season, time_of_day in initial_state.
    """
    result = _clone_scenario(scenario)
    result.initial_state["season"] = target_season
    if target_time:
        result.initial_state["time_of_day"] = target_time

    logger.info(
        "perturbation_temporal_shift",
        target_season=target_season,
        target_time=target_time,
    )
    return result


async def perturb_resource_constraint(
    scenario: BenchmarkScenario,
    reduction_factor: float = 0.5,
) -> BenchmarkScenario:
    """Reduce available resources by a factor (0.3 = 30% reduction).

    Preserves: scenario structure, geography, category.
    Changes: resource quantities in initial_state (floor, min 1).
    """
    result = _clone_scenario(scenario)

    for key in _RESOURCE_KEYS:
        if key in result.initial_state:
            original_val = result.initial_state[key]
            if isinstance(original_val, (int, float)):
                reduced = int(original_val * (1.0 - reduction_factor))
                result.initial_state[key] = max(1, reduced)

    logger.info(
        "perturbation_resource_constraint",
        reduction_factor=reduction_factor,
    )
    return result


async def perturb_cascading_injection(
    scenario: BenchmarkScenario,
    secondary_type: str,
    secondary_description: str,
) -> BenchmarkScenario:
    """Inject a secondary disaster event into the scenario.

    Preserves: all original events.
    Adds: one new event of the secondary type during active_response phase.
    Events are re-sorted chronologically.
    """
    result = _clone_scenario(scenario)

    # Place secondary event midway through existing timeline
    if result.event_sequence:
        max_offset = max(e.time_offset_minutes for e in result.event_sequence)
        inject_offset = max_offset // 2 + 30  # midpoint + 30 min
    else:
        inject_offset = 60

    secondary_event = ScenarioEvent(
        time_offset_minutes=inject_offset,
        phase=DisasterPhase.ACTIVE_RESPONSE,
        event_type=secondary_type,
        description=secondary_description,
        data_payload={"cascading": True, "secondary_disaster": True},
    )
    result.event_sequence.append(secondary_event)

    # Re-sort chronologically
    result.event_sequence.sort(key=lambda e: e.time_offset_minutes)

    logger.info(
        "perturbation_cascading_injection",
        secondary_type=secondary_type,
        inject_offset=inject_offset,
    )
    return result


async def perturb_communication_degradation(
    scenario: BenchmarkScenario,
) -> BenchmarkScenario:
    """Simulate telecom/internet failure.

    Preserves: all original events.
    Adds: telecom_failure event and marks initial_state.
    """
    result = _clone_scenario(scenario)

    # Mark initial state
    result.initial_state["telecom_degraded"] = True

    # Add telecom failure event early in active response
    if result.event_sequence:
        first_active = next(
            (
                e.time_offset_minutes
                for e in result.event_sequence
                if e.phase == DisasterPhase.ACTIVE_RESPONSE
            ),
            60,
        )
        failure_offset = max(0, first_active - 15)
    else:
        failure_offset = 45

    failure_event = ScenarioEvent(
        time_offset_minutes=failure_offset,
        phase=DisasterPhase.ACTIVE_RESPONSE,
        event_type="telecom_failure",
        description="Mobile network towers damaged, internet connectivity lost in affected area",
        data_payload={"services_affected": ["mobile", "internet", "landline"]},
    )
    result.event_sequence.append(failure_event)
    result.event_sequence.sort(key=lambda e: e.time_offset_minutes)

    logger.info("perturbation_communication_degradation")
    return result


# =============================================================================
# Contamination Detection
# =============================================================================


async def detect_contamination(
    runs_by_scenario: dict[uuid.UUID, list[Any]],
) -> set[uuid.UUID]:
    """Detect potential data contamination via performance anomaly analysis.

    Algorithm:
    1. For each scenario, collect aggregate_drs scores from evaluation runs
    2. Need at least _MIN_RUNS_FOR_DETECTION runs to analyze
    3. Compute mean and std dev of all runs except the latest
    4. Flag if latest score > mean + _CONTAMINATION_Z_THRESHOLD * std
       AND the model config has NOT changed between runs

    Args:
        runs_by_scenario: Mapping of scenario_id -> list of EvaluationRun

    Returns:
        Set of scenario IDs flagged for potential contamination.
    """
    flagged: set[uuid.UUID] = set()

    for scenario_id, runs in runs_by_scenario.items():
        if len(runs) < _MIN_RUNS_FOR_DETECTION:
            continue

        # Extract scores
        scores = [r.aggregate_drs for r in runs if r.aggregate_drs is not None]
        if len(scores) < _MIN_RUNS_FOR_DETECTION:
            continue

        # Check if model config changed between second-to-last and last run
        latest_run = runs[-1]
        previous_run = runs[-2]
        if latest_run.agent_config != previous_run.agent_config:
            # Model changed — performance jump is expected, not contamination
            continue

        # Compute stats on all scores except the latest
        historical_scores = scores[:-1]
        latest_score = scores[-1]

        mean = sum(historical_scores) / len(historical_scores)
        variance = sum((s - mean) ** 2 for s in historical_scores) / len(historical_scores)
        std = math.sqrt(variance) if variance > 0 else 0.0

        if std == 0:
            # All historical scores identical; any change is suspicious
            if latest_score > mean * 1.15:
                flagged.add(scenario_id)
            continue

        z_score = (latest_score - mean) / std
        if z_score > _CONTAMINATION_Z_THRESHOLD:
            logger.warning(
                "contamination_detected",
                scenario_id=str(scenario_id),
                mean=round(mean, 4),
                std=round(std, 4),
                latest_score=round(latest_score, 4),
                z_score=round(z_score, 2),
            )
            flagged.add(scenario_id)

    return flagged


# =============================================================================
# Self-Evolving Generator
# =============================================================================


class SelfEvolvingGenerator:
    """Orchestrates self-evolving benchmark generation.

    Combines perturbation operations, contamination detection, and
    historical scenario generation into a single evolution cycle.
    """

    def __init__(
        self,
        router: Any,
        scenario_generator: Any | None = None,
        scenario_manager: Any | None = None,
    ) -> None:
        self._router = router
        self._generator = scenario_generator
        self._manager = scenario_manager

    async def generate_from_historical(
        self,
        category: str,
        complexity: str,
        historical_context: str,
    ) -> BenchmarkScenario:
        """Generate a scenario inspired by historical disaster data.

        Uses the underlying ScenarioGenerator and marks source as 'historical'.
        """
        scenario = await self._generator.generate_scenario(category, complexity)
        scenario.source = "historical"

        logger.info(
            "generated_from_historical",
            category=category,
            complexity=complexity,
            historical_context=historical_context[:100],
        )
        return scenario

    async def evolve_benchmark(
        self,
        num_perturbations: int = 5,
        num_historical: int = 3,
    ) -> list[BenchmarkScenario]:
        """Run a full benchmark evolution cycle.

        1. Select existing scenarios for perturbation
        2. Apply random perturbation operations
        3. Generate new scenarios from historical contexts

        Args:
            num_perturbations: Number of perturbation variants to create.
            num_historical: Number of historical scenarios to generate.

        Returns:
            List of newly created BenchmarkScenario objects.
        """
        new_scenarios: list[BenchmarkScenario] = []

        # Phase 1: Perturbation of existing scenarios
        if self._manager is not None:
            existing = await self._manager.search(limit=50)
            if existing:
                for _ in range(min(num_perturbations, len(existing))):
                    source = random.choice(existing)
                    op = random.choice(PERTURBATION_OPS)
                    perturbed = await self._apply_random_perturbation(source, op)
                    if perturbed:
                        new_scenarios.append(perturbed)

        # Phase 2: Historical generation
        if self._generator is not None:
            contexts = random.sample(
                HISTORICAL_CONTEXTS,
                min(num_historical, len(HISTORICAL_CONTEXTS)),
            )
            for ctx in contexts:
                try:
                    scenario = await self.generate_from_historical(
                        category=ctx["category"],
                        complexity=random.choice(["low", "medium", "high"]),
                        historical_context=ctx["context"],
                    )
                    new_scenarios.append(scenario)
                except Exception as exc:
                    logger.warning(
                        "historical_generation_failed",
                        category=ctx["category"],
                        error=str(exc),
                    )

        logger.info(
            "evolve_benchmark_complete",
            total_new=len(new_scenarios),
            perturbations=num_perturbations,
            historical=num_historical,
        )
        return new_scenarios

    async def _apply_random_perturbation(
        self,
        scenario: BenchmarkScenario,
        operation: str,
    ) -> BenchmarkScenario | None:
        """Apply a perturbation operation to a scenario."""
        try:
            if operation == "geographic_swap":
                target = random.choice(
                    ["Tamil Nadu", "Gujarat", "West Bengal", "Kerala", "Maharashtra"]
                )
                return await perturb_geographic_swap(scenario, target_states=[target])
            elif operation == "temporal_shift":
                season = random.choice(
                    ["January", "April", "July", "October"]
                )
                return await perturb_temporal_shift(scenario, target_season=season)
            elif operation == "resource_constraint":
                factor = random.uniform(0.3, 0.5)
                return await perturb_resource_constraint(scenario, reduction_factor=factor)
            elif operation == "cascading_injection":
                return await perturb_cascading_injection(
                    scenario,
                    secondary_type="power_failure",
                    secondary_description="Regional power grid failure during disaster",
                )
            elif operation == "communication_degradation":
                return await perturb_communication_degradation(scenario)
            else:
                logger.warning("unknown_perturbation_op", operation=operation)
                return None
        except Exception as exc:
            logger.warning(
                "perturbation_failed",
                operation=operation,
                error=str(exc),
            )
            return None


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "HISTORICAL_CONTEXTS",
    "PERTURBATION_OPS",
    "SelfEvolvingGenerator",
    "detect_contamination",
    "perturb_cascading_injection",
    "perturb_communication_degradation",
    "perturb_geographic_swap",
    "perturb_resource_constraint",
    "perturb_temporal_shift",
]
