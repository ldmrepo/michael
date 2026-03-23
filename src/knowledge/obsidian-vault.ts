/**
 * ObsidianVault — Obsidian Vault CRUD & 검색 모듈
 *
 * Obsidian vault는 "마크다운 파일 폴더"일 뿐. Obsidian 앱이나 플러그인 불필요.
 * 모든 파일 I/O는 동기 (Memory 패턴 따름).
 * 프론트매터는 js-yaml로 파싱/렌더링.
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync, unlinkSync, statSync } from 'fs';
import { join, relative, basename, extname } from 'path';
import yaml from 'js-yaml';
import { log } from '../utils/logger.js';

// ─── Types ──────────────────────────────────────────

export interface VaultNoteFrontmatter {
  title: string;
  date: string;                     // YYYY-MM-DD
  type: 'daily' | 'weekly' | 'lesson' | 'playbook' | 'analysis' | 'portfolio';
  domain: 'binance' | 'polymarket' | 'portfolio' | 'risk' | 'general';
  tags: string[];
  source: 'nlm' | 'manual' | 'auto-generated';
  nlm_notebook?: string;            // 원본 NLM 노트북명
  nlm_note_id?: string;             // 원본 NLM 노트 ID (중복방지)
  status: 'active' | 'archived' | 'draft';
  [key: string]: unknown;
}

export interface VaultNote {
  path: string;                     // vault 내 상대 경로
  frontmatter: VaultNoteFrontmatter;
  content: string;                  // 프론트매터 이후 본문
  rawContent: string;               // 전체 파일 내용
}

export interface SearchOptions {
  type?: VaultNoteFrontmatter['type'];
  domain?: VaultNoteFrontmatter['domain'];
  tags?: string[];
  status?: VaultNoteFrontmatter['status'];
  dateFrom?: string;                // YYYY-MM-DD
  dateTo?: string;                  // YYYY-MM-DD
  limit?: number;
}

export interface VaultConfig {
  vaultPath: string;
}

// ─── Vault 디렉토리 구조 ──────────────────────────────

const VAULT_DIRS = [
  'daily',
  'weekly',
  'playbooks',
  'lessons',
  'lessons/binance',
  'lessons/polymarket',
  'lessons/general',
  'analysis',
  'portfolio',
  'templates',
] as const;

// ─── 기본 템플릿 ──────────────────────────────────────

const DEFAULT_TEMPLATES: Record<string, string> = {
  'daily.md': `---
title: "Daily Journal — {{date}}"
date: "{{date}}"
type: daily
domain: general
tags: [journal, daily]
source: auto-generated
status: active
---

# Daily Journal — {{date}}

## Market Summary


## Trades Executed


## Lessons Learned


## Tomorrow's Plan

`,
  'weekly.md': `---
title: "Weekly Review — {{week}}"
date: "{{date}}"
type: weekly
domain: general
tags: [review, weekly]
source: auto-generated
status: active
---

# Weekly Review — {{week}}

## Performance Summary


## Key Decisions


## Lessons


## Next Week Plan

`,
  'lesson.md': `---
title: "{{title}}"
date: "{{date}}"
type: lesson
domain: "{{domain}}"
tags: [lesson]
source: "{{source}}"
nlm_notebook: "{{nlm_notebook}}"
nlm_note_id: "{{nlm_note_id}}"
status: active
---

# {{title}}

{{content}}
`,
  'playbook.md': `---
title: "{{title}}"
date: "{{date}}"
type: playbook
domain: "{{domain}}"
tags: [playbook]
source: manual
status: active
---

# {{title}}

## Strategy


## Entry Criteria


## Exit Criteria


## Risk Management

`,
};

// ─── Class ──────────────────────────────────────────

export class ObsidianVault {
  private vaultPath: string;

  constructor(config: VaultConfig) {
    this.vaultPath = config.vaultPath;
  }

  /**
   * Vault 디렉토리 구조 생성 (멱등)
   */
  ensureStructure(): void {
    if (!existsSync(this.vaultPath)) {
      mkdirSync(this.vaultPath, { recursive: true });
    }

    for (const dir of VAULT_DIRS) {
      const dirPath = join(this.vaultPath, dir);
      if (!existsSync(dirPath)) {
        mkdirSync(dirPath, { recursive: true });
      }
    }

    // 기본 템플릿 생성 (없는 경우만)
    for (const [filename, content] of Object.entries(DEFAULT_TEMPLATES)) {
      const templatePath = join(this.vaultPath, 'templates', filename);
      if (!existsSync(templatePath)) {
        writeFileSync(templatePath, content, 'utf-8');
      }
    }

    // _index.md (MOC) 생성
    const indexPath = join(this.vaultPath, '_index.md');
    if (!existsSync(indexPath)) {
      writeFileSync(indexPath, `# Obsidian Vault — Michael's Knowledge Base

## Structure
- **daily/** — Daily trading journals
- **weekly/** — Weekly review reports
- **playbooks/** — Curated strategy playbooks
- **lessons/** — Archived lessons from NLM
- **analysis/** — Market analysis notes
- **portfolio/** — Portfolio snapshots
- **templates/** — Note templates
`, 'utf-8');
    }

    log('info', `📓 Vault structure ensured: ${this.vaultPath}`);
  }

  /**
   * 노트 생성. 파일 경로 반환.
   */
  createNote(
    note: { frontmatter: VaultNoteFrontmatter; content: string },
    subdir: string = '',
  ): string {
    const filename = this.slugify(note.frontmatter.title) + '.md';
    const relPath = subdir ? join(subdir, filename) : filename;
    const fullPath = join(this.vaultPath, relPath);

    // 디렉토리 확보
    const dir = join(this.vaultPath, subdir);
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true });
    }

    const raw = this.serializeNote(note.frontmatter, note.content);
    writeFileSync(fullPath, raw, 'utf-8');

    return relPath;
  }

  /**
   * 노트 읽기
   */
  readNote(relPath: string): VaultNote | null {
    const fullPath = join(this.vaultPath, relPath);
    if (!existsSync(fullPath)) return null;

    try {
      const rawContent = readFileSync(fullPath, 'utf-8');
      const { frontmatter, content } = this.parseNote(rawContent);
      return { path: relPath, frontmatter, content, rawContent };
    } catch (e) {
      log('warn', `⚠️ Failed to read vault note: ${relPath}: ${e}`);
      return null;
    }
  }

  /**
   * 노트 수정
   */
  updateNote(
    relPath: string,
    content: string,
    frontmatter?: Partial<VaultNoteFrontmatter>,
  ): void {
    const existing = this.readNote(relPath);
    if (!existing) {
      throw new Error(`Note not found: ${relPath}`);
    }

    const updatedFm = frontmatter
      ? { ...existing.frontmatter, ...frontmatter }
      : existing.frontmatter;
    const raw = this.serializeNote(updatedFm, content);
    writeFileSync(join(this.vaultPath, relPath), raw, 'utf-8');
  }

  /**
   * 노트 삭제
   */
  deleteNote(relPath: string): void {
    const fullPath = join(this.vaultPath, relPath);
    if (existsSync(fullPath)) {
      unlinkSync(fullPath);
    }
  }

  /**
   * 디렉토리 내 노트 목록
   */
  listNotes(subdir: string = ''): VaultNote[] {
    const dir = join(this.vaultPath, subdir);
    if (!existsSync(dir)) return [];

    const notes: VaultNote[] = [];
    this.walkDir(dir, (filePath) => {
      if (extname(filePath) !== '.md') return;
      const relPath = relative(this.vaultPath, filePath);
      if (basename(relPath).startsWith('_')) return; // skip _index.md etc.

      const note = this.readNote(relPath);
      if (note) notes.push(note);
    });

    // 날짜 내림차순 정렬
    notes.sort((a, b) => b.frontmatter.date.localeCompare(a.frontmatter.date));
    return notes;
  }

  /**
   * 프론트매터 기반 검색
   */
  searchNotes(options: SearchOptions): VaultNote[] {
    const allNotes = this.listNotes();
    return this.filterNotes(allNotes, options);
  }

  /**
   * 본문 텍스트 검색
   */
  searchByContent(query: string, options?: SearchOptions & { limit?: number }): VaultNote[] {
    const allNotes = this.listNotes();
    const queryLower = query.toLowerCase();

    // 쿼리를 단어로 분리하여 각 단어가 제목, 본문, 또는 태그에 포함되는지 체크
    const queryWords = queryLower.split(/\s+/).filter(w => w.length > 1);

    let results = allNotes.filter(note => {
      // 태그도 검색 대상에 포함
      const tags = note.frontmatter.tags?.join(' ') || '';
      const searchable = `${note.frontmatter.title} ${note.content} ${tags}`.toLowerCase();
      return queryWords.some(word => searchable.includes(word));
    });

    // 프론트매터 필터 추가 적용
    if (options) {
      results = this.filterNotes(results, options);
    }

    const limit = options?.limit || 10;
    return results.slice(0, limit);
  }

  /**
   * Daily 노트 조회
   */
  getDailyNote(date?: string): VaultNote | null {
    const d = date || this.today();
    const filename = `${d}.md`;
    return this.readNote(join('daily', filename));
  }

  /**
   * Daily 노트 생성
   */
  createDailyNote(date?: string): string {
    const d = date || this.today();
    const content = this.renderTemplate('daily.md', { date: d });
    const filename = `${d}.md`;
    const relPath = join('daily', filename);
    const fullPath = join(this.vaultPath, relPath);

    if (!existsSync(join(this.vaultPath, 'daily'))) {
      mkdirSync(join(this.vaultPath, 'daily'), { recursive: true });
    }

    writeFileSync(fullPath, content, 'utf-8');
    return relPath;
  }

  /**
   * Weekly 노트 조회
   */
  getWeeklyNote(weekStr?: string): VaultNote | null {
    const w = weekStr || this.currentWeek();
    const filename = `${w}.md`;
    return this.readNote(join('weekly', filename));
  }

  /**
   * Weekly 노트 생성
   */
  createWeeklyNote(weekStr?: string): string {
    const w = weekStr || this.currentWeek();
    const content = this.renderTemplate('weekly.md', {
      week: w,
      date: this.today(),
    });
    const filename = `${w}.md`;
    const relPath = join('weekly', filename);
    const fullPath = join(this.vaultPath, relPath);

    if (!existsSync(join(this.vaultPath, 'weekly'))) {
      mkdirSync(join(this.vaultPath, 'weekly'), { recursive: true });
    }

    writeFileSync(fullPath, content, 'utf-8');
    return relPath;
  }

  /**
   * 템플릿 렌더링
   */
  renderTemplate(name: string, vars: Record<string, string>): string {
    const templatePath = join(this.vaultPath, 'templates', name);
    if (!existsSync(templatePath)) {
      throw new Error(`Template not found: ${name}`);
    }

    let content = readFileSync(templatePath, 'utf-8');
    for (const [key, value] of Object.entries(vars)) {
      content = content.replace(new RegExp(`\\{\\{${key}\\}\\}`, 'g'), value);
    }
    return content;
  }

  /**
   * Vault 경로 반환
   */
  getVaultPath(): string {
    return this.vaultPath;
  }

  // ─── Internal ─────────────────────────────────────

  private parseNote(raw: string): { frontmatter: VaultNoteFrontmatter; content: string } {
    const fmRegex = /^---\n([\s\S]*?)\n---\n?([\s\S]*)$/;
    const match = raw.match(fmRegex);

    if (!match) {
      // No frontmatter — return defaults
      return {
        frontmatter: this.defaultFrontmatter(),
        content: raw.trim(),
      };
    }

    try {
      const parsed = yaml.load(match[1]) as Partial<VaultNoteFrontmatter>;
      const frontmatter: VaultNoteFrontmatter = {
        title: parsed.title || 'Untitled',
        date: parsed.date || this.today(),
        type: parsed.type || 'lesson',
        domain: parsed.domain || 'general',
        tags: parsed.tags || [],
        source: parsed.source || 'manual',
        status: parsed.status || 'active',
        ...parsed,
      };
      return { frontmatter, content: match[2].trim() };
    } catch {
      return { frontmatter: this.defaultFrontmatter(), content: raw.trim() };
    }
  }

  private serializeNote(frontmatter: VaultNoteFrontmatter, content: string): string {
    const fmStr = yaml.dump(frontmatter, {
      lineWidth: -1,
      quotingType: '"',
      forceQuotes: false,
    }).trim();
    return `---\n${fmStr}\n---\n\n${content}\n`;
  }

  private defaultFrontmatter(): VaultNoteFrontmatter {
    return {
      title: 'Untitled',
      date: this.today(),
      type: 'lesson',
      domain: 'general',
      tags: [],
      source: 'manual',
      status: 'active',
    };
  }

  private filterNotes(notes: VaultNote[], options: SearchOptions): VaultNote[] {
    let filtered = notes;

    if (options.type) {
      filtered = filtered.filter(n => n.frontmatter.type === options.type);
    }
    if (options.domain) {
      filtered = filtered.filter(n => n.frontmatter.domain === options.domain);
    }
    if (options.status) {
      filtered = filtered.filter(n => n.frontmatter.status === options.status);
    }
    if (options.tags && options.tags.length > 0) {
      filtered = filtered.filter(n =>
        options.tags!.some(tag => n.frontmatter.tags.includes(tag)),
      );
    }
    if (options.dateFrom) {
      filtered = filtered.filter(n => n.frontmatter.date >= options.dateFrom!);
    }
    if (options.dateTo) {
      filtered = filtered.filter(n => n.frontmatter.date <= options.dateTo!);
    }
    if (options.limit) {
      filtered = filtered.slice(0, options.limit);
    }

    return filtered;
  }

  private walkDir(dir: string, callback: (filePath: string) => void): void {
    if (!existsSync(dir)) return;

    const entries = readdirSync(dir);
    for (const entry of entries) {
      const fullPath = join(dir, entry);
      try {
        const stat = statSync(fullPath);
        if (stat.isDirectory()) {
          // Skip templates directory when listing notes
          if (basename(fullPath) === 'templates') continue;
          this.walkDir(fullPath, callback);
        } else if (stat.isFile()) {
          callback(fullPath);
        }
      } catch {
        // Skip inaccessible files
      }
    }
  }

  private slugify(title: string): string {
    return title
      .toLowerCase()
      .replace(/[^a-z0-9가-힣\s-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '')
      .substring(0, 100) || 'untitled';
  }

  private today(): string {
    return new Date().toISOString().substring(0, 10);
  }

  private currentWeek(): string {
    const now = new Date();
    const year = now.getFullYear();
    // ISO week number
    const jan1 = new Date(year, 0, 1);
    const dayOfYear = Math.ceil((now.getTime() - jan1.getTime()) / 86400000);
    const weekNum = Math.ceil((dayOfYear + jan1.getDay()) / 7);
    return `${year}-W${String(weekNum).padStart(2, '0')}`;
  }
}
