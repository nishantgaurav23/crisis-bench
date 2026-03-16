"use client";

import React, { useEffect, useState, useCallback } from "react";
import { getScenarios, getEvaluationRuns, runBenchmark } from "@/lib/api";
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

const COMPLEXITY_BADGE: Record<string, string> = {
  low: "bg-green-900 text-green-300",
  medium: "bg-yellow-900 text-yellow-300",
  high: "bg-red-900 text-red-300",
};

interface ScenarioReplayProps {
  className?: string;
  onRunSelect?: (run: EvaluationRunSummary) => void;
}

export default function ScenarioReplay({ className, onRunSelect }: ScenarioReplayProps) {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [runs, setRuns] = useState<EvaluationRunSummary[]>([]);
  const [filterCategory, setFilterCategory] = useState<string>("");
  const [filterComplexity, setFilterComplexity] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [runMessage, setRunMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getScenarios()
      .then(setScenarios)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const refreshRuns = useCallback((scenarioId: string) => {
    getEvaluationRuns(scenarioId)
      .then(setRuns)
      .catch(() => setRuns([]));
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setRuns([]);
      return;
    }
    refreshRuns(selectedId);
  }, [selectedId, refreshRuns]);

  const categories = [...new Set(scenarios.map((s) => s.category))].sort();
  const filtered = scenarios.filter((s) => {
    if (filterCategory && s.category !== filterCategory) return false;
    if (filterComplexity && s.complexity !== filterComplexity) return false;
    return true;
  });
  const selected = scenarios.find((s) => s.id === selectedId);

  const handleRunBenchmark = async () => {
    if (!selectedId) return;
    setRunning(true);
    setRunMessage(null);
    try {
      const result = await runBenchmark(selectedId);
      setRunMessage(result.message);
      // Poll for completion
      const pollInterval = setInterval(() => {
        refreshRuns(selectedId);
      }, 3000);
      // Stop polling after 2 minutes
      setTimeout(() => {
        clearInterval(pollInterval);
        setRunning(false);
        refreshRuns(selectedId);
      }, 120000);
      // Also check frequently at first
      setTimeout(() => refreshRuns(selectedId), 5000);
      setTimeout(() => refreshRuns(selectedId), 10000);
      setTimeout(() => refreshRuns(selectedId), 20000);
      setTimeout(() => {
        refreshRuns(selectedId);
        setRunning(false);
      }, 40000);
    } catch (err) {
      setRunMessage((err as Error).message);
      setRunning(false);
    }
  };

  return (
    <div data-testid="scenario-replay" className={`space-y-4 ${className ?? ""}`}>
      <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
        <h3 className="mb-3 text-sm font-medium text-gray-400">
          Benchmark Scenarios ({filtered.length}/{scenarios.length})
        </h3>

        {error && (
          <p className="mb-2 text-xs text-red-400">API unavailable: {error}</p>
        )}

        {/* Filters */}
        <div className="mb-2 flex gap-2">
          <select
            className="flex-1 rounded border border-gray-600 bg-gray-900 px-2 py-1 text-xs text-white"
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
          >
            <option value="">All categories</option>
            {categories.map((c) => (
              <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
            ))}
          </select>
          <select
            className="flex-1 rounded border border-gray-600 bg-gray-900 px-2 py-1 text-xs text-white"
            value={filterComplexity}
            onChange={(e) => setFilterComplexity(e.target.value)}
          >
            <option value="">All complexity</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </div>

        <select
          data-testid="scenario-select"
          className="w-full rounded border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-white"
          value={selectedId ?? ""}
          onChange={(e) => {
            setSelectedId(e.target.value || null);
            setRunMessage(null);
          }}
        >
          <option value="">Select a scenario...</option>
          {filtered.map((s) => (
            <option key={s.id} value={s.id}>
              {s.title || `${s.category} — ${s.complexity}`} ({s.affected_states.join(", ")})
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
          <h4 className="mb-2 text-sm font-medium text-white">
            {selected.title || selected.category}
          </h4>

          <div className="mb-3 flex items-center gap-2">
            <span
              className={`rounded border px-2 py-0.5 text-xs ${
                CATEGORY_COLORS[selected.category] ?? "text-gray-400 border-gray-600"
              }`}
            >
              {selected.category}
            </span>
            <span
              className={`rounded px-2 py-0.5 text-xs ${
                COMPLEXITY_BADGE[selected.complexity] ?? "bg-gray-800 text-gray-400"
              }`}
            >
              {selected.complexity}
            </span>
            <span className="text-xs text-gray-500">{selected.source}</span>
          </div>

          {selected.description && (
            <p className="mb-3 text-xs text-gray-400">{selected.description}</p>
          )}

          <div className="mb-3 flex items-center gap-4 text-xs text-gray-500">
            <span>States: {selected.affected_states.join(", ")}</span>
            <span>{selected.event_count} events</span>
          </div>

          {/* Run Benchmark Button */}
          <button
            data-testid="run-benchmark-btn"
            onClick={handleRunBenchmark}
            disabled={running}
            className={`w-full rounded px-4 py-2 text-sm font-medium transition-colors ${
              running
                ? "cursor-not-allowed bg-gray-700 text-gray-400"
                : "bg-blue-600 text-white hover:bg-blue-500"
            }`}
          >
            {running ? "Running Benchmark..." : "Run Benchmark"}
          </button>

          {runMessage && (
            <p className="mt-2 text-xs text-blue-400">{runMessage}</p>
          )}

          {/* Evaluation Runs */}
          {runs.length > 0 && (
            <div className="mt-4 space-y-2">
              <h4 className="text-xs font-medium text-gray-400">
                Evaluation Runs ({runs.length})
              </h4>
              {runs.map((run) => (
                <div
                  key={run.id}
                  data-testid={`run-${run.id}`}
                  className="flex cursor-pointer items-center justify-between rounded border border-gray-700 bg-gray-900 px-3 py-2 text-sm transition-colors hover:border-gray-500"
                  onClick={() => onRunSelect?.(run)}
                >
                  <div>
                    <span className="font-medium text-white">
                      DRS: {run.aggregate_drs?.toFixed(3) ?? "—"}
                    </span>
                    <div className="mt-0.5 flex gap-2 text-xs text-gray-500">
                      <span>SA: {run.situational_accuracy?.toFixed(2) ?? "—"}</span>
                      <span>DT: {run.decision_timeliness?.toFixed(2) ?? "—"}</span>
                      <span>RE: {run.resource_efficiency?.toFixed(2) ?? "—"}</span>
                      <span>CQ: {run.coordination_quality?.toFixed(2) ?? "—"}</span>
                      <span>CS: {run.communication_score?.toFixed(2) ?? "—"}</span>
                    </div>
                  </div>
                  <div className="text-right text-xs text-gray-500">
                    <div>
                      {run.total_cost_usd !== null ? `$${run.total_cost_usd.toFixed(4)}` : "—"}
                    </div>
                    <div>
                      {run.duration_seconds !== null ? `${run.duration_seconds.toFixed(1)}s` : "—"}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {runs.length === 0 && !running && (
            <p className="mt-3 text-center text-xs text-gray-500">
              No evaluation runs yet — click &quot;Run Benchmark&quot; to start
            </p>
          )}
        </div>
      )}
    </div>
  );
}
