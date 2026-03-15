# Spec S4.1: A2A Message Schemas — Explanation

## Why This Spec Exists

The 7 specialist agents + orchestrator need a **typed, validated message format** for communication. Without formal schemas, agents would pass raw dicts over Redis Streams — leading to silent failures when message formats drift between agents, no validation on critical fields like priority/depth/confidence, and no way to detect malformed messages during testing.

The A2A (Agent-to-Agent) protocol, adapted from Google's open A2A standard, provides an industry-standard vocabulary (Task, Artifact, AgentCard) that maps directly to our multi-agent disaster response architecture.

## What It Does

Defines 6 Pydantic v2 models for agent communication:

| Model | Purpose |
|-------|---------|
| `A2AMessageType` | Enum of 6 message types (TASK_SEND, TASK_UPDATE, TASK_RESULT, TASK_CANCEL, AGENT_DISCOVER, AGENT_CARD) |
| `A2AArtifact` | Typed data output from an agent (e.g., situation report, risk map, GeoJSON) |
| `A2ATask` | Task delegation from orchestrator to agent — includes priority (1-5), depth counter (0-5 for loop prevention), and trace_id |
| `A2ATaskResult` | Agent's response with status, artifacts, and optional confidence score (0.0-1.0) |
| `A2AAgentCard` | Agent capability descriptor — what task types it accepts, what artifacts it produces |
| `A2AMessage` | Redis Streams envelope wrapping any inner message with routing metadata |

### Key Capabilities

- **Redis Streams serialization**: `to_redis_dict()` flattens all fields to `dict[str, str]` for `XADD`; `from_redis_dict()` parses back from `XREAD`
- **JSON roundtrip**: Standard Pydantic `model_dump_json()` / `model_validate_json()`
- **Validation**: Priority bounds (1-5), depth bounds (0-5, prevents infinite delegation), confidence bounds (0.0-1.0), trace_id format (8 hex chars), MIME type format for artifacts
- **Broadcast support**: `target_agent=None` for discovery messages

## How It Works

1. **Orchestrator creates A2ATask** → wraps in `A2AMessage(type=TASK_SEND)` → calls `to_redis_dict()` → `XADD` to Redis Stream
2. **Agent reads from stream** → `A2AMessage.from_redis_dict(data)` → deserializes with full Pydantic validation
3. **Agent produces result** → creates `A2ATaskResult` with artifacts → wraps in `A2AMessage(type=TASK_RESULT)` → publishes back
4. **Depth counter** increments on each delegation hop; at depth > 5, the orchestrator stops delegating (AgentLoopError)

## How It Connects

| Dependency | Relationship |
|------------|-------------|
| **S2.1** (domain models) | Reuses `AgentType`, `TaskStatus`, `LLMTier` enums — ensures consistency between domain models and protocol models |
| **S2.4** (error handling) | Follows trace_id pattern (8 hex chars) for distributed tracing; depth > 5 triggers `AgentLoopError` |
| **S4.2** (A2A server) | Will use these schemas for publishing tasks to Redis Streams |
| **S4.3** (A2A client) | Will use these schemas for reading tasks from Redis Streams |
| **S7.1** (base agent) | All agents will create/consume these message types |

## Interview Q&A

**Q: Why adapt Google A2A instead of using it directly?**
A: Google's A2A spec uses HTTP/JSON-RPC transport. Our agents all run on the same machine — Redis Streams gives sub-millisecond delivery without TCP overhead. We keep the conceptual models (Task, Artifact, AgentCard) but replace the transport layer. This gives us the protocol's vocabulary and design patterns without the network overhead.

**Q: Why does A2AMessage need `to_redis_dict()` / `from_redis_dict()` instead of just using Pydantic's JSON serialization?**
A: Redis Streams `XADD` requires a flat `dict[str, str]` — no nested objects, no arrays, no non-string values. JSON serialization produces a single string. The flat dict approach lets us use Redis's built-in field filtering (e.g., read only messages where `message_type=TASK_SEND`) without deserializing the entire payload. This is the idiomatic Redis Streams pattern.

**Q: How does the depth counter prevent infinite agent loops?**
A: When the orchestrator delegates a task, `depth=0`. If that agent sub-delegates, `depth` becomes 1. At `depth > 5`, validation fails with a Pydantic `ValidationError`, preventing further delegation. Combined with the 120s global timeout (S7.1) and message deduplication (S4.2), this provides three layers of loop protection.

**Q: Why property-based testing with Hypothesis for these schemas?**
A: Serialization roundtrip bugs are subtle — they often involve edge cases in Unicode, empty strings, None values, or datetime precision. Hypothesis generates hundreds of random valid `A2AMessage` instances and verifies that `from_redis_dict(msg.to_redis_dict())` always produces an identical message. This caught a bug with `target_agent=None` handling during development that a hand-written test might have missed.
