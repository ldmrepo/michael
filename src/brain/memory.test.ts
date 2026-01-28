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

  afterEach(() => {
    memory.close();
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
});
