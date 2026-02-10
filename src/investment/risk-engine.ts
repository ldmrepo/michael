/**
 * Risk Engine - threshold management, alert processing, Telegram notifications
 */

import { log } from '../utils/logger.js';
import { PortfolioStore } from './portfolio-store.js';
import { InvestmentScheduler } from './scheduler-jobs.js';
import type { RiskAlert, RiskThreshold, ScriptOutput, AlertSeverity } from './types.js';

type SendAlertFn = (userId: string, text: string, severity: AlertSeverity,
                    buttons?: Array<{ text: string; data: string }>) => void;

export class RiskEngine {
  private store: PortfolioStore;
  private scheduler: InvestmentScheduler;
  private sendAlert?: SendAlertFn;

  constructor(store: PortfolioStore, scheduler: InvestmentScheduler) {
    this.store = store;
    this.scheduler = scheduler;
  }

  /**
   * Set callback for sending alerts to Telegram
   */
  setSendAlert(fn: SendAlertFn): void {
    this.sendAlert = fn;
  }

  /**
   * Process alerts from monitor scripts
   */
  processAlerts(userId: string, output: ScriptOutput): void {
    if (!output.alerts || output.alerts.length === 0) return;

    for (const alert of output.alerts) {
      if (alert.severity === 'critical' || alert.severity === 'warning') {
        this.notifyAlert(userId, alert);
      }
    }
  }

  /**
   * Send alert notification to Telegram
   */
  private notifyAlert(userId: string, alert: any): void {
    if (!this.sendAlert) return;

    let emoji = '⚠️';
    if (alert.severity === 'critical') emoji = '🚨';
    if (alert.severity === 'info') emoji = 'ℹ️';

    const text = `${emoji} ${alert.severity.toUpperCase()}: ${alert.message}`;
    const buttons = [];

    if (alert.type === 'liquidation_proximity' || alert.type === 'price_drop_pct') {
      buttons.push(
        { text: '포지션축소', data: `inv_reduce_position:symbol=${alert.symbol}` },
        { text: '손절설정', data: `inv_set_stoploss:symbol=${alert.symbol}` },
        { text: '확인', data: `inv_ack_alert:symbol=${alert.symbol}` },
      );
    } else {
      buttons.push(
        { text: '확인', data: `inv_ack_alert:symbol=${alert.symbol || ''}` },
      );
    }

    this.sendAlert(userId, text, alert.severity, buttons);
  }

  /**
   * Run price monitor manually
   */
  async checkPrices(userId: string): Promise<ScriptOutput> {
    return this.scheduler.spawnPython('monitor_prices.py', ['--user-id', userId], 'monitor_prices');
  }

  /**
   * Run risk monitor manually
   */
  async checkRisk(userId: string): Promise<ScriptOutput> {
    return this.scheduler.spawnPython('monitor_risk.py', ['--user-id', userId], 'monitor_risk');
  }

  // === Threshold Management ===

  getThresholds(userId: string): RiskThreshold[] {
    return this.store.getThresholds(userId);
  }

  setThreshold(userId: string, type: string, value: number, symbol?: string): void {
    this.store.upsertThreshold(userId, type, value, symbol);
    log('info', `🔔 Threshold set: ${type} ${symbol || 'global'} = ${value}`);
  }

  // === Alert Management ===

  getActiveAlerts(userId: string): RiskAlert[] {
    return this.store.getActiveAlerts(userId);
  }

  acknowledgeAlert(alertId: number): void {
    this.store.acknowledgeAlert(alertId);
  }
}
