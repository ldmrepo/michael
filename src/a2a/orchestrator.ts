/**
 * A2A Task Orchestrator
 *
 * Coordinates multi-agent tasks and manages agent discovery.
 */

import { log } from '../utils/logger.js';
import { A2AClient, createA2AClient, A2AClientConfig } from './client.js';
import { AgentCard, Task, A2AMessage, createTextMessage } from './types.js';

// --- Configuration ---

export interface OrchestratorConfig {
  /** A2A client configuration */
  clientConfig?: A2AClientConfig;
  /** Agent registry */
  agentRegistry?: Map<string, string>; // name -> url
}

// --- Agent Registration ---

/**
 * Registered agent info
 */
export interface RegisteredAgent {
  name: string;
  url: string;
  card?: AgentCard;
  lastHealthCheck?: number;
  healthy: boolean;
}

// --- Orchestration Types ---

/**
 * Multi-agent task
 */
export interface MultiAgentTask {
  id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  steps: TaskStep[];
  results: Map<string, Task>;
  createdAt: number;
  updatedAt: number;
  error?: string;
}

/**
 * Task step
 */
export interface TaskStep {
  id: string;
  agentName: string;
  message: A2AMessage;
  dependsOn?: string[]; // IDs of steps that must complete first
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  result?: Task;
  error?: string;
}

// --- Orchestrator ---

/**
 * A2A Task Orchestrator
 *
 * @example
 * ```ts
 * const orchestrator = new A2AOrchestrator();
 *
 * // Register agents
 * orchestrator.registerAgent('calendar', 'https://calendar-agent.example.com');
 * orchestrator.registerAgent('weather', 'https://weather-agent.example.com');
 *
 * // Run multi-agent workflow
 * const result = await orchestrator.runWorkflow([
 *   { agent: 'weather', message: '오늘 서울 날씨는?' },
 *   { agent: 'calendar', message: '내일 일정 확인해줘', dependsOn: ['step_0'] },
 * ]);
 * ```
 */
export class A2AOrchestrator {
  private client: A2AClient;
  private agents = new Map<string, RegisteredAgent>();
  private tasks = new Map<string, MultiAgentTask>();
  private healthCheckInterval: NodeJS.Timeout | null = null;

  constructor(config: OrchestratorConfig = {}) {
    this.client = createA2AClient(config.clientConfig);

    // Register initial agents
    if (config.agentRegistry) {
      for (const [name, url] of config.agentRegistry) {
        this.registerAgent(name, url);
      }
    }

    // Start health checks
    this.healthCheckInterval = setInterval(
      () => this.checkAgentHealth(),
      60000 // Every minute
    );
  }

  /**
   * Register an agent
   */
  registerAgent(name: string, url: string): void {
    this.agents.set(name, {
      name,
      url,
      healthy: true, // Assume healthy until checked
    });
    log('info', `📝 Registered agent: ${name} at ${url}`);
  }

  /**
   * Unregister an agent
   */
  unregisterAgent(name: string): void {
    this.agents.delete(name);
    log('info', `🗑️ Unregistered agent: ${name}`);
  }

  /**
   * Get registered agent by name
   */
  getAgent(name: string): RegisteredAgent | undefined {
    return this.agents.get(name);
  }

  /**
   * Get all registered agents
   */
  getAllAgents(): RegisteredAgent[] {
    return Array.from(this.agents.values());
  }

  /**
   * Get healthy agents only
   */
  getHealthyAgents(): RegisteredAgent[] {
    return Array.from(this.agents.values()).filter((a) => a.healthy);
  }

  /**
   * Discover agent capabilities
   */
  async discoverAgent(name: string): Promise<AgentCard | null> {
    const agent = this.agents.get(name);
    if (!agent) {
      log('warn', `Agent not found: ${name}`);
      return null;
    }

    try {
      const card = await this.client.getAgentCard(agent.url);
      agent.card = card;
      agent.healthy = true;
      agent.lastHealthCheck = Date.now();
      return card;
    } catch (error) {
      log('error', `Failed to discover agent ${name}: ${error}`);
      agent.healthy = false;
      return null;
    }
  }

  /**
   * Send message to a specific agent
   */
  async sendToAgent(
    agentName: string,
    text: string,
    metadata?: Record<string, unknown>
  ): Promise<string> {
    const agent = this.agents.get(agentName);
    if (!agent) {
      throw new Error(`Agent not found: ${agentName}`);
    }

    if (!agent.healthy) {
      throw new Error(`Agent unhealthy: ${agentName}`);
    }

    return this.client.chat(agent.url, text, metadata);
  }

