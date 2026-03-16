# Spec S7.1 — BaseAgent (LangGraph + LLM Router)

**Status**: done
**Location**: `src/agents/base.py`
**Depends On**: S2.6 (LLM Router), S4.2 (A2A Server), S4.3 (A2A Client), S2.5 (Telemetry)
**Depended By**: S7.2–S7.8 (all specialist agents), S9.3 (Langfuse integration)

---

## 1. Overview

BaseAgent is the abstract base class for all 7 specialist agents + the Orchestrator. It encapsulates:
- **LangGraph state machine** — typed state, nodes, conditional edges
- **LLM Router integration** — all LLM calls via `router.call(tier, messages)`
- **A2A protocol** — publish/subscribe tasks via Redis Streams
- **Langfuse tracing** — every LLM call and task lifecycle traced
- **Health check** — agents report readiness/liveness
- **Lifecycle management** — start, stop, graceful shutdown

Each specialist agent (S7.2–S7.8) subclasses BaseAgent and overrides:
- `build_graph()` — define the LangGraph state machine
- `get_system_prompt()` — agent-specific system prompt
- `agent_card()` — capability declaration

---

## 2. Outcomes

1. `BaseAgent` class in `src/agents/base.py` with full LangGraph state machine lifecycle
2. Typed `AgentState` (TypedDict) for state passing between graph nodes
3. `reason()` method that routes all LLM calls through `LLMRouter` with Langfuse tracing
4. A2A client/server integration — receive tasks, send results, register agent card
5. Health check endpoint data (ready/not ready, current task count, uptime)
6. Task timeout enforcement (120s default from config)
7. Delegation depth guard (max 5 from config)
8. Prometheus metrics: task count, duration, LLM cost per agent
9. Structured logging with trace_id propagation
10. `__init_subclass__` or abstract methods forcing subclasses to implement required hooks

---

## 3. Design

### 3.1 AgentState (TypedDict)

```python
class AgentState(TypedDict, total=False):
    task: dict                    # Current A2A task payload
    disaster_id: str | None       # Associated disaster
    trace_id: str                 # Propagated trace ID
    messages: list[dict[str, str]]  # LLM conversation history
    reasoning: str                # Latest LLM reasoning output
    confidence: float             # 0.0–1.0
    artifacts: list[dict]         # Output artifacts
    error: str | None             # Error message if failed
    iteration: int                # Loop counter for iterative refinement
    metadata: dict                # Agent-specific extra state
```

### 3.2 BaseAgent Class

```python
class BaseAgent(ABC):
    def __init__(
        self,
        agent_id: str,
        agent_type: AgentType,
        llm_tier: LLMTier,
        settings: CrisisSettings | None = None,
    ):
        ...

    # --- Abstract methods (subclasses MUST implement) ---
    @abstractmethod
    def build_graph(self) -> StateGraph: ...

    @abstractmethod
    def get_system_prompt(self) -> str: ...

    @abstractmethod
    def get_agent_card(self) -> A2AAgentCard: ...

    # --- Concrete methods ---
    async def start(self) -> None: ...          # Init A2A, register card, compile graph
    async def stop(self) -> None: ...           # Graceful shutdown
    async def reason(self, messages, *, tier=None, trace_id="", **kwargs) -> LLMResponse: ...
    async def handle_task(self, msg: A2AMessage) -> None: ...  # Default task handler
    async def run_graph(self, initial_state: AgentState) -> AgentState: ...  # Execute graph
    def health(self) -> dict: ...               # Health check data
```

### 3.3 Graph Execution Flow

1. Task arrives via A2A → `handle_task()`
2. Build `AgentState` from task payload
3. `run_graph(state)` executes the compiled LangGraph
4. Graph nodes call `self.reason()` for LLM calls
5. Final state → `A2ATaskResult` → sent back via A2A client
6. Metrics + logging updated

### 3.4 Timeout & Delegation Guards

- `asyncio.wait_for(run_graph(...), timeout=settings.AGENT_TIMEOUT_SECONDS)`
- If `task.depth >= settings.AGENT_MAX_DELEGATION_DEPTH`, reject immediately with `AgentDelegationError`

---

## 4. TDD Plan

### Test File: `tests/unit/test_base_agent.py`

#### Test Group 1: Initialization
- `test_base_agent_requires_abstract_methods` — cannot instantiate directly
- `test_concrete_subclass_creates_successfully` — with all abstract methods
- `test_agent_initializes_router_and_a2a` — checks router, client, server created
- `test_agent_default_tier` — default LLM tier from constructor

#### Test Group 2: State Machine
- `test_agent_state_typed_dict` — AgentState has expected keys
- `test_build_graph_returns_compiled_graph` — graph compiles without error
- `test_run_graph_executes_nodes` — state flows through graph
- `test_run_graph_timeout_raises_error` — exceeding timeout raises AgentTimeoutError

#### Test Group 3: LLM Reasoning
- `test_reason_calls_router` — reason() delegates to LLMRouter.call()
- `test_reason_uses_agent_tier_by_default` — uses self.llm_tier
- `test_reason_allows_tier_override` — can pass different tier
- `test_reason_propagates_trace_id` — trace_id passed to router
- `test_reason_logs_via_langfuse` — tracer methods called

#### Test Group 4: A2A Integration
- `test_start_registers_agent_card` — card published on start
- `test_start_begins_listening` — client.start() called
- `test_handle_task_processes_and_responds` — full task → result flow
- `test_handle_task_rejects_deep_delegation` — depth >= max → rejection
- `test_handle_task_sends_failure_on_error` — exception → failed result
- `test_stop_graceful_shutdown` — client.stop() called

#### Test Group 5: Health & Metrics
- `test_health_returns_status` — health dict has expected fields
- `test_metrics_increment_on_task` — AGENT_TASKS counter incremented
- `test_metrics_observe_duration` — AGENT_TASK_DURATION observed
- `test_structured_logging` — logger bound with agent_id

#### Test Group 6: Edge Cases
- `test_reason_with_empty_messages_raises` — validation
- `test_handle_task_with_missing_payload` — graceful error
- `test_concurrent_tasks` — multiple tasks don't interfere

---

## 5. Dependencies

| Dependency | Import | Version |
|-----------|--------|---------|
| langgraph | `from langgraph.graph import StateGraph, END` | >=0.2.0 |
| All others already in pyproject.toml | — | — |

---

## 6. Files to Create/Modify

| File | Action |
|------|--------|
| `src/agents/__init__.py` | Create (empty or exports) |
| `src/agents/base.py` | Create — BaseAgent + AgentState |
| `tests/unit/test_base_agent.py` | Create — all tests |
| `pyproject.toml` | Add langgraph dependency if missing |
