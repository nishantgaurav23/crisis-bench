"use client";

import React, { useEffect, useState } from "react";
import { getScenarios, getEvaluationRuns } from "@/lib/api";
import type { ScenarioSummary, EvaluationRunSummary } from "@/types";

const CATEGORY_COLORS: Record<string, string> = {
  cyclone: "text-red-400 border-red-800",
  flood: "text-blue-400 border-blue-800",
  earthquake: "text-orange-400 border-orange-800",
  heatwave: "text-yellow-400 border-yellow-800",
  landslide: "text-amber-400 border-amber-800",
  drought: "text-pink-400 border-pink-800",
  industrial: "text-gray-400 border-gray-600",
};

const COMPLEXITY_COLORS: Record<string, string> = {
  low: "text-green-400",
  medium: "text-yellow-400",
  high: "text-red-400",
};

interface ScenarioReplayProps {
  className?: string;
  onRunSelect?: (run: EvaluationRunSummary) => void;
}

export default function ScenarioReplay({ className, onRunSelect }: ScenarioReplayProps) {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [runs, setRuns] = useState<EvaluationRunSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getScenarios()
      .then(setScenarios)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setRuns([]);
      return;
    }
    getEvaluationRuns(selectedId)
      .then(setRuns)
      .catch(() => setRuns([]));
  }, [selectedId]);

  const selected = scenarios.find((s) => s.id === selectedId);

  return (
    <div data-testid="scenario-replay" className={`space-y-4 ${className ?? ""}`}>
      <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
        <h3 className="mb-3 text-sm font-medium text-gray-400">Benchmark Scenarios</h3>

        {error && (
          <p className="mb-2 text-xs text-red-400">API unavailable: {error}</p>
        )}

        <select
          data-testid="scenario-select"
          className="w-full rounded border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-white"
          value={selectedId ?? ""}
          onChange={(e) => setSelectedId(e.target.value || null)}
        >
          <option value="">Select a scenario...</option>
          {scenarios.map((s) => (
            <option key={s.id} value={s.id}>
              {s.category} — {s.complexity} ({s.affected_states.join(", ")})
            </option>
          ))}
        </select>

        {loading && <p className="mt-2 text-xs text-gray-500">Loading scenarios...</p>}
      </div>

      {selected && (
        <div
          data-testid="scenario-detail"
          className="rounded-lg border border-gray-700 bg-gray-800 p-4"
        >
          <div className="mb-2 flex items-center gap-2">
            <span
              className={`rounded border px-2 py-0.5 text-xs ${
                CATEGORY_COLORS[selected.category] ?? "text-gray-400 border-gray-600"
              }`}
            >
              {selected.category}
            </span>
            <span className={`text-xs ${COMPLEXITY_COLORS[selected.complexity] ?? ""}`}>
              {selected.complexity}
            </span>
            <span className="text-xs text-gray-500">{selected.source}</span>
          </div>

          <p className="text-sm text-gray-300">
            States: {selected.affected_states.join(", ")}
          </p>
          <p className="text-xs text-gray-500">
            {selected.event_count} events
          </p>

          {runs.length > 0 && (
            <div className="mt-3 space-y-2">
              <h4 className="text-xs font-medium text-gray-400">Evaluation Runs</h4>
              {runs.map((run) => (
                <div
                  key={run.id}
                  data-testid={`run-${run.id}`}
                  className="flex cursor-pointer items-center justify-between rounded bg-gray-900 px-3 py-2 text-sm transition-colors hover:bg-gray-700"
                  onClick={() => onRunSelect?.(run)}
                >
                  <span className="text-white">
                    DRS: {run.aggregate_drs?.toFixed(2) ?? "—"}
                  </span>
                  <span className="text-xs text-gray-500">
                    {run.total_cost_usd !== null ? `$${run.total_cost_usd.toFixed(2)}` : "—"}
                    {" · "}
                    {run.duration_seconds !== null ? `${run.duration_seconds.toFixed(1)}s` : "—"}
                  </span>
                </div>
              ))}
            </div>
          )}

          {runs.length === 0 && (
            <p className="mt-3 text-xs text-gray-500">No evaluation runs yet</p>
          )}
        </div>
      )}
    </div>
  );
}
