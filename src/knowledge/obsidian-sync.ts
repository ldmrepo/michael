/**
 * ObsidianSync — NLM ↔ Obsidian Vault 양방향 동기화 + 자동 컨텐츠 생성
 *
 * 1. NLM → Vault: 교훈 아카이빙 (30일 TTL 전 영구 보존)
 * 2. Vault → NLM: 플레이북을 NLM Source로 업로드
 * 3. 자동 생성: Daily journal, Weekly review, Portfolio snapshot
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { join } from 'path';
import { createHash } from 'crypto';
import { ObsidianVault, VaultNoteFrontmatter } from './obsidian-vault.js';
import type { KnowledgeManager } from './knowledge-manager.js';
import type { Memory } from '../brain/memory.js';
import { log } from '../utils/logger.js';

// ─── Types ──────────────────────────────────────────

interface SyncState {
  nlmArchived: Record<string, string>;    // noteId → vault파일경로
  vaultUploaded: Record<string, {         // vault파일경로 → NLM info
    hash: string;
    nlmSourceId?: string;
  }>;
}

export interface SyncStats {
  nlmArchived: number;
  playbooksUploaded: number;
  errors: number;
}

// Domain mapping: NLM agentId → vault subdir
const DOMAIN_MAP: Record<string, { subdir: string; domain: VaultNoteFrontmatter['domain'] }> = {
  binance_trader: { subdir: 'lessons/binance', domain: 'binance' },
  pm_trader: { subdir: 'lessons/polymarket', domain: 'polymarket' },
  portfolio: { subdir: 'lessons/general', domain: 'portfolio' },
  risk: { subdir: 'lessons/general', domain: 'risk' },
  michael: { subdir: 'lessons/general', domain: 'general' },
};

// ─── Class ──────────────────────────────────────────

export class ObsidianSync {
  private vault: ObsidianVault;
  private km: KnowledgeManager;
  private statePath: string;
  private state: SyncState;

  constructor(
    vault: ObsidianVault,
    km: KnowledgeManager,
    _memory: Memory,
    stateDir: string,
  ) {
    this.vault = vault;
    this.km = km;
    this.statePath = join(stateDir, 'obsidian-sync-state.json');
    this.state = this.loadState();
  }

  /**
   * NLM → Vault: 교훈 아카이빙
   * NLM 노트를 vault에 영구 저장. 중복 방지 (nlm_note_id 기반).
   */
  async archiveNlmLessons(agentIds: string[]): Promise<number> {
    let archived = 0;

    for (const agentId of agentIds) {
      const mapping = DOMAIN_MAP[agentId] || DOMAIN_MAP.michael;

      try {
        const client = await this.km.getClient(agentId);
        const notes = await client.noteList();

        for (const note of notes) {
          // 중복 확인
          if (this.state.nlmArchived[note.id]) continue;

          try {
            const fm: VaultNoteFrontmatter = {
              title: note.title,
              date: this.extractDateFromTitle(note.title) || this.today(),
              type: 'lesson',
              domain: mapping.domain,
              tags: ['lesson', agentId],
              source: 'nlm',
              nlm_notebook: agentId,
              nlm_note_id: note.id,
              status: 'active',
            };

            // NLM 노트 내용은 제목에서 추출 (NLM CLI는 note get이 없으므로)
            const content = `# ${note.title}\n\n*Archived from NLM notebook: ${agentId}*\n`;

            const vaultPath = this.vault.createNote(
              { frontmatter: fm, content },
              mapping.subdir,
            );

            this.state.nlmArchived[note.id] = vaultPath;
            archived++;
            log('info', `📓 Archived NLM note → vault: ${note.title}`);
          } catch (e) {
            log('warn', `⚠️ Failed to archive note ${note.id}: ${e}`);
          }
        }
      } catch (e) {
        log('warn', `⚠️ NLM archive failed for ${agentId}: ${e}`);
      }
    }

    if (archived > 0) {
      this.saveState();
      log('info', `📓 Archived ${archived} NLM notes to vault`);
    }

    return archived;
  }

  /**
   * Vault → NLM: 플레이북을 NLM Source로 업로드
   * 해시 비교로 미변경 스킵.
   */
  async syncPlaybooksToNlm(): Promise<number> {
    let uploaded = 0;
    const playbooks = this.vault.listNotes('playbooks');

    for (const pb of playbooks) {
      if (pb.frontmatter.status !== 'active') continue;

      const hash = this.hashContent(pb.rawContent);
      const existing = this.state.vaultUploaded[pb.path];

      // 미변경 스킵
      if (existing && existing.hash === hash) continue;

      try {
        const michaelClient = await this.km.getClient('michael');
        await michaelClient.addSource(
          `[Playbook] ${pb.frontmatter.title}`,
          pb.rawContent,
        );

        this.state.vaultUploaded[pb.path] = { hash };
        uploaded++;
        log('info', `📓 Uploaded playbook → NLM: ${pb.frontmatter.title}`);
      } catch (e) {
        log('warn', `⚠️ Failed to upload playbook ${pb.path}: ${e}`);
      }
    }

    if (uploaded > 0) {
      this.saveState();
      log('info', `📓 Uploaded ${uploaded} playbooks to NLM`);
    }

    return uploaded;
  }

  /**
   * Daily journal 생성 (거래 요약)
   */
  async generateDailyJournal(date?: string): Promise<string> {
    const d = date || this.today();

    // 이미 존재하면 스킵
    const existing = this.vault.getDailyNote(d);
    if (existing) {
      log('debug', `Daily journal already exists: ${d}`);
      return existing.path;
    }

    const path = this.vault.createDailyNote(d);
    log('info', `📓 Daily journal created: ${d}`);
    return path;
  }

  /**
   * Weekly review 생성
   */
  async generateWeeklyReview(weekStr?: string): Promise<string> {
    const w = weekStr || this.currentWeek();

    // 이미 존재하면 스킵
    const existing = this.vault.getWeeklyNote(w);
    if (existing) {
      log('debug', `Weekly review already exists: ${w}`);
      return existing.path;
    }

    const path = this.vault.createWeeklyNote(w);
    log('info', `📓 Weekly review created: ${w}`);
    return path;
  }

  /**
   * Portfolio snapshot 생성
   */
  async generatePortfolioSnapshot(): Promise<string> {
    const d = this.today();
    const fm: VaultNoteFrontmatter = {
      title: `Portfolio Snapshot — ${d}`,
      date: d,
      type: 'portfolio',
      domain: 'portfolio',
      tags: ['portfolio', 'snapshot'],
      source: 'auto-generated',
      status: 'active',
    };

    const content = `# Portfolio Snapshot — ${d}\n\n*Auto-generated snapshot*\n\n## Summary\n\n(To be filled by trading data)\n`;
    const path = this.vault.createNote({ frontmatter: fm, content }, 'portfolio');
    log('info', `📓 Portfolio snapshot created: ${d}`);
    return path;
  }

  /**
   * 전체 동기화 실행
   */
  async runFullSync(): Promise<SyncStats> {
    const stats: SyncStats = { nlmArchived: 0, playbooksUploaded: 0, errors: 0 };

    try {
      stats.nlmArchived = await this.archiveNlmLessons(Object.keys(DOMAIN_MAP));
    } catch (e) {
      stats.errors++;
      log('warn', `⚠️ NLM archival failed: ${e}`);
    }

    try {
      stats.playbooksUploaded = await this.syncPlaybooksToNlm();
    } catch (e) {
      stats.errors++;
      log('warn', `⚠️ Playbook sync failed: ${e}`);
    }

    log('info', `📓 Full sync: archived=${stats.nlmArchived}, uploaded=${stats.playbooksUploaded}, errors=${stats.errors}`);
    return stats;
  }

  // ─── State Persistence ────────────────────────────

  private loadState(): SyncState {
    if (!existsSync(this.statePath)) {
      return { nlmArchived: {}, vaultUploaded: {} };
    }
    try {
      return JSON.parse(readFileSync(this.statePath, 'utf-8'));
    } catch {
      return { nlmArchived: {}, vaultUploaded: {} };
    }
  }

  private saveState(): void {
    const dir = join(this.statePath, '..');
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true });
    }
    writeFileSync(this.statePath, JSON.stringify(this.state, null, 2), 'utf-8');
  }

  // ─── Helpers ──────────────────────────────────────

  private hashContent(content: string): string {
    return createHash('sha256').update(content).digest('hex').substring(0, 16);
  }

  private extractDateFromTitle(title: string): string | null {
    const match = title.match(/(\d{4}-\d{2}-\d{2})/);
    return match ? match[1] : null;
  }

  private today(): string {
    return new Date().toISOString().substring(0, 10);
  }

  private currentWeek(): string {
    const now = new Date();
    const year = now.getFullYear();
    const jan1 = new Date(year, 0, 1);
    const dayOfYear = Math.ceil((now.getTime() - jan1.getTime()) / 86400000);
    const weekNum = Math.ceil((dayOfYear + jan1.getDay()) / 7);
    return `${year}-W${String(weekNum).padStart(2, '0')}`;
  }
}
