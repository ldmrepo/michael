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
  PushNotificationConfig,
  PushNotificationConfigCreateParams,
  PushNotificationConfigCreateResult,
  PushNotificationConfigGetParams,
  PushNotificationConfigGetResult,
  PushNotificationConfigListParams,
  PushNotificationConfigListResult,
  PushNotificationConfigDeleteParams,
  PushNotificationConfigDeleteResult,
  TaskSubscribeEvent,
  createJSONRPCResponse,
  createJSONRPCError,
  JSON_RPC_ERRORS,
  generateId,
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
/**
 * Subscriber callback for task events
 */
export type TaskSubscriber = (event: TaskSubscribeEvent) => void;

export class A2AServer {
  private config: Required<A2AServerConfig>;
  private tasks = new Map<string, Task>();
  private handler: TaskHandler | null = null;
  private cleanupInterval: NodeJS.Timeout | null = null;
  /** Push notification configs keyed by taskId:configId */
  private pushNotificationConfigs = new Map<string, PushNotificationConfig>();
  /** Task subscribers keyed by taskId */
  private taskSubscribers = new Map<string, Set<TaskSubscriber>>();

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

        // Push notification config methods
        case 'tasks/pushNotificationConfig/create':
          return this.handlePushNotificationConfigCreate(id, params as unknown as PushNotificationConfigCreateParams);

        case 'tasks/pushNotificationConfig/get':
          return this.handlePushNotificationConfigGet(id, params as unknown as PushNotificationConfigGetParams);

        case 'tasks/pushNotificationConfig/list':
          return this.handlePushNotificationConfigList(id, params as unknown as PushNotificationConfigListParams);

