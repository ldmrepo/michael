/**
 * A2A Server
 *
 * JSON-RPC 2.0 server implementation for A2A protocol.
 * Handles incoming requests from other agents.
 */

import { log } from '../utils/logger.js';
import {
  JSONRPCRequest,
  JSONRPCResponse,
  Task,
  A2AMessage,
  MessageSendParams,
  MessageSendResult,
  TasksGetParams,
  TasksGetResult,
  TasksCancelParams,
  TasksCancelResult,
  TasksListParams,
  TasksListResult,
  createJSONRPCResponse,
  createJSONRPCError,
  JSON_RPC_ERRORS,
} from './types.js';
import { getMichaelAgentCard } from './agent-card.js';

// --- Configuration ---

export interface A2AServerConfig {
  /** Base URL for the server */
  baseUrl?: string;
  /** Maximum concurrent tasks */
  maxConcurrentTasks?: number;
  /** Task TTL in milliseconds */
  taskTtlMs?: number;
}

// --- Task Handler ---

/**
 * Handler for processing A2A tasks
 */
export interface TaskHandler {
  /**
   * Process a message and return a response
   */
  processMessage(
    message: A2AMessage,
    metadata?: Record<string, unknown>
  ): Promise<A2AMessage>;

  /**
   * Process a message with streaming
   */
  processMessageStream?(
    message: A2AMessage,
    onChunk: (chunk: string) => void,
    metadata?: Record<string, unknown>
  ): Promise<A2AMessage>;
}

// --- A2A Server ---

/**
 * A2A Protocol Server
 *
 * @example
 * ```ts
 * const server = new A2AServer({
 *   baseUrl: 'http://localhost:18789',
 * });
 *
 * server.setHandler({
 *   processMessage: async (message) => {
 *     const response = await agent.chat(message);
 *     return response;
 *   },
 * });
 *
 * // Handle incoming request
 * const response = await server.handleRequest(jsonRpcRequest);
 * ```
 */
export class A2AServer {
  private config: Required<A2AServerConfig>;
  private tasks = new Map<string, Task>();
  private handler: TaskHandler | null = null;
  private cleanupInterval: NodeJS.Timeout | null = null;

  constructor(config: A2AServerConfig = {}) {
    this.config = {
      baseUrl: config.baseUrl || 'http://localhost:18789',
      maxConcurrentTasks: config.maxConcurrentTasks || 100,
      taskTtlMs: config.taskTtlMs || 24 * 60 * 60 * 1000, // 24 hours
    };

    // Cleanup expired tasks every hour
    this.cleanupInterval = setInterval(() => this.cleanupTasks(), 60 * 60 * 1000);
  }

  /**
   * Set the task handler
   */
  setHandler(handler: TaskHandler): void {
    this.handler = handler;
    log('info', '🤖 A2A task handler set');
  }

  /**
   * Handle JSON-RPC request
   */
  async handleRequest(request: JSONRPCRequest): Promise<JSONRPCResponse> {
    const { id, method, params } = request;

    log('debug', `📥 A2A request: ${method}`);

    try {
      switch (method) {
        case 'message/send':
          return await this.handleMessageSend(id, params as unknown as MessageSendParams);

        case 'message/stream':
          // For HTTP, we return task info; streaming happens via SSE
          return await this.handleMessageSend(id, params as unknown as MessageSendParams);

        case 'tasks/get':
          return this.handleTasksGet(id, params as unknown as TasksGetParams);

        case 'tasks/cancel':
          return this.handleTasksCancel(id, params as unknown as TasksCancelParams);

        case 'tasks/list':
          return this.handleTasksList(id, params as TasksListParams);

        default:
          return createJSONRPCError(
            id,
            JSON_RPC_ERRORS.METHOD_NOT_FOUND,
            `Method not found: ${method}`
          );
      }
    } catch (error) {
      log('error', `❌ A2A request error: ${error}`);
      return createJSONRPCError(
        id,
        JSON_RPC_ERRORS.INTERNAL_ERROR,
        error instanceof Error ? error.message : 'Internal error'
      );
    }
  }

  /**
   * Handle message/send method
   */
  private async handleMessageSend(
    id: string | number,
    params: MessageSendParams
  ): Promise<JSONRPCResponse> {
    if (!this.handler) {
      return createJSONRPCError(
        id,
        JSON_RPC_ERRORS.AGENT_UNAVAILABLE,
        'Agent handler not configured'
      );
    }

    if (!params.message) {
      return createJSONRPCError(
        id,
        JSON_RPC_ERRORS.INVALID_PARAMS,
        'Missing required parameter: message'
      );
    }

    // Check task limit
    const workingTasks = Array.from(this.tasks.values()).filter(
      (t) => t.status === 'pending' || t.status === 'working'
    );
    if (workingTasks.length >= this.config.maxConcurrentTasks) {
      return createJSONRPCError(
        id,
        JSON_RPC_ERRORS.RATE_LIMITED,
        'Too many concurrent tasks'
      );
    }

    // Create task
    const task = this.createTask(params.message, params.metadata);

    // Process asynchronously
    this.processTask(task);

    const result: MessageSendResult = { task };
    return createJSONRPCResponse(id, result);
  }

