# Spec S6.7: Synthetic Social Media Generator — Explanation

## Why This Spec Exists

Disaster benchmark scenarios need realistic social media data to test the SituationSense agent's ability to process, classify, and extract actionable intelligence from crisis posts. Real Indian disaster Twitter/X data can't be freely redistributed, and manually writing hundreds of posts per scenario is impractical. This generator creates synthetic crisis posts matching real Indian disaster posting patterns — 40% Hindi, 30% English, 30% regional language — enabling reproducible benchmark evaluation.

## What It Does

The `SocialMediaGenerator` produces batches of synthetic crisis social media posts for any Indian disaster scenario. Given a disaster type, location, state, and regional language, it:

1. **Distributes posts** across 3 languages (40/30/30 Hindi/English/regional) and 8 categories (rescue requests, infrastructure damage, eyewitness accounts, misinformation, official updates, volunteer coordination, missing persons, donation appeals)
2. **Generates posts via LLM** using the routine tier (Qwen Flash at ~$0.04/M tokens) for cost efficiency
3. **Parses and validates** LLM JSON output into typed Pydantic models with credibility scoring
4. **Forces misinformation credibility** below 0.3, enabling downstream agents to test misinformation detection

### Key Data Models

- `PostCategory` — 8 crisis post types matching real disaster social media taxonomy
- `PostLanguage` — 10 Indian languages (Hindi, English, Tamil, Bengali, Odia, etc.)
- `SyntheticPost` — Individual post with text, language, category, location, credibility, sentiment
- `PostConfig` — Generation configuration (disaster type, location, language mix, post count)
- `PostBatch` — Result container with posts + generation cost/time tracking

## How It Works

1. `generate_batch(config)` is called with a `PostConfig` specifying the scenario
2. Posts are distributed across languages via `_distribute_languages()` (40/30/30 default)
3. Posts are distributed across categories via `_distribute_categories()` (weighted by realistic frequencies)
4. For each language × category combination, a proportional count is computed
5. `_build_prompt()` creates a system+user message asking the LLM to generate JSON posts in the specified language and category
6. The LLM Router sends the request to the routine tier (Qwen Flash → Groq → Ollama fallback)
7. `_parse_llm_response()` parses the JSON array, enforces credibility caps for misinformation, and produces validated `SyntheticPost` objects
8. Total cost and generation time are tracked in the returned `PostBatch`

## How It Connects

### Upstream (depends on)
- **S2.6 `llm_router.py`** — All generation calls go through `router.call("routine", ...)` for provider abstraction and failover

### Downstream (used by)
- **S6.6 `scenario_gen.py`** — Scenario generator will embed social media posts into generated scenarios
- **S7.3 `situation_sense.py`** — SituationSense agent processes these posts for crisis classification
- **S8.1-S8.4 Benchmark system** — Scenarios include social media feeds for evaluation
- **FR-002.4** — CrisisBERT/IndicBERT classification tested against these synthetic posts

### Design Decisions
- **Routine tier** chosen over standard because social media generation is a creative task that doesn't need strong reasoning — Qwen Flash is sufficient and 7x cheaper
- **JSON output format** enables deterministic parsing; markdown/free-text would require regex extraction
- **Misinformation credibility cap** at 0.3 is hardcoded rather than LLM-generated because LLMs inconsistently assign credibility to fake content
- **10 posts per LLM call** balances token limits against API call overhead
