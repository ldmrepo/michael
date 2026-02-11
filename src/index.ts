import dotenv from 'dotenv';
import { Gateway } from './core/gateway.js';
import { Memory } from './brain/memory.js';
import { ClaudeCodeAgent } from './agent/claude-code.js';
import { TelegramChannel } from './channels/telegram.js';
import { Scheduler } from './scheduler/cron.js';
import { HttpServer } from './core/http-server.js';
import { InvestmentService } from './investment/index.js';
import { PredictionMarketService } from './prediction-market/index.js';
import { FinanceAgentServer } from './agents/finance/server.js';
import { log } from './utils/logger.js';
import { loadMemoryConfig } from './memory-new/config.js';
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
  private httpServer: HttpServer;
  private investment: InvestmentService | null = null;
  private predictionMarket: PredictionMarketService | null = null;
  private financeAgent: FinanceAgentServer | null = null;

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

    // Agent에 Scheduler 연결 (스케줄 즉시 등록용)
    this.agent.setScheduler(this.scheduler);

    // HTTP 서버 초기화
    const httpPort = parseInt(process.env.HTTP_PORT || '3000');
    const webappUrl = process.env.WEBAPP_URL || `http://localhost:${httpPort}`;
    this.httpServer = new HttpServer({
      port: httpPort,
      baseUrl: webappUrl,
    });

    // HTTP 서버에 Agent 연결 (SSE 스트리밍용)
    this.httpServer.setAgent(this.agent);

    log('info', '🚀 Michael initialized');
  }

  /**
   * 시작
   */
  async start(): Promise<void> {
    try {
      // 벡터 검색 초기화 (선택적 - 실패해도 계속 진행)
      try {
        const dataDir = process.env.DATA_DIR || './data';
        const config = loadMemoryConfig(dataDir);
        await this.memory.initializeVectorSearch(config);
        log('info', '✅ Vector search initialized');

        // 기존 메시지 인덱싱 (최초 실행 시)
        await this.memory.syncMessagesToChunks();
      } catch (error) {
        log('warn', `⚠️ Vector search initialization failed (continuing without it): ${error}`);
      }

      // Gateway 시작
      await this.gateway.start();

      // HTTP 서버 시작
      await this.httpServer.start();

      // Scheduler 시작
      await this.scheduler.start();
      log('info', '✅ Scheduler started');

      // Telegram 시작 (토큰이 있는 경우에만)
      const telegramToken = process.env.TELEGRAM_BOT_TOKEN;
      if (telegramToken) {
        const gatewayUrl = `ws://${process.env.GATEWAY_HOST || '127.0.0.1'}:${process.env.GATEWAY_PORT || '18789'}`;
        this.telegram = new TelegramChannel(telegramToken, gatewayUrl);
        // WebAppManager 연결
        this.telegram.setWebAppManager(this.httpServer.getWebAppManager());
        await this.telegram.start();
        log('info', '✅ Telegram channel connected');
      } else {
        log('warn', '⚠️ TELEGRAM_BOT_TOKEN not set, Telegram disabled');
      }

      // Finance Agent 시작 (A2A server on :8001)
      try {
        this.financeAgent = new FinanceAgentServer();
        await this.financeAgent.start();
      } catch (error) {
        log('warn', `⚠️ Finance Agent failed to start: ${error}`);
        this.financeAgent = null;
      }

      // Investment Service 시작 (Binance API 키가 있는 경우에만)
      if (process.env.BINANCE_API_KEY) {
        try {
          this.investment = new InvestmentService(
            this.memory.getDb(),
            this.gateway,
          );
          this.investment.start();
          log('info', '✅ Investment service started');
        } catch (error) {
          log('warn', `⚠️ Investment service failed to start: ${error}`);
        }
      } else {
        log('info', 'ℹ️ BINANCE_API_KEY not set, Investment service disabled');
      }

      // Prediction Market Service 시작 (POLYMARKET_ENABLED=true 시)
      if (process.env.POLYMARKET_ENABLED === 'true') {
        try {
          this.predictionMarket = new PredictionMarketService(
            this.memory.getDb(),
            this.gateway,
          );
          this.predictionMarket.start();
          log('info', '✅ Prediction Market service started');
        } catch (error) {
          log('warn', `⚠️ Prediction Market service failed to start: ${error}`);
        }
      } else {
        log('info', 'ℹ️ POLYMARKET_ENABLED not set, Prediction Market service disabled');
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

    if (this.financeAgent) {
      await this.financeAgent.stop();
    }
    if (this.investment) {
      this.investment.stop();
    }
    if (this.predictionMarket) {
      this.predictionMarket.stop();
    }
    this.scheduler.stop();
    if (this.telegram) {
      await this.telegram.stop();
    }
    await this.httpServer.stop();
    await this.gateway.close();
    this.agent.close();
    await this.memory.close(); // async for vector search cleanup

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
