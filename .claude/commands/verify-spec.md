Verify a completed spec passes all quality checks.

## Input
- Spec ID: $ARGUMENTS (e.g., "S1.1")

## Instructions

1. **Load the spec** — Read `specs/spec-{ID}-*/spec.md` and `specs/spec-{ID}-*/checklist.md`.

2. **Code Existence Check**
   - Verify all files listed in "Target Location" exist
   - Verify test files exist
   - Report: PASS/FAIL per file

3. **Test Check**
   - Run `python -m pytest tests/ -k "{relevant_test_pattern}" -v`
   - Report: total tests, passed, failed, skipped
   - If any tests fail: FAIL with details

4. **Lint Check**
   - Run `ruff check {target_files}`
   - Run `ruff format --check {target_files}`
   - Report: PASS/FAIL with issue count

5. **Tangible Outcomes Audit**
   - Go through each tangible outcome in spec.md
   - For each one, verify it's actually met (check code, run specific tests)
   - Report: PASS/FAIL per outcome

6. **Security & Cost Check**
   - Grep for hardcoded API keys, passwords, secrets in target files
   - Grep for direct paid API calls (openai, anthropic SDK) — must be optional/fallback only
   - Verify all primary code paths use Ollama/local services
   - Report: PASS/FAIL

7. **Checklist Completeness**
   - Verify all items in checklist.md are checked
   - Report any unchecked items

8. **Dependency Consistency**
   - Verify this spec's dependencies are all "done" in roadmap.md
   - Report: PASS/FAIL

9. **Generate Verification Report**

```
## Verification Report: Spec {ID} — {Feature}

| Check | Result | Details |
|-------|--------|---------|
| Code exists | PASS/FAIL | ... |
| Tests pass | PASS/FAIL | X/Y passed |
| Lint clean | PASS/FAIL | ... |
| Outcomes met | PASS/FAIL | X/Y verified |
| Security & cost | PASS/FAIL | ... |
| Checklist complete | PASS/FAIL | ... |
| Dependencies | PASS/FAIL | ... |

**Overall: PASS / FAIL**
```

10. **If PASS** — Confirm roadmap.md shows "done" for this spec.
11. **If FAIL** — List specific items that need fixing before the spec can be considered done.
