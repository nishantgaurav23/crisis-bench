"use client";

import React from "react";
import type { EvaluationRunSummary } from "@/types";

const DIMENSIONS: {
  key: keyof EvaluationRunSummary;
  label: string;
  abbr: string;
  color: string;
  barColor: string;
  description: string;
}[] = [
  {
    key: "situational_accuracy",
    label: "Situational Accuracy",
    abbr: "SA",
    color: "text-blue-400",
    barColor: "bg-blue-500",
    description: "Correctness and completeness of disaster assessment",
  },
  {
    key: "decision_timeliness",
    label: "Decision Timeliness",
    abbr: "DT",
    color: "text-green-400",
    barColor: "bg-green-500",
    description: "Decisions made within NDMA SOP time windows",
  },
  {
    key: "resource_efficiency",
    label: "Resource Efficiency",
    abbr: "RE",
    color: "text-yellow-400",
    barColor: "bg-yellow-500",
    description: "Optimality of NDRF/SDRF deployment and resource allocation",
  },
  {
    key: "coordination_quality",
    label: "Coordination Quality",
    abbr: "CQ",
    color: "text-purple-400",
    barColor: "bg-purple-500",
    description: "Inter-agency information sharing and coordination",
  },
  {
    key: "communication_score",
    label: "Communication",
    abbr: "CS",
    color: "text-pink-400",
    barColor: "bg-pink-500",
    description: "Clarity, multilingual quality, and actionability of alerts",
  },
];

const RATING_TABLE = [
  { range: "0.85 – 1.00", rating: "Excellent", color: "text-green-400", description: "Near-optimal disaster response" },
  { range: "0.70 – 0.84", rating: "Good", color: "text-blue-400", description: "Adequate response, minor gaps" },
  { range: "0.55 – 0.69", rating: "Fair", color: "text-yellow-400", description: "Significant improvement needed" },
  { range: "0.00 – 0.54", rating: "Poor", color: "text-red-400", description: "Major gaps in response" },
];

function getDrsRating(drs: number): { rating: string; color: string } {
  if (drs >= 0.85) return { rating: "Excellent", color: "text-green-400" };
  if (drs >= 0.70) return { rating: "Good", color: "text-blue-400" };
  if (drs >= 0.55) return { rating: "Fair", color: "text-yellow-400" };
  return { rating: "Poor", color: "text-red-400" };
}

function getScoreColor(score: number): string {
  if (score >= 0.85) return "text-green-400";
  if (score >= 0.70) return "text-blue-400";
  if (score >= 0.55) return "text-yellow-400";
  return "text-red-400";
}

function getScoreLabel(score: number): string {
  if (score >= 0.85) return "Strong";
  if (score >= 0.70) return "Good";
  if (score >= 0.55) return "Weak";
  return "Poor";
}

function generateSummary(run: EvaluationRunSummary): string {
  const drs = run.aggregate_drs ?? 0;
  const sa = run.situational_accuracy ?? 0;
  const dt = run.decision_timeliness ?? 0;
  const re = run.resource_efficiency ?? 0;
  const cq = run.coordination_quality ?? 0;
  const cs = run.communication_score ?? 0;

  const scores = [
    { name: "Situational Accuracy", value: sa },
    { name: "Decision Timeliness", value: dt },
    { name: "Resource Efficiency", value: re },
    { name: "Coordination Quality", value: cq },
    { name: "Communication", value: cs },
  ];

  const strongest = scores.reduce((a, b) => (b.value > a.value ? b : a));
  const weakest = scores.reduce((a, b) => (b.value < a.value ? b : a));

  let overall: string;
  if (drs >= 0.85) {
    overall =
      "The agent system delivered a near-optimal disaster response. " +
      "All dimensions scored well, indicating the agents correctly assessed the situation, " +
      "made timely decisions, allocated resources efficiently, coordinated across agencies, " +
      "and communicated clearly with affected communities.";
  } else if (drs >= 0.70) {
    overall =
      "The agent system produced an adequate disaster response with some areas for improvement. " +
      "Core assessment and decision-making were sound, but certain dimensions show gaps that " +
      "could delay real-world response effectiveness.";
  } else if (drs >= 0.55) {
    overall =
      "The agent system showed significant weaknesses in disaster response. " +
      "While some dimensions performed acceptably, the overall coordination falls below " +
      "the threshold for reliable crisis management. Key gaps need to be addressed.";
  } else {
    overall =
      "The agent system failed to produce an adequate disaster response. " +
      "Multiple dimensions scored poorly, indicating fundamental issues with situation " +
      "assessment, decision-making, or inter-agent coordination that must be resolved.";
  }

  const strengthText =
    strongest.value >= 0.70
      ? `Strongest area: ${strongest.name} (${strongest.value.toFixed(2)}) — ` +
        "agents performed well in this dimension."
      : `Relatively strongest area: ${strongest.name} (${strongest.value.toFixed(2)}), ` +
        "though still below optimal.";

  const weaknessText =
    weakest.value < 0.60
      ? `Key weakness: ${weakest.name} (${weakest.value.toFixed(2)}) — ` +
        "this is the primary area dragging down the overall score and should be " +
        "the focus of improvement."
      : `Improvement opportunity: ${weakest.name} (${weakest.value.toFixed(2)}) — ` +
        "while acceptable, improving this dimension would most impact the overall DRS.";

  return `${overall}\n\n${strengthText}\n\n${weaknessText}`;
}

