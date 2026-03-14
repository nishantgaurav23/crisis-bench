# Spec S2.3 Checklist: Redis Streams + Cache Utilities

## Red Phase — Write Tests
- [x] Create `tests/unit/test_redis_utils.py`
- [x] Test connection management (create, close, singleton)
- [x] Test health check (healthy + unhealthy)
- [x] Test cache operations (get, set, delete, JSON variants)
- [x] Test stream publishing (raw + event envelope)
- [x] Test consumer groups (create, read, ack)
- [x] Test simple stream operations (read, len, trim)
- [x] All tests FAIL (no implementation yet)

## Green Phase — Implement
- [x] Create `src/shared/redis_utils.py`
- [x] Implement connection management
- [x] Implement health check
- [x] Implement cache operations
- [x] Implement stream publishing
- [x] Implement consumer group operations
- [x] Implement simple stream operations
- [x] Define stream name constants
- [x] All tests PASS (29/29)

## Refactor Phase — Clean Up
- [x] ruff check passes
- [x] ruff format passes
- [x] Add `__all__` exports
- [x] Consistent patterns with db.py
- [x] All tests still pass (385/385 total)
