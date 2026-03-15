# Spec S3.4: Implementation Checklist

## Phase 1: Setup
- [x] Install `leaflet`, `react-leaflet`, `@types/leaflet`
- [x] Add Leaflet CSS import

## Phase 2: Red (Tests First)
- [x] Write all test cases in `src/__tests__/components/GeoMap.test.tsx`
- [x] Verify all tests fail (no implementation yet)

## Phase 3: Green (Implementation)
- [x] Create `src/components/GeoMap.tsx` with all props
- [x] Implement severity color mapping
- [x] Implement disaster markers with popups
- [x] Implement flood zone GeoJSON overlay
- [x] Implement dynamic import wrapper for SSR safety
- [x] Add Leaflet CSS import in component
- [x] All tests pass

## Phase 4: Refactor
- [x] TypeScript strict — no `any` types
- [x] Lint clean (tsc --noEmit, no GeoMap errors)
- [x] All tests still pass (13 GeoMap + 30 existing = 43 total)

## Phase 5: Verify
- [x] All 13 GeoMap test cases pass
- [x] No hardcoded API keys or secrets
- [x] No paid service dependencies (uses OpenStreetMap free tiles)
