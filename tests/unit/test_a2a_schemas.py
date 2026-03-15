"""Tests for A2A message schemas (spec S4.1).

Tests the Pydantic models for agent-to-agent communication over Redis Streams.
Covers creation, validation, serialization roundtrips, and Hypothesis property-based tests.
"""

import uuid
from datetime import datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from src.protocols.a2a.schemas import (
    A2AAgentCard,
    A2AArtifact,
    A2AMessage,
    A2AMessageType,
    A2ATask,
    A2ATaskResult,
)
from src.shared.models import AgentType, LLMTier, TaskStatus

# =============================================================================
# Helpers
# =============================================================================


def _make_artifact(**overrides):
    defaults = {
        "name": "situation_report",
        "content_type": "application/json",
        "data": {"summary": "Cyclone approaching Odisha coast"},
    }
    defaults.update(overrides)
    return A2AArtifact(**defaults)


def _make_task(**overrides):
    defaults = {
        "source_agent": "orchestrator",
        "target_agent": "situation_sense",
        "task_type": "situation_report",
        "payload": {"disaster_id": str(uuid.uuid4())},
    }
    defaults.update(overrides)
    return A2ATask(**defaults)


def _make_task_result(**overrides):
    defaults = {
        "task_id": uuid.uuid4(),
        "agent_id": "situation_sense",
        "status": TaskStatus.COMPLETED,
    }
    defaults.update(overrides)
    return A2ATaskResult(**defaults)


def _make_agent_card(**overrides):
    defaults = {
        "agent_id": "situation_sense_001",
        "agent_type": AgentType.SITUATION_SENSE,
        "name": "SituationSense Agent",
        "description": "Multi-source data fusion for situational awareness",
        "capabilities": ["imd_data", "sachet_alerts", "social_media_nlp"],
        "input_types": ["situation_report", "data_fusion"],
        "output_types": ["geojson_update", "urgency_score"],
        "llm_tier": LLMTier.ROUTINE,
    }
    defaults.update(overrides)
    return A2AAgentCard(**defaults)


def _make_message(**overrides):
    defaults = {
        "message_type": A2AMessageType.TASK_SEND,
        "source_agent": "orchestrator",
        "target_agent": "situation_sense",
        "payload": {"task_type": "situation_report"},
    }
    defaults.update(overrides)
    return A2AMessage(**defaults)


# =============================================================================
# 1. A2AMessageType enum
# =============================================================================


class TestA2AMessageType:
    def test_a2a_message_type_enum(self):
        """All 6 message types exist."""
        assert A2AMessageType.TASK_SEND is not None
        assert A2AMessageType.TASK_UPDATE is not None
        assert A2AMessageType.TASK_RESULT is not None
        assert A2AMessageType.TASK_CANCEL is not None
        assert A2AMessageType.AGENT_DISCOVER is not None
        assert A2AMessageType.AGENT_CARD is not None
        assert len(A2AMessageType) == 6

    def test_a2a_message_type_values(self):
        """Enum values are uppercase strings."""
        for member in A2AMessageType:
            assert member.value == member.name
            assert member.value.isupper() or "_" in member.value


# =============================================================================
# 2. A2AArtifact
# =============================================================================


class TestA2AArtifact:
    def test_a2a_artifact_creation(self):
        """Create artifact with valid data, check defaults."""
        artifact = _make_artifact()
        assert artifact.name == "situation_report"
        assert artifact.content_type == "application/json"
        assert artifact.data == {"summary": "Cyclone approaching Odisha coast"}
        assert isinstance(artifact.id, uuid.UUID)
        assert isinstance(artifact.created_at, datetime)

    def test_a2a_artifact_content_type_validation(self):
        """Rejects obviously invalid content_type (must contain '/')."""
        with pytest.raises(ValidationError):
            _make_artifact(content_type="invalid")


# =============================================================================
# 3. A2ATask
# =============================================================================


