import { WebSocketMessage } from "@/types";

export type MessageHandler = (message: WebSocketMessage) => void;
export type ConnectionHandler = () => void;

export interface WebSocketClientOptions {
  url?: string;
  maxReconnectDelay?: number;
  initialReconnectDelay?: number;
}

const DEFAULT_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";
const DEFAULT_MAX_DELAY = 30000;
const DEFAULT_INITIAL_DELAY = 1000;

export class CrisisWebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private maxReconnectDelay: number;
  private initialReconnectDelay: number;
  private currentDelay: number;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private messageHandlers: Set<MessageHandler> = new Set();
  private connectHandlers: Set<ConnectionHandler> = new Set();
  private disconnectHandlers: Set<ConnectionHandler> = new Set();
  private _isConnected = false;
  private shouldReconnect = true;

  constructor(options: WebSocketClientOptions = {}) {
    this.url = options.url || DEFAULT_URL;
    this.maxReconnectDelay = options.maxReconnectDelay || DEFAULT_MAX_DELAY;
    this.initialReconnectDelay = options.initialReconnectDelay || DEFAULT_INITIAL_DELAY;
    this.currentDelay = this.initialReconnectDelay;
  }

  get isConnected(): boolean {
    return this._isConnected;
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    this.shouldReconnect = true;
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      this._isConnected = true;
      this.currentDelay = this.initialReconnectDelay;
      this.connectHandlers.forEach((handler) => handler());
    };

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        if (message.type && message.data && message.timestamp) {
          this.messageHandlers.forEach((handler) => handler(message));
        }
      } catch {
        // ignore malformed messages
      }
    };

    this.ws.onclose = () => {
      this._isConnected = false;
      this.disconnectHandlers.forEach((handler) => handler());
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      // onclose will fire after onerror
    };
  }

  disconnect(): void {
    this.shouldReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this._isConnected = false;
  }

  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.add(handler);
    return () => this.messageHandlers.delete(handler);
  }

  onConnect(handler: ConnectionHandler): () => void {
    this.connectHandlers.add(handler);
    return () => this.connectHandlers.delete(handler);
  }

  onDisconnect(handler: ConnectionHandler): () => void {
    this.disconnectHandlers.add(handler);
    return () => this.disconnectHandlers.delete(handler);
  }

  private scheduleReconnect(): void {
    if (!this.shouldReconnect) return;

    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, this.currentDelay);

    this.currentDelay = Math.min(this.currentDelay * 2, this.maxReconnectDelay);
  }
}
