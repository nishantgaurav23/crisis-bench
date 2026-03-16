# Spec S6.7: Synthetic Social Media Generator

**Status**: spec-written
**Location**: `src/data/synthetic/social_media_gen.py`
**Depends On**: S2.6 (LLM Router)
**Phase**: 6 — Data Pipeline

---

## 1. Overview

Generate realistic synthetic crisis-related social media posts for benchmark scenarios. The generator produces tweets/posts in Hindi, English, and regional Indian languages matching real Indian disaster Twitter/X patterns.

### Requirements (from FR-013)

- FR-013.2: Generate synthetic Indian social media in Hindi + English (+ Tamil/Bengali/Odia for region-specific scenarios) using LLM Router + translation
- FR-013.5: Social media mix: 40% Hindi, 30% English, 30% regional language
- FR-009.2: Scenarios include synthetic social media in Hindi/English

---

## 2. Outcomes

1. `SocialMediaGenerator` class that generates batches of synthetic crisis posts via LLM Router
2. Pydantic models for social media posts: `SyntheticPost`, `PostBatch`, `PostConfig`
3. Language distribution: 40% Hindi, 30% English, 30% regional (configurable)
4. Post categories: rescue requests, infrastructure damage reports, eyewitness accounts, misinformation, official updates, volunteer coordination, missing persons, donation appeals
5. Each post has: text, language, category, location metadata, timestamp, credibility score, sentiment
6. Generates 50-500 posts per scenario via batched LLM calls through the router
7. All LLM calls routed through `LLMRouter.call("routine", ...)` (Qwen Flash tier for cost efficiency)

---

## 3. Data Models

```python
class PostCategory(str, Enum):
    RESCUE_REQUEST = "rescue_request"
    INFRASTRUCTURE_DAMAGE = "infrastructure_damage"
    EYEWITNESS = "eyewitness"
    MISINFORMATION = "misinformation"
    OFFICIAL_UPDATE = "official_update"
    VOLUNTEER_COORDINATION = "volunteer_coordination"
    MISSING_PERSON = "missing_person"
    DONATION_APPEAL = "donation_appeal"

class PostLanguage(str, Enum):
    HINDI = "hindi"
    ENGLISH = "english"
    TAMIL = "tamil"
    BENGALI = "bengali"
    ODIA = "odia"
    MARATHI = "marathi"
    GUJARATI = "gujarati"
    KANNADA = "kannada"
    MALAYALAM = "malayalam"
    TELUGU = "telugu"

class SyntheticPost(BaseModel):
    id: str  # UUID
    text: str  # The actual post content (140-280 chars)
    language: PostLanguage
    category: PostCategory
    disaster_type: IndiaDisasterType
    location: str  # District/city name
    state: str  # Indian state
    timestamp_offset_minutes: int  # Minutes from scenario start
    credibility: float  # 0.0-1.0 (misinformation = low)
    sentiment: str  # "panic", "neutral", "hopeful", "angry", "plea"
    has_hashtags: bool
    has_location_tag: bool

class PostConfig(BaseModel):
    disaster_type: IndiaDisasterType
    location: str
    state: str
    regional_language: PostLanguage  # Which regional lang for 30%
    num_posts: int = 100
    language_mix: dict[str, float] = {"hindi": 0.4, "english": 0.3, "regional": 0.3}
    category_weights: dict[str, float] | None = None  # Optional custom weights
    scenario_description: str = ""  # Context for the LLM
    duration_hours: int = 24  # Scenario timeline duration

class PostBatch(BaseModel):
    config: PostConfig
    posts: list[SyntheticPost]
    generation_cost_usd: float
    generation_time_s: float
```

---

## 4. API Design

```python
class SocialMediaGenerator:
    def __init__(self, router: LLMRouter) -> None: ...

    async def generate_batch(self, config: PostConfig) -> PostBatch:
        """Generate a batch of synthetic posts for a scenario."""

    async def generate_posts_for_category(
        self, config: PostConfig, category: PostCategory,
        language: PostLanguage, count: int
    ) -> list[SyntheticPost]:
        """Generate posts for a specific category and language."""

    def _build_prompt(
        self, config: PostConfig, category: PostCategory,
        language: PostLanguage, count: int
    ) -> list[dict[str, str]]:
        """Build the LLM prompt for post generation."""

    def _parse_llm_response(
        self, response_text: str, config: PostConfig,
        category: PostCategory, language: PostLanguage
    ) -> list[SyntheticPost]:
        """Parse LLM output into SyntheticPost models."""

    def _distribute_categories(self, num_posts: int) -> dict[PostCategory, int]:
        """Distribute posts across categories based on weights."""

    def _distribute_languages(
        self, num_posts: int, config: PostConfig
    ) -> dict[PostLanguage, int]:
        """Distribute posts across languages per 40/30/30 mix."""
```

---

## 5. Category Distribution (defaults)

| Category | Weight | Rationale |
|----------|--------|-----------|
| rescue_request | 0.20 | Most critical, highest volume in Indian floods |
| infrastructure_damage | 0.15 | Roads, bridges, power — common reports |
| eyewitness | 0.20 | First-person accounts, high signal |
| misinformation | 0.10 | ~10% matches real crisis misinformation rate |
| official_update | 0.10 | Govt/NDMA/IMD retweets |
| volunteer_coordination | 0.10 | NGO/volunteer mobilization |
| missing_person | 0.08 | Missing person reports |
| donation_appeal | 0.07 | Relief fund appeals |

---

## 6. TDD Plan

### Test File: `tests/unit/test_social_media_gen.py`

**Red Phase Tests:**

1. `test_post_category_enum` — All 8 categories exist
2. `test_post_language_enum` — All 10 languages exist
3. `test_synthetic_post_model` — Validates all fields, credibility range
4. `test_post_config_defaults` — Default language mix 40/30/30
5. `test_post_config_custom_weights` — Custom category weights
6. `test_post_batch_model` — Batch with config, posts, cost
7. `test_distribute_languages_40_30_30` — Correct language distribution
8. `test_distribute_languages_custom_mix` — Custom mix sums to total
9. `test_distribute_categories_default` — Default weights distribute correctly
10. `test_distribute_categories_custom` — Custom weights work
11. `test_build_prompt_english` — Prompt structure for English posts
12. `test_build_prompt_hindi` — Prompt includes Hindi instruction
13. `test_build_prompt_regional` — Prompt includes regional language name
14. `test_parse_llm_response_valid` — Parses well-formed JSON from LLM
15. `test_parse_llm_response_malformed` — Handles malformed LLM output gracefully
16. `test_generate_posts_for_category` — Generates posts with mocked router
17. `test_generate_batch_full` — Full batch generation with mocked router
18. `test_generate_batch_language_distribution` — Output matches 40/30/30 mix
19. `test_generate_batch_tracks_cost` — Cost tracked from LLM responses
20. `test_misinformation_low_credibility` — Misinformation posts have credibility < 0.3

---

## 7. Implementation Notes

- Use `LLMRouter.call("routine", ...)` for all generation — Qwen Flash tier is sufficient
- Ask LLM to return JSON array of posts — parse with error handling
- Generate in batches of ~10 posts per LLM call to stay under token limits
- Timestamp offsets should be distributed across the scenario duration
- Hindi posts should use Devanagari script naturally (LLM generates directly)
- Regional language posts: LLM generates in English + includes transliterated version
- Misinformation posts should have `credibility < 0.3` and be flagged
- No external API calls — all generation via LLM Router
