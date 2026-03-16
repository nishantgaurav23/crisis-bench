# Spec S3.3: Next.js Dashboard Setup

**Phase**: 3 — API + Dashboard MVP
**Depends On**: — (no dependencies)
**Location**: `dashboard/`
**Status**: done

---

## 1. Overview

Set up the Next.js 14+ project scaffold for the CRISIS-BENCH dashboard. This is the foundation for all frontend components (GeoMap, AgentFlow, MetricsPanel, Timeline) built in S3.4–S3.7.

The dashboard provides visual feedback during development — agent status, disaster locations, and message flows on an India-centered map. It connects to the FastAPI gateway (localhost:8000) via REST and WebSocket.

## 2. Requirements

### FR-1: Project Scaffold
- Next.js 14+ with App Router (not Pages Router)
- TypeScript strict mode
- Tailwind CSS for styling
- ESLint + Prettier configuration
- `src/` directory structure

### FR-2: Project Structure
```
dashboard/
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── postcss.config.mjs
├── next.config.ts
├── .env.local.example
├── Dockerfile
├── .dockerignore
├── .eslintrc.json
├── public/
│   └── favicon.ico
└── src/
    ├── app/
    │   ├── layout.tsx          # Root layout with metadata
    │   ├── page.tsx            # Home page (dashboard shell)
    │   └── globals.css         # Tailwind directives + custom styles
    ├── components/
    │   └── DashboardShell.tsx  # Main layout: sidebar + content area
    ├── lib/
    │   ├── api.ts              # REST API client (fetch wrapper)
    │   └── websocket.ts        # WebSocket client with reconnection
    └── types/
        └── index.ts            # Shared TypeScript types (Disaster, Agent, etc.)
```

### FR-3: Environment Configuration
- `NEXT_PUBLIC_API_URL` — FastAPI gateway URL (default: `http://localhost:8000`)
- `NEXT_PUBLIC_WS_URL` — WebSocket URL (default: `ws://localhost:8000/ws`)
- `.env.local.example` template with defaults

### FR-4: API Client
- Typed fetch wrapper for REST endpoints (`/api/v1/disasters`, `/api/v1/agents`, `/health`)
- Error handling with typed error responses
- Base URL from `NEXT_PUBLIC_API_URL`

### FR-5: WebSocket Client
- Connect to `/ws` endpoint on the API gateway
- Auto-reconnect with exponential backoff (1s, 2s, 4s, max 30s)
- Parse message envelope: `{ type, data, timestamp, trace_id }`
- Event types: `disaster.created`, `disaster.updated`, `agent.status`, `agent.decision`, `metrics.update`

### FR-6: DashboardShell Component
- Responsive layout with sidebar navigation and main content area
- Sidebar links: Dashboard (home), Map, Agents, Metrics, Timeline
- Header with CRISIS-BENCH branding and connection status indicator
- Placeholder slots for components built in S3.4–S3.7

### FR-7: TypeScript Types
- Mirror Pydantic models from `src/shared/models.py`:
  - `Disaster` (id, type, severity, location, phase, timestamps)
  - `AgentCard` (agent_type, status, capabilities)
  - `WebSocketMessage` (type, data, timestamp, trace_id)
  - `HealthStatus` (status, version, services)

### FR-8: Dockerfile
- Multi-stage build: deps → build → production
- Node 20 Alpine base
- Standalone output mode for minimal image size
- Expose port 3000
- Health check endpoint

### FR-9: Docker Integration
- Add dashboard service to `docker-compose.yml`
- Environment: `NEXT_PUBLIC_API_URL=http://localhost:8000`
- Port mapping: `3000:3000`
- Depends on: api service (when available)

## 3. Non-Requirements
- No actual map rendering (S3.4)
- No agent visualization (S3.5)
- No metrics charts (S3.6)
- No timeline display (S3.7)
- No SSR data fetching — client-side only for MVP

## 4. Technical Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| App Router vs Pages | App Router | Modern Next.js pattern, better layouts, server components future |
| Styling | Tailwind CSS | Utility-first, no CSS-in-JS runtime, excellent DX |
| State Management | React hooks (useState/useEffect) | No need for Redux/Zustand yet — dashboard is read-heavy |
| Package Manager | npm | Standard, no pnpm/yarn lock file conflicts |
| Node Version | 20 LTS | Current LTS, Alpine images available |

## 5. TDD Notes

### What to Test
1. **TypeScript types** — compile-time validation (tsconfig strict)
2. **API client** — correct URL construction, error handling, response parsing
3. **WebSocket client** — connection, reconnection logic, message parsing
4. **DashboardShell** — renders sidebar, header, content area
5. **Home page** — renders without crashing, shows connection status

### Testing Stack
- Jest + React Testing Library
- `jest-environment-jsdom` for component tests
- Mock `fetch` and `WebSocket` for client tests

### Test Files
- `dashboard/src/__tests__/lib/api.test.ts`
- `dashboard/src/__tests__/lib/websocket.test.ts`
- `dashboard/src/__tests__/components/DashboardShell.test.tsx`
- `dashboard/src/__tests__/app/page.test.tsx`

## 6. Acceptance Criteria

- [ ] `cd dashboard && npm install` completes without errors
- [ ] `npm run build` produces a successful build
- [ ] `npm run lint` passes with zero warnings
- [ ] `npm test` passes all tests
- [ ] TypeScript strict mode — zero type errors
- [ ] Tailwind CSS is functional (utility classes apply styles)
- [ ] API client constructs correct URLs and handles errors
- [ ] WebSocket client connects and parses messages
- [ ] DashboardShell renders with sidebar and content area
- [ ] Dockerfile builds successfully
- [ ] Docker Compose starts dashboard service on port 3000
