"""A2A (Agent-to-Agent) message schemas for CRISIS-BENCH.

Pydantic models adapted from Google's A2A protocol for agent communication
over Redis Streams. Provides typed, validated message formats for task
delegation, result delivery, and capability discovery.

All models use ConfigDict(from_attributes=True) for ORM compatibility.
"""

import json
import re
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.shared.models import AgentType, LLMTier, TaskStatus

# =============================================================================
# Enums
# =============================================================================

_HEX8_RE = re.compile(r"^[0-9a-f]{8}$")
_MIME_RE = re.compile(r"^[\w.+-]+/[\w.+-]+$")


def _generate_trace_id() -> str:
    return uuid.uuid4().hex[:8]


class A2AMessageType(str, Enum):
    """Message types for A2A communication over Redis Streams."""

    TASK_SEND = "TASK_SEND"
    TASK_UPDATE = "TASK_UPDATE"
    TASK_RESULT = "TASK_RESULT"
    TASK_CANCEL = "TASK_CANCEL"
    AGENT_DISCOVER = "AGENT_DISCOVER"
    AGENT_CARD = "AGENT_CARD"


# =============================================================================
# A2AArtifact
# =============================================================================


class A2AArtifact(BaseModel):
    """A typed piece of data produced by an agent."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    content_type: str
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        if not _MIME_RE.match(v):
            raise ValueError(f"Invalid MIME type: {v!r} (must contain '/')")
        return v


# =============================================================================
# A2ATask
# =============================================================================


class A2ATask(BaseModel):
    """Core task model adapted from Google A2A Task."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    source_agent: str
    target_agent: str
    disaster_id: uuid.UUID | None = None
    task_type: str
    priority: int = Field(default=3, ge=1, le=5)
    status: TaskStatus = TaskStatus.PENDING
    payload: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[A2AArtifact] = Field(default_factory=list)
    trace_id: str = Field(default_factory=_generate_trace_id)
    depth: int = Field(default=0, ge=0, le=5)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    deadline: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("trace_id")
    @classmethod
    def validate_trace_id(cls, v: str) -> str:
        if not _HEX8_RE.match(v):
            raise ValueError(f"trace_id must be 8 hex chars, got {v!r}")
        return v


# =============================================================================
# A2ATaskResult
# =============================================================================


class A2ATaskResult(BaseModel):
    """Result returned by an agent for a task."""

    model_config = ConfigDict(from_attributes=True)

    task_id: uuid.UUID
    agent_id: str
    status: TaskStatus
    artifacts: list[A2AArtifact] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    error_message: str | None = None
    trace_id: str = Field(default_factory=_generate_trace_id)
    completed_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

    @field_validator("trace_id")
    @classmethod
    def validate_trace_id(cls, v: str) -> str:
        if not _HEX8_RE.match(v):
            raise ValueError(f"trace_id must be 8 hex chars, got {v!r}")
        return v


# =============================================================================
# A2AAgentCard
# =============================================================================


class A2AAgentCard(BaseModel):
    """Agent capability descriptor adapted from Google A2A AgentCard."""

    model_config = ConfigDict(from_attributes=True)

    agent_id: str
    agent_type: AgentType
    name: str
    description: str
    capabilities: list[str] = Field(default_factory=list)
    input_types: list[str] = Field(default_factory=list)
    output_types: list[str] = Field(default_factory=list)
    llm_tier: LLMTier = LLMTier.ROUTINE
    status: str = "idle"
    max_concurrent_tasks: int = 1
    version: str = "1.0.0"


# =============================================================================
# A2AMessage — Redis Streams envelope
# =============================================================================


class A2AMessage(BaseModel):
    """Envelope wrapping all messages for Redis Streams transport."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    message_type: A2AMessageType
    source_agent: str
    target_agent: str | None = None
    trace_id: str = Field(default_factory=_generate_trace_id)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("trace_id")
    @classmethod
    def validate_trace_id(cls, v: str) -> str:
        if not _HEX8_RE.match(v):
            raise ValueError(f"trace_id must be 8 hex chars, got {v!r}")
        return v

    def to_redis_dict(self) -> dict[str, str]:
        """Serialize to flat dict for Redis XADD (all values as strings)."""
        return {
            "id": str(self.id),
            "message_type": self.message_type.value,
            "source_agent": self.source_agent,
            "target_agent": self.target_agent if self.target_agent is not None else "",
            "trace_id": self.trace_id,
            "timestamp": self.timestamp.isoformat(),
            "payload": json.dumps(self.payload),
        }

    @classmethod
    def from_redis_dict(cls, data: dict[str, str]) -> "A2AMessage":
        """Deserialize from Redis XREAD dict."""
        target = data.get("target_agent", "")
        return cls(
            id=uuid.UUID(data["id"]),
            message_type=A2AMessageType(data["message_type"]),
            source_agent=data["source_agent"],
            target_agent=target if target else None,
            trace_id=data["trace_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            payload=json.loads(data["payload"]),
        )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "A2AMessageType",
    "A2AArtifact",
    "A2ATask",
    "A2ATaskResult",
    "A2AAgentCard",
    "A2AMessage",
]
