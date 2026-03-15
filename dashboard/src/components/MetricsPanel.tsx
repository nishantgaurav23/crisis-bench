"use client";

import React from "react";
import type { ProviderMetrics, MetricsSummary } from "@/types";

export const TIER_COLORS: Record<string, { bg: string; text: string }> = {
  critical: { bg: "bg-red-900/30", text: "text-red-400" },
  standard: { bg: "bg-yellow-900/30", text: "text-yellow-400" },
  routine: { bg: "bg-green-900/30", text: "text-green-400" },
  free: { bg: "bg-blue-900/30", text: "text-blue-400" },
};

export function formatTokens(n: number): string {
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${(n / 1000).toFixed(2)}K`;
  return `${(n / 1_000_000).toFixed(2)}M`;
}

export function getBudgetColor(spent: number, budget: number): string {
  const pct = spent / budget;
  if (pct < 0.5) return "text-green-400";
  if (pct < 0.8) return "text-yellow-400";
  return "text-red-400";
}

export function getLatencyColor(ms: number): string {
  if (ms < 1000) return "text-green-400";
  if (ms < 3000) return "text-yellow-400";
  return "text-red-400";
}

export const MOCK_METRICS: MetricsSummary = {
  providers: [
    {
      provider: "DeepSeek Reasoner",
      tier: "critical",
      total_cost: 1.25,
      input_tokens: 450000,
      output_tokens: 120000,
      requests: 85,
      avg_latency_ms: 2800,
      p50_latency_ms: 2500,
      p95_latency_ms: 4200,
      p99_latency_ms: 5800,
    },
    {
      provider: "DeepSeek Chat",
      tier: "standard",
      total_cost: 0.95,
      input_tokens: 680000,
      output_tokens: 210000,
      requests: 142,
      avg_latency_ms: 1200,
      p50_latency_ms: 1000,
      p95_latency_ms: 2100,
      p99_latency_ms: 3200,
    },
    {
      provider: "Qwen Flash",
      tier: "routine",
      total_cost: 0.18,
      input_tokens: 1200000,
      output_tokens: 380000,
      requests: 310,
      avg_latency_ms: 450,
      p50_latency_ms: 380,
      p95_latency_ms: 800,
      p99_latency_ms: 1200,
    },
    {
      provider: "Groq",
      tier: "free",
      total_cost: 0.0,
      input_tokens: 520000,
      output_tokens: 160000,
      requests: 95,
      avg_latency_ms: 350,
      p50_latency_ms: 300,
      p95_latency_ms: 600,
      p99_latency_ms: 900,
    },
    {
      provider: "Ollama",
      tier: "free",
      total_cost: 0.0,
      input_tokens: 180000,
      output_tokens: 45000,
      requests: 40,
      avg_latency_ms: 3500,
      p50_latency_ms: 3200,
      p95_latency_ms: 5000,
      p99_latency_ms: 6500,
    },
  ],
  total_cost: 2.38,
  total_input_tokens: 3030000,
  total_output_tokens: 915000,
  total_requests: 672,
  period_start: "2026-03-01T00:00:00Z",
  period_end: "2026-03-15T00:00:00Z",
};

interface MetricsPanelProps {
  metrics?: MetricsSummary;
  budget?: number;
  className?: string;
  onProviderClick?: (provider: ProviderMetrics) => void;
}

export default function MetricsPanel({
  metrics,
  budget = 8.0,
  className,
  onProviderClick,
}: MetricsPanelProps) {
  const data = metrics ?? MOCK_METRICS;
  const budgetColor = getBudgetColor(data.total_cost, budget);
  const pct = Math.min((data.total_cost / budget) * 100, 100);

  return (
    <div data-testid="metrics-panel" className={`space-y-4 ${className ?? ""}`}>
      {/* Budget Gauge */}
      <div
        data-testid="budget-gauge"
        className="rounded-lg border border-gray-700 bg-gray-800 p-4"
      >
        <h3 className="mb-2 text-sm font-medium text-gray-400">Monthly Budget</h3>
        <div className="flex items-end justify-between">
          <span className={`text-2xl font-bold ${budgetColor}`}>
            ${data.total_cost.toFixed(2)}
          </span>
          <span className="text-sm text-gray-500">/ ${budget.toFixed(2)}</span>
        </div>
        <div className="mt-2 h-2 w-full rounded-full bg-gray-700">
          <div
            data-testid="budget-bar"
            className={`h-2 rounded-full ${
              pct < 50 ? "bg-green-500" : pct < 80 ? "bg-yellow-500" : "bg-red-500"
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <p className="mt-1 text-xs text-gray-500">
          ${(budget - data.total_cost).toFixed(2)} remaining
        </p>
      </div>

      {/* Token Summary */}
      <div
        data-testid="token-summary"
        className="rounded-lg border border-gray-700 bg-gray-800 p-4"
      >
        <h3 className="mb-2 text-sm font-medium text-gray-400">Token Usage</h3>
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-lg font-bold text-white">
              {formatTokens(data.total_input_tokens + data.total_output_tokens)}
            </p>
            <p className="text-xs text-gray-500">Total</p>
          </div>
          <div>
            <p className="text-lg font-bold text-blue-400">
              {formatTokens(data.total_input_tokens)}
            </p>
            <p className="text-xs text-gray-500">Input</p>
          </div>
          <div>
            <p className="text-lg font-bold text-purple-400">
              {formatTokens(data.total_output_tokens)}
            </p>
            <p className="text-xs text-gray-500">Output</p>
          </div>
        </div>
        <p className="mt-2 text-xs text-gray-500">
          {data.total_requests} requests
        </p>
      </div>

      {/* Cost Breakdown */}
      <div
        data-testid="cost-breakdown"
        className="rounded-lg border border-gray-700 bg-gray-800 p-4"
      >
        <h3 className="mb-2 text-sm font-medium text-gray-400">Cost by Provider</h3>
        <div className="space-y-2">
          {data.providers.map((p) => {
            const tierStyle = TIER_COLORS[p.tier] || TIER_COLORS.free;
            return (
              <div
                key={p.provider}
                data-testid={`provider-row-${p.provider}`}
                className={`flex cursor-pointer items-center justify-between rounded px-3 py-2 ${tierStyle.bg} transition-colors hover:brightness-125`}
                onClick={() => onProviderClick?.(p)}
              >
                <div className="flex items-center gap-2">
                  <span className={`text-sm font-medium ${tierStyle.text}`}>
                    {p.provider}
                  </span>
                  <span className="text-xs text-gray-500">
                    {formatTokens(p.input_tokens + p.output_tokens)} tokens
                  </span>
                </div>
                <span className="text-sm font-mono text-white">
                  ${p.total_cost.toFixed(2)}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Latency Section */}
      <div
        data-testid="latency-section"
        className="rounded-lg border border-gray-700 bg-gray-800 p-4"
      >
        <h3 className="mb-2 text-sm font-medium text-gray-400">Latency</h3>
        <div className="space-y-2">
          {data.providers.map((p) => (
            <div
              key={p.provider}
              className="flex items-center justify-between text-sm"
            >
              <span className="text-gray-300">{p.provider}</span>
              <div className="flex gap-3 font-mono text-xs">
                <span
                  data-testid={`latency-avg-${p.provider}`}
                  className={getLatencyColor(p.avg_latency_ms)}
                >
                  {p.avg_latency_ms}ms
                </span>
                <span className="text-gray-500">
                  P95: {p.p95_latency_ms}ms
                </span>
                <span className="text-gray-500">
                  P99: {p.p99_latency_ms}ms
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
