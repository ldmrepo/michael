import dotenv from 'dotenv';
import { Gateway } from './core/gateway.js';
import { Memory } from './brain/memory.js';
import { ClaudeCodeAgent } from './agent/claude-code.js';
import { TelegramChannel } from './channels/telegram.js';
import { Scheduler } from './scheduler/cron.js';
import { log } from './utils/logger.js';
import path from 'path';

// 환경 변수 로드
dotenv.config();

/**
 * 마이클 메인 애플리케이션
 */
class Michael {
  private gateway: Gateway;
  private memory: Memory;
  private agent: ClaudeCodeAgent;
  private telegram: TelegramChannel | null = null;
  private scheduler: Scheduler;

  constructor() {
    // 환경 변수
    const gatewayPort = parseInt(process.env.GATEWAY_PORT || '18789');
    const gatewayHost = process.env.GATEWAY_HOST || '127.0.0.1';
    const dataDir = process.env.DATA_DIR || './data';
    const dbPath = path.join(dataDir, 'memory.db');

    // 컴포넌트 초기화
    this.memory = new Memory(dbPath);
    this.agent = new ClaudeCodeAgent(this.memory);
    this.gateway = new Gateway(gatewayPort, gatewayHost);
    this.scheduler = new Scheduler(this.memory, this.gateway);

    // Agent를 Gateway에 연결
    this.gateway.setAgent(this.agent);

    log('info', '🚀 Michael initialized');
  }

  /**
   * 시작
   */
  async start(): Promise<void> {
    try {
      // Gateway 시작
      await this.gateway.start();

      // Scheduler 시작
      await this.scheduler.start();
      log('info', '✅ Scheduler started');

      // Telegram 시작 (토큰이 있는 경우에만)
      const telegramToken = process.env.TELEGRAM_BOT_TOKEN;
      if (telegramToken) {
        const gatewayUrl = `ws://${process.env.GATEWAY_HOST || '127.0.0.1'}:${process.env.GATEWAY_PORT || '18789'}`;
        this.telegram = new TelegramChannel(telegramToken, gatewayUrl);
        await this.telegram.start();
        log('info', '✅ Telegram channel connected');
      } else {
        log('warn', '⚠️ TELEGRAM_BOT_TOKEN not set, Telegram disabled');
      }

      log('info', '🎉 Michael is ready!');
      log('info', '💡 Connect with: wscat -c ws://127.0.0.1:18789');

      // Graceful shutdown 설정
      process.on('SIGINT', async () => {
        await this.stop();
        process.exit(0);
      });

      process.on('SIGTERM', async () => {
        await this.stop();
        process.exit(0);
      });

    } catch (error) {
      log('error', `❌ Failed to start Michael: ${error}`);
      throw error;
    }
  }

  /**
   * 종료
   */
  async stop(): Promise<void> {
    log('info', '👋 Stopping Michael...');
    
    this.scheduler.stop();
    if (this.telegram) {
      await this.telegram.stop();
    }
    await this.gateway.close();
    this.agent.close();
    this.memory.close();

    log('info', '✅ Michael stopped');
  }
}

// 메인 실행
if (import.meta.url === `file://${process.argv[1]}`) {
  const michael = new Michael();
  michael.start().catch((error) => {
    log('error', `❌ Fatal error: ${error}`);
    process.exit(1);
  });
}

export { Michael };
