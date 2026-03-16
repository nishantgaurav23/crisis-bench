export type DisasterType =
  | "flood"
  | "cyclone"
  | "earthquake"
  | "landslide"
  | "drought"
  | "heat_wave"
  | "industrial";

export type DisasterPhase =
  | "monitoring"
  | "alert"
  | "active"
  | "response"
  | "recovery";

export type Severity = "low" | "medium" | "high" | "critical";

export interface Disaster {
  id: string;
  type: DisasterType;
  title: string;
  severity: Severity;
  phase: DisasterPhase;
  location: {
    lat: number;
    lng: number;
    name: string;
    state: string;
    district?: string;
  };
  affected_population?: number;
  created_at: string;
  updated_at: string;
}

export type AgentType =
  | "orchestrator"
  | "situation_sense"
  | "predictive_risk"
  | "resource_allocation"
  | "community_comms"
  | "infra_status"
  | "historical_memory";

export type AgentStatus = "idle" | "active" | "processing" | "error" | "offline";

export interface AgentCard {
  agent_type: AgentType;
  name: string;
  status: AgentStatus;
  capabilities: string[];
  llm_tier: string;
  last_active?: string;
}

export type WebSocketEventType =
  | "disaster.created"
  | "disaster.updated"
  | "agent.status"
  | "agent.decision"
  | "metrics.update";

export interface WebSocketMessage<T = unknown> {
  type: WebSocketEventType;
  data: T;
  timestamp: string;
  trace_id: string;
}

export interface HealthStatus {
  status: "healthy" | "degraded" | "unhealthy";
  version: string;
  services: Record<string, boolean>;
}

export interface TimelineEvent {
  id: string;
  type: WebSocketEventType;
  title: string;
  description?: string;
  severity: Severity;
  agent_type?: AgentType;
  phase?: DisasterPhase;
  timestamp: string;
}

export interface ProviderMetrics {
  provider: string;
  tier: string;
  total_cost: number;
  input_tokens: number;
  output_tokens: number;
  requests: number;
  avg_latency_ms: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
}

export interface MetricsSummary {
  providers: ProviderMetrics[];
  total_cost: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_requests: number;
  period_start: string;
  period_end: string;
}

export interface ApiError {
  detail: string;
  trace_id?: string;
}

// Benchmark types

export interface ScenarioSummary {
  id: string;
  category: string;
  complexity: string;
  affected_states: string[];
  event_count: number;
  source: string;
  created_at: string;
}

export interface EvaluationRunSummary {
  id: string;
  scenario_id: string;
  situational_accuracy: number | null;
  decision_timeliness: number | null;
  resource_efficiency: number | null;
  coordination_quality: number | null;
  communication_score: number | null;
  aggregate_drs: number | null;
  total_tokens: number | null;
  total_cost_usd: number | null;
  primary_provider: string | null;
  duration_seconds: number | null;
  completed_at: string;
}
