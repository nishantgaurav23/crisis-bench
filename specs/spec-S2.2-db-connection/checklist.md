# Spec S2.2: Implementation Checklist

## Red Phase (Tests First)
- [x] Write `tests/unit/test_db.py` with all test cases
- [x] Verify all tests fail (no implementation yet)

## Green Phase (Implement)
- [x] Implement `DBHealthStatus` dataclass
- [x] Implement `point_to_wkt()` and `polygon_to_wkt()`
- [x] Implement pool management: `create_pool()`, `close_pool()`, `get_pool()`
- [x] Implement query helpers: `execute()`, `fetch_one()`, `fetch_all()`, `fetch_val()`
- [x] Implement spatial helpers: `find_within_radius()`, `find_in_polygon()`
- [x] Implement `check_health()`
- [x] All tests pass (22/22)

## Refactor Phase
- [x] ruff lint clean
- [x] ruff format clean
- [x] Add `__all__` exports

## Verification
- [x] All outcomes from spec met
- [x] No secrets or hardcoded values
- [x] No real DB dependency in tests (all mocked)
- [x] Full test suite passes (356 tests)
