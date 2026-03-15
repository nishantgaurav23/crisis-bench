# Spec S4.1: A2A Message Schemas

**Phase**: 4 — Communication Protocols
**Status**: done
**Depends On**: S2.1 (domain models), S2.4 (error handling)
**Location**: `src/protocols/a2a/schemas.py`
**Feature**: A2A message schemas for agent-to-agent communication over Redis Streams

---

## 1. Overview

Implement Pydantic models for the A2A (Agent-to-Agent) protocol adapted from Google's A2A spec. These schemas define how agents communicate tasks, results, artifacts, and status updates over Redis Streams. This is the data layer only — no transport logic.

### Why This Spec Exists

The 7 specialist agents + orchestrator need a **typed, validated message format** for task delegation, result delivery, and capability discovery. Without formal schemas, agents would pass unstructured dicts — leading to silent failures when message formats drift. The A2A protocol provides an industry-standard vocabulary (Task, Artifact, AgentCard) that maps cleanly to our multi-agent architecture.

### Key Design Decisions

1. **Adapted A2A, not raw Google A2A**: Google's spec uses HTTP/JSON-RPC. We keep the conceptual models (Task, Artifact, AgentCard) but adapt for Redis Streams transport (string-serializable, flat enough for `XADD`).
2. **Pydantic v2 models**: Full validation, JSON serialization, and `from_attributes=True` for ORM compat — consistent with S2.1 domain models.
3. **Reuse existing enums**: `AgentType`, `TaskStatus` from `src/shared/models.py`.
4. **Trace IDs everywhere**: Every message carries a `trace_id` (from S2.4) for distributed tracing via Langfuse.
5. **Hypothesis-friendly**: All models must be compatible with `hypothesis` `from_type()` for property-based testing of serialization roundtrips.

---

## 2. Models to Implement

### 2.1 A2AMessageType (Enum)

Message types flowing through Redis Streams:
- `TASK_SEND` — Orchestrator sends task to agent
- `TASK_UPDATE` — Agent sends progress update
- `TASK_RESULT` — Agent sends final result
- `TASK_CANCEL` — Orchestrator cancels a task
- `AGENT_DISCOVER` — Request agent capabilities
- `AGENT_CARD` — Response with agent capabilities

### 2.2 A2AArtifact

An artifact is a typed piece of data produced by an agent:
- `id: uuid.UUID` — unique artifact ID
- `name: str` — human-readable name (e.g., "situation_report", "risk_map")
- `content_type: str` — MIME type (e.g., "application/json", "text/plain", "application/geo+json")
- `data: dict[str, Any]` — the artifact payload
- `created_at: datetime`

### 2.3 A2ATask

Core task model (adapted from Google A2A Task):
- `id: uuid.UUID` — unique task ID
- `source_agent: str` — sender agent ID
- `target_agent: str` — receiver agent ID
- `disaster_id: uuid.UUID | None` — links to active disaster
- `task_type: str` — what the agent should do (e.g., "situation_report", "risk_assessment")
- `priority: int` (1-5, 1=highest)
- `status: TaskStatus` — reuse from S2.1
- `payload: dict[str, Any]` — task-specific input data
- `artifacts: list[A2AArtifact]` — output artifacts (populated by agent)
- `trace_id: str` — 8-char hex for Langfuse tracing
- `depth: int` — delegation depth counter (0=original, max 5)
- `created_at: datetime`
- `deadline: datetime | None` — optional deadline (default: 120s from creation)
- `metadata: dict[str, Any]` — extensible metadata

### 2.4 A2ATaskResult

Result returned by an agent:
- `task_id: uuid.UUID` — references the original task
- `agent_id: str` — agent that produced the result
- `status: TaskStatus` — COMPLETED, FAILED, or CANCELLED
- `artifacts: list[A2AArtifact]` — output artifacts
- `confidence: float | None` — agent's confidence (0.0-1.0)
- `error_message: str | None` — if FAILED
- `trace_id: str`
- `completed_at: datetime`

### 2.5 A2AAgentCard

