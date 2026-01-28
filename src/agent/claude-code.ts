import { spawn, ChildProcess } from 'child_process';
import { Memory } from '../brain/memory.js';
import { log } from '../utils/logger.js';

/**
 * Claude Code Agent 옵션
 */
export interface ClaudeCodeOptions {
  mode?: 'interactive' | 'autopilot';
  skipPermissions?: boolean;
  model?: 'sonnet' | 'opus' | 'haiku';
  maxTokens?: number;
}

/**
 * Claude Code Agent
 * Claude Code CLI를 서브프로세스로 실행하여 Task Tool과 Subagent 시스템 활용
 */
export class ClaudeCodeAgent {
  private memory: Memory;
  private process: ChildProcess | null = null;

  constructor(memory: Memory) {
    this.memory = memory;
    log('info', '✅ Claude Code Agent initialized');
  }

  /**
   * 사용자와 대화
   */
  async chat(
    userId: string,
    message: string,
    options: ClaudeCodeOptions = {}
  ): Promise<string> {
    try {
      // 1. 메모리에서 컨텍스트 로드
      const context = await this.loadContext(userId);

      // 2. 프롬프트 구성
      const prompt = this.buildPrompt(message, context);

      // 3. Claude Code CLI 실행
      const response = await this.executeClaudeCode(prompt, options);

      // 4. 응답 파싱 및 메모리 저장
      await this.processResponse(userId, message, response);

      return response;
    } catch (error) {
      log('error', `❌ Chat failed: ${error}`);
      throw error;
    }
  }

  /**
   * 메모리에서 컨텍스트 로드
   */
  private async loadContext(userId: string): Promise<{
    recentMessages: any[];
    facts: Record<string, string>;
  }> {
    const [recentMessages, facts] = await Promise.all([
      this.memory.getRecentMessages(userId, 5),
      this.memory.getAllFacts(userId),
    ]);

    return { recentMessages, facts };
  }

  /**
   * 프롬프트 구성
   */
  private buildPrompt(
    message: string,
    context: {
      recentMessages: any[];
      facts: Record<string, string>;
    }
  ): string {
    const factsText = Object.entries(context.facts)
      .map(([key, value]) => `- ${key}: ${value}`)
      .join('\n');

    const recentMessagesText = context.recentMessages
      .map((msg) => `${msg.role}: ${msg.content}`)
      .join('\n');

    return `
You are Michael, a personal AI assistant that is always awake and remembers everything.
You are friendly, helpful, and proactive.

# User Information (Facts)
${factsText || '(No facts stored yet)'}

# Recent Conversation
${recentMessagesText || '(No recent messages)'}

# Current Message
user: ${message}

# Instructions
- Be friendly and conversational
- Remember important information that the user shares
- If the user asks you to remember something, extract the key-value pair and mark it with [FACT:key:value]
- If the user asks you to schedule something, parse the cron expression and mark it with [SCHEDULE:cron_expr:message]
- Focus on helping the user with their immediate needs

Please respond to the user's message:
`.trim();
  }

  /**
   * Claude Code CLI 실행
   */
  private async executeClaudeCode(
    prompt: string,
    options: ClaudeCodeOptions
  ): Promise<string> {
    return new Promise((resolve, reject) => {
      const args: string[] = ['-p']; // print mode
      
      // 프롬프트를 stdin으로 전달하기 위해 별도 처리

      // 옵션 추가
      if (options.skipPermissions) {
        args.push('--dangerously-skip-permissions');
      }

      if (options.model) {
        args.push('--model', options.model);
      }

      log('debug', `🤖 Executing Claude Code with prompt length: ${prompt.length}`);

      // Claude Code CLI 실행
      this.process = spawn('claude', args, {
        stdio: ['pipe', 'pipe', 'pipe'],
      });

      // 프롬프트를 stdin으로 전달
      if (this.process.stdin) {
        this.process.stdin.write(prompt);
        this.process.stdin.end();
      }

      let stdout = '';
      let stderr = '';

      this.process.stdout?.on('data', (data) => {
        stdout += data.toString();
      });

      this.process.stderr?.on('data', (data) => {
        stderr += data.toString();
        log('debug', `Claude Code stderr: ${data.toString()}`);
      });

      this.process.on('close', (code) => {
        this.process = null;

        if (code !== 0) {
          log('error', `❌ Claude Code failed with code ${code}: ${stderr}`);
          reject(new Error(`Claude Code failed: ${stderr}`));
          return;
        }

        // 응답 추출
        const response = this.extractResponse(stdout);
        resolve(response);
      });

      this.process.on('error', (error) => {
        log('error', `❌ Claude Code process error: ${error.message}`);
        reject(error);
      });
    });
  }

  /**
   * Claude Code 출력에서 응답 추출
   */
  private extractResponse(output: string): string {
    // Claude Code -p 모드는 순수 응답만 출력
    return output.trim();
  }

  /**
   * 응답 처리 및 메모리 저장
   */
  private async processResponse(
    userId: string,
    userMessage: string,
    response: string
  ): Promise<void> {
    // 사용자 메시지 저장
    await this.memory.saveMessage(userId, 'user', userMessage);

    // Fact 추출 및 저장
    const factMatches = response.matchAll(/\[FACT:(\w+):(.+?)\]/g);
    for (const match of factMatches) {
      const [, key, value] = match;
      await this.memory.saveFact(userId, key, value);
      log('info', `💾 Fact saved: ${key}=${value}`);
    }

    // Schedule 추출 및 저장
    const scheduleMatches = response.matchAll(/\[SCHEDULE:(.+?):(.+?)\]/g);
    for (const match of scheduleMatches) {
      const [, cronExpr, message] = match;
      const scheduleId = `schedule_${Date.now()}_${Math.random().toString(36).substring(7)}`;
      await this.memory.saveSchedule(scheduleId, userId, cronExpr, message);
      log('info', `⏰ Schedule saved: ${cronExpr}`);
    }

    // Fact와 Schedule 마커 제거
    const cleanResponse = response
      .replace(/\[FACT:\w+:.+?\]/g, '')
      .replace(/\[SCHEDULE:.+?:.+?\]/g, '')
      .trim();

    // Assistant 응답 저장
    await this.memory.saveMessage(userId, 'assistant', cleanResponse);
  }

  /**
   * Task Tool로 작업 실행
   */
  async executeTask(
    task: string,
    options: ClaudeCodeOptions = {}
  ): Promise<string> {
    log('info', `🎯 Executing task: ${task}`);
    return this.executeClaudeCode(task, options);
  }

  /**
   * Skills 실행
   */
  async executeSkill(skillName: string, params: any): Promise<string> {
    log('info', `🛠️ Executing skill: ${skillName}`);
    
    const prompt = `/${skillName} ${JSON.stringify(params)}`;
    return this.executeClaudeCode(prompt, {});
  }

  /**
   * Agent 종료
   */
  close(): void {
    if (this.process) {
      this.process.kill();
      this.process = null;
    }
    log('info', '👋 Claude Code Agent closed');
  }
}
