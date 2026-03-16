# S8.2 Scenario Manager — Checklist

## Phase 1: Red (Tests First)
- [x] Write validation tests (valid, missing events, invalid category, invalid complexity, missing ground truth)
- [x] Write category constants test (7 categories sum to 100)
- [x] Write ScenarioManager CRUD delegation tests (create, get, delete)
- [x] Write filtering tests (list_by_category, list_by_complexity, list_by_tags, search)
- [x] Write version tracking tests (bump_version, bump_version not found)
- [x] Write bulk operation tests (export_scenarios, import_scenarios)
- [x] Write statistics tests (get_stats, get_coverage_report)
- [x] All tests fail (RED)

## Phase 2: Green (Implement)
- [x] Define DISASTER_CATEGORIES and COMPLEXITY_LEVELS constants
- [x] Implement validate_scenario()
- [x] Implement ScenarioManager class with __init__
- [x] Implement create() with validation
- [x] Implement get() and delete() delegation
- [x] Implement list_by_category(), list_by_complexity()
- [x] Implement list_by_tags() with tag intersection
- [x] Implement search() with combined filters
- [x] Implement bump_version()
- [x] Implement export_scenarios() and import_scenarios()
- [x] Implement get_stats() and get_coverage_report()
- [x] All tests pass (GREEN)

## Phase 3: Refactor
- [x] Run ruff check + fix
- [x] Run ruff format
- [x] Run full test suite
- [x] Verify no secrets, no paid deps
