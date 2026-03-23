import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { existsSync, mkdirSync, rmSync, readFileSync } from 'fs';
import { join } from 'path';
import { ObsidianVault, VaultNoteFrontmatter } from './obsidian-vault.js';

const TEST_VAULT = `test-vault-${process.pid}`;

describe('ObsidianVault', () => {
  let vault: ObsidianVault;

  beforeEach(() => {
    vault = new ObsidianVault({ vaultPath: TEST_VAULT });
    vault.ensureStructure();
  });

  afterEach(() => {
    rmSync(TEST_VAULT, { recursive: true, force: true });
  });

  // ─── ensureStructure ──────────────────────────────

  describe('ensureStructure', () => {
    it('creates all required directories', () => {
      expect(existsSync(join(TEST_VAULT, 'daily'))).toBe(true);
      expect(existsSync(join(TEST_VAULT, 'weekly'))).toBe(true);
      expect(existsSync(join(TEST_VAULT, 'playbooks'))).toBe(true);
      expect(existsSync(join(TEST_VAULT, 'lessons'))).toBe(true);
      expect(existsSync(join(TEST_VAULT, 'lessons/binance'))).toBe(true);
      expect(existsSync(join(TEST_VAULT, 'lessons/polymarket'))).toBe(true);
      expect(existsSync(join(TEST_VAULT, 'lessons/general'))).toBe(true);
      expect(existsSync(join(TEST_VAULT, 'analysis'))).toBe(true);
      expect(existsSync(join(TEST_VAULT, 'portfolio'))).toBe(true);
      expect(existsSync(join(TEST_VAULT, 'templates'))).toBe(true);
    });

    it('creates default templates', () => {
      expect(existsSync(join(TEST_VAULT, 'templates/daily.md'))).toBe(true);
      expect(existsSync(join(TEST_VAULT, 'templates/weekly.md'))).toBe(true);
      expect(existsSync(join(TEST_VAULT, 'templates/lesson.md'))).toBe(true);
      expect(existsSync(join(TEST_VAULT, 'templates/playbook.md'))).toBe(true);
    });

    it('creates _index.md', () => {
      expect(existsSync(join(TEST_VAULT, '_index.md'))).toBe(true);
    });

    it('is idempotent', () => {
      vault.ensureStructure();
      vault.ensureStructure();
      expect(existsSync(join(TEST_VAULT, 'daily'))).toBe(true);
    });
  });

  // ─── CRUD ─────────────────────────────────────────

  describe('createNote / readNote', () => {
    it('creates and reads a note with frontmatter', () => {
      const fm: VaultNoteFrontmatter = {
        title: 'Test Lesson',
        date: '2026-02-16',
        type: 'lesson',
        domain: 'binance',
        tags: ['test', 'binance'],
        source: 'nlm',
        nlm_note_id: 'abc-123',
        status: 'active',
      };

      const path = vault.createNote({ frontmatter: fm, content: 'Hello world' }, 'lessons/binance');
      expect(path).toContain('lessons/binance');
      expect(path).toContain('.md');

      const note = vault.readNote(path);
      expect(note).not.toBeNull();
      expect(note!.frontmatter.title).toBe('Test Lesson');
      expect(note!.frontmatter.domain).toBe('binance');
      expect(note!.frontmatter.nlm_note_id).toBe('abc-123');
      expect(note!.content).toBe('Hello world');
    });

    it('returns null for non-existent note', () => {
      expect(vault.readNote('nonexistent.md')).toBeNull();
    });
  });

  describe('updateNote', () => {
    it('updates content and partial frontmatter', () => {
      const fm: VaultNoteFrontmatter = {
        title: 'Original',
        date: '2026-02-16',
        type: 'lesson',
        domain: 'general',
        tags: [],
        source: 'manual',
        status: 'active',
      };

      const path = vault.createNote({ frontmatter: fm, content: 'Old content' });
      vault.updateNote(path, 'New content', { status: 'archived' });

      const updated = vault.readNote(path);
      expect(updated!.content).toBe('New content');
      expect(updated!.frontmatter.status).toBe('archived');
      expect(updated!.frontmatter.title).toBe('Original'); // unchanged
    });

    it('throws for non-existent note', () => {
      expect(() => vault.updateNote('nonexistent.md', 'content')).toThrow('Note not found');
    });
  });

  describe('deleteNote', () => {
    it('deletes existing note', () => {
      const fm: VaultNoteFrontmatter = {
        title: 'To Delete',
        date: '2026-02-16',
        type: 'lesson',
        domain: 'general',
        tags: [],
        source: 'manual',
        status: 'active',
      };

      const path = vault.createNote({ frontmatter: fm, content: 'bye' });
      expect(vault.readNote(path)).not.toBeNull();

      vault.deleteNote(path);
      expect(vault.readNote(path)).toBeNull();
    });

    it('no-op for non-existent note', () => {
      // Should not throw
      vault.deleteNote('nonexistent.md');
    });
  });

  // ─── Listing & Search ─────────────────────────────

  describe('listNotes', () => {
    it('lists notes in subdirectory', () => {
      const notes = [
        { title: 'Note A', date: '2026-02-14' },
        { title: 'Note B', date: '2026-02-15' },
        { title: 'Note C', date: '2026-02-16' },
      ];

      for (const n of notes) {
        vault.createNote({
          frontmatter: { ...makeBaseFm(), ...n },
          content: `Content of ${n.title}`,
        }, 'lessons/general');
      }

      const result = vault.listNotes('lessons/general');
      expect(result.length).toBe(3);
      // Sorted by date DESC
      expect(result[0].frontmatter.date).toBe('2026-02-16');
      expect(result[2].frontmatter.date).toBe('2026-02-14');
    });

    it('returns empty for non-existent directory', () => {
      expect(vault.listNotes('nonexistent')).toEqual([]);
    });
  });

  describe('searchNotes', () => {
    beforeEach(() => {
      vault.createNote({
        frontmatter: { ...makeBaseFm(), title: 'BTC Trading Lesson', type: 'lesson', domain: 'binance', tags: ['btc'] },
        content: 'BTC pump trade',
      }, 'lessons/binance');

      vault.createNote({
        frontmatter: { ...makeBaseFm(), title: 'PM Strategy', type: 'playbook', domain: 'polymarket', tags: ['strategy'] },
        content: 'Polymarket playbook',
      }, 'playbooks');

      vault.createNote({
        frontmatter: { ...makeBaseFm(), title: 'Archived Note', type: 'lesson', domain: 'general', status: 'archived' },
        content: 'Old stuff',
      }, 'lessons/general');
    });

    it('filters by type', () => {
      const results = vault.searchNotes({ type: 'playbook' });
      expect(results.length).toBe(1);
      expect(results[0].frontmatter.title).toBe('PM Strategy');
    });

    it('filters by domain', () => {
      const results = vault.searchNotes({ domain: 'binance' });
      expect(results.length).toBe(1);
    });

    it('filters by status', () => {
      const results = vault.searchNotes({ status: 'archived' });
      expect(results.length).toBe(1);
      expect(results[0].frontmatter.title).toBe('Archived Note');
    });

    it('filters by tags', () => {
      const results = vault.searchNotes({ tags: ['btc'] });
      expect(results.length).toBe(1);
    });

    it('filters by date range', () => {
      vault.createNote({
        frontmatter: { ...makeBaseFm(), title: 'Old', date: '2026-01-01' },
        content: 'old',
      }, 'lessons/general');

      const results = vault.searchNotes({ dateFrom: '2026-02-01' });
      // All notes created with makeBaseFm have today's date
      expect(results.length).toBeGreaterThanOrEqual(3);
    });
  });

  describe('searchByContent', () => {
    beforeEach(() => {
      vault.createNote({
        frontmatter: { ...makeBaseFm(), title: 'Hedge Mode' },
        content: 'Binance Futures Hedge mode requires positionSide',
      }, 'lessons/binance');

      vault.createNote({
        frontmatter: { ...makeBaseFm(), title: 'USDC Guide' },
        content: 'Polymarket only accepts USDC.e bridged tokens',
      }, 'lessons/polymarket');
    });

    it('finds notes by content keyword', () => {
      const results = vault.searchByContent('Hedge');
      expect(results.length).toBe(1);
      expect(results[0].frontmatter.title).toBe('Hedge Mode');
    });

    it('finds notes by title keyword', () => {
      const results = vault.searchByContent('USDC');
      expect(results.length).toBe(1);
    });

    it('respects limit', () => {
      const results = vault.searchByContent('mode tokens', { limit: 1 });
      expect(results.length).toBeLessThanOrEqual(1);
    });

    it('returns empty for no match', () => {
      const results = vault.searchByContent('zzznonexistent');
      expect(results.length).toBe(0);
    });
  });

  // ─── Daily / Weekly ───────────────────────────────

  describe('daily notes', () => {
    it('creates and retrieves daily note', () => {
      const path = vault.createDailyNote('2026-02-16');
      expect(path).toBe(join('daily', '2026-02-16.md'));

      const note = vault.getDailyNote('2026-02-16');
      expect(note).not.toBeNull();
      expect(note!.frontmatter.type).toBe('daily');
      expect(note!.content).toContain('Daily Journal');
    });

    it('returns null for non-existent daily note', () => {
      expect(vault.getDailyNote('2099-01-01')).toBeNull();
    });
  });

  describe('weekly notes', () => {
    it('creates and retrieves weekly note', () => {
      const path = vault.createWeeklyNote('2026-W07');
      expect(path).toBe(join('weekly', '2026-W07.md'));

      const note = vault.getWeeklyNote('2026-W07');
      expect(note).not.toBeNull();
      expect(note!.frontmatter.type).toBe('weekly');
      expect(note!.content).toContain('Weekly Review');
    });

    it('returns null for non-existent weekly note', () => {
      expect(vault.getWeeklyNote('2099-W99')).toBeNull();
    });
  });

  // ─── Templates ────────────────────────────────────

  describe('renderTemplate', () => {
    it('replaces template variables', () => {
      const rendered = vault.renderTemplate('lesson.md', {
        title: 'My Lesson',
        date: '2026-02-16',
        domain: 'binance',
        source: 'nlm',
        nlm_notebook: 'binance_trader',
        nlm_note_id: 'uuid-123',
        content: 'Important stuff here',
      });

      expect(rendered).toContain('My Lesson');
      expect(rendered).toContain('2026-02-16');
      expect(rendered).toContain('binance');
      expect(rendered).toContain('Important stuff here');
    });

    it('throws for non-existent template', () => {
      expect(() => vault.renderTemplate('nonexistent.md', {})).toThrow('Template not found');
    });
  });

  // ─── Frontmatter round-trip ───────────────────────

  describe('frontmatter round-trip', () => {
    it('preserves all frontmatter fields through write/read cycle', () => {
      const fm: VaultNoteFrontmatter = {
        title: 'Round Trip Test',
        date: '2026-02-16',
        type: 'playbook',
        domain: 'polymarket',
        tags: ['test', 'roundtrip', 'yaml'],
        source: 'manual',
        nlm_notebook: 'pm_trader',
        nlm_note_id: 'note-uuid',
        status: 'draft',
      };

      const path = vault.createNote({ frontmatter: fm, content: 'Body text' }, 'playbooks');
      const note = vault.readNote(path);
      expect(note).not.toBeNull();
      expect(note!.frontmatter.title).toBe(fm.title);
      expect(note!.frontmatter.type).toBe(fm.type);
      expect(note!.frontmatter.domain).toBe(fm.domain);
      expect(note!.frontmatter.tags).toEqual(fm.tags);
      expect(note!.frontmatter.source).toBe(fm.source);
      expect(note!.frontmatter.nlm_notebook).toBe(fm.nlm_notebook);
      expect(note!.frontmatter.nlm_note_id).toBe(fm.nlm_note_id);
      expect(note!.frontmatter.status).toBe(fm.status);
      expect(note!.content).toBe('Body text');
    });
  });
});

// ─── Helpers ──────────────────────────────────────────

function makeBaseFm(): VaultNoteFrontmatter {
  return {
    title: 'Test Note',
    date: new Date().toISOString().substring(0, 10),
    type: 'lesson',
    domain: 'general',
    tags: [],
    source: 'manual',
    status: 'active',
  };
}
