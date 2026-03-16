"""Unit tests for the Communication Appropriateness metric (spec S8.9).

Tests LLM-as-judge evaluation of multilingual quality, NDMA guideline
adherence, audience appropriateness, actionable content, and channel
formatting. All tests are pure computation — no external APIs.
"""

from __future__ import annotations

import uuid

import pytest

from src.benchmark.models import (
    AgentExpectation,
    BenchmarkScenario,
    EvaluationRun,
    GroundTruthDecisions,
    ScenarioEvent,
)
from src.shared.models import DisasterPhase

# =============================================================================
# Helpers
# =============================================================================


def _make_scenario(
    agent_expectations: dict[str, AgentExpectation] | None = None,
) -> BenchmarkScenario:
    if agent_expectations is None:
        agent_expectations = {
            "community_comms": AgentExpectation(
                key_observations=[
                    "expected_languages=hindi,odia",
                    "expected_audiences=public,first_responders",
                    "expected_channels=whatsapp,sms",
                    "expected_helplines=1070,9711077372",
                    "ndma_guidelines=NDMA-CYC-01,NDMA-FLD-03",
                ],
                expected_actions=[
                    "Generate bilingual alert",
                    "Include shelter locations",
                ],
                time_window_minutes=(0, 20),
            ),
        }
    return BenchmarkScenario(
        category="cyclone",
        complexity="medium",
        affected_states=["Odisha"],
        event_sequence=[
            ScenarioEvent(
                time_offset_minutes=0,
                phase=DisasterPhase.ACTIVE_RESPONSE,
                event_type="sachet_alert",
                description="SACHET alert for cyclone",
            ),
        ],
        ground_truth_decisions=GroundTruthDecisions(
            agent_expectations=agent_expectations,
            decision_timeline={"t0": "Alert received"},
            ndma_references=["NDMA-CYC-01"],
        ),
    )


def _make_run(
    scenario_id: uuid.UUID,
    agent_decisions: list[dict] | None = None,
) -> EvaluationRun:
    if agent_decisions is None:
        agent_decisions = [
            {
                "agent_id": "community_comms",
                "communications": [
                    {
                        "language": "hindi",
                        "audience": "public",
                        "channel": "whatsapp",
                        "content": "Cyclone alert for Odisha...",
                        "helplines_included": ["1070", "9711077372"],
                        "shelter_info": True,
                        "evacuation_routes": True,
                    },
                    {
                        "language": "odia",
                        "audience": "public",
                        "channel": "sms",
                        "content": "Odisha re cyclone alert...",
                        "helplines_included": ["1070"],
                        "shelter_info": True,
                        "evacuation_routes": False,
                    },
                ],
                "languages_used": ["hindi", "odia"],
                "audiences_addressed": ["public", "first_responders"],
                "channels_formatted": ["whatsapp", "sms"],
                "ndma_references": ["NDMA-CYC-01", "NDMA-FLD-03"],
            },
        ]
    return EvaluationRun(
        scenario_id=scenario_id,
        agent_config={"acceleration": 5.0},
        agent_decisions=agent_decisions,
    )


# =============================================================================
# Test Group 1: Pydantic Models
# =============================================================================


class TestModels:
    """Tests for metric-specific Pydantic models."""

    def test_communication_entry_valid(self):
        from src.benchmark.metrics.communication import CommunicationEntry

        entry = CommunicationEntry(
            language="hindi",
            audience="public",
            channel="whatsapp",
            content="Cyclone alert...",
            helplines_included=["1070"],
            shelter_info=True,
            evacuation_routes=False,
        )
        assert entry.language == "hindi"
        assert entry.shelter_info is True

    def test_communication_entry_defaults(self):
        from src.benchmark.metrics.communication import CommunicationEntry

        entry = CommunicationEntry(
            language="english",
            audience="first_responders",
            channel="email",
            content="Technical briefing",
        )
        assert entry.helplines_included == []
        assert entry.shelter_info is False
        assert entry.evacuation_routes is False

    def test_sub_dimension_score_valid(self):
        from src.benchmark.metrics.communication import SubDimensionScore

        score = SubDimensionScore(
            name="language_match",
            score=4.5,
            coverage=0.8,
            details=["hindi covered", "odia covered"],
        )
        assert score.name == "language_match"
        assert score.score == 4.5

    def test_sub_dimension_score_bounds(self):
        from src.benchmark.metrics.communication import SubDimensionScore

        with pytest.raises(ValueError):
            SubDimensionScore(name="test", score=0.5, coverage=0.0)
        with pytest.raises(ValueError):
            SubDimensionScore(name="test", score=5.5, coverage=0.0)

    def test_communication_result_valid(self):
        from src.benchmark.metrics.communication import (
            CommunicationAppropriatenessResult,
            SubDimensionScore,
        )

        result = CommunicationAppropriatenessResult(
            sub_scores={
                "language_match": SubDimensionScore(
                    name="language_match", score=4.0, coverage=0.8,
                ),
            },
            score=4.0,
            languages_expected=["hindi", "odia"],
            languages_found=["hindi", "odia"],
            communications_count=2,
        )
        assert result.score == 4.0
        assert result.communications_count == 2


