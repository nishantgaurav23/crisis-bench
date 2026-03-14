Implement a spec using Test-Driven Development.

## Input
- Spec ID: $ARGUMENTS (e.g., "S1.1")

## Instructions

1. **Load the spec** — Read `specs/spec-{ID}-*/spec.md` and `specs/spec-{ID}-*/checklist.md`.

2. **Check dependencies** — For each dependency listed in spec.md, verify it has status "done" in `roadmap.md`. If any dependency is not done, STOP and report which ones are blocking.

3. **Follow TDD strictly** — Red → Green → Refactor:

### Red Phase (Write Failing Tests)
- Create the test file at the location specified in checklist.md
- Write tests for EVERY functional requirement in spec.md
- Write tests for EVERY edge case listed in spec.md
- Include tests for the mocking strategy specified
- Run the tests — they MUST all fail (this confirms tests are meaningful)
- Update checklist.md: mark test-writing tasks as done

### Green Phase (Minimal Implementation)
- Implement the MINIMUM code to make each test pass, one FR at a time
- After implementing each FR, run tests to confirm that FR's tests pass
- Do NOT implement anything beyond what tests require
- Update checklist.md progressively as each FR passes

### Refactor Phase
- Clean up code: remove duplication, improve naming
- Run `ruff check --fix` and `ruff format`
- Run ALL tests again — everything must still pass
- Update checklist.md: mark refactor tasks as done

4. **Integration** — If the spec has downstream consumers:
   - Wire the new code into the application
   - Run any relevant integration tests
   - Update checklist.md

5. **Verify tangible outcomes** — Go through each tangible outcome in spec.md and verify it's met.

6. **Update roadmap.md** — Change status from "spec-written" to "done" in both the phase table and Master Spec Index.

7. **Report** — Summarize what was implemented, tests passing count, and any decisions made during implementation.

## Rules
- NEVER skip the Red phase — tests must fail before you write implementation
- NEVER implement features not in the spec
- NEVER leave checklist items unchecked without explanation
- NEVER depend on paid services — all LLM calls go through Ollama (with Groq/Gemini Flash free as fallback), all DBs are Docker
- ALWAYS run ruff before declaring done
- ALWAYS use async/await for I/O operations
- ALWAYS mock external services in tests (including Ollama)
- Commit message format: `feat(S{x}.{y}): {short description}`
