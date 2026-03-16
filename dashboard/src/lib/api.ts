import {
  ApiError,
  AgentCard,
  AgentType,
  Disaster,
  EvaluationRunSummary,
  HealthStatus,
  MetricsSummary,
  ScenarioSummary,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiClientError extends Error {
  constructor(
    public status: number,
    public detail: string,
    public traceId?: string
  ) {
    super(detail);
    this.name = "ApiClientError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    let traceId: string | undefined;
    try {
      const body: ApiError = await res.json();
      detail = body.detail;
      traceId = body.trace_id;
    } catch {
      // use default detail
    }
    throw new ApiClientError(res.status, detail, traceId);
  }

  return res.json() as Promise<T>;
}

export function getHealth(): Promise<HealthStatus> {
  return request<HealthStatus>("/health");
}

const SEVERITY_MAP: Record<number, "low" | "medium" | "high" | "critical"> = {
  1: "low",
  2: "low",
  3: "medium",
  4: "high",
  5: "critical",
};

// Transform backend Disaster model to dashboard format
// Backend uses severity as int (1-5), location as {latitude, longitude}
// Dashboard expects severity as string, location as {lat, lng, name, state}
function transformDisaster(raw: Record<string, unknown>): Disaster {
  const loc = raw.location as Record<string, unknown> | null;
  const states = (raw.affected_state_ids as number[]) || [];
  return {
    id: raw.id as string,
    type: (raw.type as string) as Disaster["type"],
    title: (raw.title as string) || `${raw.type} event`,
    severity: SEVERITY_MAP[(raw.severity as number) || 1] || "medium",
    phase: (raw.phase as string) as Disaster["phase"],
    location: {
      lat: loc ? (loc.latitude as number) : 20.5,
      lng: loc ? (loc.longitude as number) : 78.9,
      name: (raw.title as string) || "Unknown",
      state: states.length > 0 ? `State ${states[0]}` : "India",
    },
    affected_population: raw.affected_population as number | undefined,
    created_at: (raw.start_time as string) || new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

export async function getDisasters(): Promise<Disaster[]> {
  const raw = await request<Record<string, unknown>[]>("/api/v1/disasters");
  return raw.map(transformDisaster);
}

export function getDisaster(id: string): Promise<Disaster> {
  return request<Disaster>(`/api/v1/disasters/${id}`);
}

export function createDisaster(
  data: Omit<Disaster, "id" | "created_at" | "updated_at">
): Promise<Disaster> {
  return request<Disaster>("/api/v1/disasters", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getAgents(): Promise<AgentCard[]> {
  return request<AgentCard[]>("/api/v1/agents");
}

export function getAgent(agentType: AgentType): Promise<AgentCard> {
  return request<AgentCard>(`/api/v1/agents/${agentType}`);
}

// Benchmark API

export function getScenarios(
  category?: string,
  complexity?: string
): Promise<ScenarioSummary[]> {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (complexity) params.set("complexity", complexity);
  const qs = params.toString();
  return request<ScenarioSummary[]>(
    `/api/v1/benchmark/scenarios${qs ? `?${qs}` : ""}`
  );
}

export function getScenario(id: string): Promise<ScenarioSummary> {
  return request<ScenarioSummary>(`/api/v1/benchmark/scenarios/${id}`);
}

export function getEvaluationRuns(
  scenarioId?: string
): Promise<EvaluationRunSummary[]> {
  const qs = scenarioId ? `?scenario_id=${scenarioId}` : "";
  return request<EvaluationRunSummary[]>(`/api/v1/benchmark/runs${qs}`);
}

export function getEvaluationRun(id: string): Promise<EvaluationRunSummary> {
  return request<EvaluationRunSummary>(`/api/v1/benchmark/runs/${id}`);
}

// Run Benchmark

export function runBenchmark(
  scenarioId: string
): Promise<{ run_id: string; scenario_id: string; status: string; message: string }> {
  return request(`/api/v1/benchmark/run/${scenarioId}`, { method: "POST" });
}

// Metrics API

export function getMetricsSummary(): Promise<MetricsSummary> {
  return request<MetricsSummary>("/api/v1/metrics/summary");
}

export { API_BASE };