# =============================================================================
# Test Group 2: Extraction
# =============================================================================


class TestExtraction:
    """Tests for extracting expectations and communications."""

    def test_extract_communication_expectations(self):
        from src.benchmark.metrics.communication import (
            extract_communication_expectations,
        )

        scenario = _make_scenario()
        expectations = extract_communication_expectations(
            scenario.ground_truth_decisions,
        )

        assert expectations["expected_languages"] == ["hindi", "odia"]
        assert expectations["expected_audiences"] == ["public", "first_responders"]
        assert expectations["expected_channels"] == ["whatsapp", "sms"]
        assert "1070" in expectations["expected_helplines"]
        assert "NDMA-CYC-01" in expectations["ndma_guidelines"]

    def test_extract_expectations_empty(self):
        from src.benchmark.metrics.communication import (
            extract_communication_expectations,
        )

        gt = GroundTruthDecisions(agent_expectations={})
        expectations = extract_communication_expectations(gt)

        assert expectations["expected_languages"] == []
        assert expectations["expected_audiences"] == []

    def test_extract_expectations_no_comms_agent(self):
        from src.benchmark.metrics.communication import (
            extract_communication_expectations,
        )

        gt = GroundTruthDecisions(
            agent_expectations={
                "situation_sense": AgentExpectation(
                    key_observations=["Some obs"],
                    expected_actions=[],
                    time_window_minutes=(0, 15),
                ),
            },
        )
        expectations = extract_communication_expectations(gt)
        assert expectations["expected_languages"] == []

    def test_extract_communications_from_decisions(self):
        from src.benchmark.metrics.communication import (
            extract_communications_from_decisions,
        )

        scenario = _make_scenario()
        run = _make_run(scenario.id)
        comms, meta = extract_communications_from_decisions(
            run.agent_decisions,
        )

        assert len(comms) == 2
        assert comms[0].language == "hindi"
        assert "hindi" in meta["languages_used"]
        assert "whatsapp" in meta["channels_formatted"]

    def test_extract_communications_empty(self):
        from src.benchmark.metrics.communication import (
            extract_communications_from_decisions,
        )

        comms, meta = extract_communications_from_decisions([])
        assert comms == []
        assert meta["languages_used"] == []

    def test_extract_communications_no_comms_agent(self):
        from src.benchmark.metrics.communication import (
            extract_communications_from_decisions,
        )

        decisions = [
            {"agent_id": "situation_sense", "observations": ["obs1"]},
        ]
        comms, meta = extract_communications_from_decisions(decisions)
        assert comms == []


# =============================================================================
# Test Group 3: Language Match Scoring
# =============================================================================


class TestLanguageMatch:
    """Tests for language match sub-dimension scoring."""

    def test_perfect_language_match(self):
        from src.benchmark.metrics.communication import score_language_match

        score = score_language_match(
            expected=["hindi", "odia"],
            actual=["hindi", "odia"],
        )
        assert score.score == 5.0
        assert score.coverage == 1.0

    def test_partial_language_match(self):
        from src.benchmark.metrics.communication import score_language_match

        score = score_language_match(
            expected=["hindi", "odia", "english"],
            actual=["hindi", "odia"],
        )
        assert score.coverage == pytest.approx(2 / 3, abs=0.01)
        assert 3.0 < score.score < 5.0

    def test_no_language_match(self):
        from src.benchmark.metrics.communication import score_language_match

        score = score_language_match(
            expected=["hindi", "odia"],
            actual=["tamil", "telugu"],
        )
        assert score.coverage == 0.0
        assert score.score == 1.0

    def test_empty_expected_languages(self):
        from src.benchmark.metrics.communication import score_language_match

        score = score_language_match(expected=[], actual=["hindi"])
        assert score.score == 3.0  # neutral when no expectations

    def test_empty_actual_languages(self):
        from src.benchmark.metrics.communication import score_language_match

        score = score_language_match(expected=["hindi"], actual=[])
        assert score.score == 1.0
        assert score.coverage == 0.0

    def test_extra_languages_ok(self):
        from src.benchmark.metrics.communication import score_language_match

        score = score_language_match(
            expected=["hindi"],
            actual=["hindi", "odia", "english"],
        )
        assert score.coverage == 1.0
        assert score.score == 5.0


