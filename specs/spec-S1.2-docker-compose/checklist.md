# Spec S1.2: Docker Compose — Implementation Checklist

## Phase 1: RED (Write Failing Tests)
- [x] Create `tests/unit/test_docker_compose.py`
- [x] Test: YAML validity of both compose files
- [x] Test: All 7 services present
- [x] Test: Port mappings correct
- [x] Test: Named volumes declared
- [x] Test: Health checks on every service
- [x] Test: All services on `crisis-net`
- [x] Test: No hardcoded secrets
- [x] Test: Dependency ordering (langfuse→postgres, grafana→prometheus)
- [x] Test: PostgreSQL init script mount
- [x] Test: CPU override merges correctly
- [x] Verify all tests FAIL (RED) ✅ 44 errors/failures

## Phase 2: GREEN (Implement Minimum Code)
- [x] Create `docker-compose.yml` with all 7 services
- [x] Create `docker-compose.cpu.yml` override
- [x] Create `scripts/init_langfuse_db.sh`
- [x] Create `monitoring/prometheus.yml`
- [x] Verify all tests PASS (GREEN) ✅ 44 passed

## Phase 3: REFACTOR
- [x] Run `ruff check` — lint clean ✅
- [x] Review compose file for best practices ✅
- [x] Full test suite: 63 passed (S1.1 + S1.2) ✅
