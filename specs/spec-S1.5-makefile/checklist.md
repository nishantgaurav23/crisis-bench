# S1.5 Makefile — Implementation Checklist

## Phase 1: Red (Write Failing Tests)
- [x] Create `tests/unit/test_makefile.py`
- [x] Test: Makefile exists at project root
- [x] Test: All required targets defined (26 targets)
- [x] Test: All targets declared as .PHONY
- [x] Test: No hardcoded secrets in Makefile
- [x] Test: `run` target uses `docker-compose up -d`
- [x] Test: `run-cpu` uses both compose files
- [x] Test: `test` target invokes `pytest`
- [x] Test: `lint` target invokes `ruff`
- [x] Test: `clean-docker` uses `docker-compose down -v`
- [x] Test: Self-documenting help target (## comments)
- [x] Run tests — all FAIL (Red) ✅

## Phase 2: Green (Implement Makefile)
- [x] Create `Makefile` at project root
- [x] Implement variables section (DOCKER_COMPOSE, PYTHON, PYTEST, RUFF, UV)
- [x] Implement `help` as default target
- [x] Implement setup targets (setup, install, env, docker-pull)
- [x] Implement service targets (run, run-cpu, stop, restart, logs, status)
- [x] Implement test targets (test, test-unit, test-integration, test-cov)
- [x] Implement lint targets (lint, lint-fix, format, format-check, check)
- [x] Implement database targets (db-init, db-reset, benchmark)
- [x] Implement clean targets (clean, clean-docker, clean-py)
- [x] Add .PHONY declarations for all targets
- [x] Run tests — all PASS (Green) ✅ 70/70

## Phase 3: Refactor
- [x] Run `ruff check tests/unit/test_makefile.py` — clean ✅
- [x] Verify `make help` output is well-formatted ✅
- [x] Verify no secrets in Makefile ✅
- [x] All tests still pass after refactor ✅ 70/70