const IMPROVEMENT_TIPS: Record<string, string[]> = {
  situational_accuracy: [
    "Integrate more real-time data sources (IMD, SACHET, CWC) for ground-truth verification",
    "Cross-validate disaster severity across multiple agencies before reporting",
    "Add satellite imagery analysis (Bhuvan/FIRMS) for spatial accuracy",
    "Implement confidence scoring so agents flag uncertain assessments",
  ],
  decision_timeliness: [
    "Pre-compute response plans for recurring disaster patterns (monsoon floods, cyclones)",
    "Use plan caching to adapt past successful responses instead of generating from scratch",
    "Set hard SOP-based deadlines: evacuation orders within 30 min of red alert",
    "Parallelize agent processing — run SituationSense and InfraStatus concurrently",
  ],
  resource_efficiency: [
    "Use OR-Tools optimization for NDRF battalion allocation instead of heuristic placement",
    "Factor in road damage and actual travel times, not straight-line distances",
    "Model shelter capacity constraints to avoid over-allocation to full shelters",
    "Include neighboring district mutual aid resources in the optimization model",
  ],
  coordination_quality: [
    "Ensure all agents share a common situation picture before making independent decisions",
    "Add explicit hand-off protocols: SituationSense → PredictiveRisk → ResourceAllocation",
    "Implement a shared context window so downstream agents see upstream reasoning",
    "Reduce redundant assessments — orchestrator should deduplicate overlapping agent scopes",
  ],
  communication_score: [
    "Generate alerts in all regional languages spoken in affected districts",
    "Include specific actionable instructions (evacuation routes, shelter locations, helplines)",
    "Tailor message complexity: simple SMS for rural areas, detailed advisories for officials",
    "Add misinformation countering — proactively address likely rumours for the disaster type",
  ],
};

