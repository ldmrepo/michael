/**
 * A2A Client
 *
 * Client for communicating with other A2A-compatible agents.
 */

import { log } from '../utils/logger.js';
import {
  AgentCard,
  JSONRPCRequest,
  JSONRPCResponse,
  A2AMessage,
  Task,
  MessageSendResult,
  TasksGetResult,
  TasksCancelResult,
  TasksListResult,
  createTextMessage,
  extractTextFromMessage,
} from './types.js';

// --- Configuration ---

export interface A2AClientConfig {
  /** Request timeout in milliseconds */
  timeoutMs?: number;
  /** Retry settings */
  retry?: {
    maxRetries: number;
    baseDelayMs: number;
  };
  /** Authentication */
  auth?: {
    type: 'bearer' | 'apiKey';
    token?: string;
    apiKey?: string;
    headerName?: string;
  };
}

// --- A2A Client ---

/**
 * A2A Protocol Client
 *
 * @example
 * ```ts
 * const client = new A2AClient({
 *   timeoutMs: 30000,
 *   auth: { type: 'bearer', token: 'xxx' },
 * });
 *
 * // Get agent card
 * const card = await client.getAgentCard('https://agent.example.com');
 *
 * // Send message
 * const task = await client.sendMessage('https://agent.example.com', {
 *   role: 'user',
 *   parts: [{ type: 'text', text: 'Hello!' }],
 * });
 *
 * // Wait for completion
 * const result = await client.waitForTask('https://agent.example.com', task.id);
 * ```
 */
export class A2AClient {
  private config: Required<A2AClientConfig>;
  private cardCache = new Map<string, { card: AgentCard; expiresAt: number }>();
  private cardCacheTtlMs = 5 * 60 * 1000; // 5 minutes

  constructor(config: A2AClientConfig = {}) {
    this.config = {
      timeoutMs: config.timeoutMs || 30000,
      retry: config.retry || { maxRetries: 3, baseDelayMs: 1000 },
      auth: config.auth || { type: 'bearer' },
    };
  }

  /**
   * Fetch Agent Card from an agent
   */
  async getAgentCard(agentUrl: string): Promise<AgentCard> {
    // Check cache
    const cached = this.cardCache.get(agentUrl);
    if (cached && Date.now() < cached.expiresAt) {
      return cached.card;
    }

    const url = new URL('/.well-known/agent.json', agentUrl);
    log('debug', `📥 Fetching agent card from ${url}`);

    const response = await this.fetchWithRetry(url.toString(), {
      method: 'GET',
    });

    const card = (await response.json()) as AgentCard;

    // Cache the card
    this.cardCache.set(agentUrl, {
      card,
      expiresAt: Date.now() + this.cardCacheTtlMs,
    });

    log('debug', `✅ Got agent card: ${card.name}`);
    return card;
  }

  /**
   * Send a message to an agent
   */
  async sendMessage(
    agentUrl: string,
    message: A2AMessage,
    metadata?: Record<string, unknown>
  ): Promise<Task> {
    const response = await this.jsonRpcCall(agentUrl, 'message/send', {
      message,
      metadata,
    });

    const result = response.result as MessageSendResult;
    return result.task;
  }

  /**
   * Send a text message to an agent
   */
  async sendText(
    agentUrl: string,
    text: string,
    metadata?: Record<string, unknown>
  ): Promise<Task> {
    return this.sendMessage(agentUrl, createTextMessage('user', text), metadata);
  }

  /**
   * Get task status
   */
  async getTask(agentUrl: string, taskId: string): Promise<Task> {
    const response = await this.jsonRpcCall(agentUrl, 'tasks/get', { taskId });
    const result = response.result as TasksGetResult;
    return result.task;
  }

  /**
   * Cancel a task
   */
  async cancelTask(agentUrl: string, taskId: string): Promise<Task> {
    const response = await this.jsonRpcCall(agentUrl, 'tasks/cancel', { taskId });
    const result = response.result as TasksCancelResult;
    return result.task;
  }

