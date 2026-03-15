import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import AgentFlow, { MOCK_AGENTS, STATUS_COLORS, TIER_STYLES } from "@/components/AgentFlow";
import type { AgentCard } from "@/types";

describe("AgentFlow", () => {
  it("renders the agent flow container", () => {
    render(<AgentFlow />);
    expect(screen.getByTestId("agent-flow")).toBeInTheDocument();
  });

  it("renders all 7 agent cards with mock data", () => {
    render(<AgentFlow />);
    const cards = screen.getAllByTestId(/^agent-card-/);
    expect(cards).toHaveLength(7);
  });

  it("renders orchestrator card", () => {
    render(<AgentFlow />);
    expect(screen.getByTestId("agent-card-orchestrator")).toBeInTheDocument();
    expect(screen.getByText("Orchestrator")).toBeInTheDocument();
  });

  it("renders all 6 specialist agent names", () => {
    render(<AgentFlow />);
    expect(screen.getByText("Situation Sense")).toBeInTheDocument();
    expect(screen.getByText("Predictive Risk")).toBeInTheDocument();
    expect(screen.getByText("Resource Allocation")).toBeInTheDocument();
    expect(screen.getByText("Community Comms")).toBeInTheDocument();
    expect(screen.getByText("Infra Status")).toBeInTheDocument();
    expect(screen.getByText("Historical Memory")).toBeInTheDocument();
  });

  it("shows status dots with correct colors for each status", () => {
    const agents: AgentCard[] = [
      {
        agent_type: "orchestrator",
        name: "Orchestrator",
        status: "active",
        capabilities: [],
        llm_tier: "critical",
      },
      {
        agent_type: "situation_sense",
        name: "Situation Sense",
        status: "processing",
        capabilities: [],
        llm_tier: "routine",
      },
      {
        agent_type: "predictive_risk",
        name: "Predictive Risk",
        status: "idle",
        capabilities: [],
        llm_tier: "standard",
      },
      {
        agent_type: "resource_allocation",
        name: "Resource Allocation",
        status: "error",
        capabilities: [],
        llm_tier: "standard",
      },
      {
        agent_type: "community_comms",
        name: "Community Comms",
        status: "offline",
        capabilities: [],
        llm_tier: "routine",
      },
    ];

    render(<AgentFlow agents={agents} />);

    const activeDot = screen.getByTestId("status-dot-orchestrator");
    expect(activeDot.className).toContain("bg-green-500");

    const processingDot = screen.getByTestId("status-dot-situation_sense");
    expect(processingDot.className).toContain("bg-blue-500");

    const idleDot = screen.getByTestId("status-dot-predictive_risk");
    expect(idleDot.className).toContain("bg-gray-500");

    const errorDot = screen.getByTestId("status-dot-resource_allocation");
    expect(errorDot.className).toContain("bg-red-500");

    const offlineDot = screen.getByTestId("status-dot-community_comms");
    expect(offlineDot.className).toContain("bg-gray-700");
  });

  it("renders LLM tier badges with correct text", () => {
    render(<AgentFlow />);
    const orchestratorCard = screen.getByTestId("agent-card-orchestrator");
    expect(orchestratorCard).toHaveTextContent("Critical");
  });

  it("renders tier badges for all tier types", () => {
    const agents: AgentCard[] = [
      {
        agent_type: "orchestrator",
        name: "Test Critical",
        status: "active",
        capabilities: [],
        llm_tier: "critical",
      },
      {
        agent_type: "situation_sense",
        name: "Test Routine",
        status: "idle",
        capabilities: [],
        llm_tier: "routine",
      },
      {
        agent_type: "predictive_risk",
        name: "Test Standard",
        status: "idle",
        capabilities: [],
        llm_tier: "standard",
      },
    ];
    render(<AgentFlow agents={agents} />);

    expect(screen.getByTestId("tier-badge-orchestrator")).toHaveTextContent("Critical");
    expect(screen.getByTestId("tier-badge-situation_sense")).toHaveTextContent("Routine");
    expect(screen.getByTestId("tier-badge-predictive_risk")).toHaveTextContent("Standard");
  });

  it("renders SVG connection lines", () => {
    render(<AgentFlow />);
    const svg = screen.getByTestId("connection-lines");
    expect(svg).toBeInTheDocument();
    expect(svg.tagName.toLowerCase()).toBe("svg");
  });

  it("fires onAgentClick when a card is clicked", () => {
    const handleClick = jest.fn();
    render(<AgentFlow onAgentClick={handleClick} />);

    fireEvent.click(screen.getByTestId("agent-card-orchestrator"));
    expect(handleClick).toHaveBeenCalledTimes(1);
    expect(handleClick).toHaveBeenCalledWith(
      expect.objectContaining({ agent_type: "orchestrator" })
    );
  });

  it("accepts custom agents via props", () => {
    const customAgents: AgentCard[] = [
      {
        agent_type: "orchestrator",
        name: "Custom Orchestrator",
        status: "active",
        capabilities: ["custom"],
        llm_tier: "critical",
      },
    ];

    render(<AgentFlow agents={customAgents} />);
    expect(screen.getByText("Custom Orchestrator")).toBeInTheDocument();
    const cards = screen.getAllByTestId(/^agent-card-/);
    expect(cards).toHaveLength(1);
  });

  it("applies custom className", () => {
    render(<AgentFlow className="custom-class" />);
    expect(screen.getByTestId("agent-flow").className).toContain("custom-class");
  });

  it("exports STATUS_COLORS mapping", () => {
    expect(STATUS_COLORS).toBeDefined();
    expect(STATUS_COLORS.active).toBe("bg-green-500");
    expect(STATUS_COLORS.processing).toBe("bg-blue-500");
    expect(STATUS_COLORS.idle).toBe("bg-gray-500");
    expect(STATUS_COLORS.error).toBe("bg-red-500");
    expect(STATUS_COLORS.offline).toBe("bg-gray-700");
  });

  it("exports TIER_STYLES mapping", () => {
    expect(TIER_STYLES).toBeDefined();
    expect(TIER_STYLES.critical).toBeDefined();
    expect(TIER_STYLES.standard).toBeDefined();
    expect(TIER_STYLES.routine).toBeDefined();
    expect(TIER_STYLES.vision).toBeDefined();
  });

  it("exports MOCK_AGENTS with 7 agents", () => {
    expect(MOCK_AGENTS).toBeDefined();
    expect(MOCK_AGENTS).toHaveLength(7);
    expect(MOCK_AGENTS[0].agent_type).toBe("orchestrator");
  });

  it("shows capabilities for each agent", () => {
    const agents: AgentCard[] = [
      {
        agent_type: "orchestrator",
        name: "Orchestrator",
        status: "active",
        capabilities: ["mission decomposition", "agent activation"],
        llm_tier: "critical",
      },
    ];
    render(<AgentFlow agents={agents} />);
    expect(screen.getByText("mission decomposition")).toBeInTheDocument();
    expect(screen.getByText("agent activation")).toBeInTheDocument();
  });

  it("distinguishes orchestrator visually from specialists", () => {
    render(<AgentFlow />);
    const orchestratorCard = screen.getByTestId("agent-card-orchestrator");
    const specialistCard = screen.getByTestId("agent-card-situation_sense");
    const orchestratorSection = screen.getByTestId("orchestrator-section");
    expect(orchestratorSection).toContainElement(orchestratorCard);
    const specialistsSection = screen.getByTestId("specialists-section");
    expect(specialistsSection).toContainElement(specialistCard);
  });
});
