"use client";

import React from "react";
import type { AgentCard, AgentStatus } from "@/types";

export const STATUS_COLORS: Record<AgentStatus, string> = {
  active: "bg-green-500",
  processing: "bg-blue-500",
  idle: "bg-gray-500",
  error: "bg-red-500",
  offline: "bg-gray-700",
};

export const TIER_STYLES: Record<string, { text: string; border: string; label: string }> = {
  critical: { text: "text-red-400", border: "border-red-800", label: "Critical" },
  standard: { text: "text-yellow-400", border: "border-yellow-800", label: "Standard" },
  routine: { text: "text-green-400", border: "border-green-800", label: "Routine" },
  vision: { text: "text-purple-400", border: "border-purple-800", label: "Vision" },
};

export const MOCK_AGENTS: AgentCard[] = [
  {
    agent_type: "orchestrator",
    name: "Orchestrator",
    status: "active",
    capabilities: ["mission decomposition", "agent activation", "synthesis", "budget management"],
    llm_tier: "critical",
    last_active: new Date().toISOString(),
  },
  {
    agent_type: "situation_sense",
    name: "Situation Sense",
    status: "processing",
    capabilities: ["multi-source fusion", "GeoJSON updates", "urgency scoring"],
    llm_tier: "routine",
    last_active: new Date(Date.now() - 120000).toISOString(),
  },
  {
    agent_type: "predictive_risk",
    name: "Predictive Risk",
    status: "processing",
    capabilities: ["forecasting", "cascading failures", "risk maps", "historical analogies"],
    llm_tier: "standard",
    last_active: new Date(Date.now() - 60000).toISOString(),
  },
  {
    agent_type: "resource_allocation",
    name: "Resource Allocation",
    status: "idle",
    capabilities: ["OR-Tools optimization", "NDRF/SDRF deployment", "shelter matching"],
    llm_tier: "standard",
  },
  {
    agent_type: "community_comms",
    name: "Community Comms",
    status: "idle",
    capabilities: ["multilingual alerts", "channel formatting", "misinformation countering"],
    llm_tier: "routine",
  },
  {
    agent_type: "infra_status",
    name: "Infra Status",
    status: "idle",
    capabilities: [
      "infrastructure tracking",
      "cascading failure prediction",
      "restoration timelines",
    ],
    llm_tier: "routine",
  },
  {
    agent_type: "historical_memory",
    name: "Historical Memory",
    status: "idle",
    capabilities: ["RAG over NDMA docs", "historical retrieval", "post-event learning"],
    llm_tier: "standard",
  },
];

interface AgentFlowProps {
  agents?: AgentCard[];
  onAgentClick?: (agent: AgentCard) => void;
  className?: string;
}

function AgentCardComponent({
  agent,
  onClick,
}: {
  agent: AgentCard;
  onClick?: (agent: AgentCard) => void;
}) {
  const tierStyle = TIER_STYLES[agent.llm_tier] || TIER_STYLES.routine;

  return (
    <div
      data-testid={`agent-card-${agent.agent_type}`}
      className="cursor-pointer rounded-lg border border-gray-700 bg-gray-800 p-4 transition-colors hover:border-gray-600"
      onClick={() => onClick?.(agent)}
    >
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            data-testid={`status-dot-${agent.agent_type}`}
            className={`h-2.5 w-2.5 rounded-full ${STATUS_COLORS[agent.status]}`}
          />
          <span className="text-sm font-medium text-white">{agent.name}</span>
        </div>
        <span
          data-testid={`tier-badge-${agent.agent_type}`}
          className={`rounded border px-1.5 py-0.5 text-xs ${tierStyle.text} ${tierStyle.border}`}
        >
          {tierStyle.label}
        </span>
      </div>
      <div className="flex flex-wrap gap-1">
        {agent.capabilities.map((cap) => (
          <span
            key={cap}
            className="rounded bg-gray-700 px-1.5 py-0.5 text-xs text-gray-400"
          >
            {cap}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function AgentFlow({ agents, onAgentClick, className }: AgentFlowProps) {
  const agentList = agents ?? MOCK_AGENTS;
  const orchestrator = agentList.find((a) => a.agent_type === "orchestrator");
  const specialists = agentList.filter((a) => a.agent_type !== "orchestrator");

  return (
    <div data-testid="agent-flow" className={`relative space-y-6 ${className ?? ""}`}>
      {/* SVG connection lines */}
      <svg
        data-testid="connection-lines"
        className="pointer-events-none absolute inset-0 h-full w-full"
        style={{ zIndex: 0 }}
      >
        {/* Lines are purely visual — rendered as a background layer */}
        {specialists.map((_, i) => {
          const isActive =
            specialists[i]?.status === "active" || specialists[i]?.status === "processing";
          return (
            <line
              key={i}
              x1="50%"
              y1="80"
              x2={`${((i + 1) / (specialists.length + 1)) * 100}%`}
              y2="160"
              stroke={isActive ? "#3b82f6" : "#374151"}
              strokeWidth="1.5"
              strokeDasharray={isActive ? "6 3" : "4 4"}
              opacity={0.6}
            />
          );
        })}
      </svg>

      {/* Orchestrator section */}
      <div data-testid="orchestrator-section" className="relative z-10 flex justify-center">
        {orchestrator && (
          <div className="w-full max-w-sm">
            <AgentCardComponent agent={orchestrator} onClick={onAgentClick} />
          </div>
        )}
      </div>

      {/* Specialists section */}
      <div
        data-testid="specialists-section"
        className="relative z-10 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3"
      >
        {specialists.map((agent) => (
          <AgentCardComponent key={agent.agent_type} agent={agent} onClick={onAgentClick} />
        ))}
      </div>
    </div>
  );
}
