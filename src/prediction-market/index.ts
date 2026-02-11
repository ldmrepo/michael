/**
 * PredictionMarketService - Main orchestrator
 * Connects PM scheduler, store, and Telegram notifications
 */

import Database from 'better-sqlite3';
import { log } from '../utils/logger.js';
import { Gateway, GatewayMessage } from '../core/gateway.js';
import { PmStore } from './pm-store.js';
import { PmScheduler } from './scheduler-jobs.js';
import type { PmScriptOutput, PmAlert } from './types.js';

export class PredictionMarketService {
  private store: PmStore;
  private scheduler: PmScheduler;
  private gateway: Gateway;
  private userId: string;
  private chatIdMap: Map<string, number> = new Map();
  private db: Database.Database;

  constructor(db: Database.Database, gateway: Gateway, userId: string = 'default') {
    this.gateway = gateway;
    this.userId = userId;
    this.db = db;

    // Initialize components
    this.store = new PmStore(db);
    this.scheduler = new PmScheduler(userId);

    // Wire up scheduler job callbacks
    this.scheduler.setJobCallback((jobName, output) => {
      this.handleJobResult(jobName, output);
    });

    // Register as Gateway handler for 'prediction-market' messages
    this.gateway.registerHandler('prediction-market', async (message) => {
      await this.handleGatewayMessage(message);
    });

    log('info', '🎯 PredictionMarketService initialized');
  }

  /**
   * Start the service
   */
  start(): void {
    this.scheduler.start();
    log('info', '✅ PredictionMarketService started');
  }

  /**
   * Stop the service
   */
  stop(): void {
    this.scheduler.stop();
    log('info', '⏹️ PredictionMarketService stopped');
  }

  /**
   * Handle Telegram callback queries for pm_ prefix
   */
  async handleCallback(action: string, userId: string): Promise<void> {
    log('debug', `🎯 PM callback: ${action}`);

    switch (action) {
      case 'pm_portfolio':
        await this.sendPortfolioSummary(userId);
        break;

      case 'pm_scan':
        await this.triggerManualScan(userId);
        break;

      case 'pm_watchlist':
        await this.sendWatchlist(userId);
        break;

      case 'pm_brief':
        await this.triggerManualBrief(userId);
        break;

      case 'pm_ack_alert': {
        const count = this.store.acknowledgeAlerts(userId);
        this.sendToTelegram(userId, `✅ ${count}개 PM 알림 확인됨`);
        break;
      }

      default:
        log('warn', `⚠️ Unknown PM action: ${action}`);
    }
  }

  /**
   * Handle incoming Gateway messages targeted to 'prediction-market'
   */
  private async handleGatewayMessage(message: GatewayMessage): Promise<void> {
    const chatId = message.metadata?.chatId;

    if (chatId) {
      this.chatIdMap.set(this.userId, chatId);
    }

    if (message.metadata?.type === 'pm_callback') {
      await this.handleCallback(message.content, this.userId);
    }
  }

  /**
   * Handle completed job results
   */
  private handleJobResult(jobName: string, output: PmScriptOutput): void {
    if (output.status === 'error') {
      log('warn', `❌ PM job ${jobName} failed: ${output.message}`);
      return;
    }

    switch (jobName) {
      case 'pm_daily_brief':
        this.handleBriefResult(output);
        break;

      case 'scan_high_prob':
      case 'scan_new_markets':
        this.handleScanResult(jobName, output);
        break;

      case 'monitor_pm_prices':
      case 'monitor_arb':
        this.handleMonitorResult(jobName, output);
        break;
    }
  }

  /**
   * Handle daily briefing result
   */
  private handleBriefResult(output: PmScriptOutput): void {
    if (!output.report) return;

    const buttons = [
      { text: '포트폴리오', data: 'pm_portfolio' },
      { text: '스캔', data: 'pm_scan' },
      { text: '워치리스트', data: 'pm_watchlist' },
    ];

    this.sendToTelegram(this.userId, output.report, buttons);
  }

  /**
   * Handle scan results (high-prob, new markets)
   */
  private handleScanResult(jobName: string, output: PmScriptOutput): void {
    if (!output.data) return;

    const markets = output.data.markets || output.data;
    if (!Array.isArray(markets) || markets.length === 0) return;

    const type = jobName === 'scan_high_prob' ? '고확률' : '신규';
    let text = `🔍 ${type} 마켓 스캔 결과: ${markets.length}개\n\n`;

    for (const m of markets.slice(0, 5)) {
      const q = (m.question || m.title || '').substring(0, 50);
      const price = m.yes_price || m.outcomePrices?.[0] || 'N/A';
      text += `• "${q}"\n  YES: $${price} | Vol: $${(m.volume || 0).toLocaleString()}\n`;
    }

    if (markets.length > 5) {
      text += `\n... +${markets.length - 5}개 더`;
    }

    this.sendToTelegram(this.userId, text);
  }

  /**
   * Handle monitor results (price changes, arbitrage)
   */
  private handleMonitorResult(jobName: string, output: PmScriptOutput): void {
    if (!output.alerts || output.alerts.length === 0) return;

    for (const alert of output.alerts) {
      this.store.insertAlert(
        this.userId,
        alert.type,
        alert.message || this.formatAlertMessage(alert),
        alert.market_id,
        JSON.stringify(alert),
      );
    }

    if (jobName === 'monitor_pm_prices') {
      this.sendPriceAlerts(output.alerts);
    } else if (jobName === 'monitor_arb') {
      this.sendArbAlerts(output.alerts);
    }
  }

