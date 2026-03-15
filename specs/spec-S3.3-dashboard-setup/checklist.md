# S3.3 Implementation Checklist

## Phase 1: Red — Write Failing Tests
- [x] Set up Jest + React Testing Library config
- [x] Write API client tests (URL construction, error handling, response parsing)
- [x] Write WebSocket client tests (connect, reconnect, message parsing)
- [x] Write DashboardShell component tests (sidebar, header, content)
- [x] Write home page render test

## Phase 2: Green — Implement Minimum Code
- [x] Initialize Next.js 14 project with TypeScript + Tailwind
- [x] Create TypeScript types (`types/index.ts`)
- [x] Implement API client (`lib/api.ts`)
- [x] Implement WebSocket client (`lib/websocket.ts`)
- [x] Implement DashboardShell component
- [x] Implement root layout and home page
- [x] Create `.env.local.example`
- [x] Verify all tests PASS (30/30 passing)

## Phase 3: Refactor + Production
- [x] Create Dockerfile (multi-stage build)
- [x] Create `.dockerignore`
- [x] Add dashboard service to `docker-compose.yml`
- [x] Run `npm run lint` — zero type errors
- [x] Run `npm run build` — production build successful
- [x] Final test run — all 30 tests pass
- [x] Update roadmap status to "done"
