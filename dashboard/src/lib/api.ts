import { ApiError, AgentCard, AgentType, Disaster, HealthStatus } from "@/types";

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

export { API_BASE };
