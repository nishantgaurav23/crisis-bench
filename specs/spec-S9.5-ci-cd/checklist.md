# Spec S9.5 — CI/CD Checklist

## Phase 1: Tests (Red)
- [x] Write `tests/unit/test_ci_cd.py` with all validation tests
- [x] Verify all tests fail (no workflow files exist yet)

## Phase 2: Implementation (Green)
- [x] Create `.github/workflows/ci.yml` — lint + unit tests
- [x] Create `.github/workflows/benchmark_regression.yml` — benchmark score check
- [x] Create `.github/workflows/docker.yml` — Docker image build + compose validation
- [x] Create `benchmark/baseline.json` — baseline benchmark scores
- [x] All tests pass (27/27)

## Phase 3: Refactor
- [x] Run `ruff check` and `ruff format` — clean
- [x] Review workflow files for best practices
- [x] All tests still pass (27/27)

## Phase 4: Finalize
- [x] Update `roadmap.md` status to `done`
- [x] Generate `explanation.md`
