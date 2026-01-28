import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { Scheduler } from './cron.js';
import { Memory } from '../brain/memory.js';
import { Gateway } from '../core/gateway.js';

describe('Scheduler', () => {
  let scheduler: Scheduler;
  let memory: Memory;
  let gateway: Gateway;
  let gatewayPort: number;

  beforeEach(async () => {
    memory = new Memory(':memory:');
    
    // 각 테스트마다 다른 포트 사용
    gatewayPort = 18791 + Math.floor(Math.random() * 1000);
    gateway = new Gateway(gatewayPort);
    await gateway.start();
    
    scheduler = new Scheduler(memory, gateway);
  });

  afterEach(async () => {
    if (scheduler) {
      scheduler.stop();
    }
    if (gateway) {
      await gateway.close();
    }
    if (memory) {
      memory.close();
    }
  });

  describe('Schedule Management', () => {
    it('should add a new schedule', async () => {
      const scheduleId = await scheduler.addSchedule(
        'user1',
        '0 9 * * *', // 매일 9시
        'Good morning!'
      );

      expect(scheduleId).toBeDefined();
      expect(scheduleId).toMatch(/^schedule_/);

      // 메모리에 저장되었는지 확인
      const schedule = await memory.getSchedule(scheduleId);
      expect(schedule).not.toBeNull();
      expect(schedule?.cronExpression).toBe('0 9 * * *');
      expect(schedule?.message).toBe('Good morning!');
    });

    it('should cancel a schedule', async () => {
      const scheduleId = await scheduler.addSchedule(
        'user1',
        '0 9 * * *',
        'Test message'
      );

      await scheduler.cancelSchedule(scheduleId);

      // 메모리에서 비활성화되었는지 확인
      const schedule = await memory.getSchedule(scheduleId);
      expect(schedule?.active).toBe(false);

      // Active jobs 목록에 없는지 확인
      const activeJobs = scheduler.getActiveJobs();
      expect(activeJobs.find((j) => j.id === scheduleId)).toBeUndefined();
    });

    it('should reactivate a schedule', async () => {
      const scheduleId = await scheduler.addSchedule(
        'user1',
        '0 9 * * *',
        'Test message'
      );

      await scheduler.cancelSchedule(scheduleId);
      await scheduler.reactivateSchedule(scheduleId);

      // 메모리에서 활성화되었는지 확인
      const schedule = await memory.getSchedule(scheduleId);
      expect(schedule?.active).toBe(true);

      // Active jobs 목록에 있는지 확인
      const activeJobs = scheduler.getActiveJobs();
      expect(activeJobs.find((j) => j.id === scheduleId)).toBeDefined();
    });

    it('should delete a schedule', async () => {
      const scheduleId = await scheduler.addSchedule(
        'user1',
        '0 9 * * *',
        'Test message'
      );

      await scheduler.deleteSchedule(scheduleId);

      // 메모리에서 삭제되었는지 확인
      const schedule = await memory.getSchedule(scheduleId);
      expect(schedule).toBeNull();
    });
  });

  describe('Schedule Loading', () => {
    it('should load schedules from memory on start', async () => {
      // 스케줄을 직접 메모리에 저장
      await memory.saveSchedule('s1', 'user1', '0 9 * * *', 'Morning');
      await memory.saveSchedule('s2', 'user1', '0 21 * * *', 'Night');

      // 새로운 Scheduler 인스턴스로 로드
      const newScheduler = new Scheduler(memory, gateway);
      await newScheduler.start();

      const activeJobs = newScheduler.getActiveJobs();
      expect(activeJobs).toHaveLength(2);

      newScheduler.stop();
    });

    it('should not load inactive schedules', async () => {
      await memory.saveSchedule('s1', 'user1', '0 9 * * *', 'Morning');
      await memory.saveSchedule('s2', 'user1', '0 21 * * *', 'Night');
      await memory.deactivateSchedule('s2');

      const newScheduler = new Scheduler(memory, gateway);
      await newScheduler.start();

      const activeJobs = newScheduler.getActiveJobs();
      expect(activeJobs).toHaveLength(1);
      expect(activeJobs[0].id).toBe('s1');

      newScheduler.stop();
    });
  });

  describe('Cron Expression Validation', () => {
    it('should accept valid cron expressions', async () => {
      const validExpressions = [
        '0 9 * * *',      // 매일 9시
        '*/5 * * * *',    // 5분마다
        '0 0 1 * *',      // 매월 1일
        '0 0 * * 0',      // 매주 일요일
      ];

      for (const expr of validExpressions) {
        const scheduleId = await scheduler.addSchedule('user1', expr, 'Test');
        expect(scheduleId).toBeDefined();
        await scheduler.deleteSchedule(scheduleId);
      }
    });

    it('should reject invalid cron expressions', async () => {
      // 잘못된 표현식은 스케줄되지 않음
      await memory.saveSchedule('invalid', 'user1', 'invalid cron', 'Test');
      
      const newScheduler = new Scheduler(memory, gateway);
      await newScheduler.start();

      const activeJobs = newScheduler.getActiveJobs();
      expect(activeJobs.find((j) => j.id === 'invalid')).toBeUndefined();

      newScheduler.stop();
    });
  });

  describe('User Schedules', () => {
    it('should get all schedules for a user', async () => {
      await scheduler.addSchedule('user1', '0 9 * * *', 'Message 1');
      await scheduler.addSchedule('user1', '0 21 * * *', 'Message 2');
      await scheduler.addSchedule('user2', '0 12 * * *', 'Message 3');

      const user1Schedules = await scheduler.getUserSchedules('user1');
      expect(user1Schedules).toHaveLength(2);

      const user2Schedules = await scheduler.getUserSchedules('user2');
      expect(user2Schedules).toHaveLength(1);
    });
  });
});
