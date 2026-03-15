import { CrisisWebSocketClient } from "@/lib/websocket";
import type { WebSocketMessage } from "@/types";

// Mock WebSocket
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  readyState = 0; // CONNECTING

  static readonly OPEN = 1;
  static readonly CLOSED = 3;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  close() {
    this.readyState = 3;
    if (this.onclose) this.onclose();
  }

  // Helper to simulate server events
  simulateOpen() {
    this.readyState = 1;
    if (this.onopen) this.onopen();
  }

  simulateMessage(data: unknown) {
    if (this.onmessage) this.onmessage({ data: JSON.stringify(data) });
  }

  simulateClose() {
    this.readyState = 3;
    if (this.onclose) this.onclose();
  }

  simulateError() {
    if (this.onerror) this.onerror();
  }
}

// Replace global WebSocket
Object.defineProperty(global, "WebSocket", {
  value: MockWebSocket,
  writable: true,
});

beforeEach(() => {
  MockWebSocket.instances = [];
  jest.useFakeTimers();
});

afterEach(() => {
  jest.useRealTimers();
});

describe("CrisisWebSocketClient", () => {
  it("connects to the default URL", () => {
    const client = new CrisisWebSocketClient();
    client.connect();

    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0].url).toBe("ws://localhost:8000/ws");

    client.disconnect();
  });

  it("connects to a custom URL", () => {
    const client = new CrisisWebSocketClient({ url: "ws://custom:9000/ws" });
    client.connect();

    expect(MockWebSocket.instances[0].url).toBe("ws://custom:9000/ws");

    client.disconnect();
  });

  it("sets isConnected to true on open", () => {
    const client = new CrisisWebSocketClient();
    expect(client.isConnected).toBe(false);

    client.connect();
    MockWebSocket.instances[0].simulateOpen();

    expect(client.isConnected).toBe(true);

    client.disconnect();
  });

  it("calls onConnect handler when connected", () => {
    const handler = jest.fn();
    const client = new CrisisWebSocketClient();
    client.onConnect(handler);
    client.connect();

    MockWebSocket.instances[0].simulateOpen();

    expect(handler).toHaveBeenCalledTimes(1);

    client.disconnect();
  });

  it("calls onDisconnect handler when disconnected", () => {
    const handler = jest.fn();
    const client = new CrisisWebSocketClient();
    client.onDisconnect(handler);
    client.connect();

    MockWebSocket.instances[0].simulateOpen();
    MockWebSocket.instances[0].simulateClose();

    expect(handler).toHaveBeenCalledTimes(1);

    client.disconnect();
  });

  it("parses and dispatches valid messages", () => {
    const handler = jest.fn();
    const client = new CrisisWebSocketClient();
    client.onMessage(handler);
    client.connect();

    const msg: WebSocketMessage = {
      type: "disaster.created",
      data: { id: "d-001", type: "cyclone" },
      timestamp: "2026-03-15T00:00:00Z",
      trace_id: "t-001",
    };

    MockWebSocket.instances[0].simulateOpen();
    MockWebSocket.instances[0].simulateMessage(msg);

    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler).toHaveBeenCalledWith(msg);

    client.disconnect();
  });

  it("ignores malformed messages", () => {
    const handler = jest.fn();
    const client = new CrisisWebSocketClient();
    client.onMessage(handler);
    client.connect();

    MockWebSocket.instances[0].simulateOpen();
    // Send invalid JSON
    if (MockWebSocket.instances[0].onmessage) {
      MockWebSocket.instances[0].onmessage({ data: "not json" });
    }

    expect(handler).not.toHaveBeenCalled();

    client.disconnect();
  });

  it("ignores messages missing required fields", () => {
    const handler = jest.fn();
    const client = new CrisisWebSocketClient();
    client.onMessage(handler);
    client.connect();

    MockWebSocket.instances[0].simulateOpen();
    MockWebSocket.instances[0].simulateMessage({ type: "test" }); // missing data + timestamp

    expect(handler).not.toHaveBeenCalled();

    client.disconnect();
  });

  it("reconnects with exponential backoff", () => {
    const client = new CrisisWebSocketClient({
      initialReconnectDelay: 1000,
      maxReconnectDelay: 30000,
    });
    client.connect();

    // First disconnect triggers reconnect after 1s
    MockWebSocket.instances[0].simulateClose();
    expect(MockWebSocket.instances).toHaveLength(1);

    jest.advanceTimersByTime(1000);
    expect(MockWebSocket.instances).toHaveLength(2);

    // Second disconnect triggers reconnect after 2s
    MockWebSocket.instances[1].simulateClose();
    jest.advanceTimersByTime(1999);
    expect(MockWebSocket.instances).toHaveLength(2);
    jest.advanceTimersByTime(1);
    expect(MockWebSocket.instances).toHaveLength(3);

    client.disconnect();
  });

  it("resets delay after successful connection", () => {
    const client = new CrisisWebSocketClient({
      initialReconnectDelay: 1000,
    });
    client.connect();

    // Disconnect and reconnect at 1s
    MockWebSocket.instances[0].simulateClose();
    jest.advanceTimersByTime(1000);

    // Successful connection resets delay
    MockWebSocket.instances[1].simulateOpen();
    MockWebSocket.instances[1].simulateClose();

    // Should reconnect after 1s again (not 2s)
    jest.advanceTimersByTime(1000);
    expect(MockWebSocket.instances).toHaveLength(3);

    client.disconnect();
  });

  it("stops reconnecting after disconnect()", () => {
    const client = new CrisisWebSocketClient({
      initialReconnectDelay: 1000,
    });
    client.connect();
    client.disconnect();

    jest.advanceTimersByTime(10000);
    // Only the initial connect + no reconnects
    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it("unsubscribes handlers via returned function", () => {
    const handler = jest.fn();
    const client = new CrisisWebSocketClient();
    const unsub = client.onMessage(handler);
    client.connect();

    MockWebSocket.instances[0].simulateOpen();

    const msg: WebSocketMessage = {
      type: "agent.status",
      data: {},
      timestamp: "2026-03-15T00:00:00Z",
      trace_id: "t-002",
    };

    MockWebSocket.instances[0].simulateMessage(msg);
    expect(handler).toHaveBeenCalledTimes(1);

    unsub();
    MockWebSocket.instances[0].simulateMessage(msg);
    expect(handler).toHaveBeenCalledTimes(1); // not called again

    client.disconnect();
  });
});