# =============================================================================
# Test Group 4: NDMA Adherence Scoring
# =============================================================================


class TestNDMAAdherence:
    """Tests for NDMA guideline adherence sub-dimension."""

    def test_all_ndma_refs_present(self):
        from src.benchmark.metrics.communication import score_ndma_adherence

        score = score_ndma_adherence(
            expected_refs=["NDMA-CYC-01", "NDMA-FLD-03"],
            actual_refs=["NDMA-CYC-01", "NDMA-FLD-03"],
        )
        assert score.score == 5.0
        assert score.coverage == 1.0

    def test_partial_ndma_refs(self):
        from src.benchmark.metrics.communication import score_ndma_adherence

        score = score_ndma_adherence(
            expected_refs=["NDMA-CYC-01", "NDMA-FLD-03"],
            actual_refs=["NDMA-CYC-01"],
        )
        assert score.coverage == 0.5
        assert 2.0 < score.score < 5.0

    def test_no_ndma_refs(self):
        from src.benchmark.metrics.communication import score_ndma_adherence

        score = score_ndma_adherence(
            expected_refs=["NDMA-CYC-01"],
            actual_refs=[],
        )
        assert score.score == 1.0

    def test_empty_expected_ndma(self):
        from src.benchmark.metrics.communication import score_ndma_adherence

        score = score_ndma_adherence(expected_refs=[], actual_refs=["NDMA-CYC-01"])
        assert score.score == 3.0  # neutral


# =============================================================================
# Test Group 5: Audience Fit Scoring
# =============================================================================


class TestAudienceFit:
    """Tests for audience appropriateness sub-dimension."""

    def test_all_audiences_addressed(self):
        from src.benchmark.metrics.communication import score_audience_fit

        score = score_audience_fit(
            expected=["public", "first_responders"],
            actual=["public", "first_responders"],
        )
        assert score.score == 5.0
        assert score.coverage == 1.0

    def test_partial_audiences(self):
        from src.benchmark.metrics.communication import score_audience_fit

        score = score_audience_fit(
            expected=["public", "first_responders", "vulnerable"],
            actual=["public"],
        )
        assert score.coverage == pytest.approx(1 / 3, abs=0.01)
        assert 1.0 < score.score < 5.0

    def test_no_audiences(self):
        from src.benchmark.metrics.communication import score_audience_fit

        score = score_audience_fit(
            expected=["public"],
            actual=[],
        )
        assert score.score == 1.0

    def test_empty_expected(self):
        from src.benchmark.metrics.communication import score_audience_fit

        score = score_audience_fit(expected=[], actual=["public"])
        assert score.score == 3.0


# =============================================================================
# Test Group 6: Actionable Content Scoring
# =============================================================================


