/**
 * InvestmentService - Main orchestrator
 * Connects all investment modules and integrates with Gateway/Telegram
 */

import Database from 'better-sqlite3';
import { log } from '../utils/logger.js';
import { Gateway, GatewayMessage } from '../core/gateway.js';
import { PortfolioStore } from './portfolio-store.js';
import { InvestmentScheduler } from './scheduler-jobs.js';
import { ResearchEngine } from './research-engine.js';
import { AnalysisEngine } from './analysis-engine.js';
import { RiskEngine } from './risk-engine.js';
import { ExecutionEngine } from './execution-engine.js';
import type { ScriptOutput } from './types.js';

export class InvestmentService {
  private store: PortfolioStore;
  private scheduler: InvestmentScheduler;
  private research: ResearchEngine;
  private analysis: AnalysisEngine;
  private risk: RiskEngine;
  private execution: ExecutionEngine;
  private gateway: Gateway;
  private userId: string;
  private chatIdMap: Map<string, number> = new Map();
  private db: Database.Database;

  constructor(db: Database.Database, gateway: Gateway, userId: string = 'default') {
    this.gateway = gateway;
    this.userId = userId;
    this.db = db;

    // Initialize components
    this.store = new PortfolioStore(db);
    this.scheduler = new InvestmentScheduler(userId);
    this.research = new ResearchEngine(this.store, this.scheduler);
    this.analysis = new AnalysisEngine(this.store, this.scheduler);
    this.risk = new RiskEngine(this.store, this.scheduler);
    this.execution = new ExecutionEngine(this.store, this.scheduler);

    // Wire up Telegram callbacks
    this.analysis.setSendReport((uid, text, buttons) => {
      this.sendToTelegram(uid, text, buttons);
    });

    this.risk.setSendAlert((uid, text, _severity, buttons) => {
      this.sendToTelegram(uid, text, buttons);
    });

    this.execution.setSendProposal((uid, text, buttons) => {
      this.sendToTelegram(uid, text, buttons);
    });

    this.execution.setSendResult((uid, text) => {
      this.sendToTelegram(uid, text);
    });

    // Wire up scheduler job callbacks (for risk alerts from monitors)
    this.scheduler.setJobCallback((jobName, output) => {
      this.handleJobResult(jobName, output);
    });

    // Register as Gateway handler for 'investment' messages
    this.gateway.registerHandler('investment', async (message) => {
      await this.handleGatewayMessage(message);
    });

    log('info', '💰 InvestmentService initialized');
  }

  /**
   * Start the investment service
   */
  start(): void {
    this.scheduler.start();
    log('info', '✅ InvestmentService started');
  }

  /**
   * Stop the investment service
   */
  stop(): void {
    this.scheduler.stop();
    log('info', '⏹️ InvestmentService stopped');
  }

  /**
   * Handle Telegram callback queries for inv_ prefix
   */
  async handleCallback(action: string, params: Record<string, string>, userId: string): Promise<void> {
    log('debug', `💰 Investment callback: ${action} ${JSON.stringify(params)}`);

    switch (action) {
      case 'inv_approve':
      case 'inv_reject':
      case 'inv_modify':
        await this.execution.handleCallback(action, params, userId);
        break;

      case 'inv_portfolio':
        await this.sendPortfolioSummary(userId);
        break;

      case 'inv_analysis_detail': {
        const latest = this.analysis.getLatest(userId);
        if (latest) {
          this.sendToTelegram(userId, latest.summary);
        } else {
          this.sendToTelegram(userId, 'No analysis available');
        }
        break;
      }

      case 'inv_risk_settings': {
        const thresholds = this.risk.getThresholds(userId);
        let text = '🔔 알림 설정:\n\n';
        if (thresholds.length === 0) {
          text += '설정된 알림이 없습니다.';
        } else {
          for (const t of thresholds) {
            text += `${t.thresholdType} ${t.symbol || 'global'}: ${t.value}\n`;
          }
        }
        this.sendToTelegram(userId, text);
        break;
      }

      case 'inv_ack_alert':
        // Acknowledge recent alerts
        const alerts = this.risk.getActiveAlerts(userId);
        for (const a of alerts) {
          this.risk.acknowledgeAlert(a.id);
        }
        this.sendToTelegram(userId, `✅ ${alerts.length}개 알림 확인됨`);
        break;

      default:
        log('warn', `⚠️ Unknown investment action: ${action}`);
    }
  }

