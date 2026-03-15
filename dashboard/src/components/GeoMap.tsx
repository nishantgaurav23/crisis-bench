"use client";

import React, { useRef, useCallback } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  GeoJSON,
} from "react-leaflet";
import * as L from "leaflet";
import type { Disaster, Severity } from "@/types";

import "leaflet/dist/leaflet.css";

// --- Constants ---
export const INDIA_CENTER: [number, number] = [20.5937, 78.9629];
export const INDIA_ZOOM = 5;

const OSM_TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const OSM_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

// --- Severity color mapping ---
const SEVERITY_COLORS: Record<Severity, string> = {
  low: "#16a34a",
  medium: "#ca8a04",
  high: "#ea580c",
  critical: "#dc2626",
};

export function severityColor(severity: Severity): string {
  return SEVERITY_COLORS[severity];
}

function createMarkerIcon(severity: Severity): L.DivIcon {
  const color = severityColor(severity);
  return L.divIcon({
    className: "crisis-marker",
    html: `<div style="
      width: 14px;
      height: 14px;
      border-radius: 50%;
      background: ${color};
      border: 2px solid white;
      box-shadow: 0 0 4px rgba(0,0,0,0.4);
    "></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  });
}

// --- Props ---
export interface GeoMapProps {
  disasters: Disaster[];
  floodZones?: GeoJSON.FeatureCollection;
  selectedDisasterId?: string;
  onDisasterSelect?: (id: string) => void;
  className?: string;
}

// --- Component ---
export default function GeoMap({
  disasters,
  floodZones,
  selectedDisasterId,
  onDisasterSelect,
  className = "",
}: GeoMapProps) {
  const mapRef = useRef<L.Map | null>(null);

  const handleMarkerClick = useCallback(
    (disaster: Disaster) => {
      onDisasterSelect?.(disaster.id);
      if (mapRef.current) {
        mapRef.current.setView(
          [disaster.location.lat, disaster.location.lng],
          8
        );
      }
    },
    [onDisasterSelect]
  );

  return (
    <div
      data-testid="geo-map"
      className={`relative h-full w-full min-h-[400px] ${className}`}
    >
      <MapContainer
        ref={mapRef}
        center={INDIA_CENTER}
        zoom={INDIA_ZOOM}
        className="h-full w-full rounded-lg"
        scrollWheelZoom={true}
      >
        <TileLayer url={OSM_TILE_URL} attribution={OSM_ATTRIBUTION} />

        {disasters.map((disaster) => (
          <Marker
            key={disaster.id}
            position={[disaster.location.lat, disaster.location.lng]}
            icon={createMarkerIcon(disaster.severity)}
            eventHandlers={{
              click: () => handleMarkerClick(disaster),
            }}
          >
            <Popup>
              <div className="text-sm text-gray-900">
                <p className="font-bold">{disaster.title}</p>
                <p>Type: {disaster.type}</p>
                <p>Severity: {disaster.severity}</p>
                <p>Phase: {disaster.phase}</p>
                <p>
                  Location: {disaster.location.name}, {disaster.location.state}
                </p>
                {disaster.affected_population && (
                  <p>
                    Affected: {disaster.affected_population.toLocaleString()}
                  </p>
                )}
              </div>
            </Popup>
          </Marker>
        ))}

        {floodZones && (
          <GeoJSON
            data={floodZones}
            style={(feature) => {
              const severity = feature?.properties?.severity as
                | Severity
                | undefined;
              const color = severity
                ? severityColor(severity)
                : SEVERITY_COLORS.medium;
              return {
                fillColor: color,
                fillOpacity: 0.25,
                color: color,
                weight: 2,
              };
            }}
          />
        )}
      </MapContainer>
    </div>
  );
}
