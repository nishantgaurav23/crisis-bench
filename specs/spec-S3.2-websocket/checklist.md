# S3.2 WebSocket Server — Implementation Checklist

## Phase 1: Red (Write Failing Tests)
- [x] Create `tests/unit/test_websocket.py`
- [x] Write ConnectionManager unit tests (connect, disconnect, broadcast, send_to_client)
- [x] Write channel subscription tests (default, custom, subscribe/unsubscribe commands)
- [x] Write WebSocket endpoint tests (connect, ping/pong, commands, broadcast envelope)
- [x] Write integration test (app has /ws route)
- [x] Verify all tests FAIL (no implementation yet)

## Phase 2: Green (Implement Minimum Code)
- [x] Create `src/api/websocket.py` with ConnectionManager
- [x] Implement connect/disconnect lifecycle
- [x] Implement channel subscription logic
- [x] Implement broadcast and send_to_client
- [x] Implement websocket_endpoint with command handling
- [x] Wire WebSocket route into `src/api/main.py`
- [x] All tests pass

## Phase 3: Refactor
- [x] Run ruff — fix any issues
- [x] Review for code clarity
- [x] Verify no secrets or paid dependencies
- [x] All tests still pass (577 total)

## Phase 4: Verify + Explain
- [x] Run /verify-spec
- [x] Generate explanation.md
- [x] Update roadmap.md status to "done"
