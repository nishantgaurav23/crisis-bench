import React from "react";
import { render, screen } from "@testing-library/react";
import DashboardShell from "@/components/DashboardShell";

describe("DashboardShell", () => {
  it("renders the shell container", () => {
    render(
      <DashboardShell>
        <p>Test content</p>
      </DashboardShell>
    );

    expect(screen.getByTestId("dashboard-shell")).toBeInTheDocument();
  });

  it("renders sidebar with navigation links", () => {
    render(
      <DashboardShell>
        <p>Test</p>
      </DashboardShell>
    );

    const nav = screen.getByTestId("sidebar-nav");
    expect(nav).toBeInTheDocument();

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Map")).toBeInTheDocument();
    expect(screen.getByText("Agents")).toBeInTheDocument();
    expect(screen.getByText("Metrics")).toBeInTheDocument();
    expect(screen.getByText("Timeline")).toBeInTheDocument();
  });

  it("renders header with CRISIS-BENCH branding", () => {
    render(
      <DashboardShell>
        <p>Test</p>
      </DashboardShell>
    );

    expect(screen.getByText("CRISIS-BENCH")).toBeInTheDocument();
    expect(screen.getByTestId("header")).toBeInTheDocument();
  });

  it("renders children in main content area", () => {
    render(
      <DashboardShell>
        <p data-testid="child">Hello World</p>
      </DashboardShell>
    );

    const main = screen.getByTestId("main-content");
    expect(main).toBeInTheDocument();
    expect(screen.getByTestId("child")).toBeInTheDocument();
    expect(screen.getByText("Hello World")).toBeInTheDocument();
  });

  it("shows Disconnected status by default", () => {
    render(
      <DashboardShell>
        <p>Test</p>
      </DashboardShell>
    );

    expect(screen.getByText("Disconnected")).toBeInTheDocument();
  });

  it("shows Connected status when isConnected is true", () => {
    render(
      <DashboardShell isConnected={true}>
        <p>Test</p>
      </DashboardShell>
    );

    expect(screen.getByText("Connected")).toBeInTheDocument();
  });
});
