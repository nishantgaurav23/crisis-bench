Check if all dependencies for a spec are satisfied.

## Input
- Spec ID: $ARGUMENTS (e.g., "S5.1")

## Instructions

1. **Read `roadmap.md`** — find the spec row and extract the "Depends On" column.

2. **For each dependency**:
   - Look up its status in the Master Spec Index
   - Check if its test files exist and pass (run tests if status says "done")
   - Determine: READY (done + tests pass) or BLOCKING (not done)

3. **Output a dependency table**:

```
## Dependency Check: Spec {ID} — {Feature}

| Dependency | Feature | Status | Tests | Verdict |
|-----------|---------|--------|-------|---------|
| S{x}.{y} | {name} | done/spec-written/pending | PASS/FAIL/N/A | READY/BLOCKING |
| S{x}.{y} | {name} | done/spec-written/pending | PASS/FAIL/N/A | READY/BLOCKING |

**Overall: READY / BLOCKED**
```

4. **If BLOCKED** — List which specs need to be completed first, in the order they should be tackled (respecting their own dependencies).

5. **If READY** — Confirm all dependencies are met. Suggest proceeding with `/create-spec` or `/implement-spec`.