        case 'tasks/pushNotificationConfig/delete':
          return this.handlePushNotificationConfigDelete(id, params as unknown as PushNotificationConfigDeleteParams);

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
      (t) => t.status.state === 'pending' || t.status.state === 'working'
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
    if (task.status.state === 'pending' || task.status.state === 'working') {
      const now = new Date().toISOString();
      task.status = { state: 'cancelled', timestamp: now };
      task.updatedAt = now;
      this.notifyTaskSubscribers(task.id, {
        type: 'statusUpdate',
        taskId: task.id,
        status: task.status,
      });
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
      tasks = tasks.filter((t) => t.status.state === params.status);
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
   * Create a new task (v0.3.0 standard)
   */
  private createTask(
    message: A2AMessage,
    metadata?: Record<string, unknown>,
    contextId?: string
  ): Task {
    const now = new Date().toISOString();
    const task: Task = {
      id: generateId('task'),
      contextId,
      status: {
        state: 'pending',
        timestamp: now,
      },
      history: [message],
      createdAt: now,
      updatedAt: now,
      metadata,
    };

    this.tasks.set(task.id, task);
    log('debug', `📝 Created task: ${task.id}`);

    return task;
  }

  /**
   * Process a task (v0.3.0 standard)
   */
  private async processTask(task: Task): Promise<void> {
    if (!this.handler) {
      const now = new Date().toISOString();
      task.status = { state: 'failed', timestamp: now, message: 'No handler configured' };
      task.error = 'No handler configured';
      task.updatedAt = now;
      this.notifyTaskSubscribers(task.id, {
        type: 'statusUpdate',
        taskId: task.id,
        status: task.status,
      });
      return;
    }

    try {
      let now = new Date().toISOString();
      task.status = { state: 'working', timestamp: now };
      task.updatedAt = now;
      this.notifyTaskSubscribers(task.id, {
        type: 'statusUpdate',
        taskId: task.id,
        status: task.status,
      });

      log('debug', `🔄 Processing task: ${task.id}`);

      // Get input from history
      const input = task.history?.[0];
      if (!input) {
        throw new Error('No input message in task history');
      }

      const response = await this.handler.processMessage(input, task.metadata);

      now = new Date().toISOString();
      task.history = [...(task.history || []), response];
      task.status = { state: 'completed', timestamp: now };
      task.updatedAt = now;

      // Notify subscribers
      this.notifyTaskSubscribers(task.id, {
        type: 'message',
        taskId: task.id,
        message: response,
      });
      this.notifyTaskSubscribers(task.id, {
        type: 'statusUpdate',
        taskId: task.id,
        status: task.status,
      });

      log('debug', `✅ Task completed: ${task.id}`);
    } catch (error) {
      const now = new Date().toISOString();
      const errorMessage = error instanceof Error ? error.message : String(error);
      task.status = { state: 'failed', timestamp: now, message: errorMessage };
      task.error = errorMessage;
      task.updatedAt = now;

      this.notifyTaskSubscribers(task.id, {
        type: 'statusUpdate',
        taskId: task.id,
        status: task.status,
      });

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

  // --- Push Notification Config Methods ---

  /**
   * Handle tasks/pushNotificationConfig/create
   */
  private handlePushNotificationConfigCreate(
    id: string | number,
    params: PushNotificationConfigCreateParams
  ): JSONRPCResponse {
    const task = this.tasks.get(params.taskId);
    if (!task) {
      return createJSONRPCError(id, JSON_RPC_ERRORS.TASK_NOT_FOUND, `Task not found: ${params.taskId}`);
    }

    const config: PushNotificationConfig = {
      id: generateId('pnc'),
      taskId: params.taskId,
      url: params.url,
      authentication: params.authentication,
      events: params.events || ['statusUpdate', 'artifactUpdate', 'message'],
      createdAt: new Date().toISOString(),
    };

    this.pushNotificationConfigs.set(`${params.taskId}:${config.id}`, config);
    log('debug', `📌 Created push notification config: ${config.id} for task ${params.taskId}`);

    const result: PushNotificationConfigCreateResult = { config };
    return createJSONRPCResponse(id, result);
  }

  /**
   * Handle tasks/pushNotificationConfig/get
   */
  private handlePushNotificationConfigGet(
    id: string | number,
    params: PushNotificationConfigGetParams
  ): JSONRPCResponse {
    const config = this.pushNotificationConfigs.get(`${params.taskId}:${params.configId}`);
    if (!config) {
      return createJSONRPCError(id, JSON_RPC_ERRORS.CONFIG_NOT_FOUND, 'Push notification config not found');
    }

    const result: PushNotificationConfigGetResult = { config };
    return createJSONRPCResponse(id, result);
  }

  /**
   * Handle tasks/pushNotificationConfig/list
   */
  private handlePushNotificationConfigList(
    id: string | number,
    params: PushNotificationConfigListParams
  ): JSONRPCResponse {
    const configs: PushNotificationConfig[] = [];
    for (const [key, config] of this.pushNotificationConfigs) {
      if (key.startsWith(`${params.taskId}:`)) {
        configs.push(config);
      }
    }

    const result: PushNotificationConfigListResult = { configs };
    return createJSONRPCResponse(id, result);
  }

  /**
   * Handle tasks/pushNotificationConfig/delete
   */
  private handlePushNotificationConfigDelete(
    id: string | number,
    params: PushNotificationConfigDeleteParams
  ): JSONRPCResponse {
    const key = `${params.taskId}:${params.configId}`;
    const exists = this.pushNotificationConfigs.has(key);
    if (exists) {
      this.pushNotificationConfigs.delete(key);
      log('debug', `🗑️ Deleted push notification config: ${params.configId}`);
    }

    const result: PushNotificationConfigDeleteResult = { success: exists };
    return createJSONRPCResponse(id, result);
  }

  // --- Task Subscription Methods ---

  /**
   * Subscribe to task updates (for SSE streaming)
   */
  subscribeToTask(taskId: string, callback: TaskSubscriber): () => void {
    if (!this.taskSubscribers.has(taskId)) {
      this.taskSubscribers.set(taskId, new Set());
    }
    this.taskSubscribers.get(taskId)!.add(callback);
    log('debug', `📡 Subscribed to task: ${taskId}`);

    // Return unsubscribe function
    return () => {
      const subscribers = this.taskSubscribers.get(taskId);
      if (subscribers) {
        subscribers.delete(callback);
        if (subscribers.size === 0) {
          this.taskSubscribers.delete(taskId);
        }
      }
      log('debug', `📡 Unsubscribed from task: ${taskId}`);
    };
  }

  /**
   * Notify all subscribers of a task event
   */
  private notifyTaskSubscribers(taskId: string, event: TaskSubscribeEvent): void {
    // Notify in-memory subscribers
    const subscribers = this.taskSubscribers.get(taskId);
    if (subscribers) {
      for (const callback of subscribers) {
        try {
          callback(event);
        } catch (error) {
          log('error', `Error notifying task subscriber: ${error}`);
        }
      }
    }

    // Send push notifications
    this.sendPushNotifications(taskId, event);
  }

  /**
   * Send push notifications for a task event
   */
  private async sendPushNotifications(taskId: string, event: TaskSubscribeEvent): Promise<void> {
    for (const [key, config] of this.pushNotificationConfigs) {
      if (!key.startsWith(`${taskId}:`)) continue;
      if (config.events && !config.events.includes(event.type)) continue;

      try {
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
        };

        if (config.authentication) {
          if (config.authentication.type === 'bearer' && config.authentication.token) {
            headers['Authorization'] = `Bearer ${config.authentication.token}`;
          } else if (config.authentication.type === 'apiKey' && config.authentication.token) {
            headers[config.authentication.headerName || 'X-API-Key'] = config.authentication.token;
          }
        }

        await fetch(config.url, {
          method: 'POST',
          headers,
          body: JSON.stringify(event),
        });
        log('debug', `📤 Sent push notification to ${config.url}`);
      } catch (error) {
        log('error', `Failed to send push notification: ${error}`);
      }
    }
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
    this.pushNotificationConfigs.clear();
    this.taskSubscribers.clear();
  }
}

// --- Factory Function ---

/**
 * Create an A2A server instance
 */
export function createA2AServer(config?: A2AServerConfig): A2AServer {
  return new A2AServer(config);
}
