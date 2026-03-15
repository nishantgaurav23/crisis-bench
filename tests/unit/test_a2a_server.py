"""Tests for A2A server (spec S4.2).

Tests the A2AServer class that publishes A2A messages to Redis Streams.
All Redis calls are mocked — no real Redis needed for unit tests.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from src.protocols.a2a.schemas import (
    A2AAgentCard,
    A2AMessageType,
    A2ATask,
    A2ATaskResult,
)
from src.shared.errors import A2AError
from src.shared.models import AgentType, LLMTier, TaskStatus

# =============================================================================
# Helpers
# =============================================================================


def _make_task(**overrides):
    defaults = {
        "source_agent": "orchestrator",
        "target_agent": "situation_sense",
        "task_type": "situation_report",
        "payload": {"disaster_id": str(uuid.uuid4())},
    }
    defaults.update(overrides)
    return A2ATask(**defaults)


def _make_result(**overrides):
    defaults = {
        "task_id": uuid.uuid4(),
        "agent_id": "situation_sense",
        "status": TaskStatus.COMPLETED,
    }
    defaults.update(overrides)
    return A2ATaskResult(**defaults)


def _make_card(**overrides):
    defaults = {
        "agent_id": "situation_sense_001",
        "agent_type": AgentType.SITUATION_SENSE,
        "name": "SituationSense Agent",
        "description": "Multi-source data fusion",
        "capabilities": ["imd_data", "sachet_alerts"],
        "llm_tier": LLMTier.ROUTINE,
    }
    defaults.update(overrides)
    return A2AAgentCard(**defaults)


# =============================================================================
# Fixtures
# =============================================================================

TASK_STREAM = "crisis:agent:tasks"
RESPONSE_STREAM = "crisis:agent:responses"


@pytest.fixture
def mock_redis():
    """Patch redis_utils functions used by A2AServer."""
    with (
        patch("src.protocols.a2a.server.stream_publish", new_callable=AsyncMock) as pub,
        patch("src.protocols.a2a.server.stream_create_group", new_callable=AsyncMock) as grp,
        patch("src.protocols.a2a.server.stream_len", new_callable=AsyncMock) as slen,
        patch("src.protocols.a2a.server.stream_trim", new_callable=AsyncMock) as trim,
    ):
        pub.return_value = "1234567890-0"
        slen.return_value = 42
        yield {
            "publish": pub,
            "create_group": grp,
            "stream_len": slen,
            "stream_trim": trim,
        }


@pytest.fixture
def server():
    from src.protocols.a2a.server import A2AServer

    return A2AServer(agent_id="orchestrator")


# =============================================================================
# 1. Initialization
# =============================================================================


class TestA2AServerInit:
    def test_init_defaults(self):
        from src.protocols.a2a.server import A2AServer

        s = A2AServer(agent_id="orchestrator")
        assert s.agent_id == "orchestrator"
        assert s.max_stream_len == 10_000

    def test_init_custom_max_stream_len(self):
        from src.protocols.a2a.server import A2AServer

        s = A2AServer(agent_id="test", max_stream_len=500)
        assert s.max_stream_len == 500


# =============================================================================
# 2. send_task
# =============================================================================


class TestSendTask:
    @pytest.mark.asyncio
    async def test_send_task_publishes_to_tasks_stream(self, mock_redis, server):
        task = _make_task()
        msg_id = await server.send_task(task)

        assert msg_id == "1234567890-0"
        mock_redis["publish"].assert_called_once()
        call_args = mock_redis["publish"].call_args
        assert call_args[0][0] == TASK_STREAM  # stream name
        redis_dict = call_args[0][1]
        assert redis_dict["message_type"] == A2AMessageType.TASK_SEND.value
        assert redis_dict["source_agent"] == "orchestrator"
        assert redis_dict["target_agent"] == "situation_sense"

    @pytest.mark.asyncio
    async def test_send_task_payload_contains_task(self, mock_redis, server):
        task = _make_task()
        await server.send_task(task)

        call_args = mock_redis["publish"].call_args
        redis_dict = call_args[0][1]
        # payload should be a JSON string containing the task data
        import json

        payload = json.loads(redis_dict["payload"])
        assert payload["task_type"] == "situation_report"
        assert payload["source_agent"] == "orchestrator"

    @pytest.mark.asyncio
    async def test_send_task_preserves_trace_id(self, mock_redis, server):
        task = _make_task(trace_id="abcd1234")
        await server.send_task(task)

        call_args = mock_redis["publish"].call_args
        redis_dict = call_args[0][1]
        assert redis_dict["trace_id"] == "abcd1234"


# =============================================================================
# 3. send_result
# =============================================================================


class TestSendResult:
    @pytest.mark.asyncio
    async def test_send_result_publishes_to_responses_stream(self, mock_redis, server):
        result = _make_result()
        msg_id = await server.send_result(result)

        assert msg_id == "1234567890-0"
        mock_redis["publish"].assert_called_once()
        call_args = mock_redis["publish"].call_args
        assert call_args[0][0] == RESPONSE_STREAM

    @pytest.mark.asyncio
    async def test_send_result_message_type(self, mock_redis, server):
        result = _make_result()
        await server.send_result(result)

        call_args = mock_redis["publish"].call_args
        redis_dict = call_args[0][1]
        assert redis_dict["message_type"] == A2AMessageType.TASK_RESULT.value

    @pytest.mark.asyncio
    async def test_send_result_contains_result_data(self, mock_redis, server):
        result = _make_result(confidence=0.95)
        await server.send_result(result)

        import json

        call_args = mock_redis["publish"].call_args
        redis_dict = call_args[0][1]
        payload = json.loads(redis_dict["payload"])
        assert payload["agent_id"] == "situation_sense"
        assert payload["confidence"] == 0.95


# =============================================================================
# 4. broadcast_update
# =============================================================================


class TestBroadcastUpdate:
    @pytest.mark.asyncio
    async def test_broadcast_update_publishes_task_update(self, mock_redis, server):
        task_id = uuid.uuid4()
        msg_id = await server.broadcast_update(
            task_id=task_id,
            source_agent="situation_sense",
            payload={"progress": 50},
        )

        assert msg_id == "1234567890-0"
        call_args = mock_redis["publish"].call_args
        assert call_args[0][0] == TASK_STREAM
        redis_dict = call_args[0][1]
        assert redis_dict["message_type"] == A2AMessageType.TASK_UPDATE.value
        assert redis_dict["target_agent"] == ""  # broadcast

    @pytest.mark.asyncio
    async def test_broadcast_update_payload(self, mock_redis, server):
        task_id = uuid.uuid4()
        await server.broadcast_update(
            task_id=task_id,
            source_agent="situation_sense",
            payload={"progress": 75},
        )

        import json

        call_args = mock_redis["publish"].call_args
        redis_dict = call_args[0][1]
        payload = json.loads(redis_dict["payload"])
        assert payload["task_id"] == str(task_id)
        assert payload["progress"] == 75


# =============================================================================
# 5. cancel_task
# =============================================================================


class TestCancelTask:
    @pytest.mark.asyncio
    async def test_cancel_task_publishes_task_cancel(self, mock_redis, server):
        task_id = uuid.uuid4()
        msg_id = await server.cancel_task(
            task_id=task_id,
            source_agent="orchestrator",
            target_agent="situation_sense",
        )

        assert msg_id == "1234567890-0"
        call_args = mock_redis["publish"].call_args
        assert call_args[0][0] == TASK_STREAM
        redis_dict = call_args[0][1]
        assert redis_dict["message_type"] == A2AMessageType.TASK_CANCEL.value
        assert redis_dict["target_agent"] == "situation_sense"


# =============================================================================
# 6. discover_agents
# =============================================================================


class TestDiscoverAgents:
    @pytest.mark.asyncio
    async def test_discover_agents_broadcasts(self, mock_redis, server):
        msg_id = await server.discover_agents(source_agent="orchestrator")

        assert msg_id == "1234567890-0"
        call_args = mock_redis["publish"].call_args
        assert call_args[0][0] == TASK_STREAM
        redis_dict = call_args[0][1]
        assert redis_dict["message_type"] == A2AMessageType.AGENT_DISCOVER.value
        assert redis_dict["target_agent"] == ""  # broadcast


# =============================================================================
# 7. register_agent_card
# =============================================================================


class TestRegisterAgentCard:
    @pytest.mark.asyncio
    async def test_register_agent_card_publishes(self, mock_redis, server):
        card = _make_card()
        msg_id = await server.register_agent_card(card)

        assert msg_id == "1234567890-0"
        call_args = mock_redis["publish"].call_args
        assert call_args[0][0] == RESPONSE_STREAM
        redis_dict = call_args[0][1]
        assert redis_dict["message_type"] == A2AMessageType.AGENT_CARD.value

    @pytest.mark.asyncio
    async def test_register_agent_card_payload(self, mock_redis, server):
        card = _make_card()
        await server.register_agent_card(card)

        import json

        call_args = mock_redis["publish"].call_args
        redis_dict = call_args[0][1]
        payload = json.loads(redis_dict["payload"])
        assert payload["agent_id"] == "situation_sense_001"
        assert payload["name"] == "SituationSense Agent"
        assert "capabilities" in payload


# =============================================================================
# 8. ensure_groups
# =============================================================================


class TestEnsureGroups:
    @pytest.mark.asyncio
    async def test_ensure_groups_creates_for_each_agent(self, mock_redis, server):
        await server.ensure_groups(["orchestrator", "situation_sense", "predictive_risk"])

        # Should create groups on both streams for each agent
        assert mock_redis["create_group"].call_count == 6  # 3 agents x 2 streams

    @pytest.mark.asyncio
    async def test_ensure_groups_empty_list(self, mock_redis, server):
        await server.ensure_groups([])
        mock_redis["create_group"].assert_not_called()


# =============================================================================
# 9. get_stream_info
# =============================================================================


class TestGetStreamInfo:
    @pytest.mark.asyncio
    async def test_get_stream_info(self, mock_redis, server):
        info = await server.get_stream_info()

        assert info["tasks_stream_len"] == 42
        assert info["responses_stream_len"] == 42
        assert mock_redis["stream_len"].call_count == 2


# =============================================================================
# 10. Error handling
# =============================================================================


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_redis_failure_raises_a2a_error(self, mock_redis, server):
        mock_redis["publish"].side_effect = ConnectionError("Redis down")

        task = _make_task()
        with pytest.raises(A2AError) as exc_info:
            await server.send_task(task)

        assert "Redis" in str(exc_info.value) or "publish" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_ensure_groups_redis_failure(self, mock_redis, server):
        mock_redis["create_group"].side_effect = ConnectionError("Redis down")

        with pytest.raises(A2AError):
            await server.ensure_groups(["test_agent"])


# =============================================================================
# 11. Stream trimming
# =============================================================================


class TestStreamTrimming:
    @pytest.mark.asyncio
    async def test_send_task_trims_when_over_max(self, mock_redis, server):
        mock_redis["stream_len"].return_value = 15_000  # over default 10k
        task = _make_task()
        await server.send_task(task)

        # Should have called trim
        mock_redis["stream_trim"].assert_called_once_with(TASK_STREAM, maxlen=10_000)

    @pytest.mark.asyncio
    async def test_send_task_no_trim_when_under_max(self, mock_redis, server):
        mock_redis["stream_len"].return_value = 5_000  # under 10k
        task = _make_task()
        await server.send_task(task)

        mock_redis["stream_trim"].assert_not_called()


# =============================================================================
# 12. Exports
# =============================================================================


class TestExports:
    def test_a2a_server_exports(self):
        from src.protocols.a2a import server as server_mod

        assert hasattr(server_mod, "A2AServer")
        assert "A2AServer" in server_mod.__all__
