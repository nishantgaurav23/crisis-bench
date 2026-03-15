import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import MetricsPanel, {
  MOCK_METRICS,
  formatTokens,
  getBudgetColor,
  getLatencyColor,
  TIER_COLORS,
} from "@/components/MetricsPanel";
import type { MetricsSummary } from "@/types";

describe("MetricsPanel", () => {
  it("renders the metrics panel container", () => {
    render(<MetricsPanel />);
    expect(screen.getByTestId("metrics-panel")).toBeInTheDocument();
  });

  it("renders all providers from mock data", () => {
    render(<MetricsPanel />);
    MOCK_METRICS.providers.forEach((p) => {
      expect(screen.getByTestId(`provider-row-${p.provider}`)).toBeInTheDocument();
    });
  });

  it("displays provider names", () => {
    render(<MetricsPanel />);
    expect(screen.getAllByText("DeepSeek Reasoner").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("DeepSeek Chat").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Qwen Flash").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Groq").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Ollama").length).toBeGreaterThanOrEqual(1);
  });

  it("renders the budget gauge section", () => {
    render(<MetricsPanel />);
    expect(screen.getByTestId("budget-gauge")).toBeInTheDocument();
  });

  it("renders the token summary section", () => {
    render(<MetricsPanel />);
    expect(screen.getByTestId("token-summary")).toBeInTheDocument();
  });

  it("renders the latency section", () => {
    render(<MetricsPanel />);
    expect(screen.getByTestId("latency-section")).toBeInTheDocument();
  });

  it("renders the cost breakdown section", () => {
    render(<MetricsPanel />);
    expect(screen.getByTestId("cost-breakdown")).toBeInTheDocument();
  });
});

describe("formatTokens", () => {
  it("formats numbers under 1000 as-is", () => {
    expect(formatTokens(500)).toBe("500");
    expect(formatTokens(0)).toBe("0");
    expect(formatTokens(999)).toBe("999");
  });

  it("formats thousands with K suffix", () => {
    expect(formatTokens(1000)).toBe("1.00K");
    expect(formatTokens(1500)).toBe("1.50K");
    expect(formatTokens(45600)).toBe("45.60K");
    expect(formatTokens(999999)).toBe("1000.00K");
  });

  it("formats millions with M suffix", () => {
    expect(formatTokens(1000000)).toBe("1.00M");
    expect(formatTokens(1234567)).toBe("1.23M");
    expect(formatTokens(50000000)).toBe("50.00M");
  });
});

describe("getBudgetColor", () => {
  it("returns green when under 50%", () => {
    expect(getBudgetColor(2, 8)).toBe("text-green-400");
    expect(getBudgetColor(0, 8)).toBe("text-green-400");
    expect(getBudgetColor(3.99, 8)).toBe("text-green-400");
  });

  it("returns yellow when between 50% and 80%", () => {
    expect(getBudgetColor(4, 8)).toBe("text-yellow-400");
    expect(getBudgetColor(5, 8)).toBe("text-yellow-400");
    expect(getBudgetColor(6.39, 8)).toBe("text-yellow-400");
  });

  it("returns red when over 80%", () => {
    expect(getBudgetColor(6.4, 8)).toBe("text-red-400");
    expect(getBudgetColor(8, 8)).toBe("text-red-400");
    expect(getBudgetColor(10, 8)).toBe("text-red-400");
  });
});

describe("getLatencyColor", () => {
  it("returns green for latency under 1000ms", () => {
    expect(getLatencyColor(500)).toBe("text-green-400");
    expect(getLatencyColor(999)).toBe("text-green-400");
  });

  it("returns yellow for latency between 1000-3000ms", () => {
    expect(getLatencyColor(1000)).toBe("text-yellow-400");
    expect(getLatencyColor(2500)).toBe("text-yellow-400");
  });

  it("returns red for latency over 3000ms", () => {
    expect(getLatencyColor(3000)).toBe("text-red-400");
    expect(getLatencyColor(5000)).toBe("text-red-400");
  });
});

describe("TIER_COLORS", () => {
  it("has colors for all tiers", () => {
    expect(TIER_COLORS.critical).toBeDefined();
    expect(TIER_COLORS.standard).toBeDefined();
    expect(TIER_COLORS.routine).toBeDefined();
    expect(TIER_COLORS.free).toBeDefined();
  });
});

describe("MetricsPanel props", () => {
  it("accepts custom metrics via props", () => {
    const customMetrics: MetricsSummary = {
      providers: [
        {
          provider: "TestProvider",
          tier: "critical",
          total_cost: 1.5,
          input_tokens: 1000,
          output_tokens: 500,
          requests: 10,
          avg_latency_ms: 200,
          p50_latency_ms: 180,
          p95_latency_ms: 400,
          p99_latency_ms: 600,
        },
      ],
      total_cost: 1.5,
      total_input_tokens: 1000,
      total_output_tokens: 500,
      total_requests: 10,
      period_start: "2026-03-01T00:00:00Z",
      period_end: "2026-03-15T00:00:00Z",
    };

    render(<MetricsPanel metrics={customMetrics} />);
    expect(screen.getAllByText("TestProvider").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByTestId("provider-row-TestProvider")).toBeInTheDocument();
  });

  it("accepts custom budget", () => {
    render(<MetricsPanel budget={20} />);
    expect(screen.getByTestId("budget-gauge")).toHaveTextContent("$20.00");
  });

  it("applies custom className", () => {
    render(<MetricsPanel className="custom-class" />);
    expect(screen.getByTestId("metrics-panel").className).toContain("custom-class");
  });

  it("fires onProviderClick when a provider row is clicked", () => {
    const handleClick = jest.fn();
    render(<MetricsPanel onProviderClick={handleClick} />);
    fireEvent.click(screen.getByTestId(`provider-row-${MOCK_METRICS.providers[0].provider}`));
    expect(handleClick).toHaveBeenCalledTimes(1);
    expect(handleClick).toHaveBeenCalledWith(
      expect.objectContaining({ provider: MOCK_METRICS.providers[0].provider })
    );
  });

  it("shows total cost in budget gauge", () => {
    render(<MetricsPanel />);
    const gauge = screen.getByTestId("budget-gauge");
    expect(gauge).toHaveTextContent(`$${MOCK_METRICS.total_cost.toFixed(2)}`);
  });

  it("shows formatted token counts in token summary", () => {
    render(<MetricsPanel />);
    const summary = screen.getByTestId("token-summary");
    expect(summary).toHaveTextContent(formatTokens(MOCK_METRICS.total_input_tokens));
    expect(summary).toHaveTextContent(formatTokens(MOCK_METRICS.total_output_tokens));
  });

  it("exports MOCK_METRICS with 5 providers", () => {
    expect(MOCK_METRICS).toBeDefined();
    expect(MOCK_METRICS.providers).toHaveLength(5);
  });

  it("shows cost per provider", () => {
    render(<MetricsPanel />);
    MOCK_METRICS.providers.forEach((p) => {
      const row = screen.getByTestId(`provider-row-${p.provider}`);
      expect(row).toHaveTextContent(`$${p.total_cost.toFixed(2)}`);
    });
  });

  it("displays latency values for each provider", () => {
    render(<MetricsPanel />);
    MOCK_METRICS.providers.forEach((p) => {
      expect(screen.getByTestId(`latency-avg-${p.provider}`)).toHaveTextContent(
        `${p.avg_latency_ms}ms`
      );
    });
  });
});
