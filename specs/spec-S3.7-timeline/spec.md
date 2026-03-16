# Spec S3.7: Event Timeline Component

**Status**: done

## Overview
A React component that displays a chronological timeline of disaster events, agent decisions, and phase transitions. Used in the CRISIS-BENCH dashboard to give operators a temporal view of the response lifecycle.

## Dependencies
- S3.3 (Next.js dashboard setup) — done

## Location
- `dashboard/src/components/Timeline.tsx`
- `dashboard/src/__tests__/components/Timeline.test.tsx`

## Requirements

### Functional
1. Display a vertical timeline of events sorted newest-first (most recent at top)
2. Each event shows: timestamp, event type, agent source, title, description, severity badge
3. Support event types: `disaster.created`, `disaster.updated`, `agent.status`, `agent.decision`, `metrics.update` (matches `WebSocketEventType`)
4. Color-code events by severity: critical (red), high (orange), medium (yellow), low (green)
5. Show disaster phase transitions visually (monitoring -> alert -> active -> response -> recovery)
6. Support filtering events by type and by agent
7. Auto-scroll to newest event when new events arrive (with opt-out if user has scrolled up)
8. Accept events via props; provide mock data for standalone rendering
9. Show relative timestamps (e.g., "2 min ago") with full timestamp on hover
10. Empty state when no events exist

### Non-Functional
- Pure client component ("use client")
- No external dependencies beyond what's in package.json
- Dark theme consistent with existing dashboard (gray-900/800/700 palette)
- Accessible: semantic HTML, ARIA labels on interactive elements
- data-testid attributes on all testable elements

## Data Model

```typescript
export interface TimelineEvent {
  id: string;
  type: WebSocketEventType;
  title: string;
  description?: string;
  severity: Severity;
  agent_type?: AgentType;
  phase?: DisasterPhase;
  timestamp: string; // ISO 8601
}
```

## Component API

```typescript
interface TimelineProps {
  events?: TimelineEvent[];
  filterByType?: WebSocketEventType;
  filterByAgent?: AgentType;
  onEventClick?: (event: TimelineEvent) => void;
  className?: string;
  maxEvents?: number; // default 50
}
```

## Mock Data
Provide `MOCK_TIMELINE_EVENTS` (8-10 events) representing a realistic cyclone response timeline: alert received, agents activated, situation assessed, evacuation ordered, resources deployed, etc.

## TDD Notes

### Tests to Write First
1. Renders timeline container
2. Renders all mock events (default)
3. Shows event titles and descriptions
4. Shows timestamps in relative format
5. Shows severity badges with correct colors
6. Shows agent source for agent events
7. Shows phase badge for phase transition events
8. Filters events by type
9. Filters events by agent
10. Fires onEventClick when event is clicked
11. Shows empty state when no events
12. Respects maxEvents prop (truncates)
13. Newest events appear first (sorted by timestamp desc)
14. Accepts custom className
15. Exports MOCK_TIMELINE_EVENTS and SEVERITY_COLORS

## Outcomes
- [ ] Timeline.tsx renders a chronological event list
- [ ] All 15 tests pass
- [ ] TypeScript compiles with no errors (`npx tsc --noEmit`)
- [ ] Consistent with existing dashboard dark theme
- [ ] TimelineEvent type exported from types/index.ts
