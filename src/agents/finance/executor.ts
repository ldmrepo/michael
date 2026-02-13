/**
 * Finance Agent Executor
 *
 * Implements A2UI generation for personal finance use cases:
 * - Portfolio analysis
 * - Market research
 * - Expense tracking
 */
import { spawn } from 'child_process';
import { BaseA2UIAgentExecutor, AgentExecutorContext } from '../base/executor.js';
import { A2AMessage } from '../../a2a/types.js';
import { FINANCE_SYSTEM_PROMPT, FINANCE_PROMPTS } from './prompts.js';
import { detectSkill } from './agent.js';
import { log } from '../../utils/logger.js';

/**
 * Finance Agent Executor
 *
 * Extends BaseA2UIAgentExecutor with finance-specific functionality
 */
export class FinanceAgentExecutor extends BaseA2UIAgentExecutor {
  protected readonly AGENT_NAME = 'FinanceAgent';
  protected readonly SYSTEM_PROMPT = FINANCE_SYSTEM_PROMPT;
  protected readonly ARTIFACT_PREFIX = 'finance_result';

  /**
   * Override CLI execution to add finance-specific flags
   *
   * - --allowedTools: Enable Bash and Read tools for finance scripts
   * - CLAUDE_PROJECT_DIR: Set to cwd for script path resolution
   */
  protected async executeClaudeCLI(prompt: string): Promise<string> {
    return new Promise((resolve, reject) => {
      const args: string[] = [
        '-p', // print mode
        '--allowedTools', 'Bash(bash:*),Read', // Enable bash for finance scripts
      ];

      // Add model if specified
      if (this.model) {
        args.push('--model', this.model);
      }

      log('debug', `🤖 [${this.AGENT_NAME}] Executing Claude CLI with args: ${args.join(' ')}`);
      log('debug', `🤖 [${this.AGENT_NAME}] Prompt length: ${prompt.length}`);

      // Spawn Claude CLI process with CLAUDE_PROJECT_DIR set
      // CLAUDECODE 환경변수 제거하여 중첩 세션 방지
      const env: Record<string, string | undefined> = { ...process.env, CLAUDE_PROJECT_DIR: process.cwd() };
      delete env.CLAUDECODE;
      delete env.CLAUDE_CODE_ENTRYPOINT;

      let settled = false;
      const proc = spawn('claude', args, {
        stdio: ['pipe', 'pipe', 'pipe'],
        cwd: process.cwd(),
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
   * Execute with skill-aware context enhancement
   *
   * @param context - Execution context
   * @returns A2A response message with A2UI components
   */
  async execute(context: AgentExecutorContext): Promise<A2AMessage> {
    // Detect skill from user input
    const userInput = this.extractUserInput(context.message);
    const detectedSkill = detectSkill(userInput);

    // Enhance context with skill-specific prompt if detected
    if (detectedSkill) {
      const enhancedContext = this.enhanceContextWithSkill(context, detectedSkill);
      return super.execute(enhancedContext);
    }

    return super.execute(context);
  }

  /**
   * Enhance context with skill-specific prompt
   */
  private enhanceContextWithSkill(
    context: AgentExecutorContext,
    skillId: string
  ): AgentExecutorContext {
    const skillPrompt = this.getSkillPrompt(skillId);

    if (!skillPrompt) {
      return context;
    }

    // Add skill context to metadata
    return {
      ...context,
      metadata: {
        ...context.metadata,
        detectedSkill: skillId,
        skillPrompt,
      },
    };
  }

  /**
   * Get skill-specific prompt
   */
  private getSkillPrompt(skillId: string): string | null {
    switch (skillId) {
      case 'portfolio-analysis':
        return FINANCE_PROMPTS.portfolioAnalysis;
      case 'market-research':
        return FINANCE_PROMPTS.marketResearch;
      case 'expense-tracking':
        return FINANCE_PROMPTS.expenseTracking;
      default:
        return null;
    }
  }

  /**
   * Override to add skill-specific context to LLM call
   */
  protected extractUserInput(message: A2AMessage): string {
    const baseInput = super.extractUserInput(message);

    // If metadata contains skill context, prepend it
    const metadata = message.metadata as Record<string, string> | undefined;
    if (metadata?.skillPrompt) {
      return `${metadata.skillPrompt}\n\n사용자 요청: ${baseInput}`;
    }

    return baseInput;
  }
}

/**
 * Create Finance Agent Executor instance
 */
export function createFinanceExecutor(): FinanceAgentExecutor {
  return new FinanceAgentExecutor();
}
