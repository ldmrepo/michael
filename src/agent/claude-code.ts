import { spawn, ChildProcess } from 'child_process';
import { mkdir, writeFile } from 'fs/promises';
import { join } from 'path';
import { Memory, Message, Schedule } from '../brain/memory.js';
import { Scheduler } from '../scheduler/cron.js';
import { log } from '../utils/logger.js';

/**
 * 벡터 검색 결과 타입 (Message + 점수)
 */
type VectorSearchResult = Message & {
  score: number;
  vectorScore?: number;
  textScore?: number;
};

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
 * A2UI 메시지 타입 (Agent에서 추출)
 */
export interface A2UIAgentMessage {
  type: 'surfaceUpdate' | 'dataModelUpdate' | 'beginRendering';
  surfaceId?: string;
  modelId?: string;
  components?: unknown[];
  data?: Record<string, unknown>;
  root?: string;
}

/**
 * 스트리밍 콜백 인터페이스 (AG-UI 프로토콜)
 */
export interface StreamingCallbacks {
  onStart?: (runId: string) => void;
  onTextContent?: (delta: string, snapshot: string) => void;
  onTextEnd?: (messageId: string, fullText: string) => void;
  onToolStart?: (toolId: string, toolName: string) => void;
  onToolEnd?: (toolId: string, result: unknown) => void;
  onA2UI?: (messages: A2UIAgentMessage[]) => void;
  onFinish?: (runId: string) => void;
  onError?: (error: Error) => void;
}

/**
 * Claude Code Agent
 * Claude Code CLI를 서브프로세스로 실행하여 Task Tool과 Subagent 시스템 활용
 */
export class ClaudeCodeAgent {
  private memory: Memory;
  private scheduler: Scheduler | null = null;
  private activeProcesses: Set<ChildProcess> = new Set();

  constructor(memory: Memory) {
    this.memory = memory;
    log('info', '✅ Claude Code Agent initialized');
  }

