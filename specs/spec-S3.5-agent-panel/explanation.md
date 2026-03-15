# Spec S3.5: Agent Status Panel — Explanation

## Why This Spec Exists

The CRISIS-BENCH system has 7 AI agents (orchestrator + 6 specialists) that collaborate during disaster response. Without a visual panel, understanding agent status and communication flow requires reading JSON logs. The AgentFlow component provides real-time visual feedback during development and serves as the "nervous system view" of the multi-agent architecture.

Building this in Phase 3 (before agents are implemented in Phase 7) means the visualization is ready when agents come online — developers can immediately see agent activation, message flow, and error states instead of debugging blind.

## What It Does

**AgentFlow** is a React component that displays:

1. **Agent Cards** — One card per agent showing name, status (color-coded dot), LLM tier badge, and capabilities list
2. **Visual Layout** — Orchestrator centered at top, 6 specialists in a responsive grid below
3. **Connection Lines** — SVG lines from orchestrator to each specialist, animated when active/processing
4. **Mock Data** — Realistic default data matching the architecture (MOCK_AGENTS), overridable via props

### Agent Status Colors
- Green (active), Blue (processing), Gray (idle), Red (error), Dark gray (offline)

### LLM Tier Badges
- Critical (red) — Orchestrator uses DeepSeek Reasoner
- Standard (yellow) — PredictiveRisk, ResourceAllocation, HistoricalMemory use DeepSeek Chat
- Routine (green) — SituationSense, CommunityComms, InfraStatus use Qwen Flash
- Vision (purple) — Reserved for SituationSense satellite imagery

## How It Works

**Architecture**: Pure presentational component — no state management, no API calls. Data flows in via `agents` prop (or falls back to `MOCK_AGENTS`). Click events bubble up via `onAgentClick`.

**Key exports**:
- `AgentFlow` (default) — Main component
- `MOCK_AGENTS` — 7 agent cards with realistic capabilities
- `STATUS_COLORS` — AgentStatus → Tailwind class mapping
- `TIER_STYLES` — LLM tier → color/label mapping

**Layout**: CSS Grid + Flexbox. Orchestrator in a centered `max-w-sm` container, specialists in a `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3` responsive grid.

**Connection lines**: SVG `<line>` elements positioned absolutely behind the cards. Blue + dashed animation for active agents, gray + dotted for idle.

## How It Connects

| Connection | Direction | Details |
|-----------|-----------|---------|
| S3.3 (Dashboard Setup) | Depends on | Uses TypeScript types (`AgentCard`, `AgentStatus`, `AgentType`) and Tailwind styling from the base setup |
| S3.3 (DashboardShell) | Renders within | AgentFlow slots into the DashboardShell's main content area |
| S9.2 (Dashboard Integration) | Will integrate with | Real agent data from WebSocket will replace MOCK_AGENTS via the `agents` prop |
| S7.1-S7.8 (Agents) | Visualizes | Each agent card corresponds to a LangGraph agent built in Phase 7 |
| S3.2 (WebSocket) | Future data source | `agent.status` events from WebSocket will update agent cards in real-time |

## Interview Talking Points

**Q: Why build the agent panel before the agents exist?**
A: Mock-first UI development. The component is designed to accept data via props — today it uses MOCK_AGENTS, tomorrow it switches to real WebSocket data by passing `agents={liveAgents}`. This is the **Dependency Inversion Principle** in practice: the UI depends on an interface (AgentCard type), not a concrete data source.

**Q: Why SVG lines instead of a graph visualization library (D3, vis.js)?**
A: 7 nodes with hub-and-spoke topology (orchestrator → specialists) is trivially expressible as SVG `<line>` elements. A graph library would add 50-200KB of JavaScript for zero benefit. This is a deliberate YAGNI decision — if we later need interactive graph editing or complex layouts, we'd introduce a library then.

**Q: Why export STATUS_COLORS and TIER_STYLES as constants?**
A: They're used in tests for assertion and will be reused by MetricsPanel (S3.6) and Timeline (S3.7) for consistent agent color coding across the dashboard.
