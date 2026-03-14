# Spec S1.3: Implementation Checklist

## Red Phase (Tests First)
- [x] Create `tests/unit/test_config.py`
- [x] Write all 22 test cases — all must FAIL (no implementation yet)

## Green Phase (Minimum Implementation)
- [x] Create `src/shared/config.py`
- [x] Implement `CrisisSettings(BaseSettings)` with all fields
- [x] Add computed properties (`postgres_dsn`, `redis_url`)
- [x] Add validators for `LOG_LEVEL`, `ENVIRONMENT`, ports, positive values
- [x] Implement `get_settings()` singleton
- [x] All tests pass

## Refactor Phase
- [x] `ruff check src/shared/config.py tests/unit/test_config.py`
- [x] `ruff format --check src/shared/config.py tests/unit/test_config.py`
- [x] Review for unnecessary complexity
- [x] Verify no hardcoded secrets

## Verification
- [x] All tests pass
- [x] Lint clean
- [x] All spec outcomes met
