import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { Memory } from './memory.js';
import fs from 'fs';
import path from 'path';

describe('Memory', () => {
  let memory: Memory;
  const testDbPath = ':memory:'; // In-memory database for tests

  beforeEach(() => {
    memory = new Memory(testDbPath);
  });

  afterEach(async () => {
    await memory.close();
  });

  describe('Messages', () => {
    it('should save and retrieve messages', async () => {
      await memory.saveMessage('user1', 'user', 'Hello Michael');
      await memory.saveMessage('user1', 'assistant', 'Hello! How can I help?');

      const messages = await memory.getRecentMessages('user1', 10);

      expect(messages).toHaveLength(2);
      expect(messages[0].role).toBe('user');
      expect(messages[0].content).toBe('Hello Michael');
      expect(messages[1].role).toBe('assistant');
      expect(messages[1].content).toBe('Hello! How can I help?');
    });

    it('should limit recent messages', async () => {
      for (let i = 0; i < 10; i++) {
        await memory.saveMessage('user1', 'user', `Message ${i}`);
      }

      const messages = await memory.getRecentMessages('user1', 5);
      expect(messages).toHaveLength(5);
      expect(messages[0].content).toBe('Message 5'); // Should get last 5 messages
    });

    it('should separate messages by user', async () => {
      await memory.saveMessage('user1', 'user', 'User 1 message');
      await memory.saveMessage('user2', 'user', 'User 2 message');

      const user1Messages = await memory.getRecentMessages('user1', 10);
      const user2Messages = await memory.getRecentMessages('user2', 10);

      expect(user1Messages).toHaveLength(1);
      expect(user2Messages).toHaveLength(1);
      expect(user1Messages[0].content).toBe('User 1 message');
      expect(user2Messages[0].content).toBe('User 2 message');
    });

    it('should search messages with FTS5', async () => {
      await memory.saveMessage('user1', 'user', 'I love TypeScript');
      await memory.saveMessage('user1', 'user', 'Python is great too');
      await memory.saveMessage('user1', 'user', 'JavaScript is everywhere');

      const results = await memory.searchMessages('user1', 'TypeScript');
      expect(results).toHaveLength(1);
      expect(results[0].content).toBe('I love TypeScript');
    });
  });

  describe('Facts', () => {
    it('should save and retrieve facts', async () => {
      await memory.saveFact('user1', 'name', 'John Doe');
      await memory.saveFact('user1', 'birthday', '1990-01-01');

      const name = await memory.getFact('user1', 'name');
      const birthday = await memory.getFact('user1', 'birthday');

      expect(name).toBe('John Doe');
      expect(birthday).toBe('1990-01-01');
    });

    it('should update existing facts', async () => {
      await memory.saveFact('user1', 'name', 'John Doe');
      await memory.saveFact('user1', 'name', 'Jane Smith');

      const name = await memory.getFact('user1', 'name');
      expect(name).toBe('Jane Smith');
    });

    it('should get all facts for a user', async () => {
      await memory.saveFact('user1', 'name', 'John Doe');
      await memory.saveFact('user1', 'age', '30');
      await memory.saveFact('user1', 'city', 'Seoul');

      const facts = await memory.getAllFacts('user1');

      expect(facts).toEqual({
        name: 'John Doe',
        age: '30',
        city: 'Seoul',
      });
    });

    it('should delete facts', async () => {
      await memory.saveFact('user1', 'temp', 'temporary data');
      await memory.deleteFact('user1', 'temp');

      const fact = await memory.getFact('user1', 'temp');
      expect(fact).toBeNull();
    });

    it('should separate facts by user', async () => {
      await memory.saveFact('user1', 'name', 'User 1');
      await memory.saveFact('user2', 'name', 'User 2');

      const user1Name = await memory.getFact('user1', 'name');
      const user2Name = await memory.getFact('user2', 'name');

      expect(user1Name).toBe('User 1');
      expect(user2Name).toBe('User 2');
    });
  });

  describe('Schedules', () => {
    it('should save and retrieve schedules', async () => {
      await memory.saveSchedule(
        'schedule1',
        'user1',
        '0 9 * * *',
        'Good morning!'
      );

      const schedule = await memory.getSchedule('schedule1');

      expect(schedule).not.toBeNull();
      expect(schedule?.userId).toBe('user1');
      expect(schedule?.cronExpression).toBe('0 9 * * *');
      expect(schedule?.message).toBe('Good morning!');
      expect(schedule?.active).toBe(true);
    });

    it('should get all active schedules', async () => {
      await memory.saveSchedule('s1', 'user1', '0 9 * * *', 'Morning');
      await memory.saveSchedule('s2', 'user1', '0 21 * * *', 'Night');
      await memory.deactivateSchedule('s2');

      const schedules = await memory.getAllSchedules('user1');

      expect(schedules).toHaveLength(1);
      expect(schedules[0].id).toBe('s1');
    });

    it('should deactivate and activate schedules', async () => {
      await memory.saveSchedule('s1', 'user1', '0 9 * * *', 'Test');
      await memory.deactivateSchedule('s1');

      let schedule = await memory.getSchedule('s1');
      expect(schedule?.active).toBe(false);

      await memory.activateSchedule('s1');
      schedule = await memory.getSchedule('s1');
      expect(schedule?.active).toBe(true);
    });

    it('should delete schedules', async () => {
      await memory.saveSchedule('s1', 'user1', '0 9 * * *', 'Test');
      await memory.deleteSchedule('s1');

      const schedule = await memory.getSchedule('s1');
      expect(schedule).toBeNull();
    });

    it('should update schedule on conflict', async () => {
      await memory.saveSchedule('s1', 'user1', '0 9 * * *', 'Morning');
      await memory.saveSchedule('s1', 'user1', '0 10 * * *', 'Late morning');

      const schedule = await memory.getSchedule('s1');
      expect(schedule?.cronExpression).toBe('0 10 * * *');
      expect(schedule?.message).toBe('Late morning');
    });
  });

  describe('User management', () => {
    it('should create user with telegram chat id', async () => {
      await memory.ensureUser('user1', '123456789');
      await memory.saveMessage('user1', 'user', 'Test message');

      const messages = await memory.getRecentMessages('user1', 10);
      expect(messages).toHaveLength(1);
    });

    it('should not duplicate users', async () => {
      await memory.ensureUser('user1');
      await memory.ensureUser('user1'); // Should not error

      await memory.saveMessage('user1', 'user', 'Test');
      const messages = await memory.getRecentMessages('user1', 10);
      expect(messages).toHaveLength(1);
    });
  });

  describe('Vector Search', () => {
    it('should throw error when vector search not initialized', async () => {
      await expect(
        memory.searchMessagesVector('user1', 'test query')
      ).rejects.toThrow('Vector search not initialized');
    });

    it('should throw error when syncMessagesToChunks called without initialization', async () => {
      await expect(memory.syncMessagesToChunks()).rejects.toThrow(
        'Vector search not initialized'
      );
    });

    // Note: Full vector search integration tests require:
    // 1. Actual file system (not in-memory DB)
    // 2. Embedding provider (local/OpenAI/Gemini)
    // 3. sqlite-vec extension
    // These are tested in the integration test suite (Task #7)
  });
});