  /**
   * List tasks
   */
  async listTasks(
    agentUrl: string,
    options?: { status?: string; limit?: number; offset?: number }
  ): Promise<{ tasks: Task[]; total: number }> {
    const response = await this.jsonRpcCall(agentUrl, 'tasks/list', options || {});
    const result = response.result as TasksListResult;
    return result;
  }

  /**
   * Wait for a task to complete
   */
  async waitForTask(
    agentUrl: string,
    taskId: string,
    options?: { pollIntervalMs?: number; timeoutMs?: number }
  ): Promise<Task> {
    const pollInterval = options?.pollIntervalMs || 1000;
    const timeout = options?.timeoutMs || 60000;
    const startTime = Date.now();

    while (Date.now() - startTime < timeout) {
      const task = await this.getTask(agentUrl, taskId);

      if (
        task.status === 'completed' ||
        task.status === 'failed' ||
        task.status === 'cancelled'
      ) {
        return task;
      }

      await this.sleep(pollInterval);
    }

    throw new Error(`Task ${taskId} timed out after ${timeout}ms`);
  }

  /**
   * Send message and wait for response (convenience method)
   */
  async chat(
    agentUrl: string,
    text: string,
    metadata?: Record<string, unknown>
  ): Promise<string> {
    const task = await this.sendText(agentUrl, text, metadata);
    const completedTask = await this.waitForTask(agentUrl, task.id);

    if (completedTask.status === 'failed') {
      throw new Error(completedTask.error || 'Task failed');
    }

    if (completedTask.status === 'cancelled') {
      throw new Error('Task was cancelled');
    }

    if (!completedTask.output) {
      return '';
    }

    return extractTextFromMessage(completedTask.output);
  }

  /**
   * Make a JSON-RPC call
   */
  private async jsonRpcCall(
    agentUrl: string,
    method: string,
    params: Record<string, unknown>
  ): Promise<JSONRPCResponse> {
    const request: JSONRPCRequest = {
      jsonrpc: '2.0',
      id: this.generateRequestId(),
      method,
      params,
    };

    log('debug', `📤 A2A call: ${method} to ${agentUrl}`);

    const response = await this.fetchWithRetry(agentUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    const jsonResponse = (await response.json()) as JSONRPCResponse;

    if (jsonResponse.error) {
      throw new Error(`A2A error: ${jsonResponse.error.message} (${jsonResponse.error.code})`);
    }

    return jsonResponse;
  }

  /**
   * Fetch with retry logic
   */
  private async fetchWithRetry(
    url: string,
    options: RequestInit
  ): Promise<Response> {
    const { maxRetries, baseDelayMs } = this.config.retry;

    // Add auth headers
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string>),
    };

    if (this.config.auth.type === 'bearer' && this.config.auth.token) {
      headers['Authorization'] = `Bearer ${this.config.auth.token}`;
    } else if (this.config.auth.type === 'apiKey' && this.config.auth.apiKey) {
      const headerName = this.config.auth.headerName || 'X-API-Key';
      headers[headerName] = this.config.auth.apiKey;
    }

    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(
          () => controller.abort(),
          this.config.timeoutMs
        );

        const response = await fetch(url, {
          ...options,
          headers,
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return response;
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));
        log('warn', `A2A request failed (attempt ${attempt + 1}): ${lastError.message}`);

        if (attempt < maxRetries) {
          const delay = baseDelayMs * Math.pow(2, attempt);
          await this.sleep(delay);
        }
      }
    }

    throw lastError || new Error('Request failed');
  }

  /**
   * Generate unique request ID
   */
  private generateRequestId(): string {
    return `req_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }

  /**
   * Sleep for specified milliseconds
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Clear agent card cache
   */
  clearCache(): void {
    this.cardCache.clear();
  }
}

// --- Factory Function ---

/**
 * Create an A2A client instance
 */
export function createA2AClient(config?: A2AClientConfig): A2AClient {
  return new A2AClient(config);
}
