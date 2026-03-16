# Spec S7.1 — BaseAgent Explanation

## Why This Spec Exists

BaseAgent is the foundation for the entire agent system (Phase 7). All 7 specialist agents + the Orchestrator inherit from it. Without a shared base class, each agent would independently implement LLM routing, A2A communication, timeout handling, metrics collection, and health checks — leading to duplicated code and inconsistent behavior.

BaseAgent encapsulates the "agent infrastructure" so that specialist agents focus only on their domain logic (the LangGraph state machine).

## What It Does

**`AgentState` (TypedDict)** — A typed dictionary that flows through the LangGraph state machine. Contains: task payload, disaster_id, trace_id, LLM messages, reasoning output, confidence score, artifacts, error state, iteration counter, and agent-specific metadata.

**`BaseAgent` (ABC)** — Abstract base class with three abstract methods subclasses must implement:
1. `build_graph()` — Define the LangGraph state machine (nodes, edges, conditional routing)
2. `get_system_prompt()` — Return the agent's system prompt for LLM calls
3. `get_agent_card()` — Return an A2AAgentCard describing capabilities

**Concrete methods provided:**
- `reason(messages, tier, trace_id)` — Route LLM calls through the LLM Router with automatic tier selection, trace_id propagation, and structured logging
- `run_graph(initial_state)` — Execute the compiled LangGraph with `asyncio.wait_for` timeout enforcement (120s default)
- `handle_task(msg)` — Full A2A task lifecycle: deserialize task → check delegation depth → build initial state → run graph → send result (completed/failed)
- `start()` / `stop()` — Lifecycle management: compile graph, register A2A agent card, start/stop listening
- `health()` — Return agent status, active task count, uptime for monitoring

**Safety guards:**
- Delegation depth check (max 5) prevents infinite agent-to-agent loops
- Timeout enforcement (120s) via `asyncio.wait_for` prevents hung agents
- Invalid task payloads caught and returned as FAILED results
- Active task counter ensures concurrent task tracking

## How It Works

1. Agent is instantiated with `agent_id`, `agent_type`, `llm_tier`, and optional settings
2. `start()` compiles the LangGraph, registers the agent card on Redis Streams, and registers a TASK_SEND handler
3. When a task arrives via A2A, `handle_task()`:
   - Validates the payload by parsing into `A2ATask`
   - Checks delegation depth against `AGENT_MAX_DELEGATION_DEPTH`
   - Increments active task counter and Prometheus metrics
   - Builds `AgentState` with system prompt + task payload as messages
   - Calls `run_graph()` which executes the compiled LangGraph with timeout
   - Sends `A2ATaskResult` (COMPLETED with confidence, or FAILED with error)
   - Decrements active task counter
4. Inside the graph, nodes call `self.reason()` which delegates to `LLMRouter.call(tier, messages)` with automatic failover across providers

## How It Connects to the Rest of the Project

| Component | Relationship |
|-----------|-------------|
| **S2.6 LLM Router** | BaseAgent wraps it via `reason()` — all LLM calls flow through the router |
| **S4.2 A2A Server** | Used to register agent cards and could send tasks to other agents |
| **S4.3 A2A Client** | Used to listen for incoming tasks and send back results |
| **S2.5 Telemetry** | Structured logging via `get_logger`, Prometheus metrics via `AGENT_TASKS`/`AGENT_TASK_DURATION` |
| **S7.2–S7.8** | All specialist agents subclass BaseAgent, implementing `build_graph()`, `get_system_prompt()`, `get_agent_card()` |
| **S7.9 Integration Test** | Tests the full agent pipeline built on BaseAgent |
| **S9.3 Langfuse** | Future: deeper Langfuse tracing integration in `reason()` |

## Key Design Decisions

1. **LangGraph StateGraph as the abstraction** — Each agent's logic is a directed graph of async functions. This enables conditional routing, iterative refinement loops, and visual debugging. The graph is compiled once at `start()` and reused.

2. **TypedDict over Pydantic for AgentState** — LangGraph requires TypedDict for state. This is an internal data structure, not a system boundary, so Pydantic validation isn't needed.

3. **Delegation depth in handle_task, not in A2ATask validation** — A2ATask validates depth 0-5 at the schema level. The base agent also checks against the configurable `AGENT_MAX_DELEGATION_DEPTH` setting for defense-in-depth.

4. **asyncio.wait_for for timeout** — Simple, robust timeout mechanism that cancels the entire graph execution if it exceeds the limit. Raises `AgentTimeoutError` which is caught by `handle_task()` and returned as a FAILED result.
