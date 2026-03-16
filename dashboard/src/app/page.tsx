"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import DashboardShell from "@/components/DashboardShell";
import AgentFlow from "@/components/AgentFlow";
import MetricsPanel from "@/components/MetricsPanel";
import Timeline from "@/components/Timeline";
import ScenarioReplay from "@/components/ScenarioReplay";
import EvaluationDetail from "@/components/EvaluationDetail";
import useCrisisWebSocket from "@/hooks/useCrisisWebSocket";
import { getHealth, getDisasters, getAgents, getMetricsSummary } from "@/lib/api";
import type {
  HealthStatus,
  AgentCard,
  EvaluationRunSummary,
  MetricsSummary,
} from "@/types";

// GeoMap uses Leaflet which requires dynamic import (no SSR)
const GeoMap = dynamic(() => import("@/components/GeoMap"), { ssr: false });

export default function Home() {
  const ws = useCrisisWebSocket();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [agents, setAgents] = useState<AgentCard[]>([]);
  const [selectedRun, setSelectedRun] = useState<EvaluationRunSummary | null>(null);

  // Fetch initial data on mount
  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch((err) => setError(err.message));

    getDisasters()
      .then(ws.setDisasters)
      .catch(() => {});

    getAgents()
      .then(setAgents)
      .catch(() => {});

    getMetricsSummary()
      .then(ws.setMetrics)
      .catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Merge agent WebSocket updates into agent list
  const mergedAgents: AgentCard[] = agents.map((a) => {
    const update = ws.agents.get(a.agent_type);
    if (update) {
      return { ...a, ...update } as AgentCard;
    }
    return a;
  });

  // Merge WebSocket metrics into initial metrics
  const currentMetrics: MetricsSummary | undefined = ws.metrics ?? undefined;

  return (
    <DashboardShell isConnected={ws.isConnected}>
      <div className="space-y-6">
        <h1 className="text-2xl font-bold" data-testid="page-title">
          CRISIS-BENCH Dashboard
        </h1>

        {error && (
          <div
            className="rounded-lg border border-red-800 bg-red-950 p-4 text-sm text-red-300"
            data-testid="error-message"
          >
            API unavailable: {error}
          </div>
        )}

        {health && (
          <div
            className="rounded-lg border border-gray-800 bg-gray-900 p-4"
            data-testid="health-status"
          >
            <h2 className="mb-2 text-sm font-medium text-gray-400">
              System Health
            </h2>
            <p className="text-sm">
              Status:{" "}
              <span
                className={
                  health.status === "healthy"
                    ? "text-green-400"
                    : "text-yellow-400"
                }
              >
                {health.status}
              </span>
            </p>
            <p className="text-xs text-gray-500">Version: {health.version}</p>
          </div>
        )}

        {/* Map + Agents Row */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="rounded-lg border border-gray-700 bg-gray-800 p-2">
            <h2 className="mb-2 px-2 text-sm font-medium text-gray-400">
              Disaster Map
            </h2>
            <div className="h-[400px]">
              <GeoMap disasters={ws.disasters} />
            </div>
          </div>

          <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
            <h2 className="mb-2 text-sm font-medium text-gray-400">
              Agent Status
            </h2>
            <AgentFlow agents={mergedAgents} />
          </div>
        </div>

        {/* Metrics + Timeline Row */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div>
            <h2 className="mb-2 text-sm font-medium text-gray-400">
              LLM Metrics
            </h2>
            <MetricsPanel metrics={currentMetrics} />
          </div>

          <div>
            <h2 className="mb-2 text-sm font-medium text-gray-400">
              Event Timeline
            </h2>
            <Timeline
              events={ws.timelineEvents.length > 0 ? ws.timelineEvents : undefined}
            />
          </div>
        </div>

        {/* Benchmark Section */}
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
