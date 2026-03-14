Run the full spec development workflow end-to-end.

## Input
- Spec ID: $ARGUMENTS (e.g., "S1.1")

## Instructions

This command orchestrates the complete spec lifecycle. Execute each step in order, stopping if any step fails.

### Step 1: Check Dependencies
- Read `roadmap.md` and find the spec's "Depends On" column
- For each dependency, verify its status is "done" and tests pass
- If any dependency is BLOCKING: **STOP** — report which dependencies must be completed first, in order

### Step 2: Create Spec (if not already created)
- Check if `specs/spec-{ID}-*/spec.md` already exists
- If NOT: run the `/create-spec` workflow — read roadmap + design + requirements, create spec.md + checklist.md
- If YES: load the existing spec

### Step 3: Implement Spec (TDD)
- Run the `/implement-spec` workflow:
  1. **Red**: Write all tests first — they must fail
  2. **Green**: Implement minimum code to pass each test
  3. **Refactor**: Clean up, run ruff, ensure all tests still pass
- Update checklist.md progressively

### Step 4: Verify Spec
- Run the `/verify-spec` workflow:
  - Code exists, tests pass, lint clean, outcomes met, no secrets, no paid dependencies
- If verification FAILS: fix the issues and re-verify

### Step 5: Generate Explanation
- Run the `/explain-spec` workflow:
  - Create `explanation.md` in the spec folder documenting why this spec exists, what it does, how it works, and how it connects to the rest of the project

### Step 6: Update Roadmap
- Update `roadmap.md`: set status to "done" in both the phase table and Master Spec Index
- Report a summary of what was built

## Output
```
## Spec {ID} Development Complete

- Feature: {name}
- Tests: X passing
- Files created/modified: [list]
- Status: done
- Explanation: specs/spec-{ID}-{slug}/explanation.md

Next spec to tackle: S{x}.{y} ({name}) — run /start-spec-dev S{x}.{y}
```

## Rules
- STOP immediately if dependencies are not met — do not proceed with partial dependencies
- Follow TDD strictly — never write implementation before tests
- All code must work with local Ollama + Docker services only
- Always generate the explanation after implementation
