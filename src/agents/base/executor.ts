/**
 * Base A2UI Agent Executor
 *
 * Abstract base class for A2UI-generating agents.
 * Uses Claude CLI for LLM calls (no API key required with Claude Max subscription).
 */
import { spawn, ChildProcess } from 'child_process';
import {
  A2AMessage,
  createTextMessage,
  extractTextFromMessage,
  MessageRole,
} from '../../a2a/types.js';
import {
  A2UIMessagePayload,
  createTextComponent,
  createSurfaceUpdate,
  createBeginRendering,
} from '../../core/a2ui.js';
import { log } from '../../utils/logger.js';

/**
 * Context for agent execution
 */
export interface AgentExecutorContext {
  /** Unique task identifier */
  taskId: string;
  /** Optional conversation context ID */
  contextId?: string;
  /** Input message from user/orchestrator */
  message: A2AMessage;
  /** Optional metadata */
  metadata?: Record<string, unknown>;
}

/**
 * Event queue interface for streaming responses
 */
export interface EventQueue {
  enqueue(event: unknown): Promise<void>;
}

/**
 * Base class for A2UI-generating agent executors
 *
 * Uses Claude CLI (-p mode) for inference.
 * No API key required when using Claude Max subscription.
 *
 * Subclasses must implement:
 * - AGENT_NAME: Agent identifier
 * - SYSTEM_PROMPT: System instructions for A2UI generation
 * - ARTIFACT_PREFIX: Prefix for generated artifacts
 */
export abstract class BaseA2UIAgentExecutor {
  /** Agent identifier */
  protected abstract readonly AGENT_NAME: string;

  /** System prompt with A2UI generation instructions */
  protected abstract readonly SYSTEM_PROMPT: string;

  /** Prefix for artifact naming */
  protected abstract readonly ARTIFACT_PREFIX: string;

  /** Active CLI processes */
  protected activeProcesses: Set<ChildProcess> = new Set();

  /** Model to use (optional, uses claude default if not set) */
  protected model?: string;

  constructor() {
    // No initialization needed for CLI mode
  }

  /**
   * Execute agent with the given context
   *
   * @param context - Execution context containing task info and input message
   * @returns A2A response message
   */
  async execute(context: AgentExecutorContext): Promise<A2AMessage> {
    const userInput = this.extractUserInput(context.message);

    try {
      // Build full prompt with system instructions
      const fullPrompt = this.buildPrompt(userInput);

      // Execute via Claude CLI
      const responseText = await this.executeClaudeCLI(fullPrompt);

      // Try to parse A2UI JSONL response
      const validMessages = this.validateA2UIResponse(responseText);

      if (validMessages.length > 0) {
        return this.createA2UIMessage(validMessages);
      }

      // Fallback to text response if no valid A2UI found
      return this.buildFallbackResponse(responseText);
    } catch (error) {
      return this.buildErrorResponse(error);
    }
  }

  /**
   * Build full prompt with system instructions
   */
  protected buildPrompt(userInput: string): string {
    return `${this.SYSTEM_PROMPT}

---

사용자 요청: ${userInput}

위 요청에 대해 A2UI JSONL 형식으로 응답하세요. 설명 없이 JSON만 출력하세요.`;
  }

  /**
   * Execute Claude CLI with the given prompt
   *
   * Uses `claude -p` (print mode) with stdin input.
   */
  protected async executeClaudeCLI(prompt: string): Promise<string> {
    return new Promise((resolve, reject) => {
      const args: string[] = ['-p']; // print mode

      // Add model if specified
      if (this.model) {
        args.push('--model', this.model);
      }

      log('debug', `🤖 [${this.AGENT_NAME}] Executing Claude CLI with prompt length: ${prompt.length}`);

      // Spawn Claude CLI process (CLAUDECODE 환경변수 제거하여 중첩 세션 방지)
      const env = { ...process.env };
      delete env.CLAUDECODE;
      delete env.CLAUDE_CODE_ENTRYPOINT;

      let settled = false;
      const proc = spawn('claude', args, {
        stdio: ['pipe', 'pipe', 'pipe'],
        env,
      });
      this.activeProcesses.add(proc);

      // 2분 타임아웃
      const timeout = setTimeout(() => {
        if (!settled) {
          settled = true;
          proc.kill();
          this.activeProcesses.delete(proc);
          reject(new Error(`[${this.AGENT_NAME}] Claude CLI timeout (120s)`));
        }
      }, 120000);

      // Send prompt via stdin
      if (proc.stdin) {
        proc.stdin.write(prompt);
        proc.stdin.end();
      }

      let stdout = '';
      let stderr = '';

      proc.stdout?.on('data', (data) => {
        stdout += data.toString();
      });

      proc.stderr?.on('data', (data) => {
        stderr += data.toString();
        log('warn', `[${this.AGENT_NAME}] stderr: ${data.toString()}`);
      });

      proc.on('close', (code) => {
        clearTimeout(timeout);
        this.activeProcesses.delete(proc);
        if (settled) return;
        settled = true;

        if (code !== 0) {
          log('error', `❌ [${this.AGENT_NAME}] Claude CLI failed with code ${code}: ${stderr}`);
          reject(new Error(`Claude CLI failed: ${stderr}`));
          return;
        }

        // Extract response (remove any system messages)
        const response = this.extractCLIResponse(stdout);
        log('debug', `✅ [${this.AGENT_NAME}] Claude CLI response length: ${response.length}`);
        resolve(response);
      });

      proc.on('error', (error) => {
        clearTimeout(timeout);
        this.activeProcesses.delete(proc);
        if (settled) return;
        settled = true;
        log('error', `❌ [${this.AGENT_NAME}] Claude CLI process error: ${error.message}`);
        reject(error);
      });
    });
  }