  /**
   * Handle tasks/get method
   */
  private handleTasksGet(
    id: string | number,
    params: TasksGetParams
  ): JSONRPCResponse {
    if (!params.taskId) {
      return createJSONRPCError(
        id,
        JSON_RPC_ERRORS.INVALID_PARAMS,
        'Missing required parameter: taskId'
      );
    }

    const task = this.tasks.get(params.taskId);
    if (!task) {
      return createJSONRPCError(
        id,
        JSON_RPC_ERRORS.TASK_NOT_FOUND,
        `Task not found: ${params.taskId}`
      );
    }

    const result: TasksGetResult = { task };
    return createJSONRPCResponse(id, result);
  }

  /**
   * Handle tasks/cancel method
   */
  private handleTasksCancel(
    id: string | number,
    params: TasksCancelParams
  ): JSONRPCResponse {
    if (!params.taskId) {
      return createJSONRPCError(
        id,
        JSON_RPC_ERRORS.INVALID_PARAMS,
        'Missing required parameter: taskId'
      );
    }

    const task = this.tasks.get(params.taskId);
    if (!task) {
      return createJSONRPCError(
        id,
        JSON_RPC_ERRORS.TASK_NOT_FOUND,
        `Task not found: ${params.taskId}`
      );
    }

    // Only cancel pending or working tasks
    if (task.status === 'pending' || task.status === 'working') {
      task.status = 'cancelled';
      task.updatedAt = new Date().toISOString();
    }

    const result: TasksCancelResult = { task };
    return createJSONRPCResponse(id, result);
  }

  /**
   * Handle tasks/list method
   */
  private handleTasksList(
    id: string | number,
    params: TasksListParams
  ): JSONRPCResponse {
    let tasks = Array.from(this.tasks.values());

    // Filter by status
    if (params.status) {
      tasks = tasks.filter((t) => t.status === params.status);
    }

    // Sort by creation time (newest first)
    tasks.sort(
      (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    );

    const total = tasks.length;

    // Apply pagination
    const offset = params.offset || 0;
    const limit = params.limit || 50;
    tasks = tasks.slice(offset, offset + limit);

    const result: TasksListResult = { tasks, total };
    return createJSONRPCResponse(id, result);
  }

  /**
   * Create a new task
   */
  private createTask(
    message: A2AMessage,
    metadata?: Record<string, unknown>
  ): Task {
    const now = new Date().toISOString();
    const task: Task = {
      id: this.generateTaskId(),
      status: 'pending',
      input: message,
      createdAt: now,
      updatedAt: now,
      metadata,
    };

    this.tasks.set(task.id, task);
    log('debug', `📝 Created task: ${task.id}`);

    return task;
  }

  /**
   * Process a task
   */
  private async processTask(task: Task): Promise<void> {
    if (!this.handler) {
      task.status = 'failed';
      task.error = 'No handler configured';
      task.updatedAt = new Date().toISOString();
      return;
    }

    try {
      task.status = 'working';
      task.updatedAt = new Date().toISOString();

      log('debug', `🔄 Processing task: ${task.id}`);

      const response = await this.handler.processMessage(
        task.input,
        task.metadata
      );

      task.output = response;
      task.status = 'completed';
      task.updatedAt = new Date().toISOString();

      log('debug', `✅ Task completed: ${task.id}`);
    } catch (error) {
      task.status = 'failed';
      task.error = error instanceof Error ? error.message : String(error);
      task.updatedAt = new Date().toISOString();

      log('error', `❌ Task failed: ${task.id} - ${task.error}`);
    }
  }

  /**
   * Get Agent Card JSON
   */
  getAgentCard(): string {
    return JSON.stringify(getMichaelAgentCard(this.config.baseUrl), null, 2);
  }

  /**
   * Get task by ID
   */
  getTask(taskId: string): Task | undefined {
    return this.tasks.get(taskId);
  }

  /**
   * Generate unique task ID
   */
  private generateTaskId(): string {
    return `task_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }

  /**
   * Cleanup expired tasks
   */
  private cleanupTasks(): void {
    const now = Date.now();
    const ttl = this.config.taskTtlMs;

    for (const [id, task] of this.tasks) {
      const taskTime = new Date(task.updatedAt).getTime();
      if (now - taskTime > ttl) {
        this.tasks.delete(id);
        log('debug', `🗑️ Cleaned up task: ${id}`);
      }
    }
  }

  /**
   * Destroy server and cleanup resources
   */
  destroy(): void {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
    }
    this.tasks.clear();
  }
}

// --- Factory Function ---

/**
 * Create an A2A server instance
 */
export function createA2AServer(config?: A2AServerConfig): A2AServer {
  return new A2AServer(config);
}
