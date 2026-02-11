/**
 * PM Store - Prediction Market tables query layer
 * Reads from pm_* tables (created by Python db_utils.py) + manages pm_alerts
 */

import Database from 'better-sqlite3';
import { log } from '../utils/logger.js';
import type {
  PmMarket, PmPosition, PmPrice, PmTrade, PmAlertRow,
} from './types.js';

export class PmStore {
  private db: Database.Database;

  constructor(db: Database.Database) {
    this.db = db;
    this.initializeAlertTable();
  }

  /**
   * Create pm_alerts table (pm_* tables are created by Python scripts)
   */
  private initializeAlertTable(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS pm_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL DEFAULT 'default',
        alert_type TEXT NOT NULL,
        market_id TEXT,
        message TEXT NOT NULL,
        data_json TEXT,
        acknowledged INTEGER DEFAULT 0,
        created_at INTEGER DEFAULT (strftime('%s','now'))
      )
    `);

    this.db.exec(`
      CREATE INDEX IF NOT EXISTS idx_pm_alerts_user
        ON pm_alerts(user_id, acknowledged, created_at DESC)
    `);

    log('debug', '✅ PM alerts table initialized');
  }

  // === Markets (read from Python-created tables) ===

  getWatchlist(): PmMarket[] {
    try {
      return this.db.prepare(
        'SELECT * FROM pm_markets WHERE active = 1 ORDER BY updated_at DESC'
      ).all() as PmMarket[];
    } catch {
      return [];
    }
  }

  getMarket(marketId: string): PmMarket | null {
    try {
      const row = this.db.prepare(
        'SELECT * FROM pm_markets WHERE id = ?'
      ).get(marketId) as PmMarket | undefined;
      return row || null;
    } catch {
      return null;
    }
  }

  getExpiringMarkets(days: number = 7): PmMarket[] {
    try {
      const cutoff = new Date();
      cutoff.setDate(cutoff.getDate() + days);
      const cutoffStr = cutoff.toISOString();
      return this.db.prepare(
        `SELECT * FROM pm_markets
         WHERE active = 1 AND end_date != '' AND end_date <= ?
         ORDER BY end_date ASC`
      ).all(cutoffStr) as PmMarket[];
    } catch {
      return [];
    }
  }

  // === Positions ===

  getOpenPositions(userId: string = 'default'): PmPosition[] {
    try {
      return this.db.prepare(
        `SELECT * FROM pm_positions
         WHERE user_id = ? AND status = 'open'
         ORDER BY opened_at DESC`
      ).all(userId) as PmPosition[];
    } catch {
      return [];
    }
  }

  getAllPositions(userId: string = 'default'): PmPosition[] {
    try {
      return this.db.prepare(
        'SELECT * FROM pm_positions WHERE user_id = ? ORDER BY opened_at DESC'
      ).all(userId) as PmPosition[];
    } catch {
      return [];
    }
  }

  getPortfolioSummary(userId: string = 'default'): {
    openPositions: number;
    closedPositions: number;
    totalInvested: number;
    realizedPnl: number;
    winCount: number;
    lossCount: number;
    winRate: number;
  } {
    try {
      const open = this.getOpenPositions(userId);
      const closed = this.db.prepare(
        `SELECT * FROM pm_positions WHERE user_id = ? AND status = 'closed'`
      ).all(userId) as PmPosition[];

      const totalInvested = open.reduce((sum, p) => sum + p.entry_price * p.size, 0);
      const realizedPnl = closed.reduce((sum, p) => sum + (p.pnl || 0), 0);
      const winCount = closed.filter(p => (p.pnl || 0) > 0).length;
      const lossCount = closed.filter(p => (p.pnl || 0) < 0).length;
      const total = winCount + lossCount;

      return {
        openPositions: open.length,
        closedPositions: closed.length,
        totalInvested: Math.round(totalInvested * 100) / 100,
        realizedPnl: Math.round(realizedPnl * 100) / 100,
        winCount,
        lossCount,
        winRate: total > 0 ? Math.round((winCount / total) * 1000) / 10 : 0,
      };
    } catch {
      return { openPositions: 0, closedPositions: 0, totalInvested: 0, realizedPnl: 0, winCount: 0, lossCount: 0, winRate: 0 };
    }
  }

  // === Prices ===

  getLatestPrice(marketId: string): PmPrice | null {
    try {
      const row = this.db.prepare(
        'SELECT * FROM pm_prices WHERE market_id = ? ORDER BY recorded_at DESC, id DESC LIMIT 1'
      ).get(marketId) as PmPrice | undefined;
      return row || null;
    } catch {
      return null;
    }
  }

  // === Trades ===

  getRecentTrades(limit: number = 20): PmTrade[] {
    try {
      return this.db.prepare(
        'SELECT * FROM pm_trades ORDER BY executed_at DESC, id DESC LIMIT ?'
      ).all(limit) as PmTrade[];
    } catch {
      return [];
    }
  }

  // === Alerts ===

  insertAlert(userId: string, alertType: string, message: string, marketId?: string, dataJson?: string): number {
    const result = this.db.prepare(`
      INSERT INTO pm_alerts (user_id, alert_type, market_id, message, data_json)
      VALUES (?, ?, ?, ?, ?)
    `).run(userId, alertType, marketId || null, message, dataJson || null);
    return Number(result.lastInsertRowid);
  }

  getActiveAlerts(userId: string): PmAlertRow[] {
    return this.db.prepare(`
      SELECT * FROM pm_alerts
      WHERE user_id = ? AND acknowledged = 0
      ORDER BY created_at DESC
    `).all(userId) as PmAlertRow[];
  }

  acknowledgeAlerts(userId: string): number {
    const result = this.db.prepare(
      'UPDATE pm_alerts SET acknowledged = 1 WHERE user_id = ? AND acknowledged = 0'
    ).run(userId);
    return result.changes;
  }

  acknowledgeAlert(alertId: number): void {
    this.db.prepare(
      'UPDATE pm_alerts SET acknowledged = 1 WHERE id = ?'
    ).run(alertId);
  }
}
