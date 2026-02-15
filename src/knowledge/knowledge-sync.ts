/**
 * KnowledgeSync — NLM 자동 동기화 로직
 * 1. Decision → NLM source 추가 (judgment 노트북)
 * 2. 일일 스냅샷: state.yaml + inputs.yaml → NLM source
 * 3. 코드베이스 동기화: repomix → NLM source
 * 4. Decision 결과 → 에이전트 노트북에 Note 기록 (write-back)
 */

import { readFileSync, existsSync } from 'fs';
import { join } from 'path';
import { execFile } from 'child_process';
import { NlmClient } from './nlm-client.js';
import type { KnowledgeManager } from './knowledge-manager.js';
import { log } from '../utils/logger.js';
import type { Decision } from '../state-store/types.js';

export class KnowledgeSync {
  constructor(
    private nlm: NlmClient,
    private stateDir: string,
  ) {}

  /**
   * Decision → NLM source 추가
   * 제목: "D-20260215-001: BUY BTC $50"
   */
  async syncDecision(decision: Decision): Promise<void> {
    const title = `${decision.id}: ${decision.action} ${decision.target} $${decision.amount}`;
    const content = [
      `# ${title}`,
      '',
      `- **Timestamp**: ${decision.timestamp}`,
      `- **Action**: ${decision.action}`,
      `- **Target**: ${decision.target}`,
      `- **Platform**: ${decision.platform}`,
      `- **Amount**: $${decision.amount}`,
      `- **Status**: ${decision.status}`,
      `- **Reason**: ${decision.reason}`,
      '',
      '## Mandate Check',
      ...Object.entries(decision.mandate_check).map(([k, v]) => `- ${k}: ${v}`),
    ].join('\n');

    await this.nlm.addSource(title, content);
    log('info', `📔 NLM decision synced: ${title}`);
  }

  /**
   * 일일 스냅샷: state.yaml + inputs.yaml → NLM source
   */
  async syncDailySnapshot(): Promise<void> {
    const today = new Date().toISOString().substring(0, 10);
    const title = `Daily Snapshot ${today}`;

    const parts: string[] = [`# ${title}\n`];

    const stateFile = join(this.stateDir, 'state.yaml');
    if (existsSync(stateFile)) {
      parts.push('## Portfolio State\n```yaml');
      parts.push(readFileSync(stateFile, 'utf-8').trim());
      parts.push('```\n');
    }

    const inputsFile = join(this.stateDir, 'inputs.yaml');
    if (existsSync(inputsFile)) {
      parts.push('## Market Inputs\n```yaml');
      parts.push(readFileSync(inputsFile, 'utf-8').trim());
      parts.push('```\n');
    }

    const content = parts.join('\n');
    await this.nlm.addSource(title, content);
    log('info', `📔 NLM daily snapshot: ${title}`);
  }

  /**
   * 코드베이스 동기화: npx repomix --stdout → nlm source add
   * 기존 "Michael Codebase" 소스 있으면 삭제 후 재업로드
   */
  async syncCodebase(): Promise<void> {
    const repomixOutput = await this.runRepomix();
    if (!repomixOutput) {
      log('warn', '⚠️ repomix failed, skipping codebase sync');
      return;
    }

    // 기존 소스 삭제 후 재업로드
    try {
      const sources = await this.nlm.listSources();
      const existing = sources.find(s => s.title === 'Michael Codebase');
      if (existing) {
        await this.nlm.deleteSource(existing.id);
      }
    } catch {
      // 삭제 실패 시 그냥 추가 (중복 허용)
    }

    await this.nlm.addSource('Michael Codebase', repomixOutput);
    log('info', '📔 NLM codebase source updated');
  }

  /**
   * Decision 실행 결과 → 해당 에이전트 노트북에 Note 기록
   * Source(외부 문서) ≠ Note(에이전트 자기 주석)
   */
  async syncDecisionOutcome(
    decision: Decision,
    km: KnowledgeManager,
  ): Promise<void> {
    const agentId = this.resolveAgentForDecision(decision);
    if (!agentId) return;

    try {
      const client = await km.getClient(agentId);
      const date = new Date().toISOString().substring(0, 10);
      const ok = decision.status === 'executed';
      const title = `[${ok ? 'SUCCESS' : 'FAIL'}] ${date}: ${decision.action} ${decision.target}`;
      const content = [
        `# ${title}`,
        `- Amount: $${decision.amount}`,
        `- Platform: ${decision.platform}`,
        `- Reason: ${decision.reason}`,
        `- Status: ${decision.status}`,
        decision.result ? `- Fill: $${decision.result.fill_price}, Fee: $${decision.result.fee}` : '',
      ].filter(Boolean).join('\n');

      await client.noteCreate(title, content);
      km.invalidateOutline(agentId);
      log('info', `📝 NLM lesson: ${title}`);
    } catch (e) {
      log('warn', `⚠️ NLM lesson sync failed: ${e}`);
    }
  }

  private resolveAgentForDecision(decision: Decision): string | null {
    if (decision.platform?.startsWith('binance')) return 'binance_trader';
    if (decision.platform === 'polymarket') return 'pm_trader';
    return null;
  }

  private runRepomix(): Promise<string | null> {
    return new Promise((resolve) => {
      execFile('npx', ['repomix', '--stdout'], { timeout: 120_000 }, (error, stdout) => {
        if (error) {
          log('warn', `⚠️ repomix error: ${error.message}`);
          resolve(null);
          return;
        }
        resolve(stdout);
      });
    });
  }
}
