import dotenv from 'dotenv';
import { Gateway } from './core/gateway.js';
import { Memory } from './brain/memory.js';
import { ClaudeCodeAgent } from './agent/claude-code.js';
import { TelegramChannel } from './channels/telegram.js';
import { Scheduler } from './scheduler/cron.js';
import { HttpServer } from './core/http-server.js';
import { FinanceAgentServer } from './agents/finance/server.js';
import { NlmClient, KnowledgeSync, KnowledgeManager, initAgentKnowledge } from './knowledge/index.js';
import cron from 'node-cron';
import { log } from './utils/logger.js';
import { killAllPythonProcesses } from './utils/spawn-python.js';
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
        try {
          const gatewayUrl = `ws://${process.env.GATEWAY_HOST || '127.0.0.1'}:${process.env.GATEWAY_PORT || '18789'}`;
          this.telegram = new TelegramChannel(telegramToken, gatewayUrl);
          // WebAppManager 연결
          this.telegram.setWebAppManager(this.httpServer.getWebAppManager());
          await this.telegram.start();
          log('info', '✅ Telegram channel connected');
        } catch (error) {
          log('warn', `⚠️ Telegram failed to start (continuing without it): ${error}`);
          this.telegram = null;
        }
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

      // Knowledge Sync (NLM) — nlm CLI 설치 시에만
      if (await NlmClient.isAvailable()) {
        try {
          const dataDir = process.env.DATA_DIR || './data';
          const km = new KnowledgeManager(dataDir);
          await initAgentKnowledge(km);

          const michaelNlm = await km.getClient('michael');
          this.agent.setKnowledge(km, michaelNlm);

          // 매주 일요일 03:00 — 30일 이상 된 Note 자동 정리
          const knowledgeSync = new KnowledgeSync(michaelNlm, dataDir);
          cron.schedule('0 3 * * 0', () => {
            knowledgeSync.pruneOldNotes(km, ['binance_trader', 'pm_trader'], 30).catch(e =>
              log('warn', `⚠️ NLM note pruning failed: ${e}`),
            );
          });

          const agents = km.listAgents();
          log('info', `✅ Knowledge sync (NLM) activated — ${agents.length} notebooks: ${agents.map(a => a.name).join(', ')}`);
        } catch (error) {
          log('warn', `⚠️ Knowledge sync (NLM) failed to initialize: ${error}`);
        }
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

    const safeStop = async (name: string, fn: () => void | Promise<void>) => {
      try { await fn(); } catch (e) { log('error', `❌ Failed to stop ${name}: ${e}`); }
    };

    await safeStop('FinanceAgent', async () => { if (this.financeAgent) await this.financeAgent.stop(); });
    await safeStop('PythonProcesses', () => { killAllPythonProcesses(); });
    await safeStop('Scheduler', () => this.scheduler.stop());
    await safeStop('Telegram', async () => { if (this.telegram) await this.telegram.stop(); });
    await safeStop('HttpServer', () => this.httpServer.stop());
    await safeStop('Gateway', () => this.gateway.close());
    await safeStop('Agent', () => this.agent.close());
    await safeStop('Memory', () => this.memory.close());

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
