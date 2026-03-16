# S7.1 Implementation Checklist

## Phase 1: Red (Write Failing Tests)
- [x] Create `tests/unit/test_base_agent.py` with all test groups
- [x] Run tests — all should fail (no implementation yet)

## Phase 2: Green (Implement)
- [x] `langgraph` already in `pyproject.toml`
- [x] `src/agents/__init__.py` already exists
- [x] Implement `AgentState` TypedDict in `src/agents/base.py`
- [x] Implement `BaseAgent` abstract class
- [x] Implement `reason()` with LLM Router + Langfuse
- [x] Implement `handle_task()` with timeout + depth guard
- [x] Implement `run_graph()` with asyncio timeout
- [x] Implement `start()` / `stop()` lifecycle
- [x] Implement `health()` check
- [x] Run tests — all 27 pass

## Phase 3: Refactor
- [x] Run `ruff check` — fixed unused imports
- [x] Run `ruff format` — formatted
- [x] Removed unnecessary variable assignment
- [x] All 27 tests still pass
