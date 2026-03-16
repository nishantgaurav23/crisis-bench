"""Unit tests for the Coordination Quality metric (spec S8.8).

Tests inter-agent information sharing, milestone KPIs, response coverage,
and redundancy avoidance. All tests are pure computation — no external APIs.
"""

from __future__ import annotations

import uuid

import pytest

from src.benchmark.metrics.coordination import (
    CoordinationQualityMetric,
    CoordinationQualityResult,
    MessageRecord,
    MilestoneRecord,
    compute_composite_score,
    compute_coverage_score,
    compute_info_sharing_score,
    compute_milestone_score,
    compute_redundancy_score,
    extract_expected_coordination,
    extract_messages,
    extract_milestones,
    ratio_to_score,
)
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
    decision_timeline: dict[str, str] | None = None,
) -> BenchmarkScenario:
    if agent_expectations is None:
        agent_expectations = {}
    if decision_timeline is None:
        decision_timeline = {}
    return BenchmarkScenario(
        id=uuid.uuid4(),
        category="cyclone",
        complexity="high",
        affected_states=["Odisha"],
        event_sequence=[
            ScenarioEvent(
                time_offset_minutes=0,
                phase=DisasterPhase.PRE_EVENT,
                event_type="cyclone_warning",
                description="IMD issues cyclone warning",
            ),
        ],
        ground_truth_decisions=GroundTruthDecisions(
            agent_expectations=agent_expectations,
            decision_timeline=decision_timeline,
            ndma_references=["NDMA-Cyclone-SOP"],
        ),
    )


def _make_run(
    scenario_id: uuid.UUID,
    agent_decisions: list[dict] | None = None,
) -> EvaluationRun:
    return EvaluationRun(
        id=uuid.uuid4(),
        scenario_id=scenario_id,
        agent_decisions=agent_decisions or [],
    )


# =============================================================================
# Tests: Extraction — Messages
# =============================================================================


class TestExtractMessages:
    def test_empty_decisions(self):
        result = extract_messages([])
        assert result == []

    def test_no_messages_field(self):
        decisions = [{"agent_id": "orchestrator"}]
        result = extract_messages(decisions)
        assert result == []

    def test_single_agent_messages(self):
        decisions = [
            {
                "agent_id": "orchestrator",
                "messages_sent": [
                    {
                        "from_agent": "orchestrator",
                        "to_agent": "situation_sense",
                        "message_type": "task_assignment",
                    },
                ],
            },
        ]
        result = extract_messages(decisions)
        assert len(result) == 1
        assert result[0].from_agent == "orchestrator"
        assert result[0].to_agent == "situation_sense"

    def test_multiple_agents_messages(self):
        decisions = [
            {
                "agent_id": "orchestrator",
                "messages_sent": [
                    {
                        "from_agent": "orchestrator",
                        "to_agent": "situation_sense",
                        "message_type": "task_assignment",
                    },
                ],
            },
            {
                "agent_id": "situation_sense",
                "messages_sent": [
                    {
                        "from_agent": "situation_sense",
                        "to_agent": "predictive_risk",
                        "message_type": "data_share",
                    },
                    {
                        "from_agent": "situation_sense",
                        "to_agent": "resource_allocation",
                        "message_type": "data_share",
                    },
                ],
            },
        ]
        result = extract_messages(decisions)
        assert len(result) == 3

    def test_invalid_message_skipped(self):
        decisions = [
            {
                "agent_id": "orchestrator",
                "messages_sent": [
                    {"from_agent": "orchestrator"},  # missing to_agent
                    {
                        "from_agent": "orchestrator",
                        "to_agent": "situation_sense",
                        "message_type": "task",
                    },
                ],
            },
        ]
        result = extract_messages(decisions)
        assert len(result) == 1


# =============================================================================
# Tests: Extraction — Milestones
# =============================================================================


class TestExtractMilestones:
    def test_empty_decisions(self):
        result = extract_milestones([])
        assert result == []

    def test_no_milestones_field(self):
        decisions = [{"agent_id": "orchestrator"}]
        result = extract_milestones(decisions)
        assert result == []

    def test_single_milestone(self):
        decisions = [
            {
                "agent_id": "orchestrator",
                "milestones_reached": [
                    {
                        "milestone_id": "initial_assessment",
                        "agent_id": "situation_sense",
                        "timestamp_minutes": 5,
                    },
                ],
            },
        ]
        result = extract_milestones(decisions)
        assert len(result) == 1
        assert result[0].milestone_id == "initial_assessment"
        assert result[0].timestamp_minutes == 5

    def test_multiple_milestones_across_decisions(self):
        decisions = [
            {
                "agent_id": "orchestrator",
                "milestones_reached": [
                    {
                        "milestone_id": "initial_assessment",
                        "agent_id": "situation_sense",
                        "timestamp_minutes": 5,
                    },
                ],
            },
            {
                "agent_id": "resource_allocation",
                "milestones_reached": [
                    {
                        "milestone_id": "resource_plan",
                        "agent_id": "resource_allocation",
                        "timestamp_minutes": 15,
                    },
                ],
            },
        ]
        result = extract_milestones(decisions)
        assert len(result) == 2


