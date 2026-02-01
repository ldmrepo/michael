/**
 * Web Channel
 *
 * WebSocket-based channel for web clients.
 * Supports AG-UI event streaming and A2UI rendering.
 */

import { WebSocket } from 'ws';
import { log } from '../utils/logger.js';
import { AGUIEventType } from '../core/events.js';

// --- Configuration ---

export interface WebChannelConfig {
  /** Gateway WebSocket URL */
  gatewayUrl: string;
  /** Channel identifier */
  channelId?: string;
  /** Reconnection settings */
  reconnect?: {
    enabled: boolean;
    maxRetries: number;
    baseDelayMs: number;
  };
}

// --- Message Types ---

/**
 * Message sent to/from Gateway
 */
export interface WebChannelMessage {
  from: 'web' | 'agent';
  to: 'agent' | 'web';
  userId: string;
  content: string;
  metadata?: Record<string, unknown>;
  // AG-UI fields
  eventType?: AGUIEventType;
  threadId?: string;
  runId?: string;
  messageId?: string;
  delta?: string;
  toolCallId?: string;
  toolCallName?: string;
  errorMessage?: string;
  errorCode?: string;
  // A2UI fields
  a2ui?: unknown;
}

// --- Event Handlers ---

export interface WebChannelEventHandlers {
  onConnect?: () => void;
  onDisconnect?: (code: number, reason: string) => void;
  onError?: (error: Error) => void;
  onMessage?: (message: WebChannelMessage) => void;
  // AG-UI event handlers
  onRunStarted?: (threadId: string, runId: string) => void;
  onRunFinished?: (threadId: string, runId: string) => void;
  onRunError?: (threadId: string, runId: string, error: string, code?: string) => void;
  onTextMessageStart?: (messageId: string, role: string) => void;
  onTextMessageContent?: (messageId: string, delta: string) => void;
  onTextMessageEnd?: (messageId: string) => void;
  onToolCallStart?: (toolCallId: string, toolName: string) => void;
  onToolCallEnd?: (toolCallId: string) => void;
  // A2UI event handlers
  onA2UISurfaceUpdate?: (surfaceId: string, components: unknown[]) => void;
  onA2UIDataUpdate?: (modelId: string, data: unknown) => void;
}

// --- Connection State ---

export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting';

// --- Web Channel Class ---

/**
 * Web Channel for browser-based clients
 *
 * @example
 * ```ts
 * const channel = new WebChannel({
 *   gatewayUrl: 'ws://localhost:18789',
 *   channelId: 'web_client_1',
 * });
 *
 * channel.on('onTextMessageContent', (messageId, delta) => {
 *   console.log('Received:', delta);
 * });
 *
 * await channel.connect();
 * channel.sendMessage('user_123', 'Hello, Michael!');
 * ```
 */
export class WebChannel {
  private config: Required<WebChannelConfig>;
  private ws: WebSocket | null = null;
  private handlers: WebChannelEventHandlers = {};
  private state: ConnectionState = 'disconnected';
  private retryCount = 0;
  private reconnectTimer: NodeJS.Timeout | null = null;

  constructor(config: WebChannelConfig) {
    this.config = {
      gatewayUrl: config.gatewayUrl,
      channelId: config.channelId || `web_${Date.now()}_${Math.random().toString(36).substring(7)}`,
      reconnect: config.reconnect || {
        enabled: true,
        maxRetries: 5,
        baseDelayMs: 1000,
      },
    };
  }

  // --- Public API ---

  /**
   * Get current connection state
   */
  getState(): ConnectionState {
    return this.state;
  }

  /**
   * Get channel ID
   */
  getChannelId(): string {
    return this.config.channelId;
  }

  /**
   * Register event handlers
   */
  on<K extends keyof WebChannelEventHandlers>(
    event: K,
    handler: WebChannelEventHandlers[K]
  ): void {
    this.handlers[event] = handler;
  }

  /**
   * Connect to Gateway
   */
  async connect(): Promise<void> {
    if (this.state === 'connected' || this.state === 'connecting') {
      log('warn', `WebChannel already ${this.state}`);
      return;
    }

    this.state = 'connecting';
    log('info', `🌐 WebChannel connecting to ${this.config.gatewayUrl}...`);

    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.config.gatewayUrl);

        this.ws.on('open', () => {
          this.state = 'connected';
          this.retryCount = 0;
          log('info', `✅ WebChannel connected: ${this.config.channelId}`);
          this.handlers.onConnect?.();
          resolve();
        });

        this.ws.on('message', (data) => {
          this.handleMessage(data);
        });

        this.ws.on('close', (code, reason) => {
          const reasonStr = reason.toString();
          log('info', `🔌 WebChannel disconnected: ${code} ${reasonStr}`);
          this.state = 'disconnected';
          this.handlers.onDisconnect?.(code, reasonStr);
          this.attemptReconnect();
        });

