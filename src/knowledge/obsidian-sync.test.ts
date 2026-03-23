import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { existsSync, mkdirSync, rmSync, writeFileSync, readFileSync } from 'fs';
import { join } from 'path';
import { ObsidianSync } from './obsidian-sync.js';
import { ObsidianVault } from './obsidian-vault.js';
import type { KnowledgeManager } from './knowledge-manager.js';
import type { Memory } from '../brain/memory.js';

const TEST_DIR = `test-sync-${process.pid}`;
const VAULT_PATH = join(TEST_DIR, 'vault');
const STATE_DIR = TEST_DIR;

// Mock NlmClient
function mockNlmClient(notes: Array<{ id: string; title: string }> = []) {
  return {
    noteList: vi.fn().mockResolvedValue(notes),
    noteCreate: vi.fn().mockResolvedValue('new-id'),
    addSource: vi.fn().mockResolvedValue(undefined),
    listSources: vi.fn().mockResolvedValue([]),
    query: vi.fn().mockResolvedValue('answer'),
    getNotebookId: vi.fn().mockReturnValue('test-notebook-id'),
  };
}

// Mock KnowledgeManager
function mockKm(clientMap: Record<string, ReturnType<typeof mockNlmClient>> = {}): KnowledgeManager {
  const defaultClient = mockNlmClient();
  return {
    getClient: vi.fn().mockImplementation(async (agentId: string) => {
      return clientMap[agentId] || defaultClient;
    }),
    listAgents: vi.fn().mockReturnValue([]),
    getNotebookId: vi.fn().mockReturnValue(null),
  } as unknown as KnowledgeManager;
}

// Mock Memory
function mockMemory(): Memory {
  return {
    getRecentMessages: vi.fn().mockReturnValue([]),
    getAllFacts: vi.fn().mockReturnValue({}),
  } as unknown as Memory;
}

