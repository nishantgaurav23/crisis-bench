"use client";

import React from "react";

interface NavItem {
  name: string;
  href: string;
  active?: boolean;
}

const navItems: NavItem[] = [
  { name: "Dashboard", href: "/", active: true },
  { name: "Map", href: "/map" },
  { name: "Agents", href: "/agents" },
  { name: "Metrics", href: "/metrics" },
  { name: "Timeline", href: "/timeline" },
];

interface DashboardShellProps {
  children: React.ReactNode;
  isConnected?: boolean;
}

export default function DashboardShell({
  children,
  isConnected = false,
}: DashboardShellProps) {
  return (
    <div className="flex h-screen" data-testid="dashboard-shell">
      {/* Sidebar */}
      <aside
        className="flex w-64 flex-col border-r border-gray-800 bg-gray-900"
        data-testid="sidebar"
      >
        <div className="flex h-16 items-center gap-2 border-b border-gray-800 px-6">
          <h1 className="text-lg font-bold text-white">CRISIS-BENCH</h1>
        </div>
        <nav className="flex-1 px-4 py-4" data-testid="sidebar-nav">
          {navItems.map((item) => (
            <a
              key={item.name}
              href={item.href}
              className={`block rounded-lg px-4 py-2 text-sm ${
                item.active
                  ? "bg-gray-800 text-white"
                  : "text-gray-400 hover:bg-gray-800 hover:text-white"
              }`}
            >
              {item.name}
            </a>
          ))}
        </nav>
      </aside>

      {/* Main content */}
      <div className="flex flex-1 flex-col">
        <header
          className="flex h-16 items-center justify-between border-b border-gray-800 px-6"
          data-testid="header"
        >
          <h2 className="text-sm font-medium text-gray-400">
            Disaster Response Coordination
          </h2>
          <div className="flex items-center gap-2" data-testid="connection-status">
            <span
              className={`h-2 w-2 rounded-full ${
                isConnected ? "bg-green-500" : "bg-red-500"
              }`}
            />
            <span className="text-xs text-gray-500">
              {isConnected ? "Connected" : "Disconnected"}
            </span>
          </div>
        </header>
        <main className="flex-1 overflow-auto p-6" data-testid="main-content">
          {children}
        </main>
      </div>
    </div>
  );
}
