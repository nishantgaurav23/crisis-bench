"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { CrisisWebSocketClient } from "@/lib/websocket";
import type {
  WebSocketMessage,
  Disaster,
  AgentCard,
  AgentStatus,
  MetricsSummary,
  TimelineEvent,
} from "@/types";

/**
 * React hook for managing WebSocket connection and dispatching
 * real-time events to dashboard state.
 */
export interface CrisisWebSocketState {
  isConnected: boolean;
  disasters: Disaster[];
  agents: Map<string, Partial<AgentCard>>;
  metrics: MetricsSummary | null;
  timelineEvents: TimelineEvent[];
}

export interface UseCrisisWebSocketReturn extends CrisisWebSocketState {
  setDisasters: (disasters: Disaster[]) => void;
  setMetrics: (metrics: MetricsSummary) => void;
}

const MAX_TIMELINE_EVENTS = 100;

let eventCounter = 0;

export default function useCrisisWebSocket(): UseCrisisWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [disasters, setDisasters] = useState<Disaster[]>([]);
  const [agentUpdates, setAgentUpdates] = useState<Map<string, Partial<AgentCard>>>(new Map());
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([]);
  const wsRef = useRef<CrisisWebSocketClient | null>(null);

  const addTimelineEvent = useCallback((event: TimelineEvent) => {
    setTimelineEvents((prev) => {
      const next = [event, ...prev];
      return next.slice(0, MAX_TIMELINE_EVENTS);
    });
  }, []);

  const handleMessage = useCallback(
    (msg: WebSocketMessage) => {
      const data = msg.data as Record<string, unknown>;

      switch (msg.type) {
        case "disaster.created":
          setDisasters((prev) => [...prev, data as unknown as Disaster]);
          addTimelineEvent({
            id: `ws-${++eventCounter}`,
            type: "disaster.created",
            title: (data.title as string) || "New Disaster",
            description: `Type: ${data.type}, Severity: ${data.severity}`,
            severity: severityFromNumber(data.severity as number),
            timestamp: msg.timestamp,
          });
          break;

        case "disaster.updated":
          setDisasters((prev) =>
            prev.map((d) => (d.id === (data.id as string) ? { ...d, ...data } as Disaster : d))
          );
          addTimelineEvent({
            id: `ws-${++eventCounter}`,
            type: "disaster.updated",
            title: "Disaster Updated",
            description: (data.description as string) || undefined,
            severity: severityFromNumber(data.severity as number),
            timestamp: msg.timestamp,
          });
          break;

        case "agent.status":
          setAgentUpdates((prev) => {
            const next = new Map(prev);
            next.set(data.agent_type as string, {
              status: data.status as AgentStatus,
              last_active: data.last_active as string,
            });
            return next;
          });
          addTimelineEvent({
            id: `ws-${++eventCounter}`,
            type: "agent.status",
            title: `${data.agent_type} → ${data.status}`,
            description: (data.current_task as string) || undefined,
            severity: "medium",
            agent_type: data.agent_type as AgentCard["agent_type"],
            timestamp: msg.timestamp,
          });
          break;

        case "agent.decision":
          addTimelineEvent({
            id: `ws-${++eventCounter}`,
            type: "agent.decision",
            title: `${data.agent_type}: ${data.decision_type}`,
            description: (data.reasoning as string) || undefined,
            severity: "high",
            agent_type: data.agent_type as AgentCard["agent_type"],
            timestamp: msg.timestamp,
          });
          break;

        case "metrics.update":
          if (data.total_cost !== undefined) {
            setMetrics((prev) => ({
              ...prev,
              ...(data as unknown as MetricsSummary),
            }) as MetricsSummary);
          }
          break;
      }
    },
    [addTimelineEvent]
  );

  useEffect(() => {
    const ws = new CrisisWebSocketClient();
    wsRef.current = ws;

    const unsubConnect = ws.onConnect(() => setIsConnected(true));
    const unsubDisconnect = ws.onDisconnect(() => setIsConnected(false));
    const unsubMessage = ws.onMessage(handleMessage);

    ws.connect();

    return () => {
      unsubConnect();
      unsubDisconnect();
      unsubMessage();
      ws.disconnect();
    };
  }, [handleMessage]);

  return {
    isConnected,
    disasters,
    agents: agentUpdates,
    metrics,
    timelineEvents,
    setDisasters,
    setMetrics,
  };
}

function severityFromNumber(n: number | undefined): "low" | "medium" | "high" | "critical" {
  if (!n || n <= 2) return "low";
  if (n === 3) return "medium";
  if (n === 4) return "high";
  return "critical";
}