  /**
   * Extract actual response from CLI output
   * Removes any CLI system messages or formatting
   */
  protected extractCLIResponse(output: string): string {
    // Claude CLI output is typically clean in -p mode
    // But we may need to handle some edge cases
    return output.trim();
  }

  /**
   * Extract user input text from A2A message
   */
  protected extractUserInput(message: A2AMessage): string {
    return extractTextFromMessage(message);
  }

  /**
   * Validate and extract A2UI messages from response text
   *
   * Expects JSONL format where each line is a valid A2UI message:
   * - surfaceUpdate
   * - dataModelUpdate
   * - beginRendering
   * - deleteSurface
   */
  protected validateA2UIResponse(text: string): A2UIMessagePayload[] {
    const lines = text.split('\n').filter((l) => l.trim());
    const valid: A2UIMessagePayload[] = [];

    for (const line of lines) {
      try {
        const parsed = JSON.parse(line);
        if (this.isValidA2UIMessage(parsed)) {
          valid.push(parsed as A2UIMessagePayload);
        }
      } catch {
        // Skip invalid JSON lines - may be explanation text
      }
    }

    return valid;
  }

  /**
   * Check if object is a valid A2UI message
   */
  protected isValidA2UIMessage(obj: unknown): boolean {
    if (typeof obj !== 'object' || obj === null) {
      return false;
    }

    const message = obj as Record<string, unknown>;
    return (
      'surfaceUpdate' in message ||
      'dataModelUpdate' in message ||
      'beginRendering' in message ||
      'deleteSurface' in message
    );
  }

  /**
   * Create A2A message with A2UI parts
   */
  protected createA2UIMessage(a2uiMessages: A2UIMessagePayload[]): A2AMessage {
    return {
      role: 'assistant' as MessageRole,
      parts: a2uiMessages.map((msg) => ({
        type: 'a2ui' as const,
        a2ui: msg,
      })),
    };
  }

  /**
   * Build fallback response when A2UI parsing fails
   * Converts plain text to A2UI format
   */
  protected buildFallbackResponse(text: string): A2AMessage {
    const trimmedText = text.trim();

    if (!trimmedText) {
      return createTextMessage('assistant', '응답을 생성할 수 없습니다.');
    }

    // Convert plain text to A2UI Text component
    const componentId = `${this.ARTIFACT_PREFIX}_text_${Date.now()}`;
    const textComponent = createTextComponent(trimmedText, componentId);

    const surfaceUpdate = createSurfaceUpdate([textComponent], 'main');
    const beginRendering = createBeginRendering('main', componentId);

    return this.createA2UIMessage([surfaceUpdate, beginRendering]);
  }

  /**
   * Build error response
   */
  protected buildErrorResponse(error: unknown): A2AMessage {
    const message =
      error instanceof Error ? error.message : '알 수 없는 오류가 발생했습니다.';

    const componentId = `${this.ARTIFACT_PREFIX}_error_${Date.now()}`;
    const errorComponent = createTextComponent(`오류: ${message}`, componentId);

    const surfaceUpdate = createSurfaceUpdate([errorComponent], 'main');
    const beginRendering = createBeginRendering('main', componentId);

    return this.createA2UIMessage([surfaceUpdate, beginRendering]);
  }

  /**
   * Get agent name
   */
  getAgentName(): string {
    return this.AGENT_NAME;
  }

  /**
   * Close any running process
   */
  close(): void {
    for (const proc of this.activeProcesses) {
      proc.kill();
    }
    this.activeProcesses.clear();
  }
}
