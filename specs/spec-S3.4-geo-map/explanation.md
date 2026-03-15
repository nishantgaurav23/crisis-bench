# Spec S3.4: India-Centered Leaflet Map — Explanation

## Why This Spec Exists
The GeoMap is the primary visual interface for disaster response coordination. Without a map, operators must mentally correlate lat/lng coordinates with disaster impact zones — unacceptable in a real-time emergency. This component provides spatial context for every disaster event, making the dashboard actionable rather than just informational.

## What It Does
- Renders an interactive Leaflet map centered on India (20.5937°N, 78.9629°E, zoom 5)
- Displays disaster markers with severity-based color coding (green/yellow/orange/red)
- Shows popup details (title, type, severity, phase, location, affected population) on click
- Renders flood zone polygons as semi-transparent GeoJSON overlays
- Supports programmatic zoom-to-disaster and selection callbacks
- Uses OpenStreetMap tiles — zero cost, zero API keys

## How It Works
- **react-leaflet v4** wraps Leaflet in React components (MapContainer, TileLayer, Marker, Popup, GeoJSON)
- **Severity color mapping** uses a `Record<Severity, string>` matching Tailwind's crisis color palette
- **Custom markers** via `L.divIcon` — colored circles with white border, sized 14px
- **GeoJSON overlay** styles flood zones with severity-based fill colors at 25% opacity
- **SSR safety** — Leaflet requires `window`, so the component uses `"use client"` directive and imports Leaflet CSS directly in the component
- **Leaflet CSS** is imported directly in the component file to avoid layout-level dependencies

## Key Decisions
1. **Direct component vs dynamic import**: Used `"use client"` directive with direct import. In production, Next.js dynamic import with `ssr: false` would be needed for the page that hosts this component.
2. **Custom div icons vs default Leaflet icons**: Default Leaflet icon PNGs have path issues in Next.js/Webpack builds. Custom `divIcon` with inline styles avoids this entirely.
3. **CSS import in component**: Leaflet CSS is imported directly in the component rather than in `layout.tsx` to keep the dependency self-contained.

## Connections
- **S3.3** (Dashboard setup): GeoMap renders inside DashboardShell
- **S3.2** (WebSocket): Real-time disaster updates will push new markers via WebSocket → state → GeoMap re-render
- **S9.2** (Dashboard integration): Will connect live disaster data from API to GeoMap props
- **S7.3** (SituationSense agent): Generates GeoJSON updates that feed into the floodZones prop

## Interview Talking Points

**Q: Why Leaflet + OpenStreetMap instead of Google Maps or Mapbox?**
A: Zero cost, zero API key, zero rate limits. OSM has excellent India coverage. Google Maps charges after 28K loads/month. For a self-hosted open-source project, free tiles with no API key is non-negotiable.

**Q: How do you handle Leaflet's SSR incompatibility with Next.js?**
A: Leaflet accesses `window` on import, which doesn't exist in Node.js SSR. We use React's `"use client"` directive to ensure the component only runs in the browser. For the page hosting this component, `next/dynamic` with `ssr: false` can be used as an additional safety layer.

**Q: Why custom `divIcon` instead of default Leaflet markers?**
A: Default Leaflet marker icons reference PNG files via relative paths that break in Webpack/Next.js builds (the classic "missing marker icon" issue). Custom `divIcon` with inline CSS avoids all asset path issues and gives us severity-based coloring with a single function.
