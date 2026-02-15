import dotenv from 'dotenv';
import { existsSync } from 'fs';
import { Gateway } from './core/gateway.js';
import { Memory } from './brain/memory.js';
import { ClaudeCodeAgent } from './agent/claude-code.js';
import { TelegramChannel } from './channels/telegram.js';
import { Scheduler } from './scheduler/cron.js';
import { HttpServer } from './core/http-server.js';
import { InvestmentService } from './investment/index.js';
import { PredictionMarketService } from './prediction-market/index.js';
import { FinanceAgentServer } from './agents/finance/server.js';
import { StateStore } from './state-store/index.js';
import { StatePopulator } from './state-store/state-populator.js';
import { JudgmentCycle, AgentRunner } from './decision/index.js';
import { Sentinel } from './sentinel/index.js';
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
  private investment: InvestmentService | null = null;
  private predictionMarket: PredictionMarketService | null = null;
  private financeAgent: FinanceAgentServer | null = null;
  private sentinel: Sentinel | null = null;

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

      // Investment Service 시작 (Binance API 키가 있는 경우에만)
      if (process.env.BINANCE_API_KEY) {
        try {
          this.investment = new InvestmentService(
            this.memory.getDb(),
            this.gateway,
          );
          await this.investment.start();
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
          await this.predictionMarket.start();
          log('info', '✅ Prediction Market service started');
        } catch (error) {
          log('warn', `⚠️ Prediction Market service failed to start: ${error}`);
        }
      } else {
        log('info', 'ℹ️ POLYMARKET_ENABLED not set, Prediction Market service disabled');
      }

      // State Store + Judgment Cycle + Sentinel (mandate.yaml 존재 시에만)
      const stateDir = path.join(process.env.DATA_DIR || './data', 'state');
      if (existsSync(path.join(stateDir, 'mandate.yaml'))) {
        try {
          const stateStore = new StateStore(stateDir);
          const statePopulator = new StatePopulator(stateStore);

          // InvestmentService에 StatePopulator 연결
          if (this.investment) {
            this.investment.setStatePopulator(statePopulator);
          }

          // JudgmentCycle 초기화 + AgentRunner 연결 + 정기 판단 스케줄
          const judgmentCycle = new JudgmentCycle(stateStore, this.agent, this.gateway);

          // AgentRunner: Gather Phase에서 전문가 스크립트 병렬 실행
          const agentRunner = new AgentRunner(statePopulator);
          judgmentCycle.setAgentRunner(agentRunner);

          // 정기 판단 루틴 (직접 cron.schedule — Scheduler 라우팅 우회)
          const scheduleJudgment = (cronExpr: string, routineType: string) => {
            cron.schedule(cronExpr, () => {
              judgmentCycle.runCycle(`__judgment_cycle__ ${routineType}`).catch(e =>
                log('warn', `⚠️ JudgmentCycle (${routineType}) failed: ${e}`),
              );
            });
          };

          // 일일 루틴: 아침(기회 포착), 낮(균형 유지), 저녁(하루 마감)
          scheduleJudgment('0 8 * * *', 'morning');
          scheduleJudgment('0 14 * * *', 'midday');
          scheduleJudgment('0 21 * * *', 'evening');

          // 주간/월간 루틴: 심층 분석
          scheduleJudgment('0 9 * * 1', 'weekly');   // 매주 월요일 09:00
          scheduleJudgment('0 9 1 * *', 'monthly');  // 매월 1일 09:00

          // Gateway에 judgment 핸들러 등록 (Sentinel 트리거 → JudgmentCycle)
          this.gateway.registerHandler('judgment', async (message) => {
            if (message.metadata?.trigger) {
              await judgmentCycle.runCycle(message.content);
            }
          });

          // Sentinel 시작
          const gatewayUrl = `ws://${process.env.GATEWAY_HOST || '127.0.0.1'}:${process.env.GATEWAY_PORT || '18789'}`;
          this.sentinel = new Sentinel(gatewayUrl, stateDir);
          await this.sentinel.start();

          // Knowledge Sync (NLM) — nlm CLI 설치 시에만
          if (await NlmClient.isAvailable()) {
            try {
              const dataDir = process.env.DATA_DIR || './data';
              const km = new KnowledgeManager(dataDir);

              // 에이전트별 노트북 자동 생성/로드
              const judgmentNlm = await km.getClient('judgment');
              const snapshotNlm = await km.getClient('snapshot');

              const knowledgeSync = new KnowledgeSync(judgmentNlm, stateDir);

              // JudgmentCycle에 NLM 연결 (KnowledgeManager + judgment 노트북 + write-back)
              judgmentCycle.setKnowledge(km, judgmentNlm, knowledgeSync);

              // Decision → NLM 자동 동기화 (judgment 노트북)
              stateStore.setOnDecisionRecorded((d) => {
                knowledgeSync.syncDecision(d).catch(e =>
                  log('warn', `⚠️ NLM decision sync failed: ${e}`),
                );
              });

              // 매일 22:00 일일 스냅샷 (snapshot 노트북)
              const snapshotSync = new KnowledgeSync(snapshotNlm, stateDir);
              cron.schedule('0 22 * * *', () => {
                snapshotSync.syncDailySnapshot().catch(e =>
                  log('warn', `⚠️ NLM snapshot sync failed: ${e}`),
                );
              });

              // 에이전트별 NLM 노트북 자동 생성/로드
              await initAgentKnowledge(km);

              const agents = km.listAgents();
              log('info', `✅ Knowledge sync (NLM) activated — ${agents.length} notebooks: ${agents.map(a => a.name).join(', ')}`);
            } catch (error) {
              log('warn', `⚠️ Knowledge sync (NLM) failed to initialize: ${error}`);
            }
          }

          log('info', '✅ State Store + Judgment Cycle + Sentinel activated');
        } catch (error) {
          log('warn', `⚠️ State Store system failed to start: ${error}`);
        }
      } else {
        log('info', 'ℹ️ mandate.yaml not found, State Store system disabled');
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

    await safeStop('Sentinel', async () => { if (this.sentinel) await this.sentinel.stop(); });
    await safeStop('FinanceAgent', async () => { if (this.financeAgent) await this.financeAgent.stop(); });
    await safeStop('Investment', () => { if (this.investment) this.investment.stop(); });
    await safeStop('PredictionMarket', () => { if (this.predictionMarket) this.predictionMarket.stop(); });
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
