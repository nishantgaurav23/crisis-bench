# Spec S4.2 Implementation Checklist

## Phase 1: Red (Write Failing Tests)
- [x] Test A2AServer initialization (agent_id, max_stream_len)
- [x] Test send_task publishes to tasks stream with correct serialization
- [x] Test send_result publishes to responses stream
- [x] Test broadcast_update publishes TASK_UPDATE to tasks stream
- [x] Test cancel_task publishes TASK_CANCEL
- [x] Test discover_agents publishes AGENT_DISCOVER broadcast
- [x] Test register_agent_card publishes AGENT_CARD
- [x] Test ensure_groups creates consumer groups for each agent
- [x] Test get_stream_info returns stream lengths
- [x] Test Redis failure raises A2AError
- [x] Test stream trimming behavior

## Phase 2: Green (Implement)
- [x] Implement A2AServer class in `src/protocols/a2a/server.py`
- [x] All 22 tests pass

## Phase 3: Refactor
- [x] Run ruff, fix lint issues (removed unused imports)
- [x] All 43 tests pass (22 server + 21 schemas)
- [x] No regressions in S4.1 tests
