# Spec S5.6 — Implementation Checklist

## Phase 1: Red (Write Tests)
- [x] Test FIRMSServer initialization (name, base URL, API key, rate limit)
- [x] Test all 5 tools registered
- [x] Test `_normalize_fire` extracts key fields
- [x] Test `get_active_fires` with mock response
- [x] Test `get_fires_by_region` with custom bbox
- [x] Test `get_high_confidence_fires` filters correctly
- [x] Test `get_fire_detail` with location params
- [x] Test `get_fire_summary` returns correct structure
- [x] Test empty results
- [x] Test error handling (timeout, server error)
- [x] Test `create_server()` factory

## Phase 2: Green (Implement)
- [x] Create `FIRMSServer` class extending `BaseMCPServer`
- [x] Implement `_normalize_fire` for field extraction
- [x] Implement all 5 MCP tools
- [x] Implement `create_server()` factory
- [x] `NASA_FIRMS_KEY` already in config (CrisisSettings)

## Phase 3: Refactor
- [x] Run ruff and fix any lint issues
- [x] Run all tests — 41 passing
- [x] Verify no hardcoded API keys
