"use client";

import React from "react";
import type { EvaluationRunSummary } from "@/types";

const DIMENSION_LABELS: Record<string, string> = {
  situational_accuracy: "Situational Accuracy",
  decision_timeliness: "Decision Timeliness",
  resource_efficiency: "Resource Efficiency",
  coordination_quality: "Coordination Quality",
  communication_score: "Communication",
};

const DIMENSION_COLORS: Record<string, string> = {
  situational_accuracy: "bg-blue-500",
  decision_timeliness: "bg-green-500",
  resource_efficiency: "bg-yellow-500",
  coordination_quality: "bg-purple-500",
  communication_score: "bg-pink-500",
};

function getDrsColor(drs: number): string {
  if (drs >= 0.8) return "text-green-400";
  if (drs >= 0.6) return "text-yellow-400";
  if (drs >= 0.4) return "text-orange-400";
  return "text-red-400";
}

interface EvaluationDetailProps {
  run: EvaluationRunSummary | null;
  onClose?: () => void;
  className?: string;
}

export default function EvaluationDetail({
  run,
  onClose,
  className,
}: EvaluationDetailProps) {
  if (!run) return null;

  const dimensions = [
    { key: "situational_accuracy", value: run.situational_accuracy },
    { key: "decision_timeliness", value: run.decision_timeliness },
    { key: "resource_efficiency", value: run.resource_efficiency },
    { key: "coordination_quality", value: run.coordination_quality },
    { key: "communication_score", value: run.communication_score },
  ];

  return (
    <div
      data-testid="evaluation-detail"
      className={`rounded-lg border border-gray-700 bg-gray-800 p-4 ${className ?? ""}`}
    >
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-400">Evaluation Results</h3>
        {onClose && (
          <button
            onClick={onClose}
            className="text-xs text-gray-500 hover:text-white"
          >
            Close
          </button>
        )}
      </div>

      {/* Aggregate DRS */}
      <div className="mb-4 text-center">
        <p className="text-xs text-gray-500">Disaster Response Score</p>
        <p
          data-testid="drs-score"
          className={`text-4xl font-bold ${getDrsColor(run.aggregate_drs ?? 0)}`}
        >
          {run.aggregate_drs !== null ? run.aggregate_drs.toFixed(2) : "—"}
        </p>
      </div>

      {/* Dimension Scores — bar chart */}
      <div className="space-y-3">
        {dimensions.map(({ key, value }) => {
          const pct = value !== null ? (value / 5.0) * 100 : 0;
          return (
            <div key={key} data-testid={`dimension-${key}`}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="text-gray-300">{DIMENSION_LABELS[key]}</span>
                <span className="font-mono text-white">
                  {value !== null ? value.toFixed(1) : "—"}/5
                </span>
              </div>
              <div className="h-2 w-full rounded-full bg-gray-700">
                <div
                  className={`h-2 rounded-full ${DIMENSION_COLORS[key]}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Run metadata */}
      <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-gray-500">
        <div>
          Provider: <span className="text-gray-300">{run.primary_provider ?? "—"}</span>
        </div>
        <div>
          Tokens: <span className="text-gray-300">{run.total_tokens?.toLocaleString() ?? "—"}</span>
        </div>
        <div>
          Cost:{" "}
          <span className="text-gray-300">
            {run.total_cost_usd !== null ? `$${run.total_cost_usd.toFixed(2)}` : "—"}
          </span>
        </div>
        <div>
          Duration:{" "}
          <span className="text-gray-300">
            {run.duration_seconds !== null ? `${run.duration_seconds.toFixed(1)}s` : "—"}
          </span>
        </div>
      </div>
    </div>
  );
}
