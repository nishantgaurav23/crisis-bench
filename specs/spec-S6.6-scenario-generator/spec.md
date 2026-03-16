# Spec S6.6: Synthetic Scenario Generator

**Status**: done

## Overview
LLM-powered synthetic disaster scenario generator that creates India-specific benchmark scenarios from historical templates, geographic data, and NDMA guidelines. Produces `BenchmarkScenario` objects for the benchmark engine (Phase 8).

## Depends On
- **S2.6** (LLM Router) — for LLM calls to generate scenario narratives
- **S6.2** (NDMA Ingestion) — for ground truth from NDMA guidelines/SOPs via ChromaDB
- **S6.5** (Census + Admin Boundaries) — for Indian geographic/demographic context

## Location
`src/data/synthetic/scenario_gen.py`

## Feature
Generate 100 India-specific disaster scenarios across 7 categories with:
- Realistic initial conditions based on Indian geography/demographics
- Temporal event sequences with escalation patterns
- Ground truth decisions derived from NDMA SOPs
- 5-dimension evaluation rubrics (SA, DT, RE, CQ, CA)

## Requirements

### R1: Scenario Distribution
100 scenarios across 7 disaster categories:
| Category | Count | % |
|----------|-------|---|
| Floods (monsoon_flood) | 30 | 30% |
| Cyclones | 20 | 20% |
| Urban Waterlogging | 15 | 15% |
| Earthquakes | 15 | 15% |
| Heatwaves | 10 | 10% |
| Landslides | 5 | 5% |
| Industrial Accidents | 5 | 5% |

Each category split equally across low/medium/high complexity.

### R2: ScenarioTemplate Data Model
India-specific templates per disaster type containing:
- Typical affected states (from INDIA_STATES)
- Season/timing constraints (e.g., cyclones Oct-Dec, floods Jun-Sep)
- Severity ranges per complexity level
- Infrastructure dependencies to model
- NDMA SOP reference keywords for ground truth retrieval

### R3: ScenarioGenerator Class
- Constructor accepts `LLMRouter` and `EmbeddingPipeline` (dependency injection)
- `generate_scenario(category, complexity)` → `BenchmarkScenario`
- `generate_batch(distribution)` → `list[BenchmarkScenario]`
- Uses "standard" tier LLM calls for generation
- Retrieves NDMA guidelines via `EmbeddingPipeline.query_similar()` for ground truth
- Selects affected states/districts from `INDIA_STATES`/`INDIA_DISTRICTS` hardcoded data
- All methods async

### R4: Language Distribution
- 40% Hindi primary language
- 30% English primary language
- 30% Regional (Tamil, Bengali, Odia, Telugu, Marathi, Gujarati, Kannada, Malayalam, Punjabi)
- Language assigned based on state's `primary_language` field

### R5: Event Sequence Structure
Each scenario has 4-8 temporal events:
```python
{
    "time_offset_minutes": int,  # minutes from scenario start
    "phase": "pre_event|active_response|recovery",
    "event_type": str,  # e.g., "imd_warning", "river_level_rise", "evacuation_order"
    "description": str,
    "data_payload": dict  # structured data for the event
}
```

### R6: Ground Truth from NDMA
- Query ChromaDB `ndma_guidelines` collection with disaster-specific queries
- Extract key decision points from retrieved SOPs
- Structure as expected agent actions with timing windows

### R7: Evaluation Rubric
Each scenario includes scoring criteria across 5 dimensions:
- Situational Accuracy (SA): key facts to identify
- Decision Timeliness (DT): time windows for critical decisions
- Resource Efficiency (RE): expected resource allocation
- Coordination Quality (CQ): inter-agent communication expectations
- Communication Appropriateness (CA): language, tone, channel expectations

### R8: Error Handling
- `ScenarioGenerationError` subclass of `DataError` for generation failures
- Graceful fallback: if LLM fails, generate template-only scenarios without LLM enrichment
- Log all generation attempts via structlog

## TDD Notes

### Tests to Write First
1. `test_scenario_template_structure` — templates have required fields
2. `test_distribution_counts` — correct category/complexity distribution
3. `test_generate_scenario_valid_output` — output matches BenchmarkScenario schema
4. `test_event_sequence_ordering` — events are chronologically ordered
5. `test_language_distribution` — language assignment follows 40/30/30 rule
6. `test_ground_truth_retrieval` — NDMA guidelines queried for ground truth
7. `test_evaluation_rubric_completeness` — all 5 dimensions present
8. `test_llm_failure_fallback` — graceful degradation when LLM fails
9. `test_affected_states_valid` — states match INDIA_STATES data
10. `test_complexity_affects_severity` — higher complexity = higher severity range

### Mocking Strategy
- Mock `LLMRouter.call()` → return structured JSON scenario text
- Mock `EmbeddingPipeline.query_similar()` → return fake NDMA guideline chunks
- Never hit real LLM APIs or ChromaDB in tests
