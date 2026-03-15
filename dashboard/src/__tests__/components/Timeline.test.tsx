import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import Timeline, {
  MOCK_TIMELINE_EVENTS,
  SEVERITY_COLORS,
  formatRelativeTime,
} from "@/components/Timeline";
import type { TimelineEvent } from "@/types";

describe("Timeline", () => {
  it("renders the timeline container", () => {
    render(<Timeline />);
    expect(screen.getByTestId("timeline")).toBeInTheDocument();
  });

  it("renders all mock events by default", () => {
    render(<Timeline />);
    const items = screen.getAllByTestId(/^timeline-event-/);
    expect(items.length).toBe(MOCK_TIMELINE_EVENTS.length);
  });

  it("shows event titles and descriptions", () => {
    const events: TimelineEvent[] = [
      {
        id: "evt-1",
        type: "disaster.created",
        title: "Cyclone Alert Issued",
        description: "IMD issued Red Alert for Odisha coast",
        severity: "critical",
        timestamp: new Date().toISOString(),
      },
    ];
    render(<Timeline events={events} />);
    expect(screen.getByText("Cyclone Alert Issued")).toBeInTheDocument();
    expect(screen.getByText("IMD issued Red Alert for Odisha coast")).toBeInTheDocument();
  });

  it("shows timestamps in relative format", () => {
    const twoMinAgo = new Date(Date.now() - 2 * 60 * 1000).toISOString();
    const events: TimelineEvent[] = [
      {
        id: "evt-1",
        type: "disaster.created",
        title: "Test Event",
        severity: "low",
        timestamp: twoMinAgo,
      },
    ];
    render(<Timeline events={events} />);
    const timeEl = screen.getByTestId("timestamp-evt-1");
    expect(timeEl.textContent).toMatch(/2m ago/);
  });

  it("shows severity badges with correct colors", () => {
    const events: TimelineEvent[] = [
      {
        id: "evt-crit",
        type: "disaster.created",
        title: "Critical Event",
        severity: "critical",
        timestamp: new Date().toISOString(),
      },
      {
        id: "evt-high",
        type: "disaster.updated",
        title: "High Event",
        severity: "high",
        timestamp: new Date().toISOString(),
      },
      {
        id: "evt-med",
        type: "agent.status",
        title: "Medium Event",
        severity: "medium",
        timestamp: new Date().toISOString(),
      },
      {
        id: "evt-low",
        type: "agent.decision",
        title: "Low Event",
        severity: "low",
        timestamp: new Date().toISOString(),
      },
    ];
    render(<Timeline events={events} />);

    expect(screen.getByTestId("severity-badge-evt-crit").className).toContain(
      SEVERITY_COLORS.critical
    );
    expect(screen.getByTestId("severity-badge-evt-high").className).toContain(
      SEVERITY_COLORS.high
    );
    expect(screen.getByTestId("severity-badge-evt-med").className).toContain(
      SEVERITY_COLORS.medium
    );
    expect(screen.getByTestId("severity-badge-evt-low").className).toContain(
      SEVERITY_COLORS.low
    );
  });

  it("shows agent source for agent events", () => {
    const events: TimelineEvent[] = [
      {
        id: "evt-1",
        type: "agent.decision",
        title: "Evacuation Order",
        severity: "critical",
        agent_type: "orchestrator",
        timestamp: new Date().toISOString(),
      },
    ];
    render(<Timeline events={events} />);
    expect(screen.getByTestId("agent-badge-evt-1")).toHaveTextContent("orchestrator");
  });

  it("shows phase badge for phase transition events", () => {
    const events: TimelineEvent[] = [
      {
        id: "evt-1",
        type: "disaster.updated",
        title: "Phase Transition",
        severity: "high",
        phase: "response",
        timestamp: new Date().toISOString(),
      },
    ];
    render(<Timeline events={events} />);
    expect(screen.getByTestId("phase-badge-evt-1")).toHaveTextContent("response");
  });

  it("filters events by type", () => {
    const events: TimelineEvent[] = [
      {
        id: "evt-1",
        type: "disaster.created",
        title: "Disaster Created",
        severity: "high",
        timestamp: new Date().toISOString(),
      },
      {
        id: "evt-2",
        type: "agent.decision",
        title: "Evacuation Ordered",
        severity: "medium",
        timestamp: new Date().toISOString(),
      },
    ];
    render(<Timeline events={events} filterByType="agent.decision" />);
    const items = screen.getAllByTestId(/^timeline-event-/);
    expect(items).toHaveLength(1);
    expect(screen.getByText("Evacuation Ordered")).toBeInTheDocument();
    expect(screen.queryByText("Disaster Created")).not.toBeInTheDocument();
  });

  it("filters events by agent", () => {
    const events: TimelineEvent[] = [
      {
        id: "evt-1",
        type: "agent.decision",
        title: "Orchestrator Decision",
        severity: "critical",
        agent_type: "orchestrator",
        timestamp: new Date().toISOString(),
      },
      {
        id: "evt-2",
        type: "agent.status",
        title: "Situation Update",
        severity: "medium",
        agent_type: "situation_sense",
        timestamp: new Date().toISOString(),
      },
      {
        id: "evt-3",
        type: "disaster.created",
        title: "No Agent",
        severity: "high",
        timestamp: new Date().toISOString(),
      },
    ];
    render(<Timeline events={events} filterByAgent="orchestrator" />);
    const items = screen.getAllByTestId(/^timeline-event-/);
    expect(items).toHaveLength(1);
    expect(screen.getByText("Orchestrator Decision")).toBeInTheDocument();
  });

  it("fires onEventClick when event is clicked", () => {
    const handleClick = jest.fn();
    const events: TimelineEvent[] = [
      {
        id: "evt-1",
        type: "disaster.created",
        title: "Click Me",
        severity: "low",
        timestamp: new Date().toISOString(),
      },
    ];
    render(<Timeline events={events} onEventClick={handleClick} />);
    fireEvent.click(screen.getByTestId("timeline-event-evt-1"));
    expect(handleClick).toHaveBeenCalledTimes(1);
    expect(handleClick).toHaveBeenCalledWith(expect.objectContaining({ id: "evt-1" }));
  });

  it("shows empty state when no events", () => {
    render(<Timeline events={[]} />);
    expect(screen.getByTestId("timeline-empty")).toBeInTheDocument();
    expect(screen.getByText(/no events/i)).toBeInTheDocument();
  });

  it("respects maxEvents prop", () => {
    const events: TimelineEvent[] = Array.from({ length: 10 }, (_, i) => ({
      id: `evt-${i}`,
      type: "disaster.created" as const,
      title: `Event ${i}`,
      severity: "low" as const,
      timestamp: new Date(Date.now() - i * 60000).toISOString(),
    }));
    render(<Timeline events={events} maxEvents={3} />);
    const items = screen.getAllByTestId(/^timeline-event-/);
    expect(items).toHaveLength(3);
  });

  it("newest events appear first (sorted by timestamp desc)", () => {
    const events: TimelineEvent[] = [
      {
        id: "evt-old",
        type: "disaster.created",
        title: "Old Event",
        severity: "low",
        timestamp: "2026-01-01T00:00:00Z",
      },
      {
        id: "evt-new",
        type: "disaster.created",
        title: "New Event",
        severity: "low",
        timestamp: "2026-03-15T00:00:00Z",
      },
    ];
    render(<Timeline events={events} />);
    const items = screen.getAllByTestId(/^timeline-event-/);
    expect(items[0]).toHaveAttribute("data-testid", "timeline-event-evt-new");
    expect(items[1]).toHaveAttribute("data-testid", "timeline-event-evt-old");
  });

  it("accepts custom className", () => {
    render(<Timeline className="my-custom" />);
    expect(screen.getByTestId("timeline").className).toContain("my-custom");
  });

  it("exports MOCK_TIMELINE_EVENTS", () => {
    expect(MOCK_TIMELINE_EVENTS).toBeDefined();
    expect(MOCK_TIMELINE_EVENTS.length).toBeGreaterThanOrEqual(8);
    expect(MOCK_TIMELINE_EVENTS[0]).toHaveProperty("id");
    expect(MOCK_TIMELINE_EVENTS[0]).toHaveProperty("type");
    expect(MOCK_TIMELINE_EVENTS[0]).toHaveProperty("title");
    expect(MOCK_TIMELINE_EVENTS[0]).toHaveProperty("severity");
    expect(MOCK_TIMELINE_EVENTS[0]).toHaveProperty("timestamp");
  });

  it("exports SEVERITY_COLORS mapping", () => {
    expect(SEVERITY_COLORS).toBeDefined();
    expect(SEVERITY_COLORS.critical).toBeDefined();
    expect(SEVERITY_COLORS.high).toBeDefined();
    expect(SEVERITY_COLORS.medium).toBeDefined();
    expect(SEVERITY_COLORS.low).toBeDefined();
  });

  describe("formatRelativeTime", () => {
    it("formats seconds ago", () => {
      const now = new Date();
      const thirtySecsAgo = new Date(now.getTime() - 30000).toISOString();
      expect(formatRelativeTime(thirtySecsAgo)).toBe("30s ago");
    });

    it("formats minutes ago", () => {
      const now = new Date();
      const fiveMinAgo = new Date(now.getTime() - 5 * 60000).toISOString();
      expect(formatRelativeTime(fiveMinAgo)).toBe("5m ago");
    });

    it("formats hours ago", () => {
      const now = new Date();
      const twoHoursAgo = new Date(now.getTime() - 2 * 3600000).toISOString();
      expect(formatRelativeTime(twoHoursAgo)).toBe("2h ago");
    });

    it("formats days ago", () => {
      const now = new Date();
      const threeDaysAgo = new Date(now.getTime() - 3 * 86400000).toISOString();
      expect(formatRelativeTime(threeDaysAgo)).toBe("3d ago");
    });
  });
});
