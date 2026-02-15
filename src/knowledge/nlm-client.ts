/**
 * NlmClient — nlm CLI 래퍼
 * NotebookLM CLI (notebooklm-mcp-cli) 를 child_process.execFile로 호출
 * NLM 미설치/미설정 시 graceful skip
 *
 * 실제 CLI 커맨드 (docs/CLI_GUIDE.md 기준):
 *   nlm notebook query <id> "question"
 *   nlm source add <id> --text "..." --title "..." --wait
 *   nlm source add <id> --file <path> --wait
 *   nlm source list <id> [--json]
 *   nlm source delete <id> --confirm
 *
 * Note CRUD:
 *   nlm note create <notebook_id> --title "..." --content "..."
 *   nlm note list <notebook_id> --json
 *   nlm note update <notebook_id> <note_id> --content "..." [--title "..."]
 *   nlm note delete <notebook_id> <note_id> --confirm
 *
 * Notebook describe:
 *   nlm describe notebook <id>
 */

import { execFile } from 'child_process';
import { log } from '../utils/logger.js';

export interface NotebookOutline {
  summary: string;
  topics: string[];
}

const NLM_BIN = process.env.NLM_BIN || 'nlm';
const EXEC_TIMEOUT = 60_000; // 60s — query can be slow

export class NlmClient {
  constructor(private notebookId: string) {}

  /**
   * nlm CLI가 설치되어 있는지 확인
   */
  static async isAvailable(): Promise<boolean> {
    try {
      await NlmClient.execRaw(['--version']);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * nlm notebook query <id> "question"
   * 응답 형식: {"value":{"answer":"...","conversation_id":"...","sources_used":[]}}
   * answer 필드만 추출하여 반환
   */
  async query(question: string): Promise<string> {
    const raw = await this.exec(['notebook', 'query', this.notebookId, question]);
    try {
      const parsed = JSON.parse(raw);
      return parsed?.value?.answer || raw;
    } catch {
      return raw;
    }
  }

  /**
   * nlm source add <id> --text "<content>" --title "<title>" --wait
   */
  async addSource(title: string, content: string): Promise<void> {
    await this.exec([
      'source', 'add', this.notebookId,
      '--text', content,
      '--title', title,
      '--wait',
    ]);
  }

  /**
   * nlm source add <id> --file <path> --wait
   */
  async addSourceFile(filePath: string): Promise<void> {
    await this.exec([
      'source', 'add', this.notebookId,
      '--file', filePath,
      '--wait',
    ]);
  }

  /**
   * nlm source list <id> --json
   */
  async listSources(): Promise<Array<{ id: string; title: string }>> {
    const raw = await this.exec(['source', 'list', this.notebookId, '--json']);
    try {
      return JSON.parse(raw);
    } catch {
      return [];
    }
  }

  /**
   * nlm source delete <id> --confirm
   */
  async deleteSource(sourceId: string): Promise<void> {
    await this.exec(['source', 'delete', sourceId, '--confirm']);
  }

  /**
   * nlm notebook create "title"
   * 출력: "✓ Created notebook: ...\n  ID: <uuid>"
   * 생성된 notebook ID 반환
   */
  static async createNotebook(title: string): Promise<string> {
    const raw = await NlmClient.execRaw(['notebook', 'create', title]);
    const match = raw.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/);
    if (!match) {
      throw new Error(`Failed to parse notebook ID from: ${raw}`);
    }
    return match[0];
  }

  /**
   * nlm describe notebook <id>
   * 응답: {"value":{"summary":["요약..."],"suggested_topics":[]}}
   */
  async describeNotebook(): Promise<NotebookOutline> {
    const raw = await this.exec(['describe', 'notebook', this.notebookId]);
    try {
      const parsed = JSON.parse(raw);
      const summaryArr = parsed?.value?.summary || [];
      return {
        summary: Array.isArray(summaryArr) ? summaryArr.join('\n') : String(summaryArr),
        topics: parsed?.value?.suggested_topics || [],
      };
    } catch {
      return { summary: raw, topics: [] };
    }
  }

  /**
   * nlm note create <notebook_id> --title "..." --content "..."
   */
  async noteCreate(title: string, content: string): Promise<string> {
    const raw = await this.exec([
      'note', 'create', this.notebookId,
      '--title', title, '--content', content,
    ]);
    const match = raw.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/);
    return match?.[0] || raw;
  }

  /**
   * nlm note list <notebook_id> --json
   */
  async noteList(): Promise<Array<{ id: string; title: string }>> {
    const raw = await this.exec(['note', 'list', this.notebookId, '--json']);
    try {
      const parsed = JSON.parse(raw);
      return parsed?.notes || [];
    } catch {
      return [];
    }
  }

  /**
   * nlm note update <notebook_id> <note_id> --content "..."
   */
  async noteUpdate(noteId: string, content: string, title?: string): Promise<void> {
    const args = ['note', 'update', this.notebookId, noteId, '--content', content];
    if (title) args.push('--title', title);
    await this.exec(args);
  }

  /**
   * nlm note delete <notebook_id> <note_id> --confirm
   */
  async noteDelete(noteId: string): Promise<void> {
    await this.exec(['note', 'delete', this.notebookId, noteId, '--confirm']);
  }

  getNotebookId(): string {
    return this.notebookId;
  }

  // ─── Internal ─────────────────────────────────────────

  private exec(args: string[]): Promise<string> {
    return NlmClient.execRaw(args);
  }

  static execRaw(args: string[]): Promise<string> {
    return new Promise((resolve, reject) => {
      execFile(NLM_BIN, args, { timeout: EXEC_TIMEOUT }, (error, stdout, stderr) => {
        if (error) {
          log('warn', `⚠️ nlm ${args[0]} failed: ${stderr || error.message}`);
          reject(new Error(stderr || error.message));
          return;
        }
        resolve(stdout.trim());
      });
    });
  }
}