        this.ws.on('error', (error) => {
          log('error', `❌ WebChannel error: ${error.message}`);
          this.handlers.onError?.(error);
          if (this.state === 'connecting') {
            reject(error);
          }
        });
      } catch (error) {
        this.state = 'disconnected';
        reject(error);
      }
    });
  }

  /**
   * Disconnect from Gateway
   */
  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.state = 'disconnected';
    log('info', '👋 WebChannel disconnected');
  }

  /**
   * Send a message to the agent
   */
  sendMessage(userId: string, content: string, metadata?: Record<string, unknown>): void {
    if (!this.ws || this.state !== 'connected') {
      log('error', 'Cannot send message: WebChannel not connected');
      return;
    }

    const message: WebChannelMessage = {
      from: 'web',
      to: 'agent',
      userId,
      content,
      metadata,
    };

    this.ws.send(JSON.stringify(message));
    log('debug', `📤 WebChannel sent: ${content.substring(0, 50)}...`);
  }

  /**
   * Send raw message to Gateway
   */
  sendRaw(message: WebChannelMessage): void {
    if (!this.ws || this.state !== 'connected') {
      log('error', 'Cannot send message: WebChannel not connected');
      return;
    }

    this.ws.send(JSON.stringify(message));
  }

  // --- Private Methods ---

  /**
   * Handle incoming message from Gateway
   */
  private handleMessage(data: unknown): void {
    try {
      const dataStr = Buffer.isBuffer(data) ? data.toString() : String(data);
      const message: WebChannelMessage = JSON.parse(dataStr);

      // Call generic message handler
      this.handlers.onMessage?.(message);

      // Handle AG-UI events
      if (message.eventType) {
        this.handleAGUIEvent(message);
      }

      // Handle A2UI messages (may come without eventType)
      if (message.a2ui) {
        this.handleA2UIEvent(message);
      }
    } catch (error) {
      log('error', `Failed to parse WebChannel message: ${error}`);
    }
  }

  /**
   * Handle AG-UI events
   */
  private handleAGUIEvent(message: WebChannelMessage): void {
    const { eventType, threadId, runId, messageId, delta, toolCallId, toolCallName, errorMessage, errorCode } = message;

    switch (eventType) {
      // Run lifecycle events
      case 'RUN_STARTED':
        this.handlers.onRunStarted?.(threadId!, runId!);
        break;
      case 'RUN_FINISHED':
        this.handlers.onRunFinished?.(threadId!, runId!);
        break;
      case 'RUN_ERROR':
        this.handlers.onRunError?.(threadId!, runId!, errorMessage!, errorCode);
        break;

      // Text message events
      case 'TEXT_MESSAGE_START':
        this.handlers.onTextMessageStart?.(messageId!, 'assistant');
        break;
      case 'TEXT_MESSAGE_CONTENT':
        this.handlers.onTextMessageContent?.(messageId!, delta!);
        break;
      case 'TEXT_MESSAGE_END':
        this.handlers.onTextMessageEnd?.(messageId!);
        break;

      // Tool call events
      case 'TOOL_CALL_START':
        this.handlers.onToolCallStart?.(toolCallId!, toolCallName!);
        break;
      case 'TOOL_CALL_END':
        this.handlers.onToolCallEnd?.(toolCallId!);
        break;

      // A2UI events (via TOOL_CALL_RESULT with A2UI MIME type)
      default:
        // Check for A2UI content in message
        if (message.a2ui) {
          this.handleA2UIEvent(message);
        }
    }
  }

  /**
   * Handle A2UI events
   */
  private handleA2UIEvent(message: WebChannelMessage): void {
    const a2ui = message.a2ui as Record<string, unknown>;

    if (!a2ui || typeof a2ui !== 'object') {
      return;
    }

    const type = a2ui.type as string;

    switch (type) {
      case 'surfaceUpdate':
        this.handlers.onA2UISurfaceUpdate?.(
          a2ui.surfaceId as string,
          a2ui.components as unknown[]
        );
        break;
      case 'dataModelUpdate':
        this.handlers.onA2UIDataUpdate?.(
          a2ui.modelId as string,
          a2ui.data
        );
        break;
    }
  }

  /**
   * Attempt to reconnect with exponential backoff
   */
  private attemptReconnect(): void {
    if (!this.config.reconnect.enabled) {
      return;
    }

    if (this.retryCount >= this.config.reconnect.maxRetries) {
      log('error', `WebChannel max reconnection attempts reached (${this.retryCount})`);
      return;
    }

    this.retryCount++;
    const delay = this.config.reconnect.baseDelayMs * Math.pow(2, this.retryCount - 1);

    log('info', `🔄 WebChannel reconnecting in ${delay}ms (attempt ${this.retryCount}/${this.config.reconnect.maxRetries})`);

    this.state = 'reconnecting';

    this.reconnectTimer = setTimeout(async () => {
      try {
        await this.connect();
      } catch (error) {
        log('error', `WebChannel reconnection failed: ${error}`);
      }
    }, delay);
  }
}

// --- Factory Function ---

/**
 * Create a WebChannel instance
 */
export function createWebChannel(config: WebChannelConfig): WebChannel {
  return new WebChannel(config);
}