  /**
   * Handle incoming Gateway messages targeted to 'investment'
   */
  private async handleGatewayMessage(message: GatewayMessage): Promise<void> {
    const chatId = message.metadata?.chatId;

    // Store chatId under internal userId ('default') for response routing
    // All investment data is stored under this.userId, not the Telegram user ID
    if (chatId) {
      this.chatIdMap.set(this.userId, chatId);
    }

    if (message.metadata?.type === 'investment_callback') {
      // Parse callback data: "inv_action:key1=val1:key2=val2" or "inv_action"
      const { action, params } = this.parseCallbackData(message.content);
      await this.handleCallback(action, params, this.userId);
    }
  }

  /**
   * Parse callback data string into action and params
   * Format: "inv_action:key=value" or "inv_action"
   */
  private parseCallbackData(data: string): { action: string; params: Record<string, string> } {
    const parts = data.split(':');
    const action = parts[0];
    const params: Record<string, string> = {};

    for (let i = 1; i < parts.length; i++) {
      const eqIdx = parts[i].indexOf('=');
      if (eqIdx > 0) {
        params[parts[i].substring(0, eqIdx)] = parts[i].substring(eqIdx + 1);
      }
    }

    return { action, params };
  }

  /**
   * Send portfolio summary to Telegram
   */
  private async sendPortfolioSummary(userId: string): Promise<void> {
    const holdings = this.store.getHoldings(userId);
    const totals = this.store.getTotalValue(userId);
    const snapshot = this.store.getLatestSnapshot(userId);

    let text = `💰 포트폴리오\n\n`;
    text += `총 자산: $${totals.total.toLocaleString('en-US', { maximumFractionDigits: 0 })}\n`;
    text += `Spot: $${totals.spot.toLocaleString('en-US', { maximumFractionDigits: 0 })} | Futures: $${totals.futures.toLocaleString('en-US', { maximumFractionDigits: 0 })}\n\n`;

    for (const h of holdings.slice(0, 10)) {
      const value = (h.currentPrice || 0) * h.quantity;
      if (value < 1 && h.symbol === 'USDT') continue;
      const pct = totals.total > 0 ? ((value / totals.total) * 100).toFixed(0) : '0';
      text += `${h.symbol} │ $${value.toLocaleString('en-US', { maximumFractionDigits: 0 })} │ ${pct}%`;
      if (h.unrealizedPnl) {
        const sign = h.unrealizedPnl >= 0 ? '+' : '';
        text += ` │ ${sign}$${h.unrealizedPnl.toFixed(0)}`;
      }
      text += '\n';
    }

    if (snapshot) {
      text += `\n📅 마지막 스냅샷: ${snapshot.date}`;
    }

    this.sendToTelegram(userId, text);
  }

  /**
   * Handle completed job results (analysis reports + monitor alerts)
   */
  private handleJobResult(jobName: string, output: ScriptOutput): void {
    // Route analysis jobs through AnalysisEngine for Claude AI analysis + DB storage
    if (jobName === 'daily_brief') {
      this.analysis.processReport(this.userId, 'daily', output);
      return;
    }
    if (jobName === 'weekly_deep') {
      this.analysis.processReport(this.userId, 'weekly', output);
      return;
    }

    if (output.alerts && output.alerts.length > 0) {
      this.risk.processAlerts(this.userId, output);
    }
  }

  /**
   * Send message to Telegram via Gateway
   */
  private sendToTelegram(
    userId: string,
    text: string,
    buttons?: Array<{ text: string; data: string }>,
  ): void {
    const metadata: any = {};

    // Resolve chatId: cache → DB lookup
    let chatId = this.chatIdMap.get(userId);
    if (!chatId) {
      try {
        const row = this.db.prepare(
          'SELECT telegram_chat_id FROM users WHERE id = ?'
        ).get(userId) as { telegram_chat_id: string } | undefined;
        if (row?.telegram_chat_id) {
          chatId = parseInt(row.telegram_chat_id, 10);
          this.chatIdMap.set(userId, chatId);
        }
      } catch {
        // DB lookup failed, continue without chatId
      }
    }

    if (chatId) {
      metadata.chatId = chatId;
    }

    if (buttons && buttons.length > 0) {
      metadata.inline_keyboard = [buttons.map(b => ({
        text: b.text,
        callback_data: b.data,
      }))];
    }

    this.gateway.broadcast({
      from: 'agent',
      to: 'telegram',
      userId,
      content: text,
      metadata,
    });
  }

  // === Public API for Agent integration ===

  getStore(): PortfolioStore { return this.store; }
  getResearch(): ResearchEngine { return this.research; }
  getAnalysis(): AnalysisEngine { return this.analysis; }
  getRisk(): RiskEngine { return this.risk; }
  getExecution(): ExecutionEngine { return this.execution; }
  getScheduler(): InvestmentScheduler { return this.scheduler; }
}
