# Explanation: S8.2 — Scenario Manager

## Why This Spec Exists

S8.1 provides raw Pydantic models and async CRUD for benchmark scenarios. But raw CRUD is not enough for a benchmark system — you need business logic: validation (does this scenario meet minimum quality?), filtering (find all cyclone scenarios at high complexity), version tracking (bump version when evolving), bulk operations (export 100 scenarios for sharing), and coverage analysis (how many flood scenarios do we have vs the target of 30?). ScenarioManager is the service layer that downstream specs (S8.3 runner, S8.11 self-evolving) call instead of touching CRUD directly.

## What It Does

### Constants
- **DISASTER_CATEGORIES** — 7 India-specific categories with target counts summing to 100 (floods 30, cyclones 20, urban waterlogging 15, earthquakes 15, heatwaves 10, landslides 5, industrial accidents 5)
- **COMPLEXITY_LEVELS** — ("low", "medium", "high")

### Validation (`validate_scenario`)
Standalone function that checks minimum scenario quality:
- At least 1 event in event_sequence
- Category is a valid DISASTER_CATEGORIES key
- Complexity is a valid COMPLEXITY_LEVELS value
- At least 1 agent_expectation in ground_truth_decisions
- Returns `list[str]` of errors (empty = valid)

### ScenarioManager Class
Async, stateless service with methods grouped into:

1. **CRUD delegation** — `create()` validates first then delegates to S8.1's `create_scenario()`. `get()` and `delete()` pass through directly.

2. **Filtering** — `list_by_category()`, `list_by_complexity()` delegate to S8.1's `list_scenarios()` with the appropriate filter. `list_by_tags()` fetches scenarios then filters in-memory by tag intersection (ALL specified tags must be present). `search()` combines category, complexity, tags, and source filters.

3. **Version tracking** — `bump_version()` fetches the scenario, increments `version`, applies any additional field updates, and persists via `update_scenario()`.

4. **Bulk operations** — `export_scenarios()` serializes to JSON-compatible dicts. `import_scenarios()` validates each item before creating, collecting errors for invalid ones.

5. **Statistics** — `get_stats()` returns total count + distributions by category, complexity, source. `get_coverage_report()` compares current counts per category against DISASTER_CATEGORIES targets, reporting gaps.

## How It Works

The ScenarioManager is intentionally stateless — no instance state, no caching, no connection management. Every method calls through to the S8.1 CRUD functions which handle database access. This makes the manager trivially testable (mock the CRUD functions) and safe for concurrent use.

Tag filtering is done in-memory because PostgreSQL's array containment query (`@>`) would require schema changes. For 100 scenarios this is perfectly adequate. If the benchmark grows beyond ~10K scenarios, this should be pushed to a SQL query.

## How It Connects

```
S8.1 (Models + CRUD) ← foundation
  ↓
S8.2 (Scenario Manager) ← THIS SPEC — business logic layer
  ↓                    ↘
S8.3 (Scenario Runner)  S8.11 (Self-Evolving Generator)
  ↓                       uses ScenarioManager.create() to persist
S8.4 (Evaluation Engine)  generated scenarios, get_coverage_report()
                           to identify which categories need more
```

### Interview Q&A

**Q: Why a separate ScenarioManager instead of putting this logic in the CRUD module?**
A: Separation of concerns. S8.1's CRUD is a thin data access layer — it speaks SQL and returns models. S8.2 is a service layer — it speaks domain concepts (categories, versions, coverage gaps). Keeping them separate means S8.3 (runner) and S8.11 (generator) depend on business rules without coupling to database details. It also makes testing cleaner: CRUD tests mock asyncpg, manager tests mock CRUD functions.

**Q: Why validate in the manager instead of Pydantic validators?**
A: Pydantic validates structure (types, field constraints). The manager validates business rules (category must be one of 7, must have events). A scenario can be structurally valid Pydantic but semantically invalid for benchmarking (e.g., empty event sequence). Also, `validate_scenario()` is a pure function returning errors — it doesn't throw, making it easy to use in bulk imports where you want to collect all errors.

**Q: Why is tag filtering done in-memory?**
A: With a target of 100 scenarios, in-memory filtering is O(100) — microseconds. Using PostgreSQL array containment (`WHERE tags @> ARRAY['coastal']`) would be premature optimization that adds SQL complexity. The YAGNI principle applies. If we scale to 10K+ scenarios, we'd push this to SQL with a GIN index on the tags array column.
