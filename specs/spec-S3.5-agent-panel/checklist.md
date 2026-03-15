# Spec S3.5: Agent Status Panel — Implementation Checklist

## Phase 1: Red (Write Tests)
- [x] Create `dashboard/src/__tests__/components/AgentFlow.test.tsx`
- [x] Test: renders all 7 agent cards
- [x] Test: each card shows agent name and status dot
- [x] Test: status dots have correct color classes
- [x] Test: LLM tier badges render with correct styles
- [x] Test: orchestrator is visually distinguished
- [x] Test: accepts custom agents via props
- [x] Test: fires onAgentClick callback
- [x] Test: renders SVG connection lines
- [x] Run tests — all FAILED (module not found)

## Phase 2: Green (Implement)
- [x] Create `dashboard/src/components/AgentFlow.tsx`
- [x] Implement AgentCardComponent (individual agent card)
- [x] Implement AgentFlow layout (orchestrator top, specialists grid)
- [x] Add SVG connection lines
- [x] Add mock data (MOCK_AGENTS)
- [x] Wire up onAgentClick handler
- [x] Run tests — all 16 PASSED

## Phase 3: Refactor
- [x] Run `npm run lint` (tsc --noEmit) — zero errors
- [x] Run `npm run build` — compiled successfully
- [x] Final test run — 59/59 tests pass (all dashboard tests)
