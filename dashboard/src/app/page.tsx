"use client";

import { useEffect, useState } from "react";
import DashboardShell from "@/components/DashboardShell";
import { CrisisWebSocketClient } from "@/lib/websocket";
import { getHealth } from "@/lib/api";
import type { HealthStatus } from "@/types";

export default function Home() {
  const [isConnected, setIsConnected] = useState(false);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ws = new CrisisWebSocketClient();

    const unsubConnect = ws.onConnect(() => setIsConnected(true));
    const unsubDisconnect = ws.onDisconnect(() => setIsConnected(false));

    ws.connect();

    getHealth()
      .then(setHealth)
      .catch((err) => setError(err.message));

    return () => {
      unsubConnect();
      unsubDisconnect();
      ws.disconnect();
    };
  }, []);

  return (
    <DashboardShell isConnected={isConnected}>
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

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          {["Map", "Agents", "Metrics", "Timeline"].map((section) => (
            <div
              key={section}
              className="flex h-48 items-center justify-center rounded-lg border border-dashed border-gray-700 text-gray-500"
            >
              {section} — Coming Soon
            </div>
          ))}
        </div>
      </div>
    </DashboardShell>
  );
}