# =============================================================================
# Tests: Extraction — Expected Coordination from Ground Truth
# =============================================================================


class TestExtractExpectedCoordination:
    def test_empty_ground_truth(self):
        gt = GroundTruthDecisions(
            agent_expectations={},
            decision_timeline={},
            ndma_references=[],
        )
        expected_msgs, expected_milestones, expected_agents = (
            extract_expected_coordination(gt)
        )
        assert expected_msgs == []
        assert expected_milestones == {}
        assert expected_agents == set()

    def test_extracts_coordination_actions(self):
        gt = GroundTruthDecisions(
            agent_expectations={
                "situation_sense": AgentExpectation(
                    key_observations=["Cyclone detected"],
                    expected_actions=[
                        "share situation report with predictive_risk",
                        "share weather data with resource_allocation",
                    ],
                    time_window_minutes=(0, 10),
                ),
                "predictive_risk": AgentExpectation(
                    key_observations=["Risk assessed"],
                    expected_actions=[
                        "share risk assessment with resource_allocation",
                    ],
                    time_window_minutes=(5, 15),
                ),
            },
            decision_timeline={
                "initial_assessment": "5",
                "resource_plan": "15",
            },
            ndma_references=[],
        )
        expected_msgs, expected_milestones, expected_agents = (
            extract_expected_coordination(gt)
        )
        # 3 share actions → 3 expected messages
        assert len(expected_msgs) == 3
        # 2 milestones
        assert len(expected_milestones) == 2
        assert expected_milestones["initial_assessment"] == 5
        assert expected_milestones["resource_plan"] == 15
        # 2 agents
        assert expected_agents == {"situation_sense", "predictive_risk"}

    def test_non_share_actions_ignored(self):
        gt = GroundTruthDecisions(
            agent_expectations={
                "resource_allocation": AgentExpectation(
                    key_observations=["Resources checked"],
                    expected_actions=[
                        "allocate NDRF battalions",  # not a "share" action
                        "share resource plan with community_comms",
                    ],
                    time_window_minutes=(10, 20),
                ),
            },
            decision_timeline={},
            ndma_references=[],
        )
        expected_msgs, _, _ = extract_expected_coordination(gt)
        assert len(expected_msgs) == 1  # only the "share" action


# =============================================================================
# Tests: Information Sharing Score
# =============================================================================


class TestInfoSharingScore:
    def test_no_expected_messages(self):
        score = compute_info_sharing_score([], [])
        assert score == 1.0  # No expectations = full score

    def test_all_messages_sent(self):
        expected = [
            ("situation_sense", "predictive_risk"),
            ("predictive_risk", "resource_allocation"),
        ]
        actual = [
            MessageRecord(
                from_agent="situation_sense",
                to_agent="predictive_risk",
                message_type="data_share",
            ),
            MessageRecord(
                from_agent="predictive_risk",
                to_agent="resource_allocation",
                message_type="data_share",
            ),
        ]
        score = compute_info_sharing_score(expected, actual)
        assert score == 1.0

    def test_half_messages_sent(self):
        expected = [
            ("situation_sense", "predictive_risk"),
            ("predictive_risk", "resource_allocation"),
        ]
        actual = [
            MessageRecord(
                from_agent="situation_sense",
                to_agent="predictive_risk",
                message_type="data_share",
            ),
        ]
        score = compute_info_sharing_score(expected, actual)
        assert score == 0.5

    def test_no_messages_sent(self):
        expected = [
            ("situation_sense", "predictive_risk"),
            ("predictive_risk", "resource_allocation"),
        ]
        score = compute_info_sharing_score(expected, [])
        assert score == 0.0


# =============================================================================
# Tests: Milestone Achievement Score
# =============================================================================