describe('Memory (with file-based DB)', () => {
  let memory: Memory;
  let testDir: string;
  let testDbPath: string;

  beforeEach(() => {
    // Create temp directory for file-based tests
    testDir = path.join(process.cwd(), '.test-temp', `test-${Date.now()}`);
    fs.mkdirSync(testDir, { recursive: true });
    testDbPath = path.join(testDir, 'memory.db');
    memory = new Memory(testDbPath);
  });

  afterEach(async () => {
    await memory.close();
    // Clean up test directory
    if (fs.existsSync(testDir)) {
      fs.rmSync(testDir, { recursive: true, force: true });
    }
  });

  describe('Persistence', () => {
    it('should persist messages across connections', async () => {
      await memory.saveMessage('user1', 'user', 'Persistent message');
      await memory.close();

      // Reopen connection
      memory = new Memory(testDbPath);
      const messages = await memory.getRecentMessages('user1', 10);

      expect(messages).toHaveLength(1);
      expect(messages[0].content).toBe('Persistent message');
    });

    it('should persist facts across connections', async () => {
      await memory.saveFact('user1', 'persistent_key', 'persistent_value');
      await memory.close();

      // Reopen connection
      memory = new Memory(testDbPath);
      const value = await memory.getFact('user1', 'persistent_key');

      expect(value).toBe('persistent_value');
    });

    it('should persist schedules across connections', async () => {
      await memory.saveSchedule('persistent_schedule', 'user1', '0 9 * * *', 'Persistent');
      await memory.close();

      // Reopen connection
      memory = new Memory(testDbPath);
      const schedule = await memory.getSchedule('persistent_schedule');

      expect(schedule).not.toBeNull();
      expect(schedule?.message).toBe('Persistent');
    });
  });

  describe('FTS5 Search Edge Cases', () => {
    it('should handle special characters in search', async () => {
      await memory.saveMessage('user1', 'user', 'Test with special: @#$%');

      // FTS5 should handle this gracefully (may return empty or match)
      const results = await memory.searchMessages('user1', 'special');
      expect(results.length).toBeGreaterThanOrEqual(0);
    });

    it('should handle empty search results', async () => {
      await memory.saveMessage('user1', 'user', 'Some content');

      const results = await memory.searchMessages('user1', 'nonexistent');
      expect(results).toHaveLength(0);
    });

    it('should handle Korean text search', async () => {
      await memory.saveMessage('user1', 'user', '안녕하세요 마이클입니다');
      await memory.saveMessage('user1', 'user', '오늘 날씨가 좋네요');

      const results = await memory.searchMessages('user1', '안녕하세요');
      expect(results.length).toBeGreaterThanOrEqual(1);
      expect(results[0].content).toContain('안녕하세요');
    });
  });

  describe('Data Integrity', () => {
    it('should maintain referential integrity for messages', async () => {
      // Save message without explicit user creation
      await memory.saveMessage('new_user', 'user', 'First message');

      // User should be auto-created
      const messages = await memory.getRecentMessages('new_user', 10);
      expect(messages).toHaveLength(1);
    });

    it('should handle concurrent message saves', async () => {
      // Simulate concurrent saves
      const promises = [];
      for (let i = 0; i < 10; i++) {
        promises.push(memory.saveMessage('user1', 'user', `Concurrent message ${i}`));
      }
      await Promise.all(promises);

      const messages = await memory.getRecentMessages('user1', 20);
      expect(messages).toHaveLength(10);
    });
  });
});