  /**
   * Scheduler 설정 (스케줄 즉시 등록용)
   */
  setScheduler(scheduler: Scheduler): void {
    this.scheduler = scheduler;
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
      // 1. 메모리에서 컨텍스트 로드 (벡터 검색 포함)
      const context = await this.loadContext(userId, message);

      // 2. 프롬프트 구성
      const prompt = this.buildPrompt(message, context);

      // 3. Claude Code CLI 실행 (비대화형 모드에서는 권한 프롬프트 건너뛰기)
      const cliOptions = { skipPermissions: true, ...options };
      const response = await this.executeClaudeCode(prompt, cliOptions);

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
   *
   * 벡터 검색이 활성화된 경우, 사용자 메시지와 의미적으로 관련된 과거 대화를 찾아
   * 최근 메시지와 함께 컨텍스트로 제공합니다.
   */
  private async loadContext(
    userId: string,
    currentMessage?: string
  ): Promise<{
    recentMessages: Message[];
    relatedMessages: VectorSearchResult[];
    facts: Record<string, string>;
    schedules: Schedule[];
  }> {
    const [recentMessages, facts, schedules] = await Promise.all([
      this.memory.getRecentMessages(userId, 5),
      this.memory.getAllFacts(userId),
      this.memory.getAllSchedules(userId),
    ]);

    // 벡터 검색으로 관련 메시지 찾기 (벡터 검색이 초기화된 경우만)
    let relatedMessages: VectorSearchResult[] = [];
    const VECTOR_SEARCH_TIMEOUT_MS = 10000; // 10 second timeout

    if (currentMessage) {
      try {
        // Timeout wrapper for vector search
        const searchPromise = this.memory.searchMessagesVector(userId, currentMessage, {
          maxResults: 3,
          minScore: 0.7,
        });
        const timeoutPromise = new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error('Vector search timeout')), VECTOR_SEARCH_TIMEOUT_MS)
        );

        relatedMessages = await Promise.race([searchPromise, timeoutPromise]);

        // 최근 메시지와 중복 제거
        const recentIds = new Set(recentMessages.map((m) => m.id));
        relatedMessages = relatedMessages.filter((m) => !recentIds.has(m.id));
      } catch (error) {
        // 초기화 에러, 타임아웃, 검색 에러 구분
        const errorMessage = error instanceof Error ? error.message : String(error);
        if (errorMessage.includes('not initialized')) {
          // 벡터 검색이 초기화되지 않은 경우 - 정상적인 상황
          log('debug', 'Vector search not initialized, skipping semantic search');
        } else if (errorMessage.includes('timeout')) {
          // 타임아웃 - 경고 레벨로 로깅
          log('warn', `Vector search timed out for user ${userId} after ${VECTOR_SEARCH_TIMEOUT_MS}ms`);
        } else {
          // 실제 검색 에러 - 경고 레벨로 로깅
          log('warn', `Vector search failed for user ${userId}: ${errorMessage}`);
        }
      }
    }

    return { recentMessages, relatedMessages, facts, schedules };
  }

  /**
   * 프롬프트 구성
   */
  private buildPrompt(
    message: string,
    context: {
      recentMessages: Message[];
      relatedMessages: VectorSearchResult[];
      facts: Record<string, string>;
      schedules: Schedule[];
    }
  ): string {
    const factsText = Object.entries(context.facts)
      .map(([key, value]) => `- ${key}: ${value}`)
      .join('\n');

    const recentMessagesText = context.recentMessages
      .map((msg) => `${msg.role}: ${msg.content}`)
      .join('\n');

    // 벡터 검색으로 찾은 관련 대화 추가
    let relatedMessagesText = '';
    if (context.relatedMessages.length > 0) {
      relatedMessagesText = context.relatedMessages
        .map((msg) => {
          const score = msg.score ? ` (relevance: ${(msg.score * 100).toFixed(0)}%)` : '';
          return `${msg.role}: ${msg.content}${score}`;
        })
        .join('\n');
    }

    // 활성 스케줄 목록
    const schedulesText = context.schedules
      .map((s) => `- id: ${s.id} | cron: ${s.cronExpression} | message: "${s.message}"`)
      .join('\n');

    return `
You are Michael, a personal AI assistant that is always awake and remembers everything.
You are friendly, helpful, and proactive.

# User Information (Facts)
${factsText || '(No facts stored yet)'}

# Active Schedules
${schedulesText || '(No active schedules)'}

# Recent Conversation
${recentMessagesText || '(No recent messages)'}

${
  relatedMessagesText
    ? `# Related Past Conversations (found via semantic search)
${relatedMessagesText}
`
    : ''
}
# Current Message
user: ${message}

# Instructions
- Be friendly and conversational
- Remember important information that the user shares
- If the user asks you to remember something, extract the key-value pair and mark it with [FACT:key:value]

## Telegram Formatting (IMPORTANT)
You MUST use Telegram-compatible Markdown format:
- Bold: *bold* (NOT **bold**)
- Italic: _italic_ (NOT *italic*)
- Code: \`code\` (same)
- NO headers (#, ##, ###) - use *bold text* instead
- NO tables - use simple lists instead
- NO horizontal rules (---)
Keep responses concise and mobile-friendly.

## Self-Modifying: Skill Creation
When the user asks to create a new feature/skill, generate a skill file using this marker:

[CREATE_SKILL:skill_name]
---
name: skill_name
description: |
  Brief description. Keywords that trigger this skill.
allowed-tools: Bash(bash:*), Bash(curl:*), Read, Write
---

# Skill Title

Detailed instructions...
[/CREATE_SKILL]

The file will be created at .claude/skills/{skill_name}/SKILL.md
Only create skills when explicitly requested.

## Schedule Management
You have direct access to the user's active schedules listed above.

- **Recurring schedule**: Use [SCHEDULE:cron_expr:message] for repeating tasks
  Example: "매일 9시에 알려줘" → [SCHEDULE:0 9 * * *:좋은 아침입니다! 오늘의 일정을 확인하세요.]
- **One-time reminder**: Use [SCHEDULE_ONCE:minutes:message] for a single reminder after N minutes
  Example: "3분 후에 알려줘" → [SCHEDULE_ONCE:3:알림입니다!]
  Example: "1시간 후에 알려줘" → [SCHEDULE_ONCE:60:알림입니다!]
- **Cancel schedule**: Use [CANCEL_SCHEDULE:schedule_id] with the exact id from the Active Schedules list
  Example: User says "알림 취소해줘" → find matching schedule id and use [CANCEL_SCHEDULE:schedule_1234_abc]
- When the user asks to cancel, show which schedule you're cancelling
- When the user asks to list schedules, describe the Active Schedules above in natural language

- Use the related past conversations to provide context-aware responses
- Focus on helping the user with their immediate needs

## A2UI Dynamic UI (Optional)
When you need to show structured information (lists, cards, forms, buttons), you can use A2UI markers.
The UI components will be rendered appropriately on the user's device.

**Available markers:**
- [A2UI_SURFACE:surfaceId]componentsJSON[/A2UI_SURFACE] - Define UI components
- [A2UI_DATA:modelId]dataJSON[/A2UI_DATA] - Set data model values

**Example - Show flight options as cards:**
\`\`\`
[A2UI_SURFACE:main][{"id":"flight1","component":{"Card":{"title":{"literalString":"KE001 Seoul-Tokyo"},"children":{"explicitList":["f1-price","f1-btn"]}}}}][/A2UI_SURFACE]
\`\`\`

**Example - Set form data:**
\`\`\`
[A2UI_DATA:booking]{"date":"2026-03-15","destination":"Tokyo"}[/A2UI_DATA]
\`\`\`

Note: Only use A2UI when it genuinely improves the user experience (e.g., showing options, forms, lists).
For simple text responses, just reply normally without A2UI.

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

      // Claude Code CLI 실행 (CLAUDECODE 환경변수 제거하여 중첩 세션 방지)
      const env = { ...process.env };
      delete env.CLAUDECODE;
      delete env.CLAUDE_CODE_ENTRYPOINT;

      let settled = false;
      const proc = spawn('claude', args, {
        stdio: ['pipe', 'pipe', 'pipe'],
        env,
      });
      this.activeProcesses.add(proc);

      // 30분 타임아웃 (스킬 실행 등 장시간 작업 대응)
      const timeout = setTimeout(() => {
        if (!settled) {
          settled = true;
          proc.kill();
          this.activeProcesses.delete(proc);
          reject(new Error('Claude Code timeout (1800s)'));
        }
      }, 1800000);

      // 프롬프트를 stdin으로 전달
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
        log('warn', `Claude Code stderr: ${data.toString()}`);
      });

      proc.on('close', (code) => {
        clearTimeout(timeout);
        this.activeProcesses.delete(proc);
        if (settled) return;
        settled = true;

        if (code !== 0) {
          log('error', `❌ Claude Code failed with code ${code}: ${stderr}`);
          reject(new Error(`Claude Code failed: ${stderr}`));
          return;
        }

        // 응답 추출
        const response = this.extractResponse(stdout);
        resolve(response);
      });

      proc.on('error', (error) => {
        clearTimeout(timeout);
        this.activeProcesses.delete(proc);
        if (settled) return;
        settled = true;
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
    response: string,
    callbacks?: StreamingCallbacks
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

    // 반복 Schedule 추출 및 저장 + Scheduler에 즉시 등록
    const scheduleMatches = response.matchAll(/\[SCHEDULE:(.+?):(.+?)\]/g);
    for (const match of scheduleMatches) {
      const [, cronExpr, message] = match;
      if (this.scheduler) {
        await this.scheduler.addSchedule(userId, cronExpr, message);
        log('info', `⏰ Schedule registered: ${cronExpr}`);
      } else {
        const scheduleId = `schedule_${Date.now()}_${Math.random().toString(36).substring(7)}`;
        await this.memory.saveSchedule(scheduleId, userId, cronExpr, message);
        log('warn', `⏰ Schedule saved to DB only (no scheduler): ${cronExpr}`);
      }
    }

    // 1회 Schedule 추출 및 등록
    const onceMatches = response.matchAll(/\[SCHEDULE_ONCE:(\d+):(.+?)\]/g);
    for (const match of onceMatches) {
      const [, minutesStr, message] = match;
      const minutes = parseInt(minutesStr, 10);
      if (this.scheduler) {
        this.scheduler.addOneTimeSchedule(userId, minutes, message);
        log('info', `⏰ One-time schedule registered: ${minutes}min`);
      } else {
        log('warn', `⏰ One-time schedule ignored (no scheduler): ${minutes}min`);
      }
    }

    // Schedule 취소 처리
    const cancelMatches = response.matchAll(/\[CANCEL_SCHEDULE:(.+?)\]/g);
    for (const match of cancelMatches) {
      const [, scheduleId] = match;
      if (this.scheduler) {
        await this.scheduler.cancelSchedule(scheduleId);
        log('info', `⏰ Schedule cancelled: ${scheduleId}`);
      } else {
        await this.memory.deactivateSchedule(scheduleId);
        log('warn', `⏰ Schedule deactivated in DB only (no scheduler): ${scheduleId}`);
      }
    }

    // Skill 생성 처리 (Self-Modifying)
    const skillMatches = response.matchAll(/\[CREATE_SKILL:(\w+)\]([\s\S]*?)\[\/CREATE_SKILL\]/g);
    for (const match of skillMatches) {
      const [, skillName, skillContent] = match;
      try {
        const skillDir = join(process.cwd(), '.claude', 'skills', skillName);
        const skillPath = join(skillDir, 'SKILL.md');

        // 디렉토리 생성
        await mkdir(skillDir, { recursive: true });

        // 스킬 파일 생성
        await writeFile(skillPath, skillContent.trim(), 'utf-8');
        log('info', `🛠️ Skill created: ${skillName} at ${skillPath}`);
      } catch (error) {
        log('error', `❌ Failed to create skill ${skillName}: ${error}`);
      }
    }

    // A2UI 마커 추출 (모든 종류를 한 번에 찾아 순서 유지)
    const a2uiMessages: A2UIAgentMessage[] = [];
    const a2uiPattern =
      /\[A2UI_(SURFACE|DATA):(\w+)\]([\s\S]*?)\[\/A2UI_\1\]/g;

    for (const match of response.matchAll(a2uiPattern)) {
      const [, markerType, id, jsonContent] = match;
      try {
        const parsedContent = JSON.parse(jsonContent.trim());

        if (markerType === 'SURFACE') {
          a2uiMessages.push({
            type: 'surfaceUpdate',
            surfaceId: id,
            components: parsedContent,
          });
          log('info', `🎨 A2UI Surface: ${id}`);
        } else if (markerType === 'DATA') {
          a2uiMessages.push({
            type: 'dataModelUpdate',
            modelId: id,
            data: parsedContent,
          });
          log('info', `📊 A2UI Data: ${id}`);
        }
      } catch (e) {
        log('warn', `⚠️ A2UI ${markerType} parse error: ${e}`);
      }
    }

    // A2UI 콜백 호출
    if (a2uiMessages.length > 0 && callbacks?.onA2UI) {
      callbacks.onA2UI(a2uiMessages);
    }

    // 모든 마커 제거
    const cleanResponse = response
      .replace(/\[FACT:\w+:.+?\]/g, '')
      .replace(/\[SCHEDULE:(.+?):(.+?)\]/g, '')
      .replace(/\[SCHEDULE_ONCE:\d+:.+?\]/g, '')
      .replace(/\[CANCEL_SCHEDULE:.+?\]/g, '')
      .replace(/\[A2UI_(SURFACE|DATA):\w+\][\s\S]*?\[\/A2UI_\1\]/g, '')
      .trim();

    // Assistant 응답 저장
    await this.memory.saveMessage(userId, 'assistant', cleanResponse);
  }

  /**
   * 스트리밍 콜백을 지원하는 사용자 대화 (AG-UI 프로토콜)
   */
  async chatWithStreaming(
    userId: string,
    message: string,
    callbacks: StreamingCallbacks,
    options: ClaudeCodeOptions = {}
  ): Promise<string> {
    try {
      // 1. 메모리에서 컨텍스트 로드 (벡터 검색 포함)
      const context = await this.loadContext(userId, message);

      // 2. 프롬프트 구성
      const prompt = this.buildPrompt(message, context);

      // 3. Claude Code CLI 실행 (스트리밍, 비대화형 모드에서는 권한 프롬프트 건너뛰기)
      const cliOptions = { skipPermissions: true, ...options };
      const response = await this.executeClaudeCodeWithStreaming(
        prompt,
        callbacks,
        cliOptions
      );

      // 4. 응답 파싱 및 메모리 저장 (콜백 전달로 A2UI 지원)
      await this.processResponse(userId, message, response, callbacks);

      return response;
    } catch (error) {
      log('error', `❌ Chat with streaming failed: ${error}`);
      if (callbacks.onError && error instanceof Error) {
        callbacks.onError(error);
      }
      throw error;
    }
  }

  /**
   * 스트리밍 콜백과 함께 Claude Code CLI 실행
   */
  private async executeClaudeCodeWithStreaming(
    prompt: string,
    callbacks: StreamingCallbacks,
    options: ClaudeCodeOptions
  ): Promise<string> {
    return new Promise((resolve, reject) => {
      const args: string[] = ['-p']; // print mode

      // 옵션 추가
      if (options.skipPermissions) {
        args.push('--dangerously-skip-permissions');
      }

      if (options.model) {
        args.push('--model', options.model);
      }

      log('debug', `🤖 Executing Claude Code (streaming) with prompt length: ${prompt.length}`);

      // Claude Code CLI 실행 (CLAUDECODE 환경변수 제거하여 중첩 세션 방지)
      const env = { ...process.env };
      delete env.CLAUDECODE;
      delete env.CLAUDE_CODE_ENTRYPOINT;

      let settled = false;
      const proc = spawn('claude', args, {
        stdio: ['pipe', 'pipe', 'pipe'],
        env,
      });
      this.activeProcesses.add(proc);

      // 30분 타임아웃 (스킬 실행 등 장시간 작업 대응)
      const timeout = setTimeout(() => {
        if (!settled) {
          settled = true;
          proc.kill();
          this.activeProcesses.delete(proc);
          const error = new Error('Claude Code timeout (1800s)');
          if (callbacks.onError) callbacks.onError(error);
          reject(error);
        }
      }, 1800000);

      // 프롬프트를 stdin으로 전달
      if (proc.stdin) {
        proc.stdin.write(prompt);
        proc.stdin.end();
      }

      let fullOutput = '';
      let lastSnapshotLength = 0;
      let stderrOutput = '';

      // stdout 스트리밍 처리
      proc.stdout?.on('data', (data) => {
        const chunk = data.toString();
        fullOutput += chunk;

        // 콜백으로 델타 전달
        if (callbacks.onTextContent) {
          const delta = fullOutput.substring(lastSnapshotLength);
          callbacks.onTextContent(delta, fullOutput);
          lastSnapshotLength = fullOutput.length;
        }
      });

      proc.stderr?.on('data', (data) => {
        stderrOutput += data.toString();
        log('warn', `Claude Code stderr: ${data.toString()}`);
      });

      proc.on('close', (code) => {
        clearTimeout(timeout);
        this.activeProcesses.delete(proc);
        if (settled) return;
        settled = true;

        if (code !== 0) {
          const error = new Error(`Claude Code failed with code ${code}: ${stderrOutput}`);
          log('error', `❌ Claude Code failed with code ${code}: ${stderrOutput}`);
          if (callbacks.onError) {
            callbacks.onError(error);
          }
          reject(error);
          return;
        }

        // 응답 추출
        const response = this.extractResponse(fullOutput);
        resolve(response);
      });

      proc.on('error', (error) => {
        clearTimeout(timeout);
        this.activeProcesses.delete(proc);
        if (settled) return;
        settled = true;
        log('error', `❌ Claude Code process error: ${error.message}`);
        if (callbacks.onError) {
          callbacks.onError(error);
        }
        reject(error);
      });
    });
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
    for (const proc of this.activeProcesses) {
      proc.kill();
    }
    this.activeProcesses.clear();
    log('info', '👋 Claude Code Agent closed');
  }
}
