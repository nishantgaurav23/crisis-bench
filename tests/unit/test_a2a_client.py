"""Tests for A2A client (spec S4.3).

Tests the async A2A client for subscribing to tasks, sending responses,
and managing message acknowledgment over Redis Streams.
All Redis operations are mocked — no real Redis connection needed.
"""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from src.protocols.a2a.client import A2AClient
from src.protocols.a2a.schemas import (
    A2AAgentCard,
    A2AMessage,
    A2AMessageType,
    A2ATaskResult,
)
from src.shared.models import AgentType, LLMTier, TaskStatus
from src.shared.redis_utils import STREAM_AGENT_RESPONSES, STREAM_AGENT_TASKS

# =============================================================================
# Helpers
# =============================================================================


def _make_redis_message(
    source_agent: str = "orchestrator",
    target_agent: str | None = "situation_sense",
    message_type: A2AMessageType = A2AMessageType.TASK_SEND,
    payload: dict | None = None,
    msg_id: str | None = None,
) -> tuple[str, dict[str, str]]:
    """Create a (stream_id, data_dict) tuple mimicking Redis XREADGROUP output."""
    msg = A2AMessage(
        message_type=message_type,
        source_agent=source_agent,
        target_agent=target_agent,
        payload=payload or {"task_type": "situation_report"},
    )
    if msg_id:
        msg.id = uuid.UUID(msg_id)
    redis_dict = msg.to_redis_dict()
    return ("1-0", redis_dict)


def _wrap_xreadgroup_response(
    stream: str, messages: list[tuple[str, dict[str, str]]]
) -> list:
    """Wrap messages in the XREADGROUP response format: [[stream, [messages]]]."""
    return [[stream, messages]]


# =============================================================================
# 1. Client Creation
# =============================================================================


class TestClientCreation:
    def test_client_creation(self):
        """Create with agent_id and agent_type, verify attributes."""
        client = A2AClient(agent_id="situation_sense", agent_type=AgentType.SITUATION_SENSE)
        assert client.agent_id == "situation_sense"
        assert client.agent_type == AgentType.SITUATION_SENSE
        assert client.task_stream == STREAM_AGENT_TASKS
        assert client.response_stream == STREAM_AGENT_RESPONSES

    def test_client_custom_streams(self):
        """Custom task_stream and response_stream."""
        client = A2AClient(
            agent_id="test_agent",
            agent_type=AgentType.ORCHESTRATOR,
            task_stream="custom:tasks",
            response_stream="custom:responses",
        )
        assert client.task_stream == "custom:tasks"
        assert client.response_stream == "custom:responses"


# =============================================================================
# 2. Start / Stop
# =============================================================================


class TestStartStop:
    @pytest.mark.asyncio
    async def test_client_start_creates_consumer_group(self):
        """start() calls stream_create_group."""
        client = A2AClient(agent_id="situation_sense", agent_type=AgentType.SITUATION_SENSE)
        with patch("src.protocols.a2a.client.stream_create_group", new_callable=AsyncMock) as mock:
            await client.start()
            mock.assert_called_once_with(
                STREAM_AGENT_TASKS,
                "situation_sense",
            )

    @pytest.mark.asyncio
    async def test_stop_signals_shutdown(self):
        """stop() sets shutdown event, listen exits."""
        client = A2AClient(agent_id="test", agent_type=AgentType.ORCHESTRATOR)

        with (
            patch("src.protocols.a2a.client.stream_create_group", new_callable=AsyncMock),
            patch("src.protocols.a2a.client.stream_read_group", new_callable=AsyncMock) as mock_read,
        ):
            mock_read.return_value = []
            await client.start()

            # Start listen in background, stop after a short delay
            async def stop_soon():
                await asyncio.sleep(0.05)
                await client.stop()

            listen_task = asyncio.create_task(client.listen(poll_interval_ms=10))
            stop_task = asyncio.create_task(stop_soon())

            await asyncio.gather(listen_task, stop_task)
            # If we get here, listen exited gracefully


# =============================================================================
# 3. Callback Registration
# =============================================================================


class TestCallbackRegistration:
    def test_register_callback(self):
        """on_message() stores callback for message type."""
        client = A2AClient(agent_id="test", agent_type=AgentType.ORCHESTRATOR)
        callback = AsyncMock()
        client.on_message(A2AMessageType.TASK_SEND, callback)
        assert A2AMessageType.TASK_SEND in client._callbacks
        assert client._callbacks[A2AMessageType.TASK_SEND] is callback


# =============================================================================
# 4. Send Methods
# =============================================================================


