"""A2A client for CRISIS-BENCH — Redis Streams subscriber.

Provides an async client for agents to receive tasks, send results,
discover other agents, and manage message acknowledgment via Redis Streams
consumer groups. Built on S4.1 schemas and S2.3 Redis utilities.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from src.protocols.a2a.schemas import (
    A2AAgentCard,
    A2AMessage,
    A2AMessageType,
    A2ATaskResult,
)
from src.shared.errors import A2AError
from src.shared.models import AgentType, TaskStatus
from src.shared.redis_utils import (
    STREAM_AGENT_RESPONSES,
    STREAM_AGENT_TASKS,
    get_redis,
    stream_ack,
    stream_create_group,
    stream_publish,
    stream_read_group,
)

logger = logging.getLogger(__name__)

MessageCallback = Callable[[A2AMessage], Awaitable[None]]

# Dedup set TTL in seconds (1 hour)
_DEDUP_TTL = 3600


class A2AClient:
    """A2A protocol client for receiving and sending messages over Redis Streams."""

    def __init__(
        self,
        agent_id: str,
        agent_type: AgentType,
        task_stream: str = STREAM_AGENT_TASKS,
        response_stream: str = STREAM_AGENT_RESPONSES,
    ) -> None:
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.task_stream = task_stream
        self.response_stream = response_stream
        self._callbacks: dict[A2AMessageType, MessageCallback] = {}
        self._shutdown = asyncio.Event()

    async def start(self) -> None:
        """Initialize consumer group for this agent."""
        await stream_create_group(self.task_stream, self.agent_id)

    async def stop(self) -> None:
        """Signal graceful shutdown of the listen loop."""
        self._shutdown.set()

    def on_message(self, message_type: A2AMessageType, callback: MessageCallback) -> None:
        """Register an async callback for a message type."""
        self._callbacks[message_type] = callback

    async def listen(
        self, poll_interval_ms: int = 1000, batch_size: int = 10
    ) -> None:
        """Main listen loop — reads from consumer group, dispatches to callbacks."""
        while not self._shutdown.is_set():
            try:
                messages = await stream_read_group(
                    self.task_stream,
                    self.agent_id,
                    f"{self.agent_id}-consumer",
                    count=batch_size,
                    block_ms=poll_interval_ms,
                )
            except Exception:
                logger.exception("Error reading from stream %s", self.task_stream)
                if self._shutdown.is_set():
                    break
                continue

            if not messages:
                await asyncio.sleep(0)  # Yield control to event loop
                continue

            # messages format: [[stream_name, [(msg_id, data_dict), ...]]]
            for _stream_name, msg_list in messages:
                for stream_id, data in msg_list:
                    await self._process_message(stream_id, data)

    async def _process_message(self, stream_id: str, data: dict[str, str]) -> None:
        """Process a single message from the stream."""
        try:
            msg = A2AMessage.from_redis_dict(data)
        except Exception:
            logger.exception("Failed to deserialize message %s", stream_id)
            await stream_ack(self.task_stream, self.agent_id, stream_id)
            return

        # Filter: only process messages addressed to this agent or broadcasts
        if msg.target_agent is not None and msg.target_agent != self.agent_id:
            await stream_ack(self.task_stream, self.agent_id, stream_id)
            return

        # Deduplication check
        if await self._is_duplicate(str(msg.id)):
            await stream_ack(self.task_stream, self.agent_id, stream_id)
            return

        # Dispatch to callback
        callback = self._callbacks.get(msg.message_type)
        if callback is not None:
            try:
                await callback(msg)
            except A2AError:
                logger.exception(
                    "A2AError in callback for %s", msg.message_type.value
                )
            except Exception:
                logger.exception(
                    "Unexpected error in callback for %s", msg.message_type.value
                )
        else:
            logger.warning(
                "No callback registered for message type %s", msg.message_type.value
            )

        # Acknowledge and mark processed
        await stream_ack(self.task_stream, self.agent_id, stream_id)
        await self._mark_processed(str(msg.id))

    async def send_result(self, result: A2ATaskResult) -> str:
        """Publish a task result to the response stream."""
        msg = A2AMessage(
            message_type=A2AMessageType.TASK_RESULT,
            source_agent=self.agent_id,
            target_agent=None,
            payload=json.loads(result.model_dump_json()),
        )
        return await stream_publish(self.response_stream, msg.to_redis_dict())

    async def send_update(
        self,
        task_id: uuid.UUID,
        status: TaskStatus,
        payload: dict[str, Any],
    ) -> str:
        """Publish a task status update."""
        msg = A2AMessage(
            message_type=A2AMessageType.TASK_UPDATE,
            source_agent=self.agent_id,
            target_agent=None,
            payload={
                "task_id": str(task_id),
                "status": status.value,
                **payload,
            },
        )
        return await stream_publish(self.response_stream, msg.to_redis_dict())

    async def send_agent_card(self, card: A2AAgentCard) -> str:
        """Publish agent card in response to discovery."""
        msg = A2AMessage(
            message_type=A2AMessageType.AGENT_CARD,
            source_agent=self.agent_id,
            target_agent=None,
            payload=json.loads(card.model_dump_json()),
        )
        return await stream_publish(self.response_stream, msg.to_redis_dict())

    async def request_discovery(self) -> str:
        """Broadcast an AGENT_DISCOVER message."""
        msg = A2AMessage(
            message_type=A2AMessageType.AGENT_DISCOVER,
            source_agent=self.agent_id,
            target_agent=None,
            payload={},
        )
        return await stream_publish(self.task_stream, msg.to_redis_dict())

    async def cancel_task(self, task_id: uuid.UUID, target_agent: str) -> str:
        """Send a TASK_CANCEL message."""
        msg = A2AMessage(
            message_type=A2AMessageType.TASK_CANCEL,
            source_agent=self.agent_id,
            target_agent=target_agent,
            payload={"task_id": str(task_id)},
        )
        return await stream_publish(self.task_stream, msg.to_redis_dict())

    async def _is_duplicate(self, message_id: str) -> bool:
        """Check if message was already processed (Redis set with TTL)."""
        client = await get_redis()
        return bool(await client.sismember(f"a2a:dedup:{self.agent_id}", message_id))

    async def _mark_processed(self, message_id: str) -> None:
        """Add message ID to dedup set with TTL."""
        client = await get_redis()
        await client.sadd(f"a2a:dedup:{self.agent_id}", message_id)
        await client.expire(f"a2a:dedup:{self.agent_id}", _DEDUP_TTL)


__all__ = [
    "A2AClient",
    "MessageCallback",
]
