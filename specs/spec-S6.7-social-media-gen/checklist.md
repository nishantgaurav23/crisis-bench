# S6.7 Implementation Checklist

## Phase 1: Red (Write Tests)
- [x] Create `tests/unit/test_social_media_gen.py`
- [x] Write all 21 tests — all must FAIL
- [x] Run `pytest tests/unit/test_social_media_gen.py` — confirm all fail

## Phase 2: Green (Implement)
- [x] Create `src/data/synthetic/social_media_gen.py`
- [x] Implement enums: `PostCategory`, `PostLanguage`
- [x] Implement models: `SyntheticPost`, `PostConfig`, `PostBatch`
- [x] Implement `SocialMediaGenerator.__init__`
- [x] Implement `_distribute_languages`
- [x] Implement `_distribute_categories`
- [x] Implement `_build_prompt`
- [x] Implement `_parse_llm_response`
- [x] Implement `generate_posts_for_category`
- [x] Implement `generate_batch`
- [x] Run `pytest tests/unit/test_social_media_gen.py` — all pass

## Phase 3: Refactor
- [x] Run `ruff check src/data/synthetic/social_media_gen.py`
- [x] Run `ruff format src/data/synthetic/social_media_gen.py`
- [x] Verify all tests still pass
- [x] Update `__init__.py` exports

## Phase 4: Verify
- [x] All 21 tests pass
- [x] Lint clean
- [x] No secrets or hardcoded API keys
- [x] All LLM calls go through router
- [x] No external API calls in tests
