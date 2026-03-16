"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import DashboardShell from "@/components/DashboardShell";
import ScenarioReplay from "@/components/ScenarioReplay";
import EvaluationDetail from "@/components/EvaluationDetail";
import useCrisisWebSocket from "@/hooks/useCrisisWebSocket";
import { getHealth, getDisasters } from "@/lib/api";
import type {
  HealthStatus,
  EvaluationRunSummary,
} from "@/types";

// GeoMap uses Leaflet which requires dynamic import (no SSR)
const GeoMap = dynamic(() => import("@/components/GeoMap"), { ssr: false });

export default function Home() {
  const ws = useCrisisWebSocket();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<EvaluationRunSummary | null>(null);

  // Fetch initial data on mount
  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch((err) => setError(err.message));

    getDisasters()
      .then(ws.setDisasters)
      .catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <DashboardShell isConnected={ws.isConnected}>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold" data-testid="page-title">
            CRISIS-BENCH
          </h1>
          {health && (
            <span
              data-testid="health-status"
              className={`rounded-full px-3 py-1 text-xs ${
                health.status === "healthy"
                  ? "bg-green-900 text-green-300"
                  : "bg-yellow-900 text-yellow-300"
              }`}
            >
              {health.status} &middot; v{health.version}
            </span>
          )}
        </div>

        {error && (
          <div
            className="rounded-lg border border-red-800 bg-red-950 p-3 text-sm text-red-300"
            data-testid="error-message"
          >
            API unavailable: {error}
          </div>
        )}

        {/* Map — full width */}
        <div className="rounded-lg border border-gray-700 bg-gray-800 p-2">
          <h2 className="mb-2 px-2 text-sm font-medium text-gray-400">
            Disaster Map — India
          </h2>
          <div className="h-[350px]">
            <GeoMap disasters={ws.disasters} />
          </div>
        </div>

        {/* Benchmark + Evaluation — side by side */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div>
            <h2 className="mb-2 text-sm font-medium text-gray-400">
              Benchmark Scenarios
            </h2>
            <ScenarioReplay onRunSelect={setSelectedRun} />
          </div>

          <div>
            <h2 className="mb-2 text-sm font-medium text-gray-400">
              Evaluation Results
            </h2>
            <EvaluationDetail
              run={selectedRun}
              onClose={() => setSelectedRun(null)}
            />
            {!selectedRun && (
              <div className="flex h-48 items-center justify-center rounded-lg border border-dashed border-gray-700 text-sm text-gray-500">
                Select a benchmark run to view evaluation details
              </div>
            )}
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
