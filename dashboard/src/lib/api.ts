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

export function getDisasters(): Promise<Disaster[]> {
  return request<Disaster[]>("/api/v1/disasters");
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

// Metrics API

export function getMetricsSummary(): Promise<MetricsSummary> {
  return request<MetricsSummary>("/api/v1/metrics/summary");
}

export { API_BASE };