class TestActionableContent:
    """Tests for actionable content sub-dimension."""

    def test_all_actionable_present(self):
        from src.benchmark.metrics.communication import (
            CommunicationEntry,
            score_actionable_content,
        )

        comms = [
            CommunicationEntry(
                language="hindi",
                audience="public",
                channel="whatsapp",
                content="Alert with details",
                helplines_included=["1070", "9711077372"],
                shelter_info=True,
                evacuation_routes=True,
            ),
        ]
        score = score_actionable_content(
            communications=comms,
            expected_helplines=["1070", "9711077372"],
        )
        assert score.score == 5.0

    def test_partial_actionable(self):
        from src.benchmark.metrics.communication import (
            CommunicationEntry,
            score_actionable_content,
        )

        comms = [
            CommunicationEntry(
                language="hindi",
                audience="public",
                channel="whatsapp",
                content="Alert",
                helplines_included=["1070"],
                shelter_info=True,
                evacuation_routes=False,
            ),
        ]
        score = score_actionable_content(
            communications=comms,
            expected_helplines=["1070", "9711077372"],
        )
        assert 2.0 < score.score < 5.0

    def test_no_actionable(self):
        from src.benchmark.metrics.communication import (
            CommunicationEntry,
            score_actionable_content,
        )

        comms = [
            CommunicationEntry(
                language="hindi",
                audience="public",
                channel="whatsapp",
                content="Alert",
            ),
        ]
        score = score_actionable_content(
            communications=comms,
            expected_helplines=["1070"],
        )
        assert score.score == 1.0

    def test_empty_communications(self):
        from src.benchmark.metrics.communication import score_actionable_content

        score = score_actionable_content(
            communications=[],
            expected_helplines=["1070"],
        )
        assert score.score == 1.0

    def test_no_expected_helplines(self):
        from src.benchmark.metrics.communication import (
            CommunicationEntry,
            score_actionable_content,
        )

        comms = [
            CommunicationEntry(
                language="hindi",
                audience="public",
                channel="whatsapp",
                content="Alert",
                shelter_info=True,
                evacuation_routes=True,
            ),
        ]
        score = score_actionable_content(
            communications=comms,
            expected_helplines=[],
        )
        # shelter + routes present = partial actionable score
        assert score.score > 1.0


# =============================================================================
# Test Group 7: Channel Format Scoring
# =============================================================================


class TestChannelFormat:
    """Tests for channel format sub-dimension."""

    def test_all_channels_covered(self):
        from src.benchmark.metrics.communication import score_channel_format

        score = score_channel_format(
            expected=["whatsapp", "sms"],
            actual=["whatsapp", "sms"],
        )
        assert score.score == 5.0
        assert score.coverage == 1.0

    def test_partial_channels(self):
        from src.benchmark.metrics.communication import score_channel_format

        score = score_channel_format(
            expected=["whatsapp", "sms", "media_briefing"],
            actual=["whatsapp"],
        )
        assert score.coverage == pytest.approx(1 / 3, abs=0.01)

    def test_no_channels(self):
        from src.benchmark.metrics.communication import score_channel_format

        score = score_channel_format(expected=["whatsapp"], actual=[])
        assert score.score == 1.0

    def test_empty_expected(self):
        from src.benchmark.metrics.communication import score_channel_format

        score = score_channel_format(expected=[], actual=["whatsapp"])
        assert score.score == 3.0


# =============================================================================
# Test Group 8: Composite Score
# =============================================================================


class TestCompositeScore:
    """Tests for composite score computation."""

    def test_all_perfect(self):
        from src.benchmark.metrics.communication import (
            SubDimensionScore,
            compute_communication_score,
        )

        sub_scores = {
            "language_match": SubDimensionScore(
                name="language_match", score=5.0, coverage=1.0,
            ),
            "ndma_adherence": SubDimensionScore(
                name="ndma_adherence", score=5.0, coverage=1.0,
            ),
            "audience_fit": SubDimensionScore(
                name="audience_fit", score=5.0, coverage=1.0,
            ),
            "actionable_content": SubDimensionScore(
                name="actionable_content", score=5.0, coverage=1.0,
            ),
            "channel_format": SubDimensionScore(
                name="channel_format", score=5.0, coverage=1.0,
            ),
        }
        score = compute_communication_score(sub_scores)
        assert score == 5.0

    def test_all_minimum(self):
        from src.benchmark.metrics.communication import (
            SubDimensionScore,
            compute_communication_score,
        )

        sub_scores = {
            "language_match": SubDimensionScore(
                name="language_match", score=1.0, coverage=0.0,
            ),
            "ndma_adherence": SubDimensionScore(
                name="ndma_adherence", score=1.0, coverage=0.0,
            ),
            "audience_fit": SubDimensionScore(
                name="audience_fit", score=1.0, coverage=0.0,
            ),
            "actionable_content": SubDimensionScore(
                name="actionable_content", score=1.0, coverage=0.0,
            ),
            "channel_format": SubDimensionScore(
                name="channel_format", score=1.0, coverage=0.0,
            ),
        }
        score = compute_communication_score(sub_scores)
        assert score == 1.0

    def test_mixed_scores(self):
        from src.benchmark.metrics.communication import (
            SubDimensionScore,
            compute_communication_score,
        )

        sub_scores = {
            "language_match": SubDimensionScore(
                name="language_match", score=5.0, coverage=1.0,
            ),
            "ndma_adherence": SubDimensionScore(
                name="ndma_adherence", score=3.0, coverage=0.5,
            ),
            "audience_fit": SubDimensionScore(
                name="audience_fit", score=4.0, coverage=0.75,
            ),
            "actionable_content": SubDimensionScore(
                name="actionable_content", score=2.0, coverage=0.25,
            ),
            "channel_format": SubDimensionScore(
                name="channel_format", score=5.0, coverage=1.0,
            ),
        }
        score = compute_communication_score(sub_scores)
        # Weighted: 5*0.25 + 3*0.25 + 4*0.20 + 2*0.20 + 5*0.10 = 1.25+0.75+0.80+0.40+0.50 = 3.70
        assert score == pytest.approx(3.7, abs=0.01)


