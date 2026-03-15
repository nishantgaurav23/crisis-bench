import React from "react";
import { render, screen, act } from "@testing-library/react";
import Home from "@/app/page";

// Mock the modules
jest.mock("@/lib/websocket", () => ({
  CrisisWebSocketClient: jest.fn().mockImplementation(() => ({
    connect: jest.fn(),
    disconnect: jest.fn(),
    onConnect: jest.fn().mockReturnValue(jest.fn()),
    onDisconnect: jest.fn().mockReturnValue(jest.fn()),
    onMessage: jest.fn().mockReturnValue(jest.fn()),
  })),
}));

jest.mock("@/lib/api", () => ({
  getHealth: jest.fn().mockReturnValue(new Promise(() => {})), // never resolves — no state update
}));

describe("Home Page", () => {
  it("renders the page title", async () => {
    await act(async () => {
      render(<Home />);
    });
    expect(screen.getByTestId("page-title")).toHaveTextContent("CRISIS-BENCH Dashboard");
  });

  it("renders the dashboard shell with sidebar", async () => {
    await act(async () => {
      render(<Home />);
    });
    expect(screen.getByTestId("dashboard-shell")).toBeInTheDocument();
    expect(screen.getByTestId("sidebar")).toBeInTheDocument();
  });

  it("renders placeholder sections for upcoming components", async () => {
    await act(async () => {
      render(<Home />);
    });
    expect(screen.getByText(/Map — Coming Soon/)).toBeInTheDocument();
    expect(screen.getByText(/Agents — Coming Soon/)).toBeInTheDocument();
    expect(screen.getByText(/Metrics — Coming Soon/)).toBeInTheDocument();
    expect(screen.getByText(/Timeline — Coming Soon/)).toBeInTheDocument();
  });
});