class TestMilestoneScore:
    def test_no_expected_milestones(self):
        score = compute_milestone_score({}, [])
        assert score == 1.0

    def test_all_milestones_met(self):
        expected = {"initial_assessment": 10, "resource_plan": 20}
        actual = [
            MilestoneRecord(
                milestone_id="initial_assessment",
                agent_id="situation_sense",
                timestamp_minutes=5,
            ),
            MilestoneRecord(
                milestone_id="resource_plan",
                agent_id="resource_allocation",
                timestamp_minutes=18,
            ),
        ]
        score = compute_milestone_score(expected, actual)
        assert score == 1.0

    def test_some_milestones_missed(self):
        expected = {
            "initial_assessment": 10,
            "resource_plan": 20,
            "evacuation_order": 30,
        }
        actual = [
            MilestoneRecord(
                milestone_id="initial_assessment",
                agent_id="situation_sense",
                timestamp_minutes=5,
            ),
        ]
        score = compute_milestone_score(expected, actual)
        # 1 of 3 milestones met on time
        assert abs(score - 1.0 / 3.0) < 0.01

    def test_milestone_late_partial_credit(self):
        expected = {"initial_assessment": 10}
        actual = [
            MilestoneRecord(
                milestone_id="initial_assessment",
                agent_id="situation_sense",
                timestamp_minutes=15,  # 50% late
            ),
        ]
        score = compute_milestone_score(expected, actual)
        # Late but completed — partial credit (0 < score < 1.0)
        assert 0.0 < score < 1.0

    def test_no_milestones_reached(self):
        expected = {"initial_assessment": 10, "resource_plan": 20}
        score = compute_milestone_score(expected, [])
        assert score == 0.0


# =============================================================================
# Tests: Response Coverage
# =============================================================================


class TestCoverageScore:
    def test_no_expected_agents(self):
        score = compute_coverage_score(set(), set())
        assert score == 1.0

    def test_all_agents_present(self):
        expected = {"situation_sense", "predictive_risk", "resource_allocation"}
        actual = {"situation_sense", "predictive_risk", "resource_allocation"}
        score = compute_coverage_score(expected, actual)
        assert score == 1.0

    def test_some_agents_missing(self):
        expected = {"situation_sense", "predictive_risk", "resource_allocation"}
        actual = {"situation_sense"}
        score = compute_coverage_score(expected, actual)
        assert abs(score - 1.0 / 3.0) < 0.01

    def test_no_agents_present(self):
        expected = {"situation_sense", "predictive_risk"}
        score = compute_coverage_score(expected, set())
        assert score == 0.0

    def test_extra_agents_dont_hurt(self):
        expected = {"situation_sense"}
        actual = {"situation_sense", "predictive_risk", "extra_agent"}
        score = compute_coverage_score(expected, actual)
        assert score == 1.0


# =============================================================================
# Tests: Redundancy Avoidance
# =============================================================================


class TestRedundancyScore:
    def test_no_messages(self):
        score = compute_redundancy_score([])
        assert score == 1.0

    def test_no_duplicates(self):
        messages = [
            MessageRecord(
                from_agent="a", to_agent="b", message_type="data_share",
            ),
            MessageRecord(
                from_agent="b", to_agent="c", message_type="data_share",
            ),
        ]
        score = compute_redundancy_score(messages)
        assert score == 1.0

    def test_some_duplicates(self):
        messages = [
            MessageRecord(
                from_agent="a", to_agent="b", message_type="data_share",
            ),
            MessageRecord(
                from_agent="a", to_agent="b", message_type="data_share",
            ),
            MessageRecord(
                from_agent="b", to_agent="c", message_type="data_share",
            ),
        ]
        score = compute_redundancy_score(messages)
        # 2 unique out of 3 total → redundancy = 1/3 → score = 1 - 1/3
        assert abs(score - 2.0 / 3.0) < 0.01

    def test_all_duplicates(self):
        messages = [
            MessageRecord(
                from_agent="a", to_agent="b", message_type="data_share",
            ),
            MessageRecord(
                from_agent="a", to_agent="b", message_type="data_share",
            ),
        ]
        score = compute_redundancy_score(messages)
        # 1 unique out of 2 → redundancy = 0.5 → score = 0.5
        assert score == 0.5


# =============================================================================
# Tests: ratio_to_score
# =============================================================================


class TestRatioToScore:
    def test_zero(self):
        assert ratio_to_score(0.0) == 1.0

    def test_half(self):
        assert ratio_to_score(0.5) == 3.0

    def test_full(self):
        assert ratio_to_score(1.0) == 5.0

    def test_clamped_below(self):
        assert ratio_to_score(-0.5) == 1.0

    def test_clamped_above(self):
        assert ratio_to_score(1.5) == 5.0


# =============================================================================
# Tests: Composite Score
# =============================================================================


class TestCompositeScore:
    def test_perfect_scores(self):
        score = compute_composite_score(1.0, 1.0, 1.0, 1.0)
        assert score == 5.0

    def test_zero_scores(self):
        score = compute_composite_score(0.0, 0.0, 0.0, 0.0)
        assert score == 1.0

    def test_mixed_scores(self):
        score = compute_composite_score(0.5, 0.5, 0.5, 0.5)
        assert score == 3.0

    def test_weighted_correctly(self):
        # info_sharing=1.0 (weight 0.30), milestone=0.0 (weight 0.30),
        # coverage=1.0 (weight 0.25), redundancy=0.0 (weight 0.15)
        score = compute_composite_score(1.0, 0.0, 1.0, 0.0)
        # (5.0*0.30 + 1.0*0.30 + 5.0*0.25 + 1.0*0.15) = 1.5+0.3+1.25+0.15 = 3.2
        assert abs(score - 3.2) < 0.01


