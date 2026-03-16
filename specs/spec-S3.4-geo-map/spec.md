# Spec S3.4: India-Centered Leaflet Map (GeoMap)

**Status**: done

## Overview
Interactive Leaflet map component centered on India with OpenStreetMap tiles, disaster markers with severity-based styling, flood zone polygons, and state/district boundary overlays. Uses `react-leaflet` for React integration.

## Depends On
- **S3.3** (Dashboard setup) — Next.js project, TypeScript, Tailwind, Jest

## Outcomes
1. `GeoMap.tsx` component renders a Leaflet map centered on India (20.5937°N, 78.9629°E, zoom 5)
2. OpenStreetMap tiles load correctly (no API key required)
3. Disaster markers display with severity-based color coding (low=green, medium=yellow, high=orange, critical=red)
4. Markers show popup with disaster title, type, severity, phase, and location info
5. Flood zone polygons render as semi-transparent overlays
6. Map supports programmatic zoom-to-disaster on marker click
7. Component accepts disasters array and optional GeoJSON overlays as props
8. Loading state shown while map initializes
9. All functionality works with mock data (no API dependency)

## Types

```typescript
// Extends existing Disaster type from @/types
interface GeoMapProps {
  disasters: Disaster[];
  floodZones?: GeoJSON.FeatureCollection;
  selectedDisasterId?: string;
  onDisasterSelect?: (id: string) => void;
  className?: string;
}

interface FloodZone {
  type: "Feature";
  geometry: GeoJSON.Polygon;
  properties: {
    name: string;
    severity: Severity;
    affected_area_km2?: number;
  };
}
```

## Technical Notes
- Use `react-leaflet` v4+ with `leaflet` v1.9+
- Must use dynamic import (`next/dynamic`) with `ssr: false` — Leaflet requires `window` object
- Leaflet CSS must be imported (either in component or via CDN link in layout)
- Tile URL: `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`
- Attribution: `&copy; OpenStreetMap contributors`
- Severity color map: low=#16a34a, medium=#ca8a04, high=#ea580c, critical=#dc2626

## TDD Plan

### Test Cases (Red phase)
1. **Renders map container** — component mounts with correct test ID
2. **Centers on India** — map initializes at [20.5937, 78.9629] zoom 5
3. **Renders disaster markers** — one marker per disaster in props
4. **Severity-based marker colors** — each severity maps to correct color
5. **Marker popup content** — clicking marker shows disaster details
6. **Renders flood zone polygons** — GeoJSON overlay renders when provided
7. **No flood zones by default** — no overlay when floodZones prop omitted
8. **Calls onDisasterSelect** — callback fires with disaster ID on marker click
9. **Handles empty disasters array** — renders map with no markers
10. **Loading state** — shows loading placeholder before map loads

### Mocking Strategy
- Mock `react-leaflet` components (MapContainer, TileLayer, Marker, Popup, GeoJSON) in tests
- Mock `next/dynamic` to render component synchronously in tests
- No external API calls to mock — all data passed via props