Agent capability descriptor (adapted from Google A2A AgentCard):
- `agent_id: str`
- `agent_type: AgentType` — reuse from S2.1
- `name: str`
- `description: str`
- `capabilities: list[str]` — what this agent can do
- `input_types: list[str]` — accepted task types
- `output_types: list[str]` — produced artifact types
- `llm_tier: LLMTier` — reuse from S2.1
- `status: str` — current agent status (idle/busy/error)
- `max_concurrent_tasks: int` — concurrency limit
- `version: str` — agent version

### 2.6 A2AMessage

The envelope that wraps all messages for Redis Streams transport:
- `id: uuid.UUID` — unique message ID
- `message_type: A2AMessageType`
- `source_agent: str`
- `target_agent: str | None` — None for broadcasts
- `trace_id: str`
- `timestamp: datetime`
- `payload: dict[str, Any]` — serialized inner model (Task, TaskResult, AgentCard)

Must support:
- `to_redis_dict() -> dict[str, str]` — flat dict for `XADD` (all values as strings)
- `from_redis_dict(data: dict[str, str]) -> A2AMessage` — parse from Redis `XREAD`
- Standard Pydantic `model_dump_json()` / `model_validate_json()` for non-Redis use

---

## 3. Validation Rules

- `priority` must be 1-5
- `depth` must be 0-5 (AgentLoopError from S2.4 if exceeded)
- `confidence` must be 0.0-1.0 when present
- `trace_id` must be 8 hex characters
- `status` transitions: PENDING → IN_PROGRESS → COMPLETED/FAILED/CANCELLED
- `deadline` must be in the future when set
- Artifact `content_type` must be a valid MIME type pattern

---

## 4. TDD Notes

### Test File: `tests/unit/test_a2a_schemas.py`

#### Red Phase Tests (write first, all must fail):

1. **test_a2a_message_type_enum** — all 6 message types exist
2. **test_a2a_artifact_creation** — create with valid data, check defaults
3. **test_a2a_artifact_content_type_validation** — rejects obviously invalid content_types
4. **test_a2a_task_creation** — create task, check defaults (status=PENDING, depth=0)
5. **test_a2a_task_priority_bounds** — rejects priority < 1 or > 5
6. **test_a2a_task_depth_bounds** — rejects depth < 0 or > 5
7. **test_a2a_task_trace_id_format** — 8-char hex validation
8. **test_a2a_task_result_creation** — create result, check defaults
9. **test_a2a_task_result_confidence_bounds** — rejects confidence outside 0.0-1.0
10. **test_a2a_agent_card_creation** — create card with all fields
11. **test_a2a_agent_card_uses_shared_enums** — AgentType, LLMTier from S2.1
12. **test_a2a_message_envelope_creation** — create message with inner payload
13. **test_a2a_message_to_redis_dict** — all values are strings, all keys present
14. **test_a2a_message_from_redis_dict_roundtrip** — serialize → deserialize = identical
15. **test_a2a_message_json_roundtrip** — model_dump_json → model_validate_json = identical
16. **test_a2a_task_with_artifacts** — task with multiple artifacts
17. **test_a2a_task_result_with_error** — FAILED status with error_message
18. **test_hypothesis_roundtrip** — Hypothesis property-based test: any valid A2AMessage roundtrips through Redis dict
19. **test_a2a_message_type_values** — enum values are uppercase strings
20. **test_a2a_exports** — all models in `__all__`

#### Green Phase:
- Implement minimum code in `src/protocols/a2a/schemas.py` to pass each test
- Use `Field(...)` with proper constraints
- Implement `to_redis_dict()` and `from_redis_dict()` as methods on A2AMessage

#### Refactor Phase:
- Run `ruff check --fix`
- Ensure all models have `ConfigDict(from_attributes=True)`
- Verify exports in `__all__`

---

## 5. Outcomes

- [ ] All 6 A2A models defined with full Pydantic v2 validation
- [ ] Redis Streams serialization roundtrip works (to_redis_dict ↔ from_redis_dict)
- [ ] JSON serialization roundtrip works
- [ ] Hypothesis property-based test passes for roundtrip
- [ ] Reuses AgentType, TaskStatus, LLMTier from S2.1
- [ ] Reuses trace_id pattern from S2.4
- [ ] All 20 tests pass
- [ ] ruff clean
- [ ] No external API dependencies