class TestSendMethods:
    @pytest.mark.asyncio
    async def test_send_result(self):
        """Publishes A2AMessage with TASK_RESULT type to response stream."""
        client = A2AClient(agent_id="situation_sense", agent_type=AgentType.SITUATION_SENSE)
        result = A2ATaskResult(
            task_id=uuid.uuid4(),
            agent_id="situation_sense",
            status=TaskStatus.COMPLETED,
            confidence=0.9,
        )
        with patch("src.protocols.a2a.client.stream_publish", new_callable=AsyncMock) as mock:
            mock.return_value = "1-1"
            stream_id = await client.send_result(result)
            assert stream_id == "1-1"
            mock.assert_called_once()
            call_args = mock.call_args
            assert call_args[0][0] == STREAM_AGENT_RESPONSES
            data = call_args[0][1]
            assert data["message_type"] == A2AMessageType.TASK_RESULT.value
            assert data["source_agent"] == "situation_sense"

    @pytest.mark.asyncio
    async def test_send_result_message_format(self):
        """Verify the A2AMessage envelope fields."""
        client = A2AClient(agent_id="situation_sense", agent_type=AgentType.SITUATION_SENSE)
        task_id = uuid.uuid4()
        result = A2ATaskResult(
            task_id=task_id,
            agent_id="situation_sense",
            status=TaskStatus.COMPLETED,
        )
        with patch("src.protocols.a2a.client.stream_publish", new_callable=AsyncMock) as mock:
            mock.return_value = "1-1"
            await client.send_result(result)
            data = mock.call_args[0][1]
            # Payload should contain the serialized result
            payload = json.loads(data["payload"])
            assert payload["task_id"] == str(task_id)
            assert payload["status"] == TaskStatus.COMPLETED.value

    @pytest.mark.asyncio
    async def test_send_update(self):
        """Publishes TASK_UPDATE with status and payload."""
        client = A2AClient(agent_id="test", agent_type=AgentType.ORCHESTRATOR)
        task_id = uuid.uuid4()
        with patch("src.protocols.a2a.client.stream_publish", new_callable=AsyncMock) as mock:
            mock.return_value = "1-2"
            stream_id = await client.send_update(
                task_id=task_id,
                status=TaskStatus.IN_PROGRESS,
                payload={"progress": 50},
            )
            assert stream_id == "1-2"
            data = mock.call_args[0][1]
            assert data["message_type"] == A2AMessageType.TASK_UPDATE.value
            payload = json.loads(data["payload"])
            assert payload["task_id"] == str(task_id)
            assert payload["status"] == TaskStatus.IN_PROGRESS.value

    @pytest.mark.asyncio
    async def test_send_agent_card(self):
        """Publishes AGENT_CARD message."""
        client = A2AClient(agent_id="situation_sense", agent_type=AgentType.SITUATION_SENSE)
        card = A2AAgentCard(
            agent_id="situation_sense",
            agent_type=AgentType.SITUATION_SENSE,
            name="SituationSense",
            description="Multi-source data fusion",
            capabilities=["imd_data"],
            llm_tier=LLMTier.ROUTINE,
        )
        with patch("src.protocols.a2a.client.stream_publish", new_callable=AsyncMock) as mock:
            mock.return_value = "1-3"
            stream_id = await client.send_agent_card(card)
            assert stream_id == "1-3"
            data = mock.call_args[0][1]
            assert data["message_type"] == A2AMessageType.AGENT_CARD.value

    @pytest.mark.asyncio
    async def test_request_discovery(self):
        """Publishes AGENT_DISCOVER broadcast (target_agent=None)."""
        client = A2AClient(agent_id="orchestrator", agent_type=AgentType.ORCHESTRATOR)
        with patch("src.protocols.a2a.client.stream_publish", new_callable=AsyncMock) as mock:
            mock.return_value = "1-4"
            stream_id = await client.request_discovery()
            assert stream_id == "1-4"
            data = mock.call_args[0][1]
            assert data["message_type"] == A2AMessageType.AGENT_DISCOVER.value
            assert data["target_agent"] == ""  # None serialized as empty string

    @pytest.mark.asyncio
    async def test_cancel_task(self):
        """Publishes TASK_CANCEL to target agent."""
        client = A2AClient(agent_id="orchestrator", agent_type=AgentType.ORCHESTRATOR)
        task_id = uuid.uuid4()
        with patch("src.protocols.a2a.client.stream_publish", new_callable=AsyncMock) as mock:
            mock.return_value = "1-5"
            stream_id = await client.cancel_task(
                task_id=task_id, target_agent="situation_sense"
            )
            assert stream_id == "1-5"
            data = mock.call_args[0][1]
            assert data["message_type"] == A2AMessageType.TASK_CANCEL.value
            assert data["target_agent"] == "situation_sense"
            payload = json.loads(data["payload"])
            assert payload["task_id"] == str(task_id)


# =============================================================================
# 5. Listen Loop
# =============================================================================


