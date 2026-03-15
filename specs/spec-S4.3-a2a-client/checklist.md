# Checklist: S4.3 — A2A Client (Redis Streams Subscriber)

## Red Phase (Tests First)
- [x] Create `tests/unit/test_a2a_client.py`
- [x] Write all 19 tests — all must fail (no implementation yet)
- [x] Verify tests fail with ImportError or AttributeError

## Green Phase (Implementation)
- [x] Create `src/protocols/a2a/client.py`
- [x] Implement `A2AClient.__init__()` — pass test_client_creation
- [x] Implement `A2AClient.start()` — pass test_client_start_creates_consumer_group
- [x] Implement `A2AClient.on_message()` — pass test_register_callback
- [x] Implement `A2AClient.send_result()` — pass test_send_result, test_send_result_message_format
- [x] Implement `A2AClient.send_update()` — pass test_send_update
- [x] Implement `A2AClient.send_agent_card()` — pass test_send_agent_card
- [x] Implement `A2AClient.request_discovery()` — pass test_request_discovery
- [x] Implement `A2AClient.cancel_task()` — pass test_cancel_task
- [x] Implement dedup methods — pass test_listen_deduplicates
- [x] Implement `A2AClient.listen()` — pass listen tests
- [x] Implement `A2AClient.stop()` — pass test_stop_signals_shutdown
- [x] Verify all 19 tests pass

## Refactor Phase
- [x] Run `ruff check --fix src/protocols/a2a/client.py tests/unit/test_a2a_client.py`
- [x] Verify `__all__` exports
- [x] All tests still pass after refactor
