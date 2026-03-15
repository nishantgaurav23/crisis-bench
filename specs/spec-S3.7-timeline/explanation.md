# Spec S3.7: Event Timeline Component — Explanation

## Why This Spec Exists

The Timeline component provides temporal context for disaster response operations. While the GeoMap (S3.4) shows *where* events happen and AgentFlow (S3.5) shows *who* is acting, the Timeline shows *when* and *what sequence* — essential for understanding how a crisis unfolds over time. Disaster response is inherently sequential: alert received, agents activated, situation assessed, evacuation ordered. Without a timeline, operators see a snapshot but miss the narrative.

## What It Does

- Renders a vertical timeline of `TimelineEvent` entries sorted newest-first
- Each event displays: severity badge (color-coded), event type label, title, description, relative timestamp, and optional agent/phase badges
- Supports filtering by event type (`WebSocketEventType`) and agent (`AgentType`)
- Provides `MOCK_TIMELINE_EVENTS` with 10 events simulating a cyclone response in Odisha
- Exports `formatRelativeTime()` for human-readable timestamps (e.g., "2m ago")
- Shows empty state when no events exist
- Respects `maxEvents` prop to cap rendered items (default 50)

## How It Works

**Data Flow**: Events come in as `TimelineEvent[]` via props (or mock data). The component filters by type/agent if specified, sorts by timestamp descending, slices to `maxEvents`, then renders each as a card on a vertical line.

**Type Integration**: Uses `WebSocketEventType`, `AgentType`, `Severity`, and `DisasterPhase` from `@/types/index.ts` — the same types used by the WebSocket client (S3.2) and agent panel (S3.5). This ensures that when live WebSocket events are connected (S9.2), they flow directly into the Timeline without transformation.

**Relative Timestamps**: `formatRelativeTime()` computes seconds/minutes/hours/days from the ISO timestamp to now. The full ISO timestamp is available via `title` attribute (hover tooltip).

**Component Pattern**: Follows the same pattern as AgentFlow: `"use client"` directive, exported mock data, `data-testid` on all elements, `className` passthrough, callback prop for click events.

## How It Connects

| Spec | Relationship |
|------|-------------|
| S3.3 (Dashboard Setup) | **Dependency** — Timeline lives in the Next.js project scaffold |
| S3.2 (WebSocket) | **Consumer** — WebSocket events will feed into Timeline via `WebSocketMessage.data` |
| S3.5 (AgentFlow) | **Sibling** — Both display agent activity; Timeline adds temporal dimension |
| S3.6 (MetricsPanel) | **Sibling** — MetricsPanel shows cost/tokens; Timeline shows the events that generated them |
| S9.2 (Dashboard Integration) | **Future consumer** — Will wire live WebSocket data into Timeline props |

## Interview Angles

**Q: Why sort newest-first instead of chronological?**
A: In active disaster response, operators care about *what just happened* — they don't want to scroll past hours of old events to see the latest evacuation order. Newest-first puts the most actionable information at the top. For post-incident review (chronological), you'd reverse the sort.

**Q: Why relative timestamps instead of absolute?**
A: "2 min ago" is immediately meaningful during a crisis — "2026-03-15T14:23:47Z" requires mental arithmetic. The full ISO timestamp is preserved in the `title` attribute for precise reference when needed.

**Q: How would you handle thousands of events in production?**
A: The `maxEvents` prop caps rendering to prevent DOM bloat. In production (S9.2), we'd add virtualized scrolling (e.g., `react-virtual`) to only render visible items, and paginate via the API with cursor-based pagination. The current implementation is a deliberate MVP — solve the rendering problem when the data volume requires it.
