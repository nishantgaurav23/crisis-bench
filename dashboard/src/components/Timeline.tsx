"use client";

import React, { useState, useEffect } from "react";
import type {
  TimelineEvent,
  WebSocketEventType,
  AgentType,
  Severity,
} from "@/types";

export const SEVERITY_COLORS: Record<Severity, string> = {
  critical: "bg-red-500",
  high: "bg-orange-500",
  medium: "bg-yellow-500",
  low: "bg-green-500",
};

const SEVERITY_TEXT: Record<Severity, string> = {
  critical: "text-red-400",
  high: "text-orange-400",
  medium: "text-yellow-400",
  low: "text-green-400",
};

const EVENT_TYPE_LABELS: Record<WebSocketEventType, string> = {
  "disaster.created": "Disaster Created",
  "disaster.updated": "Disaster Updated",
  "agent.status": "Agent Status",
  "agent.decision": "Agent Decision",
  "metrics.update": "Metrics Update",
};

export function formatRelativeTime(isoTimestamp: string): string {
  const now = Date.now();
  const then = new Date(isoTimestamp).getTime();
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

// Fixed timestamps to avoid SSR/client hydration mismatch
// (Date.now() at module load differs between server and client)
export const MOCK_TIMELINE_EVENTS: TimelineEvent[] = [
  {
    id: "evt-001",
    type: "disaster.created",
    title: "Cyclone Vardah Alert",
    description: "IMD issued Red Alert for Odisha coast — Category 4 cyclone expected landfall in 48h",
    severity: "critical",
    timestamp: "2026-03-16T10:00:00Z",
  },
  {
    id: "evt-002",
    type: "agent.status",
    title: "Orchestrator Activated",
    description: "Mission decomposition started for cyclone response",
    severity: "high",
    agent_type: "orchestrator",
    timestamp: "2026-03-16T09:59:30Z",
  },
  {
    id: "evt-003",
    type: "agent.status",
    title: "SituationSense Processing",
    description: "Fusing IMD, SACHET, and social media feeds",
    severity: "medium",
    agent_type: "situation_sense",
    timestamp: "2026-03-16T09:59:00Z",
  },
  {
    id: "evt-004",
    type: "agent.decision",
    title: "Evacuation Order Issued",
    description: "Evacuate 3 coastal districts: Puri, Ganjam, Jagatsinghpur",
    severity: "critical",
    agent_type: "orchestrator",
    phase: "active_response",
    timestamp: "2026-03-16T09:58:00Z",
  },
  {
    id: "evt-005",
    type: "disaster.updated",
    title: "Phase: Alert to Response",
    description: "Disaster phase transitioned from alert to active response",
    severity: "high",
    phase: "active_response",
    timestamp: "2026-03-16T09:57:00Z",
  },
  {
    id: "evt-006",
    type: "agent.decision",
    title: "NDRF Deployment Plan",
    description: "12 battalions allocated across 3 districts via OR-Tools optimization",
    severity: "high",
    agent_type: "resource_allocation",
    timestamp: "2026-03-16T09:56:00Z",
  },
  {
    id: "evt-007",
    type: "agent.status",
    title: "Community Comms Active",
    description: "Multilingual alerts dispatched in Odia, Hindi, English",
    severity: "medium",
    agent_type: "community_comms",
    timestamp: "2026-03-16T09:55:00Z",
  },
  {
    id: "evt-008",
    type: "agent.decision",
    title: "Infrastructure Risk Mapped",
    description: "Power grid cascading failure predicted for 4 substations",
    severity: "high",
    agent_type: "infra_status",
    timestamp: "2026-03-16T09:54:00Z",
  },
  {
    id: "evt-009",
    type: "metrics.update",
    title: "Token Budget Update",
    description: "Total spend: $0.12 across 47 LLM calls",
    severity: "low",
    timestamp: "2026-03-16T09:53:00Z",
  },
  {
    id: "evt-010",
    type: "agent.status",
    title: "Historical Memory Retrieved",
    description: "Retrieved 1999 Odisha Super Cyclone analogues from NDMA archive",
    severity: "medium",
    agent_type: "historical_memory",
    timestamp: "2026-03-16T09:52:00Z",
  },
];

/** Client-only relative timestamp to avoid SSR hydration mismatch. */
function RelativeTimestamp({ eventId, timestamp }: { eventId: string; timestamp: string }) {
  const [text, setText] = useState("");

  useEffect(() => {
    setText(formatRelativeTime(timestamp));
    const interval = setInterval(() => setText(formatRelativeTime(timestamp)), 30000);
    return () => clearInterval(interval);
  }, [timestamp]);

  return (
    <span
      data-testid={`timestamp-${eventId}`}
      className="mt-1 block text-xs text-gray-600"
      title={timestamp}
    >
      {text}
    </span>
  );
}

interface TimelineProps {
  events?: TimelineEvent[];
  filterByType?: WebSocketEventType;
  filterByAgent?: AgentType;
  onEventClick?: (event: TimelineEvent) => void;
  className?: string;
  maxEvents?: number;
}

export default function Timeline({
  events,
  filterByType,
  filterByAgent,
  onEventClick,
  className,
  maxEvents = 50,
}: TimelineProps) {
  let items = events ?? MOCK_TIMELINE_EVENTS;

  if (filterByType) {
    items = items.filter((e) => e.type === filterByType);
  }
  if (filterByAgent) {
    items = items.filter((e) => e.agent_type === filterByAgent);
  }

  // Sort newest first
  items = [...items].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );

  // Apply max
  items = items.slice(0, maxEvents);

  if (items.length === 0) {
    return (
      <div data-testid="timeline" className={className ?? ""}>
        <div
          data-testid="timeline-empty"
          className="flex items-center justify-center rounded-lg border border-dashed border-gray-700 p-8 text-sm text-gray-500"
        >
          No events to display
        </div>
      </div>
    );
  }

  return (
    <div data-testid="timeline" className={`relative ${className ?? ""}`}>
      {/* Vertical line */}
      <div className="absolute left-3 top-0 h-full w-px bg-gray-700" />

      <div className="space-y-4">
        {items.map((event) => (
          <div
            key={event.id}
            data-testid={`timeline-event-${event.id}`}
            className="relative cursor-pointer pl-8 transition-colors"
            onClick={() => onEventClick?.(event)}
          >
            {/* Dot on the line */}
            <span
              className={`absolute left-2 top-1.5 h-2.5 w-2.5 rounded-full ${SEVERITY_COLORS[event.severity]}`}
            />

            <div className="rounded-lg border border-gray-700 bg-gray-800 p-3">
              <div className="mb-1 flex items-center gap-2">
                <span
                  data-testid={`severity-badge-${event.id}`}
                  className={`rounded px-1.5 py-0.5 text-xs font-medium ${SEVERITY_COLORS[event.severity]} text-white`}
                >
                  {event.severity}
                </span>

                <span className="text-xs text-gray-500">
                  {EVENT_TYPE_LABELS[event.type]}
                </span>

                {event.agent_type && (
                  <span
                    data-testid={`agent-badge-${event.id}`}
                    className="rounded border border-blue-800 px-1.5 py-0.5 text-xs text-blue-400"
                  >
                    {event.agent_type}
                  </span>
                )}

                {event.phase && (
                  <span
                    data-testid={`phase-badge-${event.id}`}
                    className="rounded border border-purple-800 px-1.5 py-0.5 text-xs text-purple-400"
                  >
                    {event.phase}
                  </span>
                )}
              </div>

              <h3 className="text-sm font-medium text-white">{event.title}</h3>

              {event.description && (
                <p className="mt-1 text-xs text-gray-400">{event.description}</p>
              )}

              <RelativeTimestamp
                eventId={event.id}
                timestamp={event.timestamp}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