class TestListenLoop:
    @pytest.mark.asyncio
    async def test_listen_dispatches_to_callback(self):
        """Listen reads message, calls registered callback."""
        client = A2AClient(agent_id="situation_sense", agent_type=AgentType.SITUATION_SENSE)
        callback = AsyncMock()
        client.on_message(A2AMessageType.TASK_SEND, callback)

        msg_data = _make_redis_message(target_agent="situation_sense")
        response = _wrap_xreadgroup_response(STREAM_AGENT_TASKS, [msg_data])

        call_count = 0

        async def mock_read(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return response
            # Signal shutdown after first batch
            await client.stop()
            return []

        with (
            patch("src.protocols.a2a.client.stream_create_group", new_callable=AsyncMock),
            patch("src.protocols.a2a.client.stream_read_group", side_effect=mock_read),
            patch("src.protocols.a2a.client.stream_ack", new_callable=AsyncMock),
            patch("src.protocols.a2a.client.get_redis", new_callable=AsyncMock) as mock_get_redis,
        ):
            mock_redis = AsyncMock()
            mock_redis.sismember = AsyncMock(return_value=False)
            mock_redis.sadd = AsyncMock()
            mock_redis.expire = AsyncMock()
            mock_get_redis.return_value = mock_redis

            await client.start()
            await client.listen(poll_interval_ms=10)

            callback.assert_called_once()
            received_msg = callback.call_args[0][0]
            assert isinstance(received_msg, A2AMessage)
            assert received_msg.message_type == A2AMessageType.TASK_SEND

    @pytest.mark.asyncio
    async def test_listen_filters_by_target_agent(self):
        """Skips messages not addressed to this agent."""
        client = A2AClient(agent_id="situation_sense", agent_type=AgentType.SITUATION_SENSE)
        callback = AsyncMock()
        client.on_message(A2AMessageType.TASK_SEND, callback)

        # Message addressed to a different agent
        msg_data = _make_redis_message(target_agent="predictive_risk")
        response = _wrap_xreadgroup_response(STREAM_AGENT_TASKS, [msg_data])

        call_count = 0

        async def mock_read(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return response
            await client.stop()
            return []

        with (
            patch("src.protocols.a2a.client.stream_create_group", new_callable=AsyncMock),
            patch("src.protocols.a2a.client.stream_read_group", side_effect=mock_read),
            patch("src.protocols.a2a.client.stream_ack", new_callable=AsyncMock),
            patch("src.protocols.a2a.client.get_redis", new_callable=AsyncMock) as mock_get_redis,
        ):
            mock_redis = AsyncMock()
            mock_redis.sismember = AsyncMock(return_value=False)
            mock_redis.sadd = AsyncMock()
            mock_redis.expire = AsyncMock()
            mock_get_redis.return_value = mock_redis

            await client.start()
            await client.listen(poll_interval_ms=10)

            callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_listen_accepts_broadcasts(self):
        """Processes messages with target_agent=None."""
        client = A2AClient(agent_id="situation_sense", agent_type=AgentType.SITUATION_SENSE)
        callback = AsyncMock()
        client.on_message(A2AMessageType.AGENT_DISCOVER, callback)

        msg_data = _make_redis_message(
            target_agent=None,
            message_type=A2AMessageType.AGENT_DISCOVER,
        )
        response = _wrap_xreadgroup_response(STREAM_AGENT_TASKS, [msg_data])

        call_count = 0

        async def mock_read(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return response
            await client.stop()
            return []

        with (
            patch("src.protocols.a2a.client.stream_create_group", new_callable=AsyncMock),
            patch("src.protocols.a2a.client.stream_read_group", side_effect=mock_read),
            patch("src.protocols.a2a.client.stream_ack", new_callable=AsyncMock),
            patch("src.protocols.a2a.client.get_redis", new_callable=AsyncMock) as mock_get_redis,
        ):
            mock_redis = AsyncMock()
            mock_redis.sismember = AsyncMock(return_value=False)
            mock_redis.sadd = AsyncMock()
            mock_redis.expire = AsyncMock()
            mock_get_redis.return_value = mock_redis

            await client.start()
            await client.listen(poll_interval_ms=10)

            callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_listen_acknowledges_messages(self):
        """Calls stream_ack after processing."""
        client = A2AClient(agent_id="situation_sense", agent_type=AgentType.SITUATION_SENSE)
        callback = AsyncMock()
        client.on_message(A2AMessageType.TASK_SEND, callback)

        msg_data = _make_redis_message(target_agent="situation_sense")
        response = _wrap_xreadgroup_response(STREAM_AGENT_TASKS, [msg_data])

        call_count = 0

        async def mock_read(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return response
            await client.stop()
            return []

        with (
            patch("src.protocols.a2a.client.stream_create_group", new_callable=AsyncMock),
            patch("src.protocols.a2a.client.stream_read_group", side_effect=mock_read),
            patch("src.protocols.a2a.client.stream_ack", new_callable=AsyncMock) as mock_ack,
            patch("src.protocols.a2a.client.get_redis", new_callable=AsyncMock) as mock_get_redis,
        ):
            mock_redis = AsyncMock()
            mock_redis.sismember = AsyncMock(return_value=False)
            mock_redis.sadd = AsyncMock()
            mock_redis.expire = AsyncMock()
            mock_get_redis.return_value = mock_redis

            await client.start()
            await client.listen(poll_interval_ms=10)

            mock_ack.assert_called_once()

    @pytest.mark.asyncio
    async def test_listen_deduplicates(self):
        """Skips already-processed messages."""
        client = A2AClient(agent_id="situation_sense", agent_type=AgentType.SITUATION_SENSE)
        callback = AsyncMock()
        client.on_message(A2AMessageType.TASK_SEND, callback)

        msg_data = _make_redis_message(target_agent="situation_sense")
        response = _wrap_xreadgroup_response(STREAM_AGENT_TASKS, [msg_data])

        call_count = 0

        async def mock_read(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return response
            await client.stop()
            return []

        with (
            patch("src.protocols.a2a.client.stream_create_group", new_callable=AsyncMock),
            patch("src.protocols.a2a.client.stream_read_group", side_effect=mock_read),
            patch("src.protocols.a2a.client.stream_ack", new_callable=AsyncMock),
            patch("src.protocols.a2a.client.get_redis", new_callable=AsyncMock) as mock_get_redis,
        ):
            mock_redis = AsyncMock()
            # Simulate already-processed message
            mock_redis.sismember = AsyncMock(return_value=True)
            mock_redis.sadd = AsyncMock()
            mock_redis.expire = AsyncMock()
            mock_get_redis.return_value = mock_redis

            await client.start()
            await client.listen(poll_interval_ms=10)

            callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_listen_handles_no_callback(self):
        """Acknowledges but doesn't crash when no callback registered."""
        client = A2AClient(agent_id="situation_sense", agent_type=AgentType.SITUATION_SENSE)
        # No callback registered for TASK_SEND

        msg_data = _make_redis_message(target_agent="situation_sense")
        response = _wrap_xreadgroup_response(STREAM_AGENT_TASKS, [msg_data])

        call_count = 0

        async def mock_read(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return response
            await client.stop()
            return []

        with (
            patch("src.protocols.a2a.client.stream_create_group", new_callable=AsyncMock),
            patch("src.protocols.a2a.client.stream_read_group", side_effect=mock_read),
            patch("src.protocols.a2a.client.stream_ack", new_callable=AsyncMock) as mock_ack,
            patch("src.protocols.a2a.client.get_redis", new_callable=AsyncMock) as mock_get_redis,
        ):
            mock_redis = AsyncMock()
            mock_redis.sismember = AsyncMock(return_value=False)
            mock_redis.sadd = AsyncMock()
            mock_redis.expire = AsyncMock()
            mock_get_redis.return_value = mock_redis

            await client.start()
            await client.listen(poll_interval_ms=10)

            # Should still acknowledge even without a callback
            mock_ack.assert_called_once()

    @pytest.mark.asyncio
    async def test_listen_continues_on_error(self):
        """Catches error in callback, keeps listening."""
        client = A2AClient(agent_id="situation_sense", agent_type=AgentType.SITUATION_SENSE)

        from src.shared.errors import A2AError

        failing_callback = AsyncMock(side_effect=A2AError("test error"))
        client.on_message(A2AMessageType.TASK_SEND, failing_callback)

        msg_data = _make_redis_message(target_agent="situation_sense")
        response = _wrap_xreadgroup_response(STREAM_AGENT_TASKS, [msg_data])

        call_count = 0

        async def mock_read(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return response
            await client.stop()
            return []

        with (
            patch("src.protocols.a2a.client.stream_create_group", new_callable=AsyncMock),
            patch("src.protocols.a2a.client.stream_read_group", side_effect=mock_read),
            patch("src.protocols.a2a.client.stream_ack", new_callable=AsyncMock),
            patch("src.protocols.a2a.client.get_redis", new_callable=AsyncMock) as mock_get_redis,
        ):
            mock_redis = AsyncMock()
            mock_redis.sismember = AsyncMock(return_value=False)
            mock_redis.sadd = AsyncMock()
            mock_redis.expire = AsyncMock()
            mock_get_redis.return_value = mock_redis

            await client.start()
            # Should not raise — listen should catch the error and continue
            await client.listen(poll_interval_ms=10)

            failing_callback.assert_called_once()


# =============================================================================
# 6. Exports
# =============================================================================


class TestExports:
    def test_exports(self):
        """All public names in __all__."""
        from src.protocols.a2a import client

        expected = {"A2AClient", "MessageCallback"}
        assert expected.issubset(set(client.__all__))
