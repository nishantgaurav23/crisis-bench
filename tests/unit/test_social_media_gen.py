"""Tests for synthetic social media generator (S6.7).

TDD Red Phase — all tests written before implementation.
Tests cover: enums, models, distribution logic, prompt building,
LLM response parsing, and full batch generation.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.shared.models import IndiaDisasterType

# =============================================================================
# Test 1-2: Enum completeness
# =============================================================================


def test_post_category_enum():
    from src.data.synthetic.social_media_gen import PostCategory

    expected = {
        "rescue_request",
        "infrastructure_damage",
        "eyewitness",
        "misinformation",
        "official_update",
        "volunteer_coordination",
        "missing_person",
        "donation_appeal",
    }
    actual = {c.value for c in PostCategory}
    assert actual == expected


def test_post_language_enum():
    from src.data.synthetic.social_media_gen import PostLanguage

    expected = {
        "hindi",
        "english",
        "tamil",
        "bengali",
        "odia",
        "marathi",
        "gujarati",
        "kannada",
        "malayalam",
        "telugu",
    }
    actual = {lang.value for lang in PostLanguage}
    assert actual == expected


# =============================================================================
# Test 3-6: Pydantic model validation
# =============================================================================


def test_synthetic_post_model():
    from src.data.synthetic.social_media_gen import (
        PostCategory,
        PostLanguage,
        SyntheticPost,
    )

    post = SyntheticPost(
        id=str(uuid.uuid4()),
        text="Flood water rising near Patna Junction, need rescue! #BiharFloods",
        language=PostLanguage.ENGLISH,
        category=PostCategory.RESCUE_REQUEST,
        disaster_type=IndiaDisasterType.MONSOON_FLOOD,
        location="Patna",
        state="Bihar",
        timestamp_offset_minutes=120,
        credibility=0.9,
        sentiment="panic",
        has_hashtags=True,
        has_location_tag=True,
    )
    assert post.language == PostLanguage.ENGLISH
    assert post.category == PostCategory.RESCUE_REQUEST
    assert 0.0 <= post.credibility <= 1.0
    assert post.has_hashtags is True


def test_synthetic_post_credibility_range():
    from src.data.synthetic.social_media_gen import (
        PostCategory,
        PostLanguage,
        SyntheticPost,
    )

    with pytest.raises(Exception):
        SyntheticPost(
            id="test",
            text="test",
            language=PostLanguage.ENGLISH,
            category=PostCategory.EYEWITNESS,
            disaster_type=IndiaDisasterType.CYCLONE,
            location="Chennai",
            state="Tamil Nadu",
            timestamp_offset_minutes=0,
            credibility=1.5,  # Out of range
            sentiment="neutral",
            has_hashtags=False,
            has_location_tag=False,
        )


def test_post_config_defaults():
    from src.data.synthetic.social_media_gen import PostConfig, PostLanguage

    config = PostConfig(
        disaster_type=IndiaDisasterType.CYCLONE,
        location="Bhubaneswar",
        state="Odisha",
        regional_language=PostLanguage.ODIA,
    )
    assert config.num_posts == 100
    assert config.language_mix == {"hindi": 0.4, "english": 0.3, "regional": 0.3}
    assert config.duration_hours == 24


def test_post_config_custom_weights():
    from src.data.synthetic.social_media_gen import PostConfig, PostLanguage

    config = PostConfig(
        disaster_type=IndiaDisasterType.EARTHQUAKE,
        location="Delhi",
        state="Delhi",
        regional_language=PostLanguage.HINDI,
        category_weights={"rescue_request": 0.5, "eyewitness": 0.5},
    )
    assert config.category_weights == {"rescue_request": 0.5, "eyewitness": 0.5}


def test_post_batch_model():
    from src.data.synthetic.social_media_gen import (
        PostBatch,
        PostConfig,
        PostLanguage,
    )

    config = PostConfig(
        disaster_type=IndiaDisasterType.MONSOON_FLOOD,
        location="Patna",
        state="Bihar",
        regional_language=PostLanguage.HINDI,
        num_posts=10,
    )
    batch = PostBatch(
        config=config,
        posts=[],
        generation_cost_usd=0.001,
        generation_time_s=2.5,
    )
    assert batch.generation_cost_usd == 0.001
    assert len(batch.posts) == 0


# =============================================================================
# Test 7-10: Distribution logic
# =============================================================================


def test_distribute_languages_40_30_30():
    from src.data.synthetic.social_media_gen import (
        PostConfig,
        PostLanguage,
        SocialMediaGenerator,
    )

    gen = SocialMediaGenerator(router=MagicMock())
    config = PostConfig(
        disaster_type=IndiaDisasterType.CYCLONE,
        location="Puri",
        state="Odisha",
        regional_language=PostLanguage.ODIA,
        num_posts=100,
    )
    dist = gen._distribute_languages(100, config)
    assert dist[PostLanguage.HINDI] == 40
    assert dist[PostLanguage.ENGLISH] == 30
    assert dist[PostLanguage.ODIA] == 30
    assert sum(dist.values()) == 100


def test_distribute_languages_custom_mix():
    from src.data.synthetic.social_media_gen import (
        PostConfig,
        PostLanguage,
        SocialMediaGenerator,
    )

    gen = SocialMediaGenerator(router=MagicMock())
    config = PostConfig(
        disaster_type=IndiaDisasterType.CYCLONE,
        location="Chennai",
        state="Tamil Nadu",
        regional_language=PostLanguage.TAMIL,
        num_posts=50,
        language_mix={"hindi": 0.2, "english": 0.5, "regional": 0.3},
    )
    dist = gen._distribute_languages(50, config)
    assert sum(dist.values()) == 50
    assert dist[PostLanguage.ENGLISH] == 25
    assert dist[PostLanguage.TAMIL] == 15


def test_distribute_categories_default():
    from src.data.synthetic.social_media_gen import (
        PostCategory,
        PostConfig,
        PostLanguage,
        SocialMediaGenerator,
    )

    gen = SocialMediaGenerator(router=MagicMock())
    config = PostConfig(
        disaster_type=IndiaDisasterType.MONSOON_FLOOD,
        location="Patna",
        state="Bihar",
        regional_language=PostLanguage.HINDI,
    )
    dist = gen._distribute_categories(100, config)
    assert sum(dist.values()) == 100
    # rescue_request should be 20% of 100
    assert dist[PostCategory.RESCUE_REQUEST] == 20
    assert dist[PostCategory.EYEWITNESS] == 20
    assert dist[PostCategory.MISINFORMATION] == 10


def test_distribute_categories_custom():
    from src.data.synthetic.social_media_gen import (
        PostCategory,
        PostConfig,
        PostLanguage,
        SocialMediaGenerator,
    )

    gen = SocialMediaGenerator(router=MagicMock())
    config = PostConfig(
        disaster_type=IndiaDisasterType.EARTHQUAKE,
        location="Delhi",
        state="Delhi",
        regional_language=PostLanguage.HINDI,
        category_weights={"rescue_request": 0.6, "eyewitness": 0.4},
    )
    dist = gen._distribute_categories(50, config)
    assert sum(dist.values()) == 50
    assert dist[PostCategory.RESCUE_REQUEST] == 30
    assert dist[PostCategory.EYEWITNESS] == 20


# =============================================================================
# Test 11-13: Prompt building
# =============================================================================


def test_build_prompt_english():
    from src.data.synthetic.social_media_gen import (
        PostCategory,
        PostConfig,
        PostLanguage,
        SocialMediaGenerator,
    )

    gen = SocialMediaGenerator(router=MagicMock())
    config = PostConfig(
        disaster_type=IndiaDisasterType.CYCLONE,
        location="Puri",
        state="Odisha",
        regional_language=PostLanguage.ODIA,
        scenario_description="Cyclone Fani making landfall near Puri",
    )
    msgs = gen._build_prompt(config, PostCategory.RESCUE_REQUEST, PostLanguage.ENGLISH, 5)
    assert len(msgs) == 2  # system + user
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert "english" in msgs[1]["content"].lower() or "English" in msgs[1]["content"]
    assert "rescue" in msgs[1]["content"].lower()
    assert "JSON" in msgs[1]["content"] or "json" in msgs[1]["content"]


def test_build_prompt_hindi():
    from src.data.synthetic.social_media_gen import (
        PostCategory,
        PostConfig,
        PostLanguage,
        SocialMediaGenerator,
    )

    gen = SocialMediaGenerator(router=MagicMock())
    config = PostConfig(
        disaster_type=IndiaDisasterType.MONSOON_FLOOD,
        location="Patna",
        state="Bihar",
        regional_language=PostLanguage.HINDI,
    )
    msgs = gen._build_prompt(config, PostCategory.EYEWITNESS, PostLanguage.HINDI, 3)
    assert "hindi" in msgs[1]["content"].lower() or "Hindi" in msgs[1]["content"]


def test_build_prompt_regional():
    from src.data.synthetic.social_media_gen import (
        PostCategory,
        PostConfig,
        PostLanguage,
        SocialMediaGenerator,
    )

    gen = SocialMediaGenerator(router=MagicMock())
    config = PostConfig(
        disaster_type=IndiaDisasterType.CYCLONE,
        location="Chennai",
        state="Tamil Nadu",
        regional_language=PostLanguage.TAMIL,
    )
    msgs = gen._build_prompt(config, PostCategory.INFRASTRUCTURE_DAMAGE, PostLanguage.TAMIL, 5)
    assert "tamil" in msgs[1]["content"].lower() or "Tamil" in msgs[1]["content"]


# =============================================================================
# Test 14-15: LLM response parsing
# =============================================================================


def test_parse_llm_response_valid():
    from src.data.synthetic.social_media_gen import (
        PostCategory,
        PostConfig,
        PostLanguage,
        SocialMediaGenerator,
    )

    gen = SocialMediaGenerator(router=MagicMock())
    config = PostConfig(
        disaster_type=IndiaDisasterType.CYCLONE,
        location="Puri",
        state="Odisha",
        regional_language=PostLanguage.ODIA,
    )
    llm_output = json.dumps(
        [
            {
                "text": "Urgent rescue needed at Puri beach road! #CycloneFani",
                "timestamp_offset_minutes": 60,
                "credibility": 0.85,
                "sentiment": "panic",
                "has_hashtags": True,
                "has_location_tag": True,
            },
            {
                "text": "Trees uprooted on NH-16 near Puri, road blocked",
                "timestamp_offset_minutes": 90,
                "credibility": 0.9,
                "sentiment": "neutral",
                "has_hashtags": False,
                "has_location_tag": False,
            },
        ]
    )
    posts = gen._parse_llm_response(
        llm_output, config, PostCategory.RESCUE_REQUEST, PostLanguage.ENGLISH
    )
    assert len(posts) == 2
    assert posts[0].language == PostLanguage.ENGLISH
    assert posts[0].category == PostCategory.RESCUE_REQUEST
    assert posts[0].disaster_type == IndiaDisasterType.CYCLONE
    assert posts[0].location == "Puri"
    assert posts[0].state == "Odisha"


def test_parse_llm_response_malformed():
    from src.data.synthetic.social_media_gen import (
        PostCategory,
        PostConfig,
        PostLanguage,
        SocialMediaGenerator,
    )

    gen = SocialMediaGenerator(router=MagicMock())
    config = PostConfig(
        disaster_type=IndiaDisasterType.CYCLONE,
        location="Puri",
        state="Odisha",
        regional_language=PostLanguage.ODIA,
    )
    # Malformed JSON — should return empty list, not crash
    posts = gen._parse_llm_response(
        "this is not json {{{", config, PostCategory.EYEWITNESS, PostLanguage.ENGLISH
    )
    assert posts == []


# =============================================================================
# Test 16-20: Generation with mocked router
# =============================================================================


@pytest.mark.asyncio
async def test_generate_posts_for_category():
    from src.data.synthetic.social_media_gen import (
        PostCategory,
        PostConfig,
        PostLanguage,
        SocialMediaGenerator,
    )

    mock_router = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps(
        [
            {
                "text": f"Rescue needed at location {i}!",
                "timestamp_offset_minutes": i * 30,
                "credibility": 0.8,
                "sentiment": "panic",
                "has_hashtags": True,
                "has_location_tag": False,
            }
            for i in range(5)
        ]
    )
    mock_response.cost_usd = 0.0001
    mock_router.call = AsyncMock(return_value=mock_response)

    gen = SocialMediaGenerator(router=mock_router)
    config = PostConfig(
        disaster_type=IndiaDisasterType.MONSOON_FLOOD,
        location="Patna",
        state="Bihar",
        regional_language=PostLanguage.HINDI,
    )
    posts = await gen.generate_posts_for_category(
        config, PostCategory.RESCUE_REQUEST, PostLanguage.ENGLISH, 5
    )
    assert len(posts) == 5
    for p in posts:
        assert p.category == PostCategory.RESCUE_REQUEST
        assert p.language == PostLanguage.ENGLISH
    mock_router.call.assert_called()


@pytest.mark.asyncio
async def test_generate_batch_full():
    from src.data.synthetic.social_media_gen import (
        PostConfig,
        PostLanguage,
        SocialMediaGenerator,
    )

    mock_router = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps(
        [
            {
                "text": f"Post number {i}",
                "timestamp_offset_minutes": i * 10,
                "credibility": 0.7,
                "sentiment": "neutral",
                "has_hashtags": False,
                "has_location_tag": False,
            }
            for i in range(10)
        ]
    )
    mock_response.cost_usd = 0.0002
    mock_router.call = AsyncMock(return_value=mock_response)

    gen = SocialMediaGenerator(router=mock_router)
    config = PostConfig(
        disaster_type=IndiaDisasterType.CYCLONE,
        location="Puri",
        state="Odisha",
        regional_language=PostLanguage.ODIA,
        num_posts=20,
    )
    batch = await gen.generate_batch(config)
    assert batch.config == config
    assert len(batch.posts) > 0
    assert batch.generation_cost_usd >= 0
    assert batch.generation_time_s >= 0


@pytest.mark.asyncio
async def test_generate_batch_language_distribution():
    from src.data.synthetic.social_media_gen import (
        PostConfig,
        PostLanguage,
        SocialMediaGenerator,
    )

    mock_router = AsyncMock()

    def make_response(count):
        resp = MagicMock()
        resp.content = json.dumps(
            [
                {
                    "text": f"Post {i}",
                    "timestamp_offset_minutes": i * 5,
                    "credibility": 0.8,
                    "sentiment": "neutral",
                    "has_hashtags": False,
                    "has_location_tag": False,
                }
                for i in range(count)
            ]
        )
        resp.cost_usd = 0.0001
        return resp

    mock_router.call = AsyncMock(side_effect=lambda *a, **kw: make_response(10))

    gen = SocialMediaGenerator(router=mock_router)
    config = PostConfig(
        disaster_type=IndiaDisasterType.CYCLONE,
        location="Puri",
        state="Odisha",
        regional_language=PostLanguage.ODIA,
        num_posts=100,
    )
    batch = await gen.generate_batch(config)

    # Check that posts have mixed languages
    languages = {p.language for p in batch.posts}
    assert len(languages) >= 2  # At least 2 different languages


@pytest.mark.asyncio
async def test_generate_batch_tracks_cost():
    from src.data.synthetic.social_media_gen import (
        PostConfig,
        PostLanguage,
        SocialMediaGenerator,
    )

    mock_router = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps(
        [
            {
                "text": "Test post",
                "timestamp_offset_minutes": 0,
                "credibility": 0.8,
                "sentiment": "neutral",
                "has_hashtags": False,
                "has_location_tag": False,
            }
        ]
    )
    mock_response.cost_usd = 0.005
    mock_router.call = AsyncMock(return_value=mock_response)

    gen = SocialMediaGenerator(router=mock_router)
    config = PostConfig(
        disaster_type=IndiaDisasterType.MONSOON_FLOOD,
        location="Guwahati",
        state="Assam",
        regional_language=PostLanguage.BENGALI,
        num_posts=10,
    )
    batch = await gen.generate_batch(config)
    assert batch.generation_cost_usd > 0


def test_misinformation_low_credibility():
    from src.data.synthetic.social_media_gen import (
        PostCategory,
        PostConfig,
        PostLanguage,
        SocialMediaGenerator,
    )

    gen = SocialMediaGenerator(router=MagicMock())
    config = PostConfig(
        disaster_type=IndiaDisasterType.EARTHQUAKE,
        location="Delhi",
        state="Delhi",
        regional_language=PostLanguage.HINDI,
    )
    llm_output = json.dumps(
        [
            {
                "text": "FAKE: Government says earthquake is 9.0 magnitude!",
                "timestamp_offset_minutes": 10,
                "credibility": 0.9,  # LLM might return high, but we force it low
                "sentiment": "panic",
                "has_hashtags": False,
                "has_location_tag": False,
            }
        ]
    )
    posts = gen._parse_llm_response(
        llm_output, config, PostCategory.MISINFORMATION, PostLanguage.ENGLISH
    )
    assert len(posts) == 1
    # Misinformation posts must have credibility capped at 0.3
    assert posts[0].credibility <= 0.3