class TestA2ATask:
    def test_a2a_task_creation(self):
        """Create task, check defaults."""
        task = _make_task()
        assert task.status == TaskStatus.PENDING
        assert task.depth == 0
        assert task.priority == 3
        assert isinstance(task.id, uuid.UUID)
        assert isinstance(task.trace_id, str)
        assert len(task.trace_id) == 8
        assert task.artifacts == []

    def test_a2a_task_priority_bounds(self):
        """Rejects priority < 1 or > 5."""
        with pytest.raises(ValidationError):
            _make_task(priority=0)
        with pytest.raises(ValidationError):
            _make_task(priority=6)

    def test_a2a_task_depth_bounds(self):
        """Rejects depth < 0 or > 5."""
        with pytest.raises(ValidationError):
            _make_task(depth=-1)
        with pytest.raises(ValidationError):
            _make_task(depth=6)

    def test_a2a_task_trace_id_format(self):
        """trace_id must be 8 hex chars."""
        task = _make_task()
        assert len(task.trace_id) == 8
        int(task.trace_id, 16)  # must not raise

        # explicit valid trace_id
        task2 = _make_task(trace_id="abcd1234")
        assert task2.trace_id == "abcd1234"

        # invalid trace_id (not hex)
        with pytest.raises(ValidationError):
            _make_task(trace_id="xyz12345")

        # wrong length
        with pytest.raises(ValidationError):
            _make_task(trace_id="abc")

    def test_a2a_task_with_artifacts(self):
        """Task with multiple artifacts."""
        art1 = _make_artifact(name="report")
        art2 = _make_artifact(name="risk_map", content_type="application/geo+json")
        task = _make_task(artifacts=[art1, art2])
        assert len(task.artifacts) == 2
        assert task.artifacts[0].name == "report"
        assert task.artifacts[1].name == "risk_map"


# =============================================================================
# 4. A2ATaskResult
# =============================================================================


class TestA2ATaskResult:
    def test_a2a_task_result_creation(self):
        """Create result, check defaults."""
        result = _make_task_result()
        assert result.status == TaskStatus.COMPLETED
        assert result.artifacts == []
        assert result.confidence is None
        assert result.error_message is None
        assert isinstance(result.trace_id, str)
        assert len(result.trace_id) == 8

    def test_a2a_task_result_confidence_bounds(self):
        """Rejects confidence outside 0.0-1.0."""
        with pytest.raises(ValidationError):
            _make_task_result(confidence=-0.1)
        with pytest.raises(ValidationError):
            _make_task_result(confidence=1.1)

        # valid boundaries
        r1 = _make_task_result(confidence=0.0)
        assert r1.confidence == 0.0
        r2 = _make_task_result(confidence=1.0)
        assert r2.confidence == 1.0

    def test_a2a_task_result_with_error(self):
        """FAILED status with error_message."""
        result = _make_task_result(
            status=TaskStatus.FAILED,
            error_message="IMD API timeout after 60s",
        )
        assert result.status == TaskStatus.FAILED
        assert result.error_message == "IMD API timeout after 60s"


# =============================================================================
# 5. A2AAgentCard
# =============================================================================


class TestA2AAgentCard:
    def test_a2a_agent_card_creation(self):
        """Create card with all fields."""
        card = _make_agent_card()
        assert card.agent_id == "situation_sense_001"
        assert card.name == "SituationSense Agent"
        assert len(card.capabilities) == 3
        assert card.max_concurrent_tasks == 1
        assert card.status == "idle"
        assert card.version == "1.0.0"

    def test_a2a_agent_card_uses_shared_enums(self):
        """AgentType, LLMTier from S2.1."""
        card = _make_agent_card()
        assert isinstance(card.agent_type, AgentType)
        assert isinstance(card.llm_tier, LLMTier)
        assert card.agent_type == AgentType.SITUATION_SENSE
        assert card.llm_tier == LLMTier.ROUTINE


# =============================================================================
# 6. A2AMessage envelope
# =============================================================================


