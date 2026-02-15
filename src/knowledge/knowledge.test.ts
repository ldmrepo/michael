/**
 * Knowledge Service (NLM) Tests
 * NLM CLI mock으로 nlm-client + knowledge-sync 검증
 *
 * 실제 CLI 커맨드 참조: https://github.com/jacob-bd/notebooklm-mcp-cli
 *   nlm notebook query <id> "question"
 *   nlm source add <id> --text "..." --title "..." --wait
 *   nlm source add <id> --file <path> --wait
 *   nlm source list <id> [--json]
 *   nlm source delete <id> --confirm
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mkdirSync, writeFileSync, readFileSync, rmSync } from 'fs';
import { join } from 'path';
import type { Decision } from '../state-store/types.js';

// Mock child_process.execFile before imports
vi.mock('child_process', () => ({
  execFile: vi.fn(),
}));

import { execFile } from 'child_process';
import { NlmClient } from './nlm-client.js';
import { KnowledgeSync } from './knowledge-sync.js';
import { KnowledgeManager } from './knowledge-manager.js';
import { seedFoundationalKnowledge, FOUNDATIONAL_PREFIX } from './init-agent-knowledge.js';
import type { AgentDefinition } from '../decision/agent-registry.js';

const mockedExecFile = vi.mocked(execFile);

// Helper: execFile success mock
function mockExecSuccess(stdout: string = '') {
  mockedExecFile.mockImplementation((_cmd, _args, _opts, callback) => {
    (callback as any)(null, stdout, '');
    return {} as any;
  });
}

// Helper: execFile failure mock
function mockExecFailure(message: string = 'command not found') {
  mockedExecFile.mockImplementation((_cmd, _args, _opts, callback) => {
    (callback as any)(new Error(message), '', message);
    return {} as any;
  });
}

const TEST_DIR = `test-knowledge-${process.pid}`;
const NOTEBOOK_ID = 'test-notebook-123';

const mockDecision: Decision = {
  id: 'D-20260215-001',
  timestamp: '2026-02-15T14:00:00.000Z',
  action: 'BUY',
  target: 'BTC',
  platform: 'binance_spot',
  amount: 50,
  reason: 'RSI oversold bounce signal',
  inputs_used: ['technical', 'sentiment'],
  mandate_check: { max_single_trade: 'OK(3.4%)', min_cash: 'OK(15%)' },
  status: 'proposed',
};

describe('NlmClient', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('isAvailable', () => {
    it('returns true when nlm CLI is installed', async () => {
      mockExecSuccess('nlm version 0.1.9');
      const result = await NlmClient.isAvailable();
      expect(result).toBe(true);
      expect(mockedExecFile).toHaveBeenCalledWith(
        'nlm',
        ['--version'],
        expect.any(Object),
        expect.any(Function),
      );
    });

    it('returns false when nlm CLI is not installed', async () => {
      mockExecFailure('command not found');
      const result = await NlmClient.isAvailable();
      expect(result).toBe(false);
    });
  });

  describe('query', () => {
    it('parses JSON response and extracts answer field', async () => {
      const jsonResponse = JSON.stringify({
        value: {
          answer: 'BTC shows strong RSI divergence pattern from 2025-12.',
          conversation_id: 'conv-123',
          sources_used: [],
        },
      });
      mockExecSuccess(jsonResponse);
      const client = new NlmClient(NOTEBOOK_ID);
      const result = await client.query('과거 BTC 급락 패턴은?');
      expect(result).toBe('BTC shows strong RSI divergence pattern from 2025-12.');
      expect(mockedExecFile).toHaveBeenCalledWith(
        'nlm',
        ['notebook', 'query', NOTEBOOK_ID, '과거 BTC 급락 패턴은?'],
        expect.any(Object),
        expect.any(Function),
      );
    });

    it('returns raw output when response is not JSON', async () => {
      mockExecSuccess('plain text answer');
      const client = new NlmClient(NOTEBOOK_ID);
      const result = await client.query('test');
      expect(result).toBe('plain text answer');
    });

    it('throws on query failure', async () => {
      mockExecFailure('network error');
      const client = new NlmClient(NOTEBOOK_ID);
      await expect(client.query('test')).rejects.toThrow('network error');
    });
  });

  describe('addSource', () => {
    it('calls nlm source add with --text, --title, --wait', async () => {
      mockExecSuccess('Source added');
      const client = new NlmClient(NOTEBOOK_ID);
      await client.addSource('Test Source', 'some content');
      expect(mockedExecFile).toHaveBeenCalledWith(
        'nlm',
        ['source', 'add', NOTEBOOK_ID, '--text', 'some content', '--title', 'Test Source', '--wait'],
        expect.any(Object),
        expect.any(Function),
      );
    });
  });

  describe('addSourceFile', () => {
    it('calls nlm source add with --file and --wait', async () => {
      mockExecSuccess('Source added');
      const client = new NlmClient(NOTEBOOK_ID);
      await client.addSourceFile('/tmp/output.txt');
      expect(mockedExecFile).toHaveBeenCalledWith(
        'nlm',
        ['source', 'add', NOTEBOOK_ID, '--file', '/tmp/output.txt', '--wait'],
        expect.any(Object),
        expect.any(Function),
      );
    });
  });

  describe('listSources', () => {
    it('parses JSON source list', async () => {
      const sources = [{ id: 's1', title: 'Source A' }, { id: 's2', title: 'Source B' }];
      mockExecSuccess(JSON.stringify(sources));
      const client = new NlmClient(NOTEBOOK_ID);
      const result = await client.listSources();
      expect(result).toEqual(sources);
      expect(mockedExecFile).toHaveBeenCalledWith(
        'nlm',
        ['source', 'list', NOTEBOOK_ID, '--json'],
        expect.any(Object),
        expect.any(Function),
      );
    });

    it('returns empty array on invalid JSON', async () => {
      mockExecSuccess('not json');
      const client = new NlmClient(NOTEBOOK_ID);
      const result = await client.listSources();
      expect(result).toEqual([]);
    });
  });

  describe('deleteSource', () => {
    it('calls nlm source delete with --confirm', async () => {
      mockExecSuccess('Source deleted');
      const client = new NlmClient(NOTEBOOK_ID);
      await client.deleteSource('source-abc');
      expect(mockedExecFile).toHaveBeenCalledWith(
        'nlm',
        ['source', 'delete', 'source-abc', '--confirm'],
        expect.any(Object),
        expect.any(Function),
      );
    });
  });
});

describe('KnowledgeSync', () => {
  let nlm: NlmClient;
  let sync: KnowledgeSync;

  beforeEach(() => {
    vi.clearAllMocks();
    mkdirSync(TEST_DIR, { recursive: true });
    nlm = new NlmClient(NOTEBOOK_ID);
    sync = new KnowledgeSync(nlm, TEST_DIR);
  });

  afterEach(() => {
    rmSync(TEST_DIR, { recursive: true, force: true });
  });

  describe('syncDecision', () => {
    it('adds NLM source with formatted decision data', async () => {
      mockExecSuccess('Source added');
      await sync.syncDecision(mockDecision);

      expect(mockedExecFile).toHaveBeenCalledWith(
        'nlm',
        expect.arrayContaining([
          'source', 'add', NOTEBOOK_ID,
          '--title', 'D-20260215-001: BUY BTC $50',
        ]),
        expect.any(Object),
        expect.any(Function),
      );

      // Check content includes key fields
      const callArgs = mockedExecFile.mock.calls[0][1] as string[];
      const contentIdx = callArgs.indexOf('--text');
      const content = callArgs[contentIdx + 1];
      expect(content).toContain('BUY');
      expect(content).toContain('BTC');
      expect(content).toContain('binance_spot');
      expect(content).toContain('RSI oversold bounce signal');
      expect(content).toContain('max_single_trade: OK(3.4%)');
    });

    it('includes HOLD decisions', async () => {
      mockExecSuccess('Source added');
      const holdDecision: Decision = {
        ...mockDecision,
        id: 'D-20260215-002',
        action: 'HOLD',
        target: '',
        amount: 0,
        reason: 'All indicators normal',
      };
      await sync.syncDecision(holdDecision);
      expect(mockedExecFile).toHaveBeenCalled();
    });
  });

  describe('syncDailySnapshot', () => {
    it('adds source with state.yaml and inputs.yaml content', async () => {
      writeFileSync(join(TEST_DIR, 'state.yaml'), 'state:\n  total_nav: 1500\n');
      writeFileSync(join(TEST_DIR, 'inputs.yaml'), 'inputs:\n  fear_greed: 35\n');
      mockExecSuccess('Source added');

      await sync.syncDailySnapshot();

      expect(mockedExecFile).toHaveBeenCalledWith(
        'nlm',
        expect.arrayContaining(['source', 'add', NOTEBOOK_ID]),
        expect.any(Object),
        expect.any(Function),
      );

      const callArgs = mockedExecFile.mock.calls[0][1] as string[];
      const contentIdx = callArgs.indexOf('--text');
      const content = callArgs[contentIdx + 1];
      expect(content).toContain('Daily Snapshot');
      expect(content).toContain('total_nav: 1500');
      expect(content).toContain('fear_greed: 35');
    });

    it('handles missing state/inputs files gracefully', async () => {
      mockExecSuccess('Source added');
      await sync.syncDailySnapshot();

      // Should still add source (just without YAML blocks)
      expect(mockedExecFile).toHaveBeenCalled();
      const callArgs = mockedExecFile.mock.calls[0][1] as string[];
      const contentIdx = callArgs.indexOf('--text');
      const content = callArgs[contentIdx + 1];
      expect(content).toContain('Daily Snapshot');
      expect(content).not.toContain('Portfolio State');
    });
  });
});

describe('KnowledgeManager', () => {
  const MANAGER_DIR = `test-km-${process.pid}`;

  beforeEach(() => {
    vi.clearAllMocks();
    mkdirSync(MANAGER_DIR, { recursive: true });
  });

  afterEach(() => {
    rmSync(MANAGER_DIR, { recursive: true, force: true });
  });

  describe('getClient', () => {
    it('creates notebook on first access and persists registry', async () => {
      mockExecSuccess('✓ Created notebook: Michael: judgment\n  ID: aaaa1111-2222-3333-4444-555566667777');
      const km = new KnowledgeManager(MANAGER_DIR);
      const client = await km.getClient('judgment');

      expect(client).toBeInstanceOf(NlmClient);
      expect(client.getNotebookId()).toBe('aaaa1111-2222-3333-4444-555566667777');

      // Verify nlm notebook create was called
      expect(mockedExecFile).toHaveBeenCalledWith(
        'nlm',
        ['notebook', 'create', 'Michael: judgment'],
        expect.any(Object),
        expect.any(Function),
      );

      // Verify registry persisted
      const registryContent = readFileSync(join(MANAGER_DIR, 'nlm-notebooks.json'), 'utf-8');
      const registry = JSON.parse(registryContent);
      expect(registry.judgment.notebookId).toBe('aaaa1111-2222-3333-4444-555566667777');
    });

    it('returns cached client on second access without creating notebook', async () => {
      mockExecSuccess('✓ Created notebook: Michael: sentinel\n  ID: bbbb1111-2222-3333-4444-555566667777');
      const km = new KnowledgeManager(MANAGER_DIR);

      const first = await km.getClient('sentinel');
      vi.clearAllMocks();

      const second = await km.getClient('sentinel');
      expect(second).toBe(first); // same instance
      expect(mockedExecFile).not.toHaveBeenCalled(); // no CLI call
    });

    it('loads from persisted registry file', async () => {
      // Pre-populate registry file
      writeFileSync(join(MANAGER_DIR, 'nlm-notebooks.json'), JSON.stringify({
        judgment: {
          notebookId: 'cccc1111-2222-3333-4444-555566667777',
          title: 'Michael: judgment',
          createdAt: '2026-02-15T00:00:00Z',
        },
      }));

      const km = new KnowledgeManager(MANAGER_DIR);
      const client = await km.getClient('judgment');

      expect(client.getNotebookId()).toBe('cccc1111-2222-3333-4444-555566667777');
      expect(mockedExecFile).not.toHaveBeenCalled(); // no create call
    });
  });

  describe('listAgents', () => {
    it('returns all registered agents', () => {
      writeFileSync(join(MANAGER_DIR, 'nlm-notebooks.json'), JSON.stringify({
        judgment: { notebookId: 'id-1', title: 'Michael: judgment', createdAt: '' },
        sentinel: { notebookId: 'id-2', title: 'Michael: sentinel', createdAt: '' },
        snapshot: { notebookId: 'id-3', title: 'Michael: snapshot', createdAt: '' },
      }));

      const km = new KnowledgeManager(MANAGER_DIR);
      const agents = km.listAgents();
      expect(agents).toHaveLength(3);
      expect(agents.map(a => a.name)).toEqual(['judgment', 'sentinel', 'snapshot']);
    });
  });

  describe('registerNotebook', () => {
    it('manually registers existing notebook ID', () => {
      const km = new KnowledgeManager(MANAGER_DIR);
      km.registerNotebook('market', 'dddd1111-2222-3333-4444-555566667777');

      expect(km.getNotebookId('market')).toBe('dddd1111-2222-3333-4444-555566667777');

      // Verify persisted
      const content = readFileSync(join(MANAGER_DIR, 'nlm-notebooks.json'), 'utf-8');
      expect(JSON.parse(content).market.notebookId).toBe('dddd1111-2222-3333-4444-555566667777');
    });
  });
});

describe('seedFoundationalKnowledge', () => {
  const SEED_DIR = `test-seed-${process.pid}`;
  const KNOWLEDGE_DIR = join(SEED_DIR, 'knowledge', 'market-data');

  const mockAgent: AgentDefinition = {
    id: 'market_data',
    name: '시장 데이터 수집가',
    team: 'intelligence',
    role: 'test role',
    instructions: 'test instructions',
    tools: [{ script: 'test.py', skillDir: 'investment' }],
    knowledgeDir: join(SEED_DIR, 'knowledge', 'market-data'),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mkdirSync(KNOWLEDGE_DIR, { recursive: true });
  });

  afterEach(() => {
    rmSync(SEED_DIR, { recursive: true, force: true });
  });

  it('seeds foundational knowledge when file exists and no source present', async () => {
    // Write foundational.md
    const mdContent = '# Market Data — Foundational Knowledge\n\n## 핵심 개념\nTest content';
    writeFileSync(join(KNOWLEDGE_DIR, 'foundational.md'), mdContent);

    // Mock listSources → empty (no existing source)
    const listResponse = JSON.stringify([]);
    mockedExecFile.mockImplementation((_cmd, args, _opts, callback) => {
      const argsArr = args as string[];
      if (argsArr[0] === 'source' && argsArr[1] === 'list') {
        (callback as any)(null, listResponse, '');
      } else if (argsArr[0] === 'source' && argsArr[1] === 'add') {
        (callback as any)(null, 'Source added', '');
      }
      return {} as any;
    });

    const client = new NlmClient(NOTEBOOK_ID);
    const result = await seedFoundationalKnowledge(client, mockAgent);

    expect(result).toBe(true);

    // Verify addSource was called with correct title and content
    const addCall = mockedExecFile.mock.calls.find(
      c => (c[1] as string[])[0] === 'source' && (c[1] as string[])[1] === 'add',
    );
    expect(addCall).toBeDefined();
    const addArgs = addCall![1] as string[];
    expect(addArgs).toContain(`${FOUNDATIONAL_PREFIX} 시장 데이터 수집가`);
    expect(addArgs).toContain(mdContent);
  });

  it('skips when foundational source already exists', async () => {
    writeFileSync(join(KNOWLEDGE_DIR, 'foundational.md'), 'content');

    // Mock listSources → already has [Foundational] source
    const sources = [{ id: 's1', title: `${FOUNDATIONAL_PREFIX} 시장 데이터 수집가` }];
    mockExecSuccess(JSON.stringify(sources));

    const client = new NlmClient(NOTEBOOK_ID);
    const result = await seedFoundationalKnowledge(client, mockAgent);

    expect(result).toBe(false);
    // Should only have called listSources, not addSource
    expect(mockedExecFile).toHaveBeenCalledTimes(1);
  });

  it('skips when foundational.md does not exist', async () => {
    // Don't create foundational.md — directory exists but file doesn't
    const sources: any[] = [];
    mockExecSuccess(JSON.stringify(sources));

    const client = new NlmClient(NOTEBOOK_ID);
    const result = await seedFoundationalKnowledge(client, mockAgent);

    expect(result).toBe(false);
    // Only listSources called
    expect(mockedExecFile).toHaveBeenCalledTimes(1);
  });

  it('attempts seed even when listSources fails', async () => {
    const mdContent = '# Foundational Knowledge\nRecovery test';
    writeFileSync(join(KNOWLEDGE_DIR, 'foundational.md'), mdContent);

    // First call (listSources) fails, second call (addSource) succeeds
    let callCount = 0;
    mockedExecFile.mockImplementation((_cmd, _args, _opts, callback) => {
      callCount++;
      if (callCount === 1) {
        (callback as any)(new Error('network error'), '', 'network error');
      } else {
        (callback as any)(null, 'Source added', '');
      }
      return {} as any;
    });

    const client = new NlmClient(NOTEBOOK_ID);
    const result = await seedFoundationalKnowledge(client, mockAgent);

    expect(result).toBe(true);
    expect(mockedExecFile).toHaveBeenCalledTimes(2); // listSources + addSource
  });
});
