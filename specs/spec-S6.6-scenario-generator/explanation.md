# S6.6 Explanation: Synthetic Scenario Generator

## Why This Spec Exists

The benchmark engine (Phase 8) needs 100 India-specific disaster scenarios to evaluate multi-agent system performance. Hand-writing 100 scenarios is impractical and biased — we need programmatic generation that's grounded in real Indian geography, demographics, and NDMA procedures.

S6.6 bridges the data pipeline (Phase 6) to the benchmark system (Phase 8) by producing `BenchmarkScenario` objects that the Scenario Manager (S8.2) and Self-Evolving generator (S8.11) consume.

## What It Does

**`ScenarioGenerator`** creates disaster scenarios using:

1. **Templates** — 7 India-specific disaster templates (flood, cyclone, waterlogging, earthquake, heatwave, landslide, industrial) with geographically accurate affected states, seasonal constraints, and severity ranges.

2. **LLM generation** — Uses the LLM Router (standard tier: DeepSeek Chat) to produce rich narrative scenarios with realistic event sequences, initial conditions, and ground truth decisions.

3. **NDMA ground truth** — Queries ChromaDB via `EmbeddingPipeline.query_similar()` to retrieve actual NDMA guidelines/SOPs, grounding the scenario's expected decisions in real government procedures.

4. **Geographic context** — Selects affected states from census data, assigns primary languages from state records, and estimates population from district data.

5. **Graceful fallback** — If the LLM fails, generates template-only scenarios with basic event sequences and default rubrics (no data loss, just less narrative richness).

## How It Works

### Data Flow
```
INDIA_STATES/DISTRICTS (S6.5) ──┐
                                 ├── ScenarioGenerator ──> BenchmarkScenario
NDMA Guidelines (S6.2/ChromaDB) ─┤
                                 │
LLM Router (S2.6) ──────────────┘
```

### Key Design Decisions

- **Template-first architecture**: Each disaster type has a `ScenarioTemplate` with hardcoded geographic constraints (cyclones only hit coastal states, landslides only in hilly states). The LLM enriches templates rather than generating from scratch — preventing geographic nonsense like "cyclone hits Delhi."

- **Standard tier LLM**: Uses DeepSeek Chat ($0.28/M tokens) — good enough for creative text generation, not worth the 10x cost of Reasoner tier.

- **Complexity scaling**: Low = 1 state, severity 1-2; Medium = 2 states, severity 2-4; High = 3 states, severity 4-5. This creates a natural difficulty gradient for the benchmark.

- **Language from geography**: Primary language is determined by the affected state's Census record (Odisha → Odia, Tamil Nadu → Tamil), not randomly assigned. This ensures linguistic realism.

### Distribution
100 scenarios: 30 floods, 20 cyclones, 15 waterlogging, 15 earthquakes, 10 heatwaves, 5 landslides, 5 industrial — matching India's actual disaster frequency distribution.

## How It Connects

| Dependency | Direction | What Flows |
|-----------|-----------|------------|
| S2.6 (LLM Router) | upstream | LLM calls for narrative generation |
| S6.2 (NDMA Ingestion) | upstream | Ground truth from NDMA guidelines via ChromaDB |
| S6.5 (Census/Admin) | upstream | State/district data, languages, populations |
| S8.2 (Scenario Manager) | downstream | Loads generated `BenchmarkScenario` objects |
| S8.11 (Self-Evolving) | downstream | Perturbation operations on generated scenarios |
| S6.7 (Social Media Gen) | sibling | Generates synthetic tweets for these scenarios |

## Interview Relevance

**Q: Why use LLM for scenario generation instead of rule-based templates?**
A: Pure templates produce repetitive, unrealistic scenarios — every cyclone would read the same. LLMs add narrative variation (different failure modes, cascading effects) while templates ensure geographic and temporal validity. The fallback mechanism means the system works even without LLM access.

**Q: How do you prevent the LLM from generating geographically invalid scenarios?**
A: Template constraints. The LLM can only enrich scenarios within the template's allowed states, seasons, and severity ranges. If it generates an earthquake in Lakshadweep (seismic zone 3, mild risk), the severity is capped by the template. The LLM adds narrative depth; the template enforces physical reality.

**Q: What is the cost to generate all 100 scenarios?**
A: At ~2,000 output tokens per scenario using DeepSeek Chat ($0.28/$0.42 per M tokens): 100 scenarios * 2,000 tokens * $0.42/M = ~$0.084 total. With input tokens: ~$0.15 total. Well within the $3-8/month budget.
