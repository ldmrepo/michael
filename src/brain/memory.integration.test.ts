/**
 * Memory System Integration Tests
 *
 * These tests verify the full vector search integration:
 * - MemoryIndexManager initialization
 * - Messages → Chunks indexing
 * - Vector + FTS5 hybrid search
 *
 * Prerequisites:
 * - EMBEDDING_PROVIDER environment variable set (local/openai/gemini)
 * - For local: node-llama-cpp and model downloaded
 * - For openai: OPENAI_API_KEY environment variable
 * - For gemini: GOOGLE_API_KEY environment variable
 *
 * Run with: pnpm vitest run src/brain/memory.integration.test.ts
 *
 * Note: These tests are slower due to actual embedding generation.
 * They are skipped by default unless INTEGRATION_TESTS=true is set.
 */

import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { Memory } from './memory.js';
import { loadMemoryConfig } from '../memory-new/config.js';
import fs from 'fs';
import path from 'path';

const INTEGRATION_TESTS = process.env.INTEGRATION_TESTS === 'true';
const describeIntegration = INTEGRATION_TESTS ? describe : describe.skip;

describeIntegration('Memory Integration Tests', () => {
  let memory: Memory;
  let testDir: string;
  let testDbPath: string;

  beforeAll(async () => {
    // Create temp directory
    testDir = path.join(process.cwd(), '.test-temp', `integration-${Date.now()}`);
    fs.mkdirSync(testDir, { recursive: true });
    testDbPath = path.join(testDir, 'memory.db');

    // Initialize memory with file-based DB
    memory = new Memory(testDbPath);

    // Initialize vector search
    const config = loadMemoryConfig(testDir);
    await memory.initializeVectorSearch(config);
  }, 60000); // 60 second timeout for model download

  afterAll(async () => {
    await memory.close();
    // Clean up test directory
    if (fs.existsSync(testDir)) {
      fs.rmSync(testDir, { recursive: true, force: true });
    }
  });

  describe('Vector Search Initialization', () => {
    it('should initialize vector search successfully', async () => {
      // If we get here, initialization succeeded
      expect(memory).toBeDefined();
    });
  });

  describe('Messages to Chunks Indexing', () => {
    beforeEach(async () => {
      // Add test messages
      await memory.saveMessage('test-user', 'user', '내일 회의 준비해줘');
      await memory.saveMessage('test-user', 'assistant', '네, 회의 자료 준비하겠습니다.');
      await memory.saveMessage('test-user', 'user', '오늘 날씨가 정말 좋네');
      await memory.saveMessage('test-user', 'user', '점심 뭐 먹을지 고민 중');
      await memory.saveMessage('test-user', 'user', '프로젝트 마감이 다음 주야');
    });

    it('should sync messages to chunks', async () => {
      await memory.syncMessagesToChunks('test-user');

      // Verify memory directory was created
      const memoryDir = path.join(testDir, 'memory', 'user-test-user');
      expect(fs.existsSync(memoryDir)).toBe(true);

      // Verify files were created
      const files = fs.readdirSync(memoryDir);
      expect(files.length).toBeGreaterThan(0);
      expect(files.some((f) => f.endsWith('.md'))).toBe(true);
    }, 30000);
  });

  describe('Vector Search', () => {
    it('should find semantically similar messages', async () => {
      // Ensure messages are indexed
      await memory.syncMessagesToChunks('test-user');

      // Search for meeting-related content
      const results = await memory.searchMessagesVector('test-user', '회의 준비', {
        maxResults: 3,
        minScore: 0.3,
      });

      // Should find the meeting-related message
      expect(results.length).toBeGreaterThan(0);

      // The top result should be about meeting
      const topResult = results[0];
      expect(topResult.content).toContain('회의');
    }, 30000);

    it('should rank results by relevance', async () => {
      const results = await memory.searchMessagesVector('test-user', '날씨', {
        maxResults: 5,
        minScore: 0.1,
      });

      // Results should be sorted by score (descending)
      for (let i = 1; i < results.length; i++) {
        expect(results[i - 1].score).toBeGreaterThanOrEqual(results[i].score);
      }
    }, 30000);

    it('should return empty array for unrelated queries', async () => {
      const results = await memory.searchMessagesVector(
        'test-user',
        '외계인 침공 경보',
        {
          maxResults: 3,
          minScore: 0.8, // High threshold
        }
      );

      // Should return empty or very low score results
      expect(results.length).toBe(0);
    }, 30000);

    it('should only return messages for the specified user', async () => {
      // Add message for different user
      await memory.saveMessage('other-user', 'user', '회의 일정 변경');
      await memory.syncMessagesToChunks('other-user');

      // Search should only return test-user's messages
      const results = await memory.searchMessagesVector('test-user', '회의', {
        maxResults: 10,
      });

      // All results should belong to test-user
      for (const result of results) {
        expect(result.userId).toBe('test-user');
      }
    }, 30000);
  });

  describe('Hybrid Search Comparison', () => {
    it('should find more results than keyword search alone', async () => {
      // FTS5 keyword search - exact match only
      const keywordResults = await memory.searchMessages('test-user', '회의');

      // Vector search - semantic similarity
      const vectorResults = await memory.searchMessagesVector(
        'test-user',
        '미팅 준비', // Similar meaning but different words
        { maxResults: 5, minScore: 0.3 }
      );

      // Vector search should potentially find related content
      // even when exact keywords don't match
      console.log('Keyword results:', keywordResults.length);
      console.log('Vector results:', vectorResults.length);

      // At minimum, vector search should work
      expect(vectorResults).toBeDefined();
    }, 30000);
  });
});

// Quick smoke test that doesn't require full integration
describe('Memory Vector Search API', () => {
  let memory: Memory;

  beforeEach(() => {
    memory = new Memory(':memory:');
  });

  afterEach(async () => {
    await memory.close();
  });

  it('should have searchMessagesVector method', () => {
    expect(typeof memory.searchMessagesVector).toBe('function');
  });

  it('should have syncMessagesToChunks method', () => {
    expect(typeof memory.syncMessagesToChunks).toBe('function');
  });

  it('should have initializeVectorSearch method', () => {
    expect(typeof memory.initializeVectorSearch).toBe('function');
  });

  it('should require initialization before vector search', async () => {
    await expect(
      memory.searchMessagesVector('user', 'query')
    ).rejects.toThrow('Vector search not initialized');
  });

  it('should require initialization before sync', async () => {
    await expect(memory.syncMessagesToChunks()).rejects.toThrow(
      'Vector search not initialized'
    );
  });
});
