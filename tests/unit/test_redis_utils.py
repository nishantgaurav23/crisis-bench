"""Tests for src/shared/redis_utils.py — Redis Streams + cache utilities.

All tests mock redis.asyncio so no real Redis is needed.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.shared.redis_utils import (
    STREAM_AGENT_RESPONSES,
    STREAM_AGENT_TASKS,
    STREAM_BHUVAN,
    STREAM_EVAL,
    STREAM_IMD,
    STREAM_SACHET,
    STREAM_SEISMIC,
    STREAM_SOCIAL,
    RedisHealthStatus,
    cache_delete,
    cache_get,
    cache_get_json,
    cache_set,
    cache_set_json,
    check_health,
    close_redis,
    create_redis,
    get_redis,
    stream_ack,
    stream_create_group,
    stream_len,
    stream_publish,
    stream_publish_event,
    stream_read,
    stream_read_group,
    stream_trim,
)

# =============================================================================
# Stream Name Constants
# =============================================================================


class TestStreamConstants:
    def test_data_streams(self):
        assert STREAM_IMD == "crisis:data:imd"
        assert STREAM_SACHET == "crisis:data:sachet"
        assert STREAM_SEISMIC == "crisis:data:seismic"
        assert STREAM_SOCIAL == "crisis:data:social"
        assert STREAM_BHUVAN == "crisis:data:bhuvan"

    def test_agent_streams(self):
        assert STREAM_AGENT_TASKS == "crisis:agent:tasks"
        assert STREAM_AGENT_RESPONSES == "crisis:agent:responses"

    def test_eval_stream(self):
        assert STREAM_EVAL == "crisis:eval:results"


# =============================================================================
# Connection Management
# =============================================================================


class TestCreateRedis:
    @pytest.mark.asyncio
    @patch("src.shared.redis_utils.redis_async.from_url")
    @patch("src.shared.redis_utils.get_settings")
    async def test_creates_client_with_correct_url(self, mock_settings, mock_from_url):
        settings = MagicMock()
        settings.redis_url = "redis://localhost:6379/0"
        mock_settings.return_value = settings

        mock_client = AsyncMock()
        mock_from_url.return_value = mock_client

        client = await create_redis()

        mock_from_url.assert_called_once_with("redis://localhost:6379/0", decode_responses=True)
        assert client is mock_client


class TestCloseRedis:
    @pytest.mark.asyncio
    async def test_closes_existing_client(self):
        import src.shared.redis_utils as redis_module

        mock_client = AsyncMock()
        redis_module._redis = mock_client

        await close_redis()

        mock_client.aclose.assert_called_once()
        assert redis_module._redis is None

    @pytest.mark.asyncio
    async def test_close_when_none(self):
        """Closing when no client exists should not raise."""
        import src.shared.redis_utils as redis_module

        redis_module._redis = None
        await close_redis()  # Should not raise


class TestGetRedis:
    @pytest.mark.asyncio
    @patch("src.shared.redis_utils.create_redis", new_callable=AsyncMock)
    async def test_creates_client_if_none(self, mock_create_redis):
        import src.shared.redis_utils as redis_module

        redis_module._redis = None
        mock_client = AsyncMock()
        mock_create_redis.return_value = mock_client

        result = await get_redis()

        mock_create_redis.assert_called_once()
        assert result is mock_client

    @pytest.mark.asyncio
    async def test_returns_existing_client(self):
        import src.shared.redis_utils as redis_module

        mock_client = AsyncMock()
        redis_module._redis = mock_client

        result = await get_redis()

        assert result is mock_client


# =============================================================================
# Health Check
# =============================================================================


class TestCheckHealth:
    @pytest.mark.asyncio
    @patch("src.shared.redis_utils.get_redis", new_callable=AsyncMock)
    async def test_healthy_redis(self, mock_get_redis):
        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        mock_client.info.return_value = {"redis_version": "7.2.4"}
        mock_get_redis.return_value = mock_client

        status = await check_health()

        assert isinstance(status, RedisHealthStatus)
        assert status.connected is True
        assert status.version == "7.2.4"
        assert status.latency_ms >= 0

    @pytest.mark.asyncio
    @patch("src.shared.redis_utils.get_redis", new_callable=AsyncMock)
    async def test_unhealthy_redis(self, mock_get_redis):
        mock_get_redis.side_effect = Exception("Connection refused")

        status = await check_health()

        assert status.connected is False
        assert status.version is None


# =============================================================================
# Cache Operations
# =============================================================================


class TestCacheSet:
    @pytest.mark.asyncio
    @patch("src.shared.redis_utils.get_redis", new_callable=AsyncMock)
    async def test_sets_value_with_default_ttl(self, mock_get_redis):
        mock_client = AsyncMock()
        mock_get_redis.return_value = mock_client

        await cache_set("mykey", "myvalue")

        mock_client.setex.assert_called_once_with("mykey", 300, "myvalue")

    @pytest.mark.asyncio
    @patch("src.shared.redis_utils.get_redis", new_callable=AsyncMock)
    async def test_sets_value_with_custom_ttl(self, mock_get_redis):
        mock_client = AsyncMock()
        mock_get_redis.return_value = mock_client

        await cache_set("mykey", "myvalue", ttl_seconds=60)

        mock_client.setex.assert_called_once_with("mykey", 60, "myvalue")


class TestCacheGet:
    @pytest.mark.asyncio
    @patch("src.shared.redis_utils.get_redis", new_callable=AsyncMock)
    async def test_returns_value_when_exists(self, mock_get_redis):
        mock_client = AsyncMock()
        mock_client.get.return_value = "myvalue"
        mock_get_redis.return_value = mock_client

        result = await cache_get("mykey")

        assert result == "myvalue"
        mock_client.get.assert_called_once_with("mykey")

    @pytest.mark.asyncio
    @patch("src.shared.redis_utils.get_redis", new_callable=AsyncMock)
    async def test_returns_none_when_missing(self, mock_get_redis):
        mock_client = AsyncMock()
        mock_client.get.return_value = None
        mock_get_redis.return_value = mock_client

        result = await cache_get("missing")

        assert result is None


class TestCacheDelete:
    @pytest.mark.asyncio
    @patch("src.shared.redis_utils.get_redis", new_callable=AsyncMock)
    async def test_deletes_key(self, mock_get_redis):
        mock_client = AsyncMock()
        mock_get_redis.return_value = mock_client

        await cache_delete("mykey")

        mock_client.delete.assert_called_once_with("mykey")


class TestCacheSetJson:
    @pytest.mark.asyncio
    @patch("src.shared.redis_utils.get_redis", new_callable=AsyncMock)
    async def test_serializes_dict_to_json(self, mock_get_redis):
        mock_client = AsyncMock()
        mock_get_redis.return_value = mock_client

        data = {"severity": "extreme", "district": "Puri"}
        await cache_set_json("alert:1", data)

        call_args = mock_client.setex.call_args
        assert call_args.args[0] == "alert:1"
        assert call_args.args[1] == 300
        assert json.loads(call_args.args[2]) == data


class TestCacheGetJson:
    @pytest.mark.asyncio
    @patch("src.shared.redis_utils.get_redis", new_callable=AsyncMock)
    async def test_deserializes_json_to_dict(self, mock_get_redis):
        mock_client = AsyncMock()
        data = {"severity": "extreme", "district": "Puri"}
        mock_client.get.return_value = json.dumps(data)
        mock_get_redis.return_value = mock_client

        result = await cache_get_json("alert:1")

        assert result == data

    @pytest.mark.asyncio
    @patch("src.shared.redis_utils.get_redis", new_callable=AsyncMock)
    async def test_returns_none_when_missing(self, mock_get_redis):
        mock_client = AsyncMock()
        mock_client.get.return_value = None
        mock_get_redis.return_value = mock_client

        result = await cache_get_json("missing")

        assert result is None


# =============================================================================
# Stream Publishing
# =============================================================================


class TestStreamPublish:
    @pytest.mark.asyncio
    @patch("src.shared.redis_utils.get_redis", new_callable=AsyncMock)
    async def test_publishes_dict_to_stream(self, mock_get_redis):
        mock_client = AsyncMock()
        mock_client.xadd.return_value = "1234567890-0"
        mock_get_redis.return_value = mock_client

        data = {"temperature": "42.5", "station": "IMD_DEL"}
        msg_id = await stream_publish("crisis:data:imd", data)

        mock_client.xadd.assert_called_once_with("crisis:data:imd", data)
        assert msg_id == "1234567890-0"


class TestStreamPublishEvent:
    @pytest.mark.asyncio
    @patch("src.shared.redis_utils.get_redis", new_callable=AsyncMock)
    async def test_publishes_with_envelope(self, mock_get_redis):
        mock_client = AsyncMock()
        mock_client.xadd.return_value = "1234567890-0"
        mock_get_redis.return_value = mock_client

        payload = {"cyclone_name": "FANI", "category": 4}
        await stream_publish_event("crisis:data:imd", "cyclone_warning", payload)

        call_args = mock_client.xadd.call_args
        stream_name = call_args.args[0]
        message = call_args.args[1]

        assert stream_name == "crisis:data:imd"
        assert message["event_type"] == "cyclone_warning"
        assert json.loads(message["payload_json"]) == payload
        assert "timestamp" in message
        assert "trace_id" in message

    @pytest.mark.asyncio
    @patch("src.shared.redis_utils.get_redis", new_callable=AsyncMock)
    async def test_uses_provided_trace_id(self, mock_get_redis):
        mock_client = AsyncMock()
        mock_client.xadd.return_value = "1234567890-0"
        mock_get_redis.return_value = mock_client

        await stream_publish_event(
            "crisis:data:imd",
            "test_event",
            {"data": "value"},
            trace_id="custom-trace-123",
        )

        call_args = mock_client.xadd.call_args
        message = call_args.args[1]
        assert message["trace_id"] == "custom-trace-123"


# =============================================================================
# Consumer Groups
# =============================================================================


class TestStreamCreateGroup:
    @pytest.mark.asyncio
    @patch("src.shared.redis_utils.get_redis", new_callable=AsyncMock)
    async def test_creates_group(self, mock_get_redis):
        mock_client = AsyncMock()
        mock_get_redis.return_value = mock_client

        await stream_create_group("crisis:data:imd", "agent_situation_sense")

        mock_client.xgroup_create.assert_called_once_with(
            "crisis:data:imd", "agent_situation_sense", id="0", mkstream=True
        )

    @pytest.mark.asyncio
    @patch("src.shared.redis_utils.get_redis", new_callable=AsyncMock)
    async def test_ignores_busygroup_error(self, mock_get_redis):
        from redis.exceptions import ResponseError

        mock_client = AsyncMock()
        mock_client.xgroup_create.side_effect = ResponseError(
            "BUSYGROUP Consumer Group name already exists"
        )
        mock_get_redis.return_value = mock_client

        # Should not raise
        await stream_create_group("crisis:data:imd", "agent_situation_sense")

    @pytest.mark.asyncio
    @patch("src.shared.redis_utils.get_redis", new_callable=AsyncMock)
    async def test_raises_non_busygroup_errors(self, mock_get_redis):
        from redis.exceptions import ResponseError

        mock_client = AsyncMock()
        mock_client.xgroup_create.side_effect = ResponseError("SOME OTHER ERROR")
        mock_get_redis.return_value = mock_client

        with pytest.raises(ResponseError, match="SOME OTHER ERROR"):
            await stream_create_group("crisis:data:imd", "agent_situation_sense")


class TestStreamReadGroup:
    @pytest.mark.asyncio
    @patch("src.shared.redis_utils.get_redis", new_callable=AsyncMock)
    async def test_reads_with_correct_params(self, mock_get_redis):
        mock_client = AsyncMock()
        messages = [["crisis:data:imd", [("1-0", {"data": "test"})]]]
        mock_client.xreadgroup.return_value = messages
        mock_get_redis.return_value = mock_client

        result = await stream_read_group(
            "crisis:data:imd", "my_group", "consumer_1", count=5, block_ms=1000
        )

        mock_client.xreadgroup.assert_called_once_with(
            "my_group",
            "consumer_1",
            {"crisis:data:imd": ">"},
            count=5,
            block=1000,
        )
        assert result == messages


class TestStreamAck:
    @pytest.mark.asyncio
    @patch("src.shared.redis_utils.get_redis", new_callable=AsyncMock)
    async def test_acknowledges_messages(self, mock_get_redis):
        mock_client = AsyncMock()
        mock_client.xack.return_value = 2
        mock_get_redis.return_value = mock_client

        result = await stream_ack("crisis:data:imd", "my_group", "1-0", "2-0")

        mock_client.xack.assert_called_once_with("crisis:data:imd", "my_group", "1-0", "2-0")
        assert result == 2


# =============================================================================
# Simple Stream Operations
# =============================================================================


class TestStreamRead:
    @pytest.mark.asyncio
    @patch("src.shared.redis_utils.get_redis", new_callable=AsyncMock)
    async def test_reads_from_stream(self, mock_get_redis):
        mock_client = AsyncMock()
        messages = [["crisis:data:imd", [("1-0", {"data": "test"})]]]
        mock_client.xread.return_value = messages
        mock_get_redis.return_value = mock_client

        result = await stream_read("crisis:data:imd", last_id="0-0", count=10)

        mock_client.xread.assert_called_once_with({"crisis:data:imd": "0-0"}, count=10)
        assert result == messages


class TestStreamLen:
    @pytest.mark.asyncio
    @patch("src.shared.redis_utils.get_redis", new_callable=AsyncMock)
    async def test_returns_stream_length(self, mock_get_redis):
        mock_client = AsyncMock()
        mock_client.xlen.return_value = 42
        mock_get_redis.return_value = mock_client

        result = await stream_len("crisis:data:imd")

        mock_client.xlen.assert_called_once_with("crisis:data:imd")
        assert result == 42


class TestStreamTrim:
    @pytest.mark.asyncio
    @patch("src.shared.redis_utils.get_redis", new_callable=AsyncMock)
    async def test_trims_stream(self, mock_get_redis):
        mock_client = AsyncMock()
        mock_client.xtrim.return_value = 5
        mock_get_redis.return_value = mock_client

        result = await stream_trim("crisis:data:imd", maxlen=100)

        mock_client.xtrim.assert_called_once_with("crisis:data:imd", maxlen=100)
        assert result == 5


# =============================================================================
# Module-level cleanup fixture
# =============================================================================


@pytest.fixture(autouse=True)
def reset_redis():
    """Reset the module-level Redis client between tests."""
    import src.shared.redis_utils as redis_module

    original = redis_module._redis
    redis_module._redis = None
    yield
    redis_module._redis = original
