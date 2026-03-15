"""A2A server — publishes agent-to-agent messages over Redis Streams.

Wraps redis_utils with A2A-specific logic: task sending, result delivery,
broadcasts, agent discovery, and consumer group management.
"""

from __future__ import annotations

import uuid
from typing import Any

from src.protocols.a2a.schemas import (
    A2AAgentCard,
    A2AMessage,
    A2AMessageType,
    A2ATask,
    A2ATaskResult,
)
from src.shared.errors import A2AError
from src.shared.redis_utils import (
    STREAM_AGENT_RESPONSES,
    STREAM_AGENT_TASKS,
    stream_create_group,
    stream_len,
    stream_publish,
    stream_trim,
)
from src.shared.telemetry import get_logger

logger = get_logger("a2a.server")


class A2AServer:
    """Publishes A2A messages to Redis Streams.

    Handles all 6 message types: TASK_SEND, TASK_UPDATE, TASK_RESULT,
    TASK_CANCEL, AGENT_DISCOVER, AGENT_CARD.
    """

    def __init__(self, agent_id: str, max_stream_len: int = 10_000) -> None:
        self.agent_id = agent_id
        self.max_stream_len = max_stream_len

    async def send_task(self, task: A2ATask) -> str:
        """Publish a task to the tasks stream. Returns Redis message ID."""
        msg = A2AMessage(
            message_type=A2AMessageType.TASK_SEND,
            source_agent=task.source_agent,
            target_agent=task.target_agent,
            trace_id=task.trace_id,
            payload=task.model_dump(mode="json"),
        )
        return await self._publish(STREAM_AGENT_TASKS, msg)

    async def send_result(self, result: A2ATaskResult) -> str:
        """Publish a task result to the responses stream."""
        msg = A2AMessage(
            message_type=A2AMessageType.TASK_RESULT,
            source_agent=result.agent_id,
            target_agent=None,
            trace_id=result.trace_id,
            payload=result.model_dump(mode="json"),
        )
        return await self._publish(STREAM_AGENT_RESPONSES, msg)

    async def broadcast_update(
        self,
        task_id: uuid.UUID,
        source_agent: str,
        payload: dict[str, Any],
    ) -> str:
        """Broadcast a task update (no specific target)."""
        msg = A2AMessage(
            message_type=A2AMessageType.TASK_UPDATE,
            source_agent=source_agent,
            target_agent=None,
            payload={"task_id": str(task_id), **payload},
        )
        return await self._publish(STREAM_AGENT_TASKS, msg)

    async def cancel_task(
        self,
        task_id: uuid.UUID,
        source_agent: str,
        target_agent: str,
    ) -> str:
        """Send a task cancellation to a specific agent."""
        msg = A2AMessage(
            message_type=A2AMessageType.TASK_CANCEL,
            source_agent=source_agent,
            target_agent=target_agent,
            payload={"task_id": str(task_id)},
        )
        return await self._publish(STREAM_AGENT_TASKS, msg)

    async def discover_agents(self, source_agent: str) -> str:
        """Broadcast an agent discovery request."""
        msg = A2AMessage(
            message_type=A2AMessageType.AGENT_DISCOVER,
            source_agent=source_agent,
            target_agent=None,
            payload={},
        )
        return await self._publish(STREAM_AGENT_TASKS, msg)

    async def register_agent_card(self, card: A2AAgentCard) -> str:
        """Publish an agent card to the responses stream."""
        msg = A2AMessage(
            message_type=A2AMessageType.AGENT_CARD,
            source_agent=card.agent_id,
            target_agent=None,
            payload=card.model_dump(mode="json"),
        )
        return await self._publish(STREAM_AGENT_RESPONSES, msg)

    async def ensure_groups(self, agent_ids: list[str]) -> None:
        """Create consumer groups on both streams for each agent ID."""
        try:
            for agent_id in agent_ids:
                await stream_create_group(STREAM_AGENT_TASKS, agent_id)
                await stream_create_group(STREAM_AGENT_RESPONSES, agent_id)
        except Exception as exc:
            raise A2AError(
                f"Failed to create consumer groups: {exc}",
                context={"agent_ids": agent_ids},
            ) from exc

    async def get_stream_info(self) -> dict[str, int]:
        """Return current stream lengths."""
        return {
            "tasks_stream_len": await stream_len(STREAM_AGENT_TASKS),
            "responses_stream_len": await stream_len(STREAM_AGENT_RESPONSES),
        }

    async def _publish(self, stream: str, msg: A2AMessage) -> str:
        """Serialize and publish a message, trimming if needed."""
        try:
            redis_dict = msg.to_redis_dict()
            msg_id = await stream_publish(stream, redis_dict)

            logger.info(
                "a2a_published",
                stream=stream,
                message_type=msg.message_type.value,
                source_agent=msg.source_agent,
                target_agent=msg.target_agent,
                trace_id=msg.trace_id,
                redis_msg_id=msg_id,
            )

            # Trim if over max length
            length = await stream_len(stream)
            if length > self.max_stream_len:
                await stream_trim(stream, maxlen=self.max_stream_len)

            return msg_id

        except A2AError:
            raise
        except Exception as exc:
            raise A2AError(
                f"Failed to publish {msg.message_type.value} to {stream}: {exc}",
                context={
                    "stream": stream,
                    "message_type": msg.message_type.value,
                    "trace_id": msg.trace_id,
                },
            ) from exc


__all__ = ["A2AServer"]