describe('ObsidianSync', () => {
  let vault: ObsidianVault;
  let memory: Memory;

  beforeEach(() => {
    mkdirSync(TEST_DIR, { recursive: true });
    vault = new ObsidianVault({ vaultPath: VAULT_PATH });
    vault.ensureStructure();
    memory = mockMemory();
  });

  afterEach(() => {
    rmSync(TEST_DIR, { recursive: true, force: true });
  });

  // ─── NLM → Vault Archival ─────────────────────────

  describe('archiveNlmLessons', () => {
    it('archives NLM notes to vault', async () => {
      const client = mockNlmClient([
        { id: 'note-1', title: '[SUCCESS] 2026-02-15: BTC pump trade' },
        { id: 'note-2', title: '[FAILURE] 2026-02-14: Bad entry' },
      ]);
      const km = mockKm({ binance_trader: client });
      const sync = new ObsidianSync(vault, km, memory, STATE_DIR);

      const count = await sync.archiveNlmLessons(['binance_trader']);
      expect(count).toBe(2);

      // Verify files created in lessons/binance
      const notes = vault.listNotes('lessons/binance');
      expect(notes.length).toBe(2);
      expect(notes.some(n => n.frontmatter.nlm_note_id === 'note-1')).toBe(true);
      expect(notes.some(n => n.frontmatter.nlm_note_id === 'note-2')).toBe(true);
    });

    it('skips already-archived notes (dedup)', async () => {
      const client = mockNlmClient([
        { id: 'note-1', title: '[SUCCESS] 2026-02-15: Repeat note' },
      ]);
      const km = mockKm({ binance_trader: client });
      const sync = new ObsidianSync(vault, km, memory, STATE_DIR);

      // First archive
      await sync.archiveNlmLessons(['binance_trader']);
      // Second archive (same notes)
      const count = await sync.archiveNlmLessons(['binance_trader']);
      expect(count).toBe(0);
    });

    it('extracts date from note title', async () => {
      const client = mockNlmClient([
        { id: 'note-d', title: '[SUCCESS] 2026-01-20: Date test' },
      ]);
      const km = mockKm({ binance_trader: client });
      const sync = new ObsidianSync(vault, km, memory, STATE_DIR);

      await sync.archiveNlmLessons(['binance_trader']);
      const notes = vault.listNotes('lessons/binance');
      expect(notes[0].frontmatter.date).toBe('2026-01-20');
    });

    it('maps agent to correct domain/subdir', async () => {
      const pmClient = mockNlmClient([
        { id: 'pm-1', title: 'PM lesson' },
      ]);
      const km = mockKm({ pm_trader: pmClient });
      const sync = new ObsidianSync(vault, km, memory, STATE_DIR);

      await sync.archiveNlmLessons(['pm_trader']);
      const notes = vault.listNotes('lessons/polymarket');
      expect(notes.length).toBe(1);
      expect(notes[0].frontmatter.domain).toBe('polymarket');
    });
  });

  // ─── Vault → NLM Playbook Upload ─────────────────

  describe('syncPlaybooksToNlm', () => {
    it('uploads active playbooks to NLM', async () => {
      // Create a playbook in vault
      vault.createNote({
        frontmatter: {
          title: 'BTC Scalping Strategy',
          date: '2026-02-16',
          type: 'playbook',
          domain: 'binance',
          tags: ['btc', 'scalping'],
          source: 'manual',
          status: 'active',
        },
        content: '# BTC Scalping\n\nBuy dips, sell rips.',
      }, 'playbooks');

      const michaelClient = mockNlmClient();
      const km = mockKm({ michael: michaelClient });
      const sync = new ObsidianSync(vault, km, memory, STATE_DIR);

      const count = await sync.syncPlaybooksToNlm();
      expect(count).toBe(1);
      expect(michaelClient.addSource).toHaveBeenCalledWith(
        '[Playbook] BTC Scalping Strategy',
        expect.stringContaining('BTC Scalping'),
      );
    });

    it('skips unchanged playbooks (hash match)', async () => {
      vault.createNote({
        frontmatter: {
          title: 'Static Playbook',
          date: '2026-02-16',
          type: 'playbook',
          domain: 'general',
          tags: [],
          source: 'manual',
          status: 'active',
        },
        content: 'Same content',
      }, 'playbooks');

      const michaelClient = mockNlmClient();
      const km = mockKm({ michael: michaelClient });
      const sync = new ObsidianSync(vault, km, memory, STATE_DIR);

      await sync.syncPlaybooksToNlm();
      // Second call — should skip
      const count = await sync.syncPlaybooksToNlm();
      expect(count).toBe(0);
    });

    it('re-uploads when playbook content changes', async () => {
      const pbFm = {
        title: 'Evolving Playbook',
        date: '2026-02-16',
        type: 'playbook' as const,
        domain: 'general' as const,
        tags: [] as string[],
        source: 'manual' as const,
        status: 'active' as const,
      };

      const path = vault.createNote({ frontmatter: pbFm, content: 'v1' }, 'playbooks');

      const michaelClient = mockNlmClient();
      const km = mockKm({ michael: michaelClient });
      const sync = new ObsidianSync(vault, km, memory, STATE_DIR);

      await sync.syncPlaybooksToNlm();

      // Modify content
      vault.updateNote(path, 'v2 — updated strategy');

      const count = await sync.syncPlaybooksToNlm();
      expect(count).toBe(1);
    });

    it('skips archived playbooks', async () => {
      vault.createNote({
        frontmatter: {
          title: 'Old Playbook',
          date: '2026-01-01',
          type: 'playbook',
          domain: 'general',
          tags: [],
          source: 'manual',
          status: 'archived',
        },
        content: 'deprecated',
      }, 'playbooks');

      const michaelClient = mockNlmClient();
      const km = mockKm({ michael: michaelClient });
      const sync = new ObsidianSync(vault, km, memory, STATE_DIR);

      const count = await sync.syncPlaybooksToNlm();
      expect(count).toBe(0);
    });
  });

  // ─── Daily / Weekly generation ────────────────────

  describe('generateDailyJournal', () => {
    it('creates daily journal for given date', async () => {
      const km = mockKm();
      const sync = new ObsidianSync(vault, km, memory, STATE_DIR);

      const path = await sync.generateDailyJournal('2026-02-16');
      expect(path).toContain('daily');

      const note = vault.getDailyNote('2026-02-16');
      expect(note).not.toBeNull();
    });

    it('skips if daily journal already exists', async () => {
      const km = mockKm();
      const sync = new ObsidianSync(vault, km, memory, STATE_DIR);

      await sync.generateDailyJournal('2026-02-16');
      const path2 = await sync.generateDailyJournal('2026-02-16');
      // Should return existing path
      expect(path2).toContain('daily');
    });
  });

  describe('generateWeeklyReview', () => {
    it('creates weekly review for given week', async () => {
      const km = mockKm();
      const sync = new ObsidianSync(vault, km, memory, STATE_DIR);

      const path = await sync.generateWeeklyReview('2026-W07');
      expect(path).toContain('weekly');

      const note = vault.getWeeklyNote('2026-W07');
      expect(note).not.toBeNull();
    });

    it('skips if weekly review already exists', async () => {
      const km = mockKm();
      const sync = new ObsidianSync(vault, km, memory, STATE_DIR);

      await sync.generateWeeklyReview('2026-W07');
      const path2 = await sync.generateWeeklyReview('2026-W07');
      expect(path2).toContain('weekly');
    });
  });

  describe('generatePortfolioSnapshot', () => {
    it('creates portfolio snapshot', async () => {
      const km = mockKm();
      const sync = new ObsidianSync(vault, km, memory, STATE_DIR);

      const path = await sync.generatePortfolioSnapshot();
      expect(path).toContain('portfolio');

      const notes = vault.listNotes('portfolio');
      expect(notes.length).toBe(1);
      expect(notes[0].frontmatter.type).toBe('portfolio');
    });
  });

  // ─── Full Sync ────────────────────────────────────

  describe('runFullSync', () => {
    it('runs archival and playbook upload', async () => {
      // Add NLM notes
      const client = mockNlmClient([
        { id: 'n1', title: 'Lesson 1' },
      ]);
      const km = mockKm({ michael: client, binance_trader: client });
      const sync = new ObsidianSync(vault, km, memory, STATE_DIR);

      const stats = await sync.runFullSync();
      expect(stats.errors).toBe(0);
      expect(stats.nlmArchived).toBeGreaterThanOrEqual(0);
    });
  });

  // ─── State Persistence ────────────────────────────

  describe('state persistence', () => {
    it('persists archive state across instances', async () => {
      const client = mockNlmClient([
        { id: 'persist-1', title: 'Persist test' },
      ]);
      const km = mockKm({ michael: client });

      // First instance archives
      const sync1 = new ObsidianSync(vault, km, memory, STATE_DIR);
      await sync1.archiveNlmLessons(['michael']);

      // Second instance should skip the same note
      const sync2 = new ObsidianSync(vault, km, memory, STATE_DIR);
      const count = await sync2.archiveNlmLessons(['michael']);
      expect(count).toBe(0);
    });
  });
});
