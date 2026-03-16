# Spec S8.2 — Scenario Manager

## Overview

**Location**: `src/benchmark/scenario_manager.py`
**Depends On**: S8.1 (Scenario models + CRUD)
**Downstream**: S8.3 (Scenario Runner), S8.11 (Self-Evolving Generator)

Higher-level scenario management layer on top of S8.1's raw CRUD. Provides business logic for category/tag filtering, complexity-level queries, version tracking (bump + history), scenario validation, bulk import/export, and summary statistics. This is the primary interface used by S8.3 (runner) and S8.11 (self-evolving generator).

## Outcomes

1. **ScenarioManager class** — async, stateless service wrapping S8.1 CRUD with business logic
2. **Category constants** — 7 India disaster categories with target counts (floods 30, cyclones 20, urban waterlogging 15, earthquakes 15, heatwaves 10, landslides 5, industrial 5)
3. **Complexity filtering** — query by low/medium/high with counts per level
4. **Tag-based filtering** — find scenarios by tags (e.g., "cascading", "multi-state", "coastal")
5. **Version tracking** — bump version on update, retrieve version history for a scenario
6. **Scenario validation** — ensure minimum requirements (has events, has ground truth, valid rubric weights)
7. **Bulk export/import** — JSON serialization of scenario sets for sharing/backup
8. **Summary statistics** — counts by category, complexity, source; coverage gaps vs target

## Constants

```python
DISASTER_CATEGORIES = {
    "flood": 30,
    "cyclone": 20,
    "urban_waterlogging": 15,
    "earthquake": 15,
    "heatwave": 10,
    "landslide": 5,
    "industrial_accident": 5,
}
# Total: 100 scenarios target

COMPLEXITY_LEVELS = ("low", "medium", "high")
```

## Class: ScenarioManager

### Core CRUD (delegates to S8.1)
- `async def create(scenario: BenchmarkScenario) -> uuid.UUID` — validate then create
- `async def get(scenario_id: uuid.UUID) -> BenchmarkScenario | None`
- `async def delete(scenario_id: uuid.UUID) -> bool`

### Filtering
- `async def list_by_category(category: str, limit: int = 50, offset: int = 0) -> list[BenchmarkScenario]`
- `async def list_by_complexity(complexity: str, limit: int = 50, offset: int = 0) -> list[BenchmarkScenario]`
- `async def list_by_tags(tags: list[str], limit: int = 50, offset: int = 0) -> list[BenchmarkScenario]` — scenarios containing ALL specified tags
- `async def search(category: str | None, complexity: str | None, tags: list[str] | None, source: str | None, limit: int, offset: int) -> list[BenchmarkScenario]` — combined filter

### Version Tracking
- `async def bump_version(scenario_id: uuid.UUID, **updates) -> BenchmarkScenario | None` — increment version, apply updates, return updated scenario
- `async def get_version_history(scenario_id: uuid.UUID) -> list[dict]` — query evaluation_runs to see how scenario evolved (version field in scenarios table)

### Validation
- `def validate_scenario(scenario: BenchmarkScenario) -> list[str]` — returns list of validation errors (empty = valid)
  - Must have at least 1 event in event_sequence
  - Must have at least 1 agent_expectation in ground_truth
  - Category must be in DISASTER_CATEGORIES
  - Complexity must be in COMPLEXITY_LEVELS
  - If rubric present, weights must sum to 1.0

### Bulk Operations
- `async def export_scenarios(category: str | None = None) -> list[dict]` — export as JSON-serializable dicts
- `async def import_scenarios(data: list[dict]) -> tuple[int, list[str]]` — import from dicts, returns (success_count, errors)

### Statistics
- `async def get_stats() -> dict` — returns category counts, complexity distribution, source distribution, coverage gaps vs DISASTER_CATEGORIES targets
- `async def get_coverage_report() -> dict` — detailed gap analysis: which categories need more scenarios

## TDD Notes

### Test File: `tests/unit/test_scenario_manager.py`

1. **Validation tests**: valid scenario passes, missing events fails, invalid category fails, invalid complexity fails, missing ground truth fails
2. **Category constants**: verify all 7 categories sum to 100
3. **ScenarioManager.create**: validates before delegating to CRUD
4. **ScenarioManager.create rejects invalid**: returns error for invalid scenario
5. **list_by_category**: delegates with correct filter
6. **list_by_complexity**: delegates with correct filter
7. **list_by_tags**: filters scenarios by tag intersection
8. **search**: combined multi-filter
9. **bump_version**: increments version, applies updates
10. **bump_version not found**: returns None for missing scenario
11. **export_scenarios**: returns JSON-serializable list
12. **import_scenarios**: creates valid scenarios, reports errors for invalid
13. **get_stats**: returns correct category/complexity/source counts
14. **get_coverage_report**: identifies gaps vs target counts

## Non-Goals

- Scenario generation (S6.6 + S8.11)
- Scenario execution/running (S8.3)
- Perturbation operations (S8.11)
- Evaluation scoring (S8.4-S8.9)
