# Spec S3.5: Agent Status Panel (AgentFlow)

**Phase**: 3 — API + Dashboard MVP
**Depends On**: S3.3 (Next.js dashboard setup)
**Location**: `dashboard/src/components/AgentFlow.tsx`
**Status**: pending

---

## 1. Overview

Build the AgentFlow component that displays the status and communication flow of all 7 specialist agents + orchestrator. This is a visual panel showing each agent as a card with real-time status, connected by lines representing message flow between agents.

Initially uses mock data — real agent data integration happens in S9.2.

## 2. Requirements

### FR-1: Agent Cards
- Display 8 agent cards (orchestrator + 7 specialists)
- Each card shows:
  - Agent name (human-readable)
  - Agent type (from `AgentType`)
  - Status indicator (color-coded dot: green=active, blue=processing, gray=idle, red=error, dark=offline)
  - LLM tier badge (critical, standard, routine, vision)
  - Last active timestamp (relative: "2m ago", "just now")
  - Capabilities list (collapsed, expandable)

### FR-2: Agent Layout
- Orchestrator card centered at the top
- 7 specialist agents arranged below in a grid (2 rows)
- Visual connection lines from orchestrator to each specialist
- Responsive: stacks vertically on mobile

### FR-3: Status Colors
| Status | Color | Dot Class |
|--------|-------|-----------|
| active | green | bg-green-500 |
| processing | blue | bg-blue-500 |
| idle | gray | bg-gray-500 |
| error | red | bg-red-500 |
| offline | dark gray | bg-gray-700 |

### FR-4: LLM Tier Badges
| Tier | Label | Style |
|------|-------|-------|
| critical | Critical | text-red-400 border-red-800 |
| standard | Standard | text-yellow-400 border-yellow-800 |
| routine | Routine | text-green-400 border-green-800 |
| vision | Vision | text-purple-400 border-purple-800 |

### FR-5: Message Flow (Visual)
- Animated dashed lines from orchestrator to active agents
- Lines are gray when agent is idle, colored when active
- Optional: show last message type on the connection line

### FR-6: Mock Data
- Provide a `MOCK_AGENTS` array matching the 8 agents defined in the architecture
- Use realistic capabilities from `design.md`
- Default state: orchestrator active, 2-3 agents processing, rest idle

### FR-7: AgentFlow Props
```typescript
interface AgentFlowProps {
  agents?: AgentCard[];       // Override mock data with real data
  onAgentClick?: (agent: AgentCard) => void;  // Click handler for agent detail
  className?: string;
}
```

## 3. Non-Requirements
- No real WebSocket data (S9.2)
- No agent detail modal/page
- No real-time message history
- No drag-and-drop or interactive graph editing

## 4. Technical Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Layout | CSS Grid + flexbox | No need for a graph library — 8 nodes with simple connections |
| Connection lines | SVG lines | Lightweight, no D3/vis.js dependency needed for 8 connections |
| Animation | CSS animation | `animate-pulse` for processing, dashed stroke-dashoffset for flow |
| State | Props + local state | No global state needed — data flows from parent |

## 5. TDD Notes

### What to Test
1. **AgentCard** — renders name, status dot, tier badge, capabilities
2. **AgentFlow** — renders all 8 agents with mock data
3. **AgentFlow** — accepts custom agents via props
4. **Status colors** — correct color class for each status
5. **Tier badges** — correct styling for each tier
6. **Click handler** — fires onAgentClick with correct agent
7. **Responsive** — component renders without errors at different viewports

### Test Files
- `dashboard/src/__tests__/components/AgentFlow.test.tsx`

## 6. Acceptance Criteria

- [ ] AgentFlow renders 8 agent cards (orchestrator + 7 specialists)
- [ ] Each card shows name, status dot, LLM tier badge
- [ ] Status dots use correct colors for all 5 states
- [ ] Orchestrator is visually distinguished (top/center)
- [ ] SVG connection lines drawn from orchestrator to specialists
- [ ] Mock data is realistic and matches architecture
- [ ] `onAgentClick` callback works
- [ ] Component accepts optional `agents` prop to override mock data
- [ ] All tests pass
- [ ] `npm run lint` passes
- [ ] Component renders correctly in dark theme (gray-900 background)