  /**
   * Run a multi-agent workflow
   */
  async runWorkflow(
    steps: Array<{
      agent: string;
      message: string;
      dependsOn?: string[];
    }>
  ): Promise<MultiAgentTask> {
    const taskId = this.generateTaskId();
    const now = Date.now();

    // Create task steps
    const taskSteps: TaskStep[] = steps.map((step, index) => ({
      id: `step_${index}`,
      agentName: step.agent,
      message: createTextMessage('user', step.message),
      dependsOn: step.dependsOn,
      status: 'pending',
    }));

    // Create multi-agent task
    const task: MultiAgentTask = {
      id: taskId,
      status: 'pending',
      steps: taskSteps,
      results: new Map(),
      createdAt: now,
      updatedAt: now,
    };

    this.tasks.set(taskId, task);

    // Execute workflow
    try {
      task.status = 'running';
      await this.executeWorkflow(task);
      task.status = 'completed';
    } catch (error) {
      task.status = 'failed';
      task.error = error instanceof Error ? error.message : String(error);
    }

    task.updatedAt = Date.now();
    return task;
  }

  /**
   * Execute workflow steps
   */
  private async executeWorkflow(task: MultiAgentTask): Promise<void> {
    const completedSteps = new Set<string>();

    while (true) {
      // Find steps that can be executed
      const readySteps = task.steps.filter(
        (step) =>
          step.status === 'pending' &&
          (!step.dependsOn ||
            step.dependsOn.every((dep) => completedSteps.has(dep)))
      );

      if (readySteps.length === 0) {
        // Check if all steps are complete
        const allDone = task.steps.every(
          (s) =>
            s.status === 'completed' ||
            s.status === 'failed' ||
            s.status === 'skipped'
        );
        if (allDone) break;

        // Check for deadlock
        const hasPending = task.steps.some((s) => s.status === 'pending');
        if (hasPending) {
          throw new Error('Workflow deadlock: pending steps with unmet dependencies');
        }
        break;
      }

      // Execute ready steps in parallel
      await Promise.all(
        readySteps.map(async (step) => {
          try {
            step.status = 'running';
            const agent = this.agents.get(step.agentName);

            if (!agent || !agent.healthy) {
              step.status = 'failed';
              step.error = `Agent unavailable: ${step.agentName}`;
              return;
            }

            // Build context from dependent steps
            const context = this.buildStepContext(task, step);
            const messageWithContext = this.injectContext(step.message, context);

            // Execute step
            const agentTask = await this.client.sendMessage(
              agent.url,
              messageWithContext
            );

            // Wait for completion
            const result = await this.client.waitForTask(agent.url, agentTask.id);

            step.result = result;
            step.status = result.status.state === 'completed' ? 'completed' : 'failed';
            if (result.error) {
              step.error = result.error;
            }

            task.results.set(step.id, result);
            completedSteps.add(step.id);
          } catch (error) {
            step.status = 'failed';
            step.error = error instanceof Error ? error.message : String(error);
          }
        })
      );

      task.updatedAt = Date.now();
    }
  }

  /**
   * Build context from dependent steps
   */
  private buildStepContext(
    task: MultiAgentTask,
    step: TaskStep
  ): Record<string, string> {
    const context: Record<string, string> = {};

    if (!step.dependsOn) return context;

    for (const depId of step.dependsOn) {
      const depResult = task.results.get(depId);
      // Get last assistant message from history
      const history = depResult?.history || [];
      const lastAssistantMessage = history.filter((m: { role: string }) => m.role === 'assistant').pop();
      if (lastAssistantMessage) {
        const text = lastAssistantMessage.parts
          .filter((p: { type: string }) => p.type === 'text')
          .map((p: { type: string; text?: string }) => p.text || '')
          .join('\n');
        context[depId] = text;
      }
    }

    return context;
  }

  /**
   * Inject context into message
   */
  private injectContext(
    message: A2AMessage,
    context: Record<string, string>
  ): A2AMessage {
    if (Object.keys(context).length === 0) {
      return message;
    }

    // Add context as a prefix to the message
    const contextText = Object.entries(context)
      .map(([key, value]) => `[이전 결과 (${key})]: ${value}`)
      .join('\n');

    const originalText = message.parts
      .filter((p) => p.type === 'text')
      .map((p) => (p as { text: string }).text)
      .join('\n');

    return createTextMessage(
      message.role,
      `${contextText}\n\n[요청]: ${originalText}`
    );
  }

  /**
   * Check health of all agents
   */
  private async checkAgentHealth(): Promise<void> {
    for (const [name, agent] of this.agents) {
      try {
        await this.client.getAgentCard(agent.url);
        agent.healthy = true;
        agent.lastHealthCheck = Date.now();
      } catch {
        agent.healthy = false;
        log('warn', `Agent ${name} health check failed`);
      }
    }
  }

  /**
   * Get task by ID
   */
  getTask(taskId: string): MultiAgentTask | undefined {
    return this.tasks.get(taskId);
  }

  /**
   * Generate unique task ID
   */
  private generateTaskId(): string {
    return `multi_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }

  /**
   * Destroy orchestrator and cleanup
   */
  destroy(): void {
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
      this.healthCheckInterval = null;
    }
    this.agents.clear();
    this.tasks.clear();
  }
}

// --- Factory Function ---

/**
 * Create an A2A orchestrator instance
 */
export function createOrchestrator(config?: OrchestratorConfig): A2AOrchestrator {
  return new A2AOrchestrator(config);
}
