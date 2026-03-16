"""Scenario manager for CRISIS-BENCH (spec S8.2).

Higher-level scenario management layer on top of S8.1's raw CRUD.
Provides business logic for category/tag filtering, complexity-level queries,
version tracking, scenario validation, bulk import/export, and summary statistics.
"""

from __future__ import annotations

import uuid
from collections import Counter
from typing import Any

from src.benchmark.models import (
    BenchmarkScenario,
    count_scenarios,
    create_scenario,
    delete_scenario,
    get_scenario,
    list_scenarios,
    update_scenario,
)

# =============================================================================
# Constants
# =============================================================================

DISASTER_CATEGORIES: dict[str, int] = {
    "flood": 30,
    "cyclone": 20,
    "urban_waterlogging": 15,
    "earthquake": 15,
    "heatwave": 10,
    "landslide": 5,
    "industrial_accident": 5,
}

COMPLEXITY_LEVELS: tuple[str, ...] = ("low", "medium", "high")


# =============================================================================
# Validation
# =============================================================================


def validate_scenario(scenario: BenchmarkScenario) -> list[str]:
    """Validate a scenario meets minimum requirements.

    Returns a list of error strings (empty means valid).
    """
    errors: list[str] = []

    if not scenario.event_sequence:
        errors.append("Scenario must have at least 1 event in event_sequence")

    if scenario.category not in DISASTER_CATEGORIES:
        errors.append(
            f"Invalid category '{scenario.category}'. "
            f"Must be one of: {', '.join(sorted(DISASTER_CATEGORIES))}"
        )

    if scenario.complexity not in COMPLEXITY_LEVELS:
        errors.append(
            f"Invalid complexity '{scenario.complexity}'. "
            f"Must be one of: {', '.join(COMPLEXITY_LEVELS)}"
        )

    if not scenario.ground_truth_decisions.agent_expectations:
        errors.append("Scenario must have at least 1 agent_expectations in ground_truth_decisions")

    return errors


# =============================================================================
# ScenarioManager
# =============================================================================


class ScenarioManager:
    """Async, stateless service wrapping S8.1 CRUD with business logic."""

    # ── Core CRUD ────────────────────────────────────────────────────────

    async def create(self, scenario: BenchmarkScenario) -> uuid.UUID:
        """Validate then create a scenario."""
        errors = validate_scenario(scenario)
        if errors:
            raise ValueError(f"Scenario validation failed: {'; '.join(errors)}")
        return await create_scenario(scenario)

    async def get(self, scenario_id: uuid.UUID) -> BenchmarkScenario | None:
        """Get a scenario by ID."""
        return await get_scenario(scenario_id)

    async def delete(self, scenario_id: uuid.UUID) -> bool:
        """Delete a scenario by ID."""
        return await delete_scenario(scenario_id)

    # ── Filtering ────────────────────────────────────────────────────────

    async def list_by_category(
        self,
        category: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BenchmarkScenario]:
        """List scenarios filtered by category."""
        return await list_scenarios(
            category=category,
            complexity=None,
            limit=limit,
            offset=offset,
        )

    async def list_by_complexity(
        self,
        complexity: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BenchmarkScenario]:
        """List scenarios filtered by complexity."""
        return await list_scenarios(
            category=None,
            complexity=complexity,
            limit=limit,
            offset=offset,
        )

    async def list_by_tags(
        self,
        tags: list[str],
        limit: int = 50,
        offset: int = 0,
    ) -> list[BenchmarkScenario]:
        """List scenarios containing ALL specified tags."""
        all_scenarios = await list_scenarios(limit=limit, offset=offset)
        tag_set = set(tags)
        return [s for s in all_scenarios if tag_set.issubset(set(s.tags))]

    async def search(
        self,
        category: str | None = None,
        complexity: str | None = None,
        tags: list[str] | None = None,
        source: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BenchmarkScenario]:
        """Combined multi-filter search."""
        results = await list_scenarios(
            category=category,
            complexity=complexity,
            limit=limit,
            offset=offset,
        )
        if tags:
            tag_set = set(tags)
            results = [s for s in results if tag_set.issubset(set(s.tags))]
        if source:
            results = [s for s in results if s.source == source]
        return results

    # ── Version Tracking ─────────────────────────────────────────────────

    async def bump_version(
        self,
        scenario_id: uuid.UUID,
        **updates: Any,
    ) -> BenchmarkScenario | None:
        """Increment version and apply updates. Returns updated scenario or None."""
        scenario = await get_scenario(scenario_id)
        if scenario is None:
            return None

        new_version = scenario.version + 1
        updates["version"] = new_version
        await update_scenario(scenario_id, **updates)

        return await get_scenario(scenario_id)

    # ── Bulk Operations ──────────────────────────────────────────────────

    async def export_scenarios(
        self,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """Export scenarios as JSON-serializable dicts."""
        scenarios = await list_scenarios(category=category, limit=10000)
        return [s.model_dump(mode="json") for s in scenarios]

    async def import_scenarios(
        self,
        data: list[dict[str, Any]],
    ) -> tuple[int, list[str]]:
        """Import scenarios from dicts. Returns (success_count, errors)."""
        success = 0
        errors: list[str] = []

        for i, item in enumerate(data):
            try:
                scenario = BenchmarkScenario.model_validate(item)
                validation_errors = validate_scenario(scenario)
                if validation_errors:
                    errors.append(f"Item {i}: {'; '.join(validation_errors)}")
                    continue
                await create_scenario(scenario)
                success += 1
            except Exception as exc:
                errors.append(f"Item {i}: {exc}")

        return success, errors

    # ── Statistics ────────────────────────────────────────────────────────

    async def get_stats(self) -> dict[str, Any]:
        """Category, complexity, and source distribution statistics."""
        total = await count_scenarios()
        all_scenarios = await list_scenarios(limit=10000)

        by_category: dict[str, int] = Counter(s.category for s in all_scenarios)
        by_complexity: dict[str, int] = Counter(s.complexity for s in all_scenarios)
        by_source: dict[str, int] = Counter(s.source for s in all_scenarios)

        return {
            "total": total,
            "by_category": dict(by_category),
            "by_complexity": dict(by_complexity),
            "by_source": dict(by_source),
        }

    async def get_coverage_report(self) -> dict[str, dict[str, int]]:
        """Gap analysis: current counts vs target per category."""
        all_scenarios = await list_scenarios(limit=10000)
        current_counts: dict[str, int] = Counter(s.category for s in all_scenarios)

        report: dict[str, dict[str, int]] = {}
        for cat, target in DISASTER_CATEGORIES.items():
            current = current_counts.get(cat, 0)
            report[cat] = {
                "current": current,
                "target": target,
                "gap": max(0, target - current),
            }
        return report


__all__ = [
    "COMPLEXITY_LEVELS",
    "DISASTER_CATEGORIES",
    "ScenarioManager",
    "validate_scenario",
]