  /**
   * Format alert message from alert data
   */
  private formatAlertMessage(alert: PmAlert): string {
    if (alert.type === 'price_change') {
      const dir = (alert.change_pct || 0) > 0 ? '📈' : '📉';
      return `${dir} ${alert.change_pct?.toFixed(1)}% "${alert.question || ''}"`;
    }
    if (alert.type === 'arbitrage') {
      return `⚡ Arb: ${alert.net_profit_pct?.toFixed(1)}% "${alert.question || ''}"`;
    }
    return alert.message || 'Alert';
  }

  /**
   * Send price change alerts to Telegram
   */
  private sendPriceAlerts(alerts: PmAlert[]): void {
    let text = '🔔 PM 가격 변동\n\n';

    for (const a of alerts.slice(0, 5)) {
      const dir = (a.change_pct || 0) > 0 ? '📈' : '📉';
      text += `${dir} ${a.change_pct?.toFixed(1)}% "${(a.question || '').substring(0, 40)}"\n`;
      if (a.prev_price !== undefined && a.current_price !== undefined) {
        text += `  YES: $${a.prev_price?.toFixed(2)} → $${a.current_price?.toFixed(2)}`;
      }
      text += '\n\n';
    }

    if (alerts.length > 5) {
      text += `... +${alerts.length - 5}개 더`;
    }

    const buttons = [{ text: '확인', data: 'pm_ack_alert' }];
    this.sendToTelegram(this.userId, text, buttons);
  }

  /**
   * Send arbitrage alerts to Telegram
   */
  private sendArbAlerts(alerts: PmAlert[]): void {
    const arbAlerts = alerts.filter(a => a.type === 'arbitrage');
    if (arbAlerts.length === 0) return;

    let text = '⚡ 차익거래 기회\n\n';

    for (const a of arbAlerts.slice(0, 3)) {
      text += `"${(a.question || '').substring(0, 40)}"\n`;
      if (a.net_profit_pct) {
        text += `  순이익: ${a.net_profit_pct.toFixed(1)}%\n`;
      }
      if (a.message) {
        text += `  ${a.message}\n`;
      }
      text += '\n';
    }

    const buttons = [{ text: '확인', data: 'pm_ack_alert' }];
    this.sendToTelegram(this.userId, text, buttons);
  }

  /**
   * Send portfolio summary
   */
  private async sendPortfolioSummary(userId: string): Promise<void> {
    const summary = this.store.getPortfolioSummary(userId);
    const positions = this.store.getOpenPositions(userId);

    let text = '🎯 PM 포트폴리오\n\n';
    text += `포지션: ${summary.openPositions}개 | 투자: $${summary.totalInvested.toLocaleString()}\n`;
    text += `실현 P&L: $${summary.realizedPnl.toFixed(2)} | 승률: ${summary.winRate}%\n\n`;

    if (positions.length > 0) {
      for (const p of positions.slice(0, 10)) {
        const market = this.store.getMarket(p.market_id);
        const latest = this.store.getLatestPrice(p.market_id);
        const q = market ? market.question.substring(0, 40) : p.market_id.substring(0, 20);
        const cp = latest
          ? (p.side === 'YES' ? latest.yes_price : latest.no_price)
          : p.current_price;
        const cpStr = cp !== null ? `$${cp.toFixed(2)}` : 'N/A';
        text += `${p.side} ${p.size} @ $${p.entry_price.toFixed(2)} → ${cpStr}\n`;
        text += `  ${q}\n`;
      }
    } else {
      text += '오픈 포지션 없음';
    }

    const buttons = [
      { text: '브리핑', data: 'pm_brief' },
      { text: '워치리스트', data: 'pm_watchlist' },
    ];

    this.sendToTelegram(userId, text, buttons);
  }

  /**
   * Send watchlist
   */
  private async sendWatchlist(userId: string): Promise<void> {
    const watchlist = this.store.getWatchlist();

    let text = `🎯 PM 워치리스트: ${watchlist.length} 마켓\n\n`;

    if (watchlist.length === 0) {
      text += '워치리스트가 비어있습니다.';
    } else {
      for (const m of watchlist.slice(0, 10)) {
        const latest = this.store.getLatestPrice(m.id);
        const price = latest ? `YES $${latest.yes_price.toFixed(2)}` : 'N/A';
        const q = m.question.substring(0, 40);
        text += `• "${q}"\n  ${price} | Vol: $${(m.volume || 0).toLocaleString()}\n`;
      }
      if (watchlist.length > 10) {
        text += `\n... +${watchlist.length - 10}개 더`;
      }
    }

    const buttons = [
      { text: '스캔', data: 'pm_scan' },
      { text: '포트폴리오', data: 'pm_portfolio' },
    ];

    this.sendToTelegram(userId, text, buttons);
  }

  /**
   * Trigger manual scan
   */
  private async triggerManualScan(userId: string): Promise<void> {
    this.sendToTelegram(userId, '🔍 고확률 마켓 스캔 시작...');
    const output = await this.scheduler.runJobByName('scan_high_prob');
    if (output.status === 'error') {
      this.sendToTelegram(userId, `❌ 스캔 실패: ${output.message}`);
    }
    // handleJobResult will send the scan results
  }

  /**
   * Trigger manual briefing
   */
  private async triggerManualBrief(userId: string): Promise<void> {
    this.sendToTelegram(userId, '📊 브리핑 생성 중...');
    const output = await this.scheduler.runJobByName('pm_daily_brief');
    if (output.status === 'error') {
      this.sendToTelegram(userId, `❌ 브리핑 실패: ${output.message}`);
    }
    // handleJobResult will send the briefing
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
        // DB lookup failed
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

  // === Public API ===

  getStore(): PmStore { return this.store; }
  getScheduler(): PmScheduler { return this.scheduler; }
}