function getImprovements(run: EvaluationRunSummary): { dimension: string; tips: string[] }[] {
  const dims: { key: string; label: string; value: number }[] = [
    { key: "situational_accuracy", label: "Situational Accuracy", value: run.situational_accuracy ?? 0 },
    { key: "decision_timeliness", label: "Decision Timeliness", value: run.decision_timeliness ?? 0 },
    { key: "resource_efficiency", label: "Resource Efficiency", value: run.resource_efficiency ?? 0 },
    { key: "coordination_quality", label: "Coordination Quality", value: run.coordination_quality ?? 0 },
    { key: "communication_score", label: "Communication", value: run.communication_score ?? 0 },
  ];

  // Sort by score ascending — worst first
  const sorted = [...dims].sort((a, b) => a.value - b.value);

  // Return top 2-3 weakest dimensions that are below 0.80
  const weak = sorted.filter((d) => d.value < 0.80).slice(0, 3);
  if (weak.length === 0) {
    // Everything is strong — return the single lowest for marginal improvement
    weak.push(sorted[0]);
  }

  return weak.map((d) => ({
    dimension: `${d.label} (${d.value.toFixed(2)})`,
    tips: IMPROVEMENT_TIPS[d.key] ?? [],
  }));
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

  const drs = run.aggregate_drs ?? 0;
  const { rating, color } = getDrsRating(drs);

  return (
    <div
      data-testid="evaluation-detail"
      className={`space-y-4 ${className ?? ""}`}
    >
      {/* Header + Close */}
      <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-400">Evaluation Results</h3>
          {onClose && (
            <button
              onClick={onClose}
              className="rounded px-2 py-0.5 text-xs text-gray-500 hover:bg-gray-700 hover:text-white"
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
            className={`text-4xl font-bold ${color}`}
          >
            {drs.toFixed(3)}
          </p>
          <p className={`text-sm font-medium ${color}`}>{rating}</p>
          <p className="mt-1 text-xs text-gray-500">
            Weighted average of 5 evaluation dimensions
          </p>
        </div>

        {/* Plain-English Summary */}
        <div className="mb-4 rounded border border-gray-700 bg-gray-900 p-3">
          <h4 className="mb-1.5 text-xs font-medium text-gray-400">Summary</h4>
          {generateSummary(run).split("\n\n").map((para, i) => (
            <p key={i} className="mb-1.5 text-xs leading-relaxed text-gray-300 last:mb-0">
              {para}
            </p>
          ))}
        </div>

        {/* Dimension Scores Table */}
        <div className="overflow-hidden rounded border border-gray-700">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-700 bg-gray-900">
                <th className="px-3 py-2 text-left text-gray-400">Dimension</th>
                <th className="px-3 py-2 text-center text-gray-400">Score</th>
                <th className="px-3 py-2 text-center text-gray-400">Rating</th>
                <th className="hidden px-3 py-2 text-left text-gray-400 sm:table-cell">Bar</th>
              </tr>
            </thead>
            <tbody>
              {DIMENSIONS.map((dim) => {
                const value = (run[dim.key] as number | null) ?? 0;
                const pct = Math.round(value * 100);
                return (
                  <tr
                    key={dim.key}
                    data-testid={`dimension-${dim.key}`}
                    className="border-b border-gray-800"
                  >
                    <td className="px-3 py-2">
                      <span className={`font-medium ${dim.color}`}>
                        {dim.abbr}
                      </span>
                      <span className="ml-1.5 text-gray-300">{dim.label}</span>
                      <p className="mt-0.5 text-gray-600">{dim.description}</p>
                    </td>
                    <td className="px-3 py-2 text-center">
                      <span className={`font-mono font-bold ${getScoreColor(value)}`}>
                        {value.toFixed(2)}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-center">
                      <span className={`text-xs ${getScoreColor(value)}`}>
                        {getScoreLabel(value)}
                      </span>
                    </td>
                    <td className="hidden px-3 py-2 sm:table-cell">
                      <div className="h-2 w-full min-w-[60px] rounded-full bg-gray-700">
                        <div
                          className={`h-2 rounded-full ${dim.barColor}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Run Metadata */}
        <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
          <div className="text-gray-500">
            Provider: <span className="text-gray-300">{run.primary_provider ?? "—"}</span>
          </div>
          <div className="text-gray-500">
            Tokens: <span className="text-gray-300">{run.total_tokens?.toLocaleString() ?? "—"}</span>
          </div>
          <div className="text-gray-500">
            Cost:{" "}
            <span className="text-gray-300">
              {run.total_cost_usd !== null ? `$${run.total_cost_usd.toFixed(4)}` : "—"}
            </span>
          </div>
          <div className="text-gray-500">
            Duration:{" "}
            <span className="text-gray-300">
              {run.duration_seconds !== null ? `${run.duration_seconds.toFixed(1)}s` : "—"}
            </span>
          </div>
        </div>
      </div>

      {/* DRS Rating Reference Table */}
      <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
        <h4 className="mb-2 text-xs font-medium text-gray-400">
          DRS Rating Reference
        </h4>
        <div className="overflow-hidden rounded border border-gray-700">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-700 bg-gray-900">
                <th className="px-3 py-1.5 text-left text-gray-400">Range</th>
                <th className="px-3 py-1.5 text-left text-gray-400">Rating</th>
                <th className="px-3 py-1.5 text-left text-gray-400">Interpretation</th>
              </tr>
            </thead>
            <tbody>
              {RATING_TABLE.map((row) => (
                <tr
                  key={row.range}
                  className={`border-b border-gray-800 ${
                    rating === row.rating ? "bg-gray-750 bg-opacity-50" : ""
                  }`}
                >
                  <td className="px-3 py-1.5 font-mono text-gray-300">
                    {row.range}
                  </td>
                  <td className={`px-3 py-1.5 font-medium ${row.color}`}>
                    {row.rating}
                    {rating === row.rating && (
                      <span className="ml-1 text-gray-500">&larr;</span>
                    )}
                  </td>
                  <td className="px-3 py-1.5 text-gray-400">
                    {row.description}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Dimension Weight Reference */}
      <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
        <h4 className="mb-2 text-xs font-medium text-gray-400">
          DRS Weight Formula
        </h4>
        <p className="font-mono text-xs text-gray-400">
          DRS = 0.25&times;SA + 0.20&times;DT + 0.20&times;RE + 0.20&times;CQ + 0.15&times;CS
        </p>
        <p className="mt-1 text-xs text-gray-600">
          Situational Accuracy weighted highest (25%) as correct assessment
          drives all downstream decisions. Communication weighted lowest (15%)
          as it depends on other dimensions being correct first.
        </p>
      </div>

      {/* Areas of Improvement */}
      <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
        <h4 className="mb-3 text-xs font-medium text-gray-400">
          Areas of Improvement
        </h4>
        <div className="space-y-4">
          {getImprovements(run).map((item, idx) => (
            <div key={idx}>
              <p className="mb-1.5 text-xs font-medium text-yellow-400">
                {item.dimension}
              </p>
              <ul className="space-y-1">
                {item.tips.map((tip, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-xs text-gray-300"
                  >
                    <span className="mt-0.5 text-gray-600">&bull;</span>
                    <span>{tip}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