# =============================================================================
# Test Group 9: Full Compute
# =============================================================================


class TestFullCompute:
    """Tests for the complete CommunicationAppropriatenessMetric.compute()."""

    @pytest.mark.asyncio
    async def test_compute_returns_result(self):
        from src.benchmark.metrics.communication import (
            CommunicationAppropriatenessMetric,
            CommunicationAppropriatenessResult,
        )

        metric = CommunicationAppropriatenessMetric()
        scenario = _make_scenario()
        run = _make_run(scenario.id)

        result = await metric.compute(scenario, run)

        assert isinstance(result, CommunicationAppropriatenessResult)
        assert 1.0 <= result.score <= 5.0
        assert len(result.sub_scores) == 5
        assert result.communications_count == 2

    @pytest.mark.asyncio
    async def test_compute_perfect_match(self):
        from src.benchmark.metrics.communication import (
            CommunicationAppropriatenessMetric,
        )

        metric = CommunicationAppropriatenessMetric()
        scenario = _make_scenario()
        run = _make_run(scenario.id)

        result = await metric.compute(scenario, run)

        # Default fixtures have good coverage
        assert result.score >= 3.5
        assert result.sub_scores["language_match"].coverage == 1.0

    @pytest.mark.asyncio
    async def test_compute_sub_scores_present(self):
        from src.benchmark.metrics.communication import (
            CommunicationAppropriatenessMetric,
        )

        metric = CommunicationAppropriatenessMetric()
        scenario = _make_scenario()
        run = _make_run(scenario.id)

        result = await metric.compute(scenario, run)

        for name in [
            "language_match",
            "ndma_adherence",
            "audience_fit",
            "actionable_content",
            "channel_format",
        ]:
            assert name in result.sub_scores
            assert 1.0 <= result.sub_scores[name].score <= 5.0


# =============================================================================
# Test Group 10: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and graceful degradation."""

    @pytest.mark.asyncio
    async def test_empty_decisions(self):
        from src.benchmark.metrics.communication import (
            CommunicationAppropriatenessMetric,
        )

        metric = CommunicationAppropriatenessMetric()
        scenario = _make_scenario()
        run = _make_run(scenario.id, agent_decisions=[])

        result = await metric.compute(scenario, run)
        assert result.score >= 1.0
        assert result.communications_count == 0

    @pytest.mark.asyncio
    async def test_empty_ground_truth(self):
        from src.benchmark.metrics.communication import (
            CommunicationAppropriatenessMetric,
        )

        metric = CommunicationAppropriatenessMetric()
        scenario = _make_scenario(agent_expectations={})
        run = _make_run(scenario.id)

        result = await metric.compute(scenario, run)
        assert result.score >= 1.0

    @pytest.mark.asyncio
    async def test_both_empty(self):
        from src.benchmark.metrics.communication import (
            CommunicationAppropriatenessMetric,
        )

        metric = CommunicationAppropriatenessMetric()
        scenario = _make_scenario(agent_expectations={})
        run = _make_run(scenario.id, agent_decisions=[])

        result = await metric.compute(scenario, run)
        assert result.score >= 1.0

    @pytest.mark.asyncio
    async def test_missing_communications_field(self):
        from src.benchmark.metrics.communication import (
            CommunicationAppropriatenessMetric,
        )

        metric = CommunicationAppropriatenessMetric()
        scenario = _make_scenario()
        run = _make_run(
            scenario.id,
            agent_decisions=[
                {
                    "agent_id": "community_comms",
                    "reasoning": "Generated alerts in Hindi",
                    "languages_used": ["hindi"],
                },
            ],
        )

        result = await metric.compute(scenario, run)
        assert result.score >= 1.0