class TestA2AMessage:
    def test_a2a_message_envelope_creation(self):
        """Create message with inner payload."""
        msg = _make_message()
        assert msg.message_type == A2AMessageType.TASK_SEND
        assert msg.source_agent == "orchestrator"
        assert msg.target_agent == "situation_sense"
        assert isinstance(msg.id, uuid.UUID)
        assert isinstance(msg.trace_id, str)
        assert len(msg.trace_id) == 8
        assert isinstance(msg.timestamp, datetime)

    def test_a2a_message_to_redis_dict(self):
        """All values are strings, all keys present."""
        msg = _make_message()
        redis_dict = msg.to_redis_dict()
        assert isinstance(redis_dict, dict)
        for key, value in redis_dict.items():
            assert isinstance(key, str), f"Key {key} is not a string"
            assert isinstance(value, (str, bytes)), f"Value for {key} is not a string"
        # Required keys
        assert "id" in redis_dict
        assert "message_type" in redis_dict
        assert "source_agent" in redis_dict
        assert "trace_id" in redis_dict
        assert "timestamp" in redis_dict
        assert "payload" in redis_dict

    def test_a2a_message_from_redis_dict_roundtrip(self):
        """Serialize -> deserialize = identical."""
        msg = _make_message(
            payload={"task_type": "risk_assessment", "severity": 4},
        )
        redis_dict = msg.to_redis_dict()
        restored = A2AMessage.from_redis_dict(redis_dict)
        assert restored.id == msg.id
        assert restored.message_type == msg.message_type
        assert restored.source_agent == msg.source_agent
        assert restored.target_agent == msg.target_agent
        assert restored.trace_id == msg.trace_id
        assert restored.payload == msg.payload

    def test_a2a_message_json_roundtrip(self):
        """model_dump_json -> model_validate_json = identical."""
        msg = _make_message()
        json_str = msg.model_dump_json()
        restored = A2AMessage.model_validate_json(json_str)
        assert restored.id == msg.id
        assert restored.message_type == msg.message_type
        assert restored.source_agent == msg.source_agent
        assert restored.payload == msg.payload

    def test_a2a_message_broadcast(self):
        """target_agent=None for broadcasts."""
        msg = _make_message(
            target_agent=None,
            message_type=A2AMessageType.AGENT_DISCOVER,
        )
        assert msg.target_agent is None
        redis_dict = msg.to_redis_dict()
        restored = A2AMessage.from_redis_dict(redis_dict)
        assert restored.target_agent is None


# =============================================================================
# 7. Hypothesis property-based test
# =============================================================================


# Strategy for valid A2AMessage instances
a2a_message_strategy = st.builds(
    A2AMessage,
    message_type=st.sampled_from(list(A2AMessageType)),
    source_agent=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "Pd")),
        min_size=1,
        max_size=30,
    ),
    target_agent=st.one_of(
        st.none(),
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Pd")),
            min_size=1,
            max_size=30,
        ),
    ),
    payload=st.fixed_dictionaries(
        {"key": st.text(min_size=1, max_size=20)},
    ),
)


class TestHypothesis:
    @given(msg=a2a_message_strategy)
    @settings(max_examples=50)
    def test_hypothesis_roundtrip(self, msg):
        """Any valid A2AMessage roundtrips through Redis dict."""
        redis_dict = msg.to_redis_dict()
        restored = A2AMessage.from_redis_dict(redis_dict)
        assert restored.id == msg.id
        assert restored.message_type == msg.message_type
        assert restored.source_agent == msg.source_agent
        assert restored.target_agent == msg.target_agent
        assert restored.trace_id == msg.trace_id


# =============================================================================
# 8. Exports
# =============================================================================


class TestExports:
    def test_a2a_exports(self):
        """All models in __all__."""
        from src.protocols.a2a import schemas

        expected = {
            "A2AMessageType",
            "A2AArtifact",
            "A2ATask",
            "A2ATaskResult",
            "A2AAgentCard",
            "A2AMessage",
        }
        assert expected.issubset(set(schemas.__all__))
