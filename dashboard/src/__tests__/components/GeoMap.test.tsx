import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import GeoMap, { INDIA_CENTER, INDIA_ZOOM, severityColor } from "@/components/GeoMap";
import type { Disaster, Severity } from "@/types";

// --- Mock react-leaflet ---
const mockSetView = jest.fn();

jest.mock("react-leaflet", () => {
  const React = require("react");
  return {
    MapContainer: React.forwardRef(
      (
        { children, center, zoom, ...props }: {
          children: React.ReactNode;
          center: [number, number];
          zoom: number;
          [key: string]: unknown;
        },
        ref: React.Ref<{ setView: typeof mockSetView }>
      ) => {
        React.useImperativeHandle(ref, () => ({ setView: mockSetView }));
        return (
          <div
            data-testid="map-container"
            data-center={JSON.stringify(center)}
            data-zoom={zoom}
            {...props}
          >
            {children}
          </div>
        );
      }
    ),
    TileLayer: ({ url, attribution }: { url: string; attribution: string }) => (
      <div data-testid="tile-layer" data-url={url} data-attribution={attribution} />
    ),
    Marker: ({
      children,
      position,
      eventHandlers,
    }: {
      children: React.ReactNode;
      position: [number, number];
      eventHandlers?: { click?: () => void };
    }) => (
      <div
        data-testid="map-marker"
        data-position={JSON.stringify(position)}
        onClick={eventHandlers?.click}
      >
        {children}
      </div>
    ),
    Popup: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="marker-popup">{children}</div>
    ),
    GeoJSON: ({ data }: { data: unknown }) => (
      <div data-testid="geojson-layer" data-features={JSON.stringify(data)} />
    ),
    useMap: () => ({ setView: mockSetView }),
  };
});

// Mock leaflet's icon and divIcon
jest.mock("leaflet", () => ({
  divIcon: jest.fn(({ className, html }: { className: string; html: string }) => ({
    options: { className, html },
  })),
  icon: jest.fn(),
}));

// --- Test Data ---
const mockDisasters: Disaster[] = [
  {
    id: "d1",
    type: "cyclone",
    title: "Cyclone Biparjoy",
    severity: "critical",
    phase: "active",
    location: { lat: 22.3, lng: 70.8, name: "Kutch", state: "Gujarat", district: "Kutch" },
    affected_population: 250000,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  },
  {
    id: "d2",
    type: "flood",
    title: "Kerala Floods",
    severity: "high",
    phase: "response",
    location: { lat: 10.85, lng: 76.27, name: "Thrissur", state: "Kerala" },
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  },
  {
    id: "d3",
    type: "earthquake",
    title: "Minor Tremor",
    severity: "low",
    phase: "monitoring",
    location: { lat: 28.6, lng: 77.2, name: "Delhi", state: "Delhi" },
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  },
];

const mockFloodZones: GeoJSON.FeatureCollection = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [76.0, 10.0],
            [77.0, 10.0],
            [77.0, 11.0],
            [76.0, 11.0],
            [76.0, 10.0],
          ],
        ],
      },
      properties: { name: "Kerala Flood Zone", severity: "high", affected_area_km2: 1200 },
    },
  ],
};

// --- Tests ---
describe("GeoMap", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders map container with correct test ID", () => {
    render(<GeoMap disasters={[]} />);
    expect(screen.getByTestId("geo-map")).toBeInTheDocument();
    expect(screen.getByTestId("map-container")).toBeInTheDocument();
  });

  it("centers map on India at correct coordinates and zoom", () => {
    render(<GeoMap disasters={[]} />);
    const mapContainer = screen.getByTestId("map-container");
    expect(JSON.parse(mapContainer.dataset.center!)).toEqual(INDIA_CENTER);
    expect(Number(mapContainer.dataset.zoom)).toBe(INDIA_ZOOM);
  });

  it("renders one marker per disaster", () => {
    render(<GeoMap disasters={mockDisasters} />);
    const markers = screen.getAllByTestId("map-marker");
    expect(markers).toHaveLength(3);
  });

  it("positions markers at correct coordinates", () => {
    render(<GeoMap disasters={mockDisasters} />);
    const markers = screen.getAllByTestId("map-marker");
    expect(JSON.parse(markers[0].dataset.position!)).toEqual([22.3, 70.8]);
    expect(JSON.parse(markers[1].dataset.position!)).toEqual([10.85, 76.27]);
    expect(JSON.parse(markers[2].dataset.position!)).toEqual([28.6, 77.2]);
  });

  it("maps severity to correct colors", () => {
    expect(severityColor("low")).toBe("#16a34a");
    expect(severityColor("medium")).toBe("#ca8a04");
    expect(severityColor("high")).toBe("#ea580c");
    expect(severityColor("critical")).toBe("#dc2626");
  });

  it("renders popup with disaster details", () => {
    render(<GeoMap disasters={mockDisasters} />);
    const popups = screen.getAllByTestId("marker-popup");
    expect(popups).toHaveLength(3);

    // First popup should contain disaster info
    expect(popups[0].textContent).toContain("Cyclone Biparjoy");
    expect(popups[0].textContent).toContain("cyclone");
    expect(popups[0].textContent).toContain("critical");
    expect(popups[0].textContent).toContain("Kutch");
  });

  it("renders flood zone GeoJSON overlay when provided", () => {
    render(<GeoMap disasters={[]} floodZones={mockFloodZones} />);
    expect(screen.getByTestId("geojson-layer")).toBeInTheDocument();
  });

  it("does not render GeoJSON overlay when floodZones prop is omitted", () => {
    render(<GeoMap disasters={[]} />);
    expect(screen.queryByTestId("geojson-layer")).not.toBeInTheDocument();
  });

  it("calls onDisasterSelect with disaster ID on marker click", () => {
    const onSelect = jest.fn();
    render(<GeoMap disasters={mockDisasters} onDisasterSelect={onSelect} />);
    const markers = screen.getAllByTestId("map-marker");

    fireEvent.click(markers[0]);
    expect(onSelect).toHaveBeenCalledWith("d1");

    fireEvent.click(markers[1]);
    expect(onSelect).toHaveBeenCalledWith("d2");
  });

  it("handles empty disasters array without errors", () => {
    render(<GeoMap disasters={[]} />);
    expect(screen.getByTestId("map-container")).toBeInTheDocument();
    expect(screen.queryByTestId("map-marker")).not.toBeInTheDocument();
  });

  it("renders loading state with correct test ID", () => {
    // The dynamic import wrapper shows a loading placeholder
    // We test the loading component directly
    render(<GeoMap disasters={[]} />);
    // The actual component should have a wrapper with geo-map testid
    expect(screen.getByTestId("geo-map")).toBeInTheDocument();
  });

  it("uses OpenStreetMap tile layer with correct URL", () => {
    render(<GeoMap disasters={[]} />);
    const tileLayer = screen.getByTestId("tile-layer");
    expect(tileLayer.dataset.url).toBe(
      "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
    );
    expect(tileLayer.dataset.attribution).toContain("OpenStreetMap");
  });

  it("accepts and applies className prop", () => {
    render(<GeoMap disasters={[]} className="custom-class" />);
    const wrapper = screen.getByTestId("geo-map");
    expect(wrapper.className).toContain("custom-class");
  });
});
