import { getHealth, getDisasters, getDisaster, getAgents, getAgent, createDisaster, ApiClientError, API_BASE } from "@/lib/api";
import type { Disaster, HealthStatus, AgentCard } from "@/types";

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch;

beforeEach(() => {
  mockFetch.mockReset();
});

describe("API Client", () => {
  describe("API_BASE", () => {
    it("defaults to http://localhost:8000", () => {
      expect(API_BASE).toBe("http://localhost:8000");
    });
  });

  describe("getHealth", () => {
    it("fetches health status from /health", async () => {
      const mockHealth: HealthStatus = {
        status: "healthy",
        version: "0.1.0",
        services: { postgres: true, redis: true },
      };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockHealth),
      });

      const result = await getHealth();

      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/health",
        expect.objectContaining({
          headers: expect.objectContaining({
            "Content-Type": "application/json",
          }),
        })
      );
      expect(result).toEqual(mockHealth);
    });
  });

  describe("getDisasters", () => {
    it("fetches disasters from /api/v1/disasters", async () => {
      const mockDisasters: Disaster[] = [
        {
          id: "d-001",
          type: "cyclone",
          title: "Cyclone Biparjoy",
          severity: "critical",
          phase: "active",
          location: { lat: 23.0, lng: 70.0, name: "Gujarat Coast", state: "Gujarat" },
          created_at: "2026-03-15T00:00:00Z",
          updated_at: "2026-03-15T00:00:00Z",
        },
      ];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockDisasters),
      });

      const result = await getDisasters();

      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/disasters",
        expect.anything()
      );
      expect(result).toHaveLength(1);
      expect(result[0].type).toBe("cyclone");
    });
  });

  describe("getDisaster", () => {
    it("fetches a single disaster by ID", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            id: "d-001",
            type: "flood",
            title: "Kerala Floods",
            severity: "high",
            phase: "response",
            location: { lat: 10.0, lng: 76.0, name: "Wayanad", state: "Kerala" },
            created_at: "2026-03-15T00:00:00Z",
            updated_at: "2026-03-15T00:00:00Z",
          }),
      });

      const result = await getDisaster("d-001");

      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/disasters/d-001",
        expect.anything()
      );
      expect(result.id).toBe("d-001");
    });
  });

  describe("createDisaster", () => {
    it("sends POST to /api/v1/disasters", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            id: "d-new",
            type: "earthquake",
            title: "Kutch Earthquake",
            severity: "critical",
            phase: "alert",
            location: { lat: 23.4, lng: 69.8, name: "Bhuj", state: "Gujarat" },
            created_at: "2026-03-15T00:00:00Z",
            updated_at: "2026-03-15T00:00:00Z",
          }),
      });

      const result = await createDisaster({
        type: "earthquake",
        title: "Kutch Earthquake",
        severity: "critical",
        phase: "alert",
        location: { lat: 23.4, lng: 69.8, name: "Bhuj", state: "Gujarat" },
      });

      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/disasters",
        expect.objectContaining({ method: "POST" })
      );
      expect(result.id).toBe("d-new");
    });
  });

  describe("getAgents", () => {
    it("fetches agent cards from /api/v1/agents", async () => {
      const mockAgents: AgentCard[] = [
        {
          agent_type: "orchestrator",
          name: "Orchestrator",
          status: "idle",
          capabilities: ["mission_decomposition", "synthesis"],
          llm_tier: "critical",
        },
      ];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockAgents),
      });

      const result = await getAgents();

      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/agents",
        expect.anything()
      );
      expect(result[0].agent_type).toBe("orchestrator");
    });
  });

  describe("getAgent", () => {
    it("fetches single agent by type", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            agent_type: "situation_sense",
            name: "SituationSense",
            status: "active",
            capabilities: ["data_fusion"],
            llm_tier: "routine",
          }),
      });

      const result = await getAgent("situation_sense");

      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/agents/situation_sense",
        expect.anything()
      );
      expect(result.agent_type).toBe("situation_sense");
    });
  });

  describe("error handling", () => {
    it("throws ApiClientError on non-OK response with JSON body", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ detail: "Not found", trace_id: "t-123" }),
      });

      await expect(getDisaster("nonexistent")).rejects.toThrow(ApiClientError);
      await mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ detail: "Not found", trace_id: "t-123" }),
      });

      try {
        await getDisaster("nonexistent");
      } catch (err) {
        expect(err).toBeInstanceOf(ApiClientError);
        const apiErr = err as ApiClientError;
        expect(apiErr.status).toBe(404);
        expect(apiErr.detail).toBe("Not found");
        expect(apiErr.traceId).toBe("t-123");
      }
    });

    it("throws ApiClientError with fallback message on non-JSON error", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error("not json")),
      });

      try {
        await getHealth();
      } catch (err) {
        expect(err).toBeInstanceOf(ApiClientError);
        const apiErr = err as ApiClientError;
        expect(apiErr.status).toBe(500);
        expect(apiErr.detail).toBe("HTTP 500");
      }
    });
  });
});
