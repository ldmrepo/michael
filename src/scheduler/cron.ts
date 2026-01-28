import cron from 'node-cron';
import { Memory, Schedule } from '../brain/memory.js';
import { Gateway } from '../core/gateway.js';
import { log } from '../utils/logger.js';

/**
 * Cron Job 정보
 */
interface CronJob {
  id: string;
  task: cron.ScheduledTask;
  schedule: Schedule;
}

/**
 * Scheduler 클래스
 * node-cron 기반 스케줄 작업 관리
 */
export class Scheduler {
  private memory: Memory;
  private gateway: Gateway;
  private jobs: Map<string, CronJob> = new Map();

  constructor(memory: Memory, gateway: Gateway) {
    this.memory = memory;
    this.gateway = gateway;
    log('info', '✅ Scheduler initialized');
  }

  /**
   * 시작 (메모리에서 스케줄 로드)
   */
  async start(): Promise<void> {
    try {
      log('info', '⏰ Loading schedules from memory...');
      
      // 메모리에서 모든 활성 스케줄 로드
      const schedules = await this.memory.getAllSchedules();
      
      // 각 스케줄을 Cron Job으로 등록
      for (const schedule of schedules) {
        this.scheduleJob(schedule);
      }

      log('info', `✅ Loaded ${schedules.length} schedules`);

    } catch (error) {
      log('error', `❌ Failed to start Scheduler: ${error}`);
      throw error;
    }
  }

  /**
   * 스케줄 작업 등록
   */
  scheduleJob(schedule: Schedule): void {
    try {
      // 이미 등록된 작업이 있으면 취소
      if (this.jobs.has(schedule.id)) {
        this.cancelJob(schedule.id);
      }

      // Cron 표현식 검증
      if (!cron.validate(schedule.cronExpression)) {
        log('error', `❌ Invalid cron expression: ${schedule.cronExpression}`);
        return;
      }

      // Cron 작업 생성
      const task = cron.schedule(schedule.cronExpression, async () => {
        await this.executeJob(schedule);
      });

      // 작업 저장
      this.jobs.set(schedule.id, {
        id: schedule.id,
        task,
        schedule,
      });

      log('info', `⏰ Scheduled job: ${schedule.id} (${schedule.cronExpression})`);

    } catch (error) {
      log('error', `❌ Failed to schedule job ${schedule.id}: ${error}`);
    }
  }

  /**
   * 스케줄 작업 실행
   */
  private async executeJob(schedule: Schedule): Promise<void> {
    try {
      log('info', `🔔 Executing scheduled job: ${schedule.id}`);

      // Gateway를 통해 Telegram으로 메시지 전송
      this.gateway.broadcast({
        from: 'scheduler',
        to: 'telegram',
        userId: schedule.userId,
        content: schedule.message,
        metadata: {
          scheduleId: schedule.id,
          cronExpression: schedule.cronExpression,
        },
      });

      log('info', `✅ Scheduled job executed: ${schedule.id}`);

    } catch (error) {
      log('error', `❌ Failed to execute job ${schedule.id}: ${error}`);
    }
  }

  /**
   * 새 스케줄 추가
   */
  async addSchedule(
    userId: string,
    cronExpression: string,
    message: string
  ): Promise<string> {
    try {
      // 스케줄 ID 생성
      const scheduleId = `schedule_${Date.now()}_${Math.random().toString(36).substring(7)}`;

      // 메모리에 저장
      await this.memory.saveSchedule(scheduleId, userId, cronExpression, message);

      // Cron Job 등록
      const schedule = await this.memory.getSchedule(scheduleId);
      if (schedule) {
        this.scheduleJob(schedule);
      }

      log('info', `✅ Schedule added: ${scheduleId}`);
      return scheduleId;

    } catch (error) {
      log('error', `❌ Failed to add schedule: ${error}`);
      throw error;
    }
  }

  /**
   * 스케줄 취소
   */
  async cancelSchedule(scheduleId: string): Promise<void> {
    try {
      // Cron Job 취소
      this.cancelJob(scheduleId);

      // 메모리에서 비활성화
      await this.memory.deactivateSchedule(scheduleId);

      log('info', `✅ Schedule cancelled: ${scheduleId}`);

    } catch (error) {
      log('error', `❌ Failed to cancel schedule ${scheduleId}: ${error}`);
      throw error;
    }
  }

  /**
   * Cron Job 취소 (내부 메서드)
   */
  private cancelJob(scheduleId: string): void {
    const job = this.jobs.get(scheduleId);
    if (job) {
      job.task.stop();
      this.jobs.delete(scheduleId);
      log('debug', `🛑 Cron job stopped: ${scheduleId}`);
    }
  }

  /**
   * 스케줄 재활성화
   */
  async reactivateSchedule(scheduleId: string): Promise<void> {
    try {
      // 메모리에서 활성화
      await this.memory.activateSchedule(scheduleId);

      // Cron Job 재등록
      const schedule = await this.memory.getSchedule(scheduleId);
      if (schedule) {
        this.scheduleJob(schedule);
      }

      log('info', `✅ Schedule reactivated: ${scheduleId}`);

    } catch (error) {
      log('error', `❌ Failed to reactivate schedule ${scheduleId}: ${error}`);
      throw error;
    }
  }

  /**
   * 스케줄 삭제
   */
  async deleteSchedule(scheduleId: string): Promise<void> {
    try {
      // Cron Job 취소
      this.cancelJob(scheduleId);

      // 메모리에서 삭제
      await this.memory.deleteSchedule(scheduleId);

      log('info', `✅ Schedule deleted: ${scheduleId}`);

    } catch (error) {
      log('error', `❌ Failed to delete schedule ${scheduleId}: ${error}`);
      throw error;
    }
  }

  /**
   * 사용자의 모든 스케줄 조회
   */
  async getUserSchedules(userId: string): Promise<Schedule[]> {
    return await this.memory.getAllSchedules(userId);
  }

  /**
   * 활성 스케줄 목록 조회
   */
  getActiveJobs(): Array<{ id: string; cronExpression: string; message: string }> {
    return Array.from(this.jobs.values()).map((job) => ({
      id: job.id,
      cronExpression: job.schedule.cronExpression,
      message: job.schedule.message,
    }));
  }

  /**
   * 종료 (모든 Cron Job 취소)
   */
  stop(): void {
    log('info', '👋 Stopping Scheduler...');

    this.jobs.forEach((job) => {
      job.task.stop();
    });
    this.jobs.clear();

    log('info', '✅ Scheduler stopped');
  }
}
