/**
 * KnowledgeSync — NLM 자동 동기화 로직
 * 1. 일일 스냅샷: state.yaml + inputs.yaml → NLM source
 * 2. 코드베이스 동기화: repomix → NLM source
 */

import { readFileSync, existsSync } from 'fs';
import { join } from 'path';
import { execFile } from 'child_process';
import { NlmClient } from './nlm-client.js';
import type { KnowledgeManager } from './knowledge-manager.js';
import { log } from '../utils/logger.js';

export class KnowledgeSync {
  constructor(
    private nlm: NlmClient,
    private stateDir: string,
  ) {}

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
   * Note 자동 정리: 오래된 Note 삭제
   * 제목의 날짜 파싱 → maxAgeDays 초과 시 삭제
   * Note 제목 형식: "[SUCCESS] 2026-02-15: BUY BTC" 또는 "[FAIL] 2026-02-10: ..."
   */
  async pruneOldNotes(
    km: KnowledgeManager,
    agentIds: string[],
    maxAgeDays: number = 30,
  ): Promise<number> {
    const cutoff = Date.now() - maxAgeDays * 24 * 60 * 60 * 1000;
    let deleted = 0;

    for (const agentId of agentIds) {
      try {
        const client = await km.getClient(agentId);
        const notes = await client.noteList();

        for (const note of notes) {
          const dateMatch = note.title.match(/(\d{4}-\d{2}-\d{2})/);
          if (!dateMatch) continue;

          const noteDate = new Date(dateMatch[1]).getTime();
          if (isNaN(noteDate) || noteDate >= cutoff) continue;

          await client.noteDelete(note.id);
          deleted++;
          log('info', `🗑️ NLM pruned: ${note.title} (${agentId})`);
        }

        if (deleted > 0) km.invalidateOutline(agentId);
      } catch (e) {
        log('warn', `⚠️ NLM prune failed for ${agentId}: ${e}`);
      }
    }

    if (deleted > 0) log('info', `🗑️ NLM pruned ${deleted} old notes`);
    return deleted;
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
