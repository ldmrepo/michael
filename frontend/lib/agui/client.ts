/**
 * AG-UI Client
 *
 * High-level client for AG-UI protocol communication.
 * Manages the connection lifecycle, event handling, and A2UI rendering state.
 */

import {
  AGUIEvent,
  AGUIState,
  AGUIStatus,
  A2UI_MIME_TYPE,
  ToolCallRequestEvent,
  ToolCallResultEvent,
} from './types';
import { parseAGUIStream, AGUIParseResult } from './parser';
import { createToolResultMessage, ToolResultMessage } from './events';
import {
  Surface,
  A2UIMessage,
  handleA2UIMessage,
  createEmptySurface,
} from '@/components/a2ui';

// --- Client Options ---

/**
 * Options for configuring the AG-UI client
 */
export interface AGUIClientOptions {
  /** Base URL for the backend API */
  baseUrl: string;

  /** Default surface ID (default: 'main') */
  surfaceId?: string;

  // --- Event Callbacks ---

  /** Called when text content is streamed */
  onTextDelta?: (delta: string, messageId: string) => void;

  /** Called when A2UI message is received */
  onA2UIMessage?: (message: A2UIMessage, surface: Surface) => void;

  /** Called when surface state changes */
  onSurfaceUpdate?: (surface: Surface) => void;

  /** Called when run state changes */
  onStateChange?: (state: AGUIState) => void;

  /** Called when a frontend tool request is received */
  onToolRequest?: (
    toolName: string,
    args: Record<string, unknown>,
    toolCallId: string
  ) => Promise<unknown>;

  /** Called when an error occurs */
  onError?: (error: Error) => void;

  /** Called when the run completes */
  onComplete?: (surface: Surface) => void;
}

// --- Client Class ---

/**
 * AG-UI Client for managing agent communication
 *
 * @example
 * ```ts
 * const client = new AGUIClient({
 *   baseUrl: '/api',
 *   onSurfaceUpdate: (surface) => setSurface(surface),
 *   onComplete: (surface) => addMessage({ role: 'assistant', surface }),
 * });
 *
 * await client.sendMessage('서울에서 부산 KTX');
 * ```
 */
export class AGUIClient {
  private options: AGUIClientOptions;
  private state: AGUIState;
  private surface: Surface;
  private abortController: AbortController | null = null;

  constructor(options: AGUIClientOptions) {
    this.options = options;
    this.state = {
      threadId: null,
      runId: null,
      status: 'idle',
    };
    this.surface = createEmptySurface(options.surfaceId || 'main');
  }

  // --- Public Methods ---

  /**
   * Send a message and process the AG-UI stream response
   */
  async sendMessage(message: string, threadId?: string): Promise<Surface> {
    // Cancel any existing request
    this.cancel();

    this.abortController = new AbortController();
    this.updateState({ status: 'running' });
    this.surface = createEmptySurface(this.options.surfaceId || 'main');

    try {
      const response = await fetch(`${this.options.baseUrl}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          threadId: threadId || this.state.threadId,
        }),
        signal: this.abortController.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No response body');
      }

      await this.processStream(reader);

      return this.surface;
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        // Request was cancelled, not an error
        this.updateState({ status: 'idle' });
        return this.surface;
      }

      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      this.updateState({ status: 'error', error: errorMessage });
      this.options.onError?.(error instanceof Error ? error : new Error(errorMessage));
      throw error;
    }
  }

  /**
   * Cancel the current request
   */
  cancel(): void {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
    this.updateState({ status: 'idle' });
  }

  /**
   * Get the current surface state
   */
  getSurface(): Surface {
    return this.surface;
  }

  /**
   * Get the current run state
   */
  getState(): AGUIState {
    return { ...this.state };
  }

  /**
   * Check if a request is currently in progress
   */
  isRunning(): boolean {
    return this.state.status === 'running';
  }

  // --- Private Methods ---

  /**
   * Process the SSE stream using the AG-UI parser
   */
  private async processStream(
    reader: ReadableStreamDefaultReader<Uint8Array>
  ): Promise<void> {
    for await (const result of parseAGUIStream(reader, {
      surfaceId: this.options.surfaceId,
      onTextDelta: this.options.onTextDelta,
      onA2UIMessage: (msg) => {
        this.options.onA2UIMessage?.(msg, this.surface);
      },
      onToolRequest: (request) => {
        this.handleToolRequest(request);
      },
    })) {
      await this.handleParseResult(result);
    }
  }

  /**
   * Handle a parse result from the stream
   */
  private async handleParseResult(result: AGUIParseResult): Promise<void> {
    // Update state
    this.updateState({
      threadId: result.threadId,
      runId: result.runId,
      status: result.status,
    });

    // Update surface
    this.surface = result.surface;

    // Notify surface update
    if (result.surface.isReady) {
      this.options.onSurfaceUpdate?.(result.surface);
    }

    // Handle completion
    if (result.status === 'completed') {
      this.options.onComplete?.(result.surface);
    }

    // Handle tool requests
    if (result.toolRequest) {
      await this.handleToolRequest(result.toolRequest);
    }
  }

  /**
   * Handle a frontend tool request
   */
  private async handleToolRequest(request: ToolCallRequestEvent): Promise<void> {
    if (!this.options.onToolRequest) {
      console.warn('Tool request received but no handler configured:', request.toolName);
      return;
    }

    try {
      const result = await this.options.onToolRequest(
        request.toolName,
        request.arguments as Record<string, unknown>,
        request.toolCallId
      );

      // Send the result back to the server
      await this.sendToolResult(request.toolCallId, result);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Tool execution failed';
      await this.sendToolResult(request.toolCallId, null, errorMessage);
    }
  }

  /**
   * Send a tool result back to the server
   */
  private async sendToolResult(
    toolCallId: string,
    result: unknown,
    error?: string
  ): Promise<void> {
    if (!this.state.threadId) {
      console.warn('Cannot send tool result: no active thread');
      return;
    }

    const message = createToolResultMessage(
      this.state.threadId,
      toolCallId,
      result,
      error
    );

    try {
      await fetch(`${this.options.baseUrl}/tool/result`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(message),
      });
    } catch (err) {
      console.error('Failed to send tool result:', err);
    }
  }

  /**
   * Update the internal state and notify listeners
   */
  private updateState(partial: Partial<AGUIState>): void {
    this.state = { ...this.state, ...partial };
    this.options.onStateChange?.(this.state);
  }
}

// --- React Hook (Optional Helper) ---

/**
 * Create a simple AG-UI client configuration for React components
 *
 * @example
 * ```ts
 * const [surface, setSurface] = useState<Surface | null>(null);
 *
 * const clientConfig = useAGUIClientConfig({
 *   baseUrl: '/api',
 *   onSurfaceUpdate: setSurface,
 * });
 *
 * const client = new AGUIClient(clientConfig);
 * ```
 */
export function createClientConfig(
  baseUrl: string,
  callbacks: Partial<Omit<AGUIClientOptions, 'baseUrl'>> = {}
): AGUIClientOptions {
  return {
    baseUrl,
    surfaceId: 'main',
    ...callbacks,
  };
}