# =============================================================================
# Tests: Full Metric Compute
# =============================================================================


class TestCoordinationQualityMetric:
    @pytest.mark.asyncio
    async def test_perfect_coordination(self):
        scenario = _make_scenario(
            agent_expectations={
                "situation_sense": AgentExpectation(
                    key_observations=["Cyclone detected"],
                    expected_actions=[
                        "share situation report with predictive_risk",
                    ],
                    time_window_minutes=(0, 10),
                ),
                "predictive_risk": AgentExpectation(
                    key_observations=["Risk assessed"],
                    expected_actions=[
                        "share risk assessment with resource_allocation",
                    ],
                    time_window_minutes=(5, 15),
                ),
            },
            decision_timeline={
                "initial_assessment": "10",
                "resource_plan": "20",
            },
        )
        run = _make_run(
            scenario.id,
            agent_decisions=[
                {
                    "agent_id": "situation_sense",
                    "messages_sent": [
                        {
                            "from_agent": "situation_sense",
                            "to_agent": "predictive_risk",
                            "message_type": "data_share",
                        },
                    ],
                    "milestones_reached": [
                        {
                            "milestone_id": "initial_assessment",
                            "agent_id": "situation_sense",
                            "timestamp_minutes": 8,
                        },
                    ],
                },
                {
                    "agent_id": "predictive_risk",
                    "messages_sent": [
                        {
                            "from_agent": "predictive_risk",
                            "to_agent": "resource_allocation",
                            "message_type": "data_share",
                        },
                    ],
                    "milestones_reached": [
                        {
                            "milestone_id": "resource_plan",
                            "agent_id": "resource_allocation",
                            "timestamp_minutes": 18,
                        },
                    ],
                },
            ],
        )

        metric = CoordinationQualityMetric()
        result = await metric.compute(scenario, run)

        assert isinstance(result, CoordinationQualityResult)
        assert result.score >= 4.0  # Near-perfect coordination
        assert result.info_sharing_ratio == 1.0
        assert result.milestone_ratio == 1.0
        assert result.coverage_ratio == 1.0

    @pytest.mark.asyncio
    async def test_no_coordination(self):
        scenario = _make_scenario(
            agent_expectations={
                "situation_sense": AgentExpectation(
                    key_observations=["Cyclone detected"],
                    expected_actions=[
                        "share situation report with predictive_risk",
                    ],
                    time_window_minutes=(0, 10),
                ),
            },
            decision_timeline={"initial_assessment": "10"},
        )
        run = _make_run(
            scenario.id,
            agent_decisions=[],  # No agent decisions at all
        )

        metric = CoordinationQualityMetric()
        result = await metric.compute(scenario, run)

        assert result.score <= 2.0
        assert result.info_sharing_ratio == 0.0
        assert result.milestone_ratio == 0.0
        assert result.coverage_ratio == 0.0

    @pytest.mark.asyncio
    async def test_empty_ground_truth(self):
        scenario = _make_scenario()  # No expectations
        run = _make_run(scenario.id, agent_decisions=[])

        metric = CoordinationQualityMetric()
        result = await metric.compute(scenario, run)

        # No expectations → full score by default
        assert result.score == 5.0

    @pytest.mark.asyncio
    async def test_partial_coordination(self):
        scenario = _make_scenario(
            agent_expectations={
                "situation_sense": AgentExpectation(
                    key_observations=["Cyclone detected"],
                    expected_actions=[
                        "share situation report with predictive_risk",
                        "share weather data with resource_allocation",
                    ],
                    time_window_minutes=(0, 10),
                ),
            },
            decision_timeline={
                "initial_assessment": "10",
                "resource_plan": "20",
            },
        )
        run = _make_run(
            scenario.id,
            agent_decisions=[
                {
                    "agent_id": "situation_sense",
                    "messages_sent": [
                        {
                            "from_agent": "situation_sense",
                            "to_agent": "predictive_risk",
                            "message_type": "data_share",
                        },
                        # Missing: share with resource_allocation
                    ],
                    "milestones_reached": [
                        {
                            "milestone_id": "initial_assessment",
                            "agent_id": "situation_sense",
                            "timestamp_minutes": 8,
                        },
                        # Missing: resource_plan milestone
                    ],
                },
            ],
        )

        metric = CoordinationQualityMetric()
        result = await metric.compute(scenario, run)

        assert 1.0 <= result.score <= 5.0
        assert result.info_sharing_ratio == 0.5
        assert result.milestone_ratio == 0.5
