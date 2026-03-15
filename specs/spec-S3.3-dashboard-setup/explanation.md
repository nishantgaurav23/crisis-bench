# S3.3 Explanation: Next.js Dashboard Setup

## Why This Spec Exists

The dashboard provides visual feedback during development — seeing agent status, disaster locations, and message flows on an India-centered map catches integration bugs faster than reading JSON logs. Building it early (Phase 3) means every subsequent spec (agents, benchmarks) can be visually verified. It also serves as a living demo for interviews.

## What It Does

Sets up the complete Next.js 14+ project scaffold with:
- **TypeScript types** mirroring backend Pydantic models (Disaster, AgentCard, WebSocketMessage, HealthStatus)
- **REST API client** with typed fetch wrapper for all backend endpoints (`/health`, `/api/v1/disasters`, `/api/v1/agents`)
- **WebSocket client** with auto-reconnect (exponential backoff: 1s → 2s → 4s → max 30s) for real-time updates
- **DashboardShell** layout with sidebar navigation (Dashboard, Map, Agents, Metrics, Timeline) and connection status indicator
- **Dockerfile** for multi-stage production build (deps → build → standalone runtime)
- **Docker Compose** integration on port 3000

## How It Works

### Architecture
```
Dashboard (localhost:3000)
├── REST ──→ FastAPI Gateway (localhost:8000)
│   └── /health, /api/v1/disasters, /api/v1/agents
└── WebSocket ──→ /ws
    └── disaster.created, agent.status, metrics.update
```

### Key Technical Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| App Router | Next.js 14+ App Router | Modern pattern, better layouts, React Server Components ready |
| Styling | Tailwind CSS v4 | Utility-first, no runtime CSS-in-JS, fast builds |
| State | React hooks (useState/useEffect) | Dashboard is read-heavy, no need for Redux/Zustand yet |
| WebSocket | Custom client class | Simple reconnect logic, no heavy dependency (socket.io unnecessary) |
| Testing | Jest + React Testing Library | Standard React testing stack, `@testing-library/jest-dom` for DOM assertions |
| Docker | Multi-stage + standalone output | Minimal image size (~100MB vs ~1GB with full node_modules) |

### WebSocket Reconnection Strategy
The `CrisisWebSocketClient` implements exponential backoff:
1. Initial delay: 1 second
2. Each failure doubles the delay: 1s → 2s → 4s → 8s → 16s → 30s (capped)
3. Successful connection resets the delay to 1s
4. `disconnect()` stops all reconnection attempts

### Type Safety
TypeScript types in `src/types/index.ts` mirror the backend Pydantic models:
- `Disaster` — matches `src/shared/models.py` disaster schema
- `AgentCard` — matches the 7 agent types (orchestrator through historical_memory)
- `WebSocketMessage<T>` — generic envelope for all WS event types
- `HealthStatus` — matches `/health` endpoint response

## How It Connects

### Upstream Dependencies
- None — S3.3 has no dependencies

### Downstream Dependents
- **S3.4 (GeoMap)** — uses DashboardShell layout, types, and API client
- **S3.5 (AgentFlow)** — uses DashboardShell, AgentCard types, WebSocket for live updates
- **S3.6 (MetricsPanel)** — uses DashboardShell, metrics WebSocket events
- **S3.7 (Timeline)** — uses DashboardShell, WebSocket event stream
- **S9.2 (Dashboard Integration)** — builds on all S3.x components for live data

### Integration Points
- **FastAPI Gateway (S3.1)** — REST API calls via `lib/api.ts`
- **WebSocket Server (S3.2)** — real-time event stream via `lib/websocket.ts`
- **Docker Compose (S1.2)** — dashboard service added on port 3000

## Test Coverage

| Test File | Tests | What's Covered |
|-----------|-------|----------------|
| `api.test.ts` | 8 | URL construction, GET/POST, error handling (JSON + non-JSON) |
| `websocket.test.ts` | 12 | Connect, reconnect backoff, message parsing, unsubscribe, malformed messages |
| `DashboardShell.test.tsx` | 6 | Sidebar nav, header, content area, connection status |
| `page.test.tsx` | 3 | Page title, shell rendering, placeholder sections |
| **Total** | **30** | |

## Interview Talking Points

**Q: Why build the dashboard scaffold before any agents exist?**
A: Visual feedback loop. Each subsequent spec (agents, benchmarks) can push data through the WebSocket and see it rendered immediately. Debugging "why isn't this agent responding?" is vastly easier with a status panel than grepping JSON logs.

**Q: Why a custom WebSocket client instead of socket.io?**
A: socket.io adds 50KB+ to the bundle, requires a socket.io-compatible server, and brings features we don't need (rooms, namespaces, binary data). Our WebSocket needs are simple: connect, receive JSON, reconnect on failure. The custom client is ~80 lines and does exactly what we need.

**Q: Why Tailwind CSS instead of CSS Modules or styled-components?**
A: Tailwind is utility-first — no context-switching between component files and CSS files, no runtime JS (unlike styled-components), and excellent for responsive layouts. The build step purges unused classes, so production CSS is tiny. Trade-off: utility classes can be verbose in JSX, but the DX improvement (no naming CSS classes) is worth it.
