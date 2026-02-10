/**
 * Portfolio Store - Investment tables initialization and CRUD
 * Uses the shared Memory database (better-sqlite3)
 */

import Database from 'better-sqlite3';
import { log } from '../utils/logger.js';
import type {
  Holding, Transaction, Snapshot, Research,
  Analysis, RiskAlert, RiskThreshold,
  Proposal, DcaSchedule, ResearchCategory,
} from './types.js';

export class PortfolioStore {
  private db: Database.Database;

  constructor(db: Database.Database) {
    this.db = db;
    this.initializeInvestmentTables();
  }

  /**
   * Create all investment tables
   */
  private initializeInvestmentTables(): void {
    // Module 1: Portfolio
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS investment_holdings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        exchange TEXT DEFAULT 'binance',
        account_type TEXT NOT NULL CHECK(account_type IN ('spot','futures')),
        symbol TEXT NOT NULL,
        quantity REAL NOT NULL,
        avg_entry_price REAL,
        current_price REAL,
        unrealized_pnl REAL,
        leverage INTEGER,
        liquidation_price REAL,
        position_side TEXT DEFAULT 'BOTH',
        updated_at INTEGER DEFAULT (strftime('%s','now')),
        UNIQUE(user_id, exchange, account_type, symbol, position_side)
      )
    `);

    this.db.exec(`
      CREATE TABLE IF NOT EXISTS investment_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        exchange TEXT DEFAULT 'binance',
        account_type TEXT NOT NULL,
        symbol TEXT NOT NULL,
        side TEXT NOT NULL CHECK(side IN ('BUY','SELL')),
        order_type TEXT NOT NULL,
        quantity REAL NOT NULL,
        price REAL NOT NULL,
        fee REAL DEFAULT 0,
        fee_asset TEXT,
        realized_pnl REAL,
        order_id TEXT,
        source TEXT DEFAULT 'manual',
        executed_at INTEGER NOT NULL,
        created_at INTEGER DEFAULT (strftime('%s','now'))
      )
    `);

    this.db.exec(`
      CREATE TABLE IF NOT EXISTS investment_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        date TEXT NOT NULL,
        total_value_usd REAL NOT NULL,
        spot_value_usd REAL,
        futures_value_usd REAL,
        unrealized_pnl_usd REAL,
        btc_price REAL,
        holdings_json TEXT,
        created_at INTEGER DEFAULT (strftime('%s','now')),
        UNIQUE(user_id, date)
      )
    `);

    // Module 2: Research
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS investment_research (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        category TEXT NOT NULL,
        symbol TEXT,
        data_json TEXT NOT NULL,
        collected_at INTEGER DEFAULT (strftime('%s','now'))
      )
    `);

    this.db.exec(`
      CREATE INDEX IF NOT EXISTS idx_research_source
        ON investment_research(source, collected_at DESC)
    `);

    this.db.exec(`
      CREATE INDEX IF NOT EXISTS idx_research_category
        ON investment_research(category, collected_at DESC)
    `);

    // Module 3: Analysis
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS investment_analysis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        analysis_type TEXT NOT NULL,
        market_regime TEXT,
        overall_score INTEGER,
        summary TEXT NOT NULL,
        details_json TEXT,
        recommendations_json TEXT,
        created_at INTEGER DEFAULT (strftime('%s','now'))
      )
    `);

    // Module 4: Risk
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS investment_risk_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        alert_type TEXT NOT NULL,
        severity TEXT NOT NULL CHECK(severity IN ('info','warning','critical')),
        symbol TEXT,
        message TEXT NOT NULL,
        data_json TEXT,
        acknowledged INTEGER DEFAULT 0,
        created_at INTEGER DEFAULT (strftime('%s','now'))
      )
    `);

    this.db.exec(`
      CREATE TABLE IF NOT EXISTS investment_risk_thresholds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        threshold_type TEXT NOT NULL,
        symbol TEXT,
        value REAL NOT NULL,
        active INTEGER DEFAULT 1,
        created_at INTEGER DEFAULT (strftime('%s','now')),
        UNIQUE(user_id, threshold_type, symbol)
      )
    `);

    // Module 5: Execution
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS investment_proposals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        proposal_type TEXT NOT NULL,
        status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','executed','failed','expired')),
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        account_type TEXT NOT NULL,
        order_type TEXT NOT NULL,
        quantity REAL NOT NULL,
        price REAL,
        leverage INTEGER,
        stop_loss REAL,
        take_profit REAL,
        rationale TEXT,
        analysis_id INTEGER,
        telegram_message_id INTEGER,
        approved_at INTEGER,
        executed_at INTEGER,
        execution_result_json TEXT,
        expires_at INTEGER,
        created_at INTEGER DEFAULT (strftime('%s','now'))
      )
    `);

    this.db.exec(`
      CREATE TABLE IF NOT EXISTS investment_dca_schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        account_type TEXT DEFAULT 'spot',
        amount_usd REAL NOT NULL,
        cron_expression TEXT NOT NULL,
        active INTEGER DEFAULT 1,
        last_executed_at INTEGER,
        total_invested REAL DEFAULT 0,
        total_quantity REAL DEFAULT 0,
        created_at INTEGER DEFAULT (strftime('%s','now'))
      )
    `);

    log('debug', '✅ Investment tables initialized');
  }

  // === Holdings ===

  getHoldings(userId: string, accountType?: string): Holding[] {
    let query = `
      SELECT id, user_id as userId, exchange, account_type as accountType,
             symbol, quantity, avg_entry_price as avgEntryPrice,
             current_price as currentPrice, unrealized_pnl as unrealizedPnl,
             leverage, liquidation_price as liquidationPrice,
             position_side as positionSide, updated_at as updatedAt
      FROM investment_holdings WHERE user_id = ?
    `;
    const params: any[] = [userId];
    if (accountType) {
      query += ' AND account_type = ?';
      params.push(accountType);
    }
    query += ' ORDER BY current_price * quantity DESC';
    return this.db.prepare(query).all(...params) as Holding[];
  }

  getTotalValue(userId: string): { spot: number; futures: number; total: number } {
    const holdings = this.getHoldings(userId);
    let spot = 0, futures = 0;
    for (const h of holdings) {
      const value = (h.currentPrice || 0) * h.quantity;
      if (h.accountType === 'spot') spot += value;
      else futures += value;
    }
    return { spot, futures, total: spot + futures };
  }

  // === Transactions ===

  getTransactions(userId: string, limit = 50): Transaction[] {
    return this.db.prepare(`
      SELECT id, user_id as userId, exchange, account_type as accountType,
             symbol, side, order_type as orderType, quantity, price,
             fee, fee_asset as feeAsset, realized_pnl as realizedPnl,
             order_id as orderId, source, executed_at as executedAt,
             created_at as createdAt
      FROM investment_transactions WHERE user_id = ?
      ORDER BY executed_at DESC LIMIT ?
    `).all(userId, limit) as Transaction[];
  }

  // === Snapshots ===

  getSnapshots(userId: string, days = 30): Snapshot[] {
    return this.db.prepare(`
      SELECT id, user_id as userId, date, total_value_usd as totalValueUsd,
             spot_value_usd as spotValueUsd, futures_value_usd as futuresValueUsd,
             unrealized_pnl_usd as unrealizedPnlUsd, btc_price as btcPrice,
             holdings_json as holdingsJson, created_at as createdAt
      FROM investment_snapshots WHERE user_id = ?
      ORDER BY date DESC LIMIT ?
    `).all(userId, days) as Snapshot[];
  }

  getLatestSnapshot(userId: string): Snapshot | null {
    const row = this.db.prepare(`
      SELECT id, user_id as userId, date, total_value_usd as totalValueUsd,
             spot_value_usd as spotValueUsd, futures_value_usd as futuresValueUsd,
             unrealized_pnl_usd as unrealizedPnlUsd, btc_price as btcPrice,
             holdings_json as holdingsJson, created_at as createdAt
      FROM investment_snapshots WHERE user_id = ?
      ORDER BY date DESC LIMIT 1
    `).get(userId) as Snapshot | undefined;
    return row || null;
  }

  // === Research ===

  getLatestResearch(category?: ResearchCategory, hours = 24): Research[] {
    const cutoff = Math.floor(Date.now() / 1000) - hours * 3600;
    let query = `
      SELECT id, source, category, symbol, data_json as dataJson,
             collected_at as collectedAt
      FROM investment_research WHERE collected_at > ?
    `;
    const params: any[] = [cutoff];
    if (category) {
      query += ' AND category = ?';
      params.push(category);
    }
    query += ' ORDER BY collected_at DESC';
    return this.db.prepare(query).all(...params) as Research[];
  }

  // === Analysis ===

  getLatestAnalysis(userId: string): Analysis | null {
    const row = this.db.prepare(`
      SELECT id, user_id as userId, analysis_type as analysisType,
             market_regime as marketRegime, overall_score as overallScore,
             summary, details_json as detailsJson,
             recommendations_json as recommendationsJson,
             created_at as createdAt
      FROM investment_analysis WHERE user_id = ?
      ORDER BY created_at DESC LIMIT 1
    `).get(userId) as Analysis | undefined;
    return row || null;
  }

  insertAnalysis(userId: string, analysisType: string, summary: string,
                 marketRegime?: string, overallScore?: number,
                 detailsJson?: string, recommendationsJson?: string): number {
    const result = this.db.prepare(`
      INSERT INTO investment_analysis
        (user_id, analysis_type, market_regime, overall_score, summary, details_json, recommendations_json)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(userId, analysisType, marketRegime || null, overallScore ?? null,
           summary, detailsJson || null, recommendationsJson || null);
    return Number(result.lastInsertRowid);
  }

  // === Risk ===

  getActiveAlerts(userId: string): RiskAlert[] {
    return this.db.prepare(`
      SELECT id, user_id as userId, alert_type as alertType,
             severity, symbol, message, data_json as dataJson,
             acknowledged, created_at as createdAt
      FROM investment_risk_alerts
      WHERE user_id = ? AND acknowledged = 0
      ORDER BY created_at DESC
    `).all(userId) as RiskAlert[];
  }

  acknowledgeAlert(alertId: number): void {
    this.db.prepare(
      'UPDATE investment_risk_alerts SET acknowledged = 1 WHERE id = ?'
    ).run(alertId);
  }

  getThresholds(userId: string): RiskThreshold[] {
    return this.db.prepare(`
      SELECT id, user_id as userId, threshold_type as thresholdType,
             symbol, value, active, created_at as createdAt
      FROM investment_risk_thresholds
      WHERE user_id = ? AND active = 1
    `).all(userId) as RiskThreshold[];
  }

  upsertThreshold(userId: string, thresholdType: string, value: number, symbol?: string): void {
    this.db.prepare(`
      INSERT INTO investment_risk_thresholds (user_id, threshold_type, symbol, value)
      VALUES (?, ?, ?, ?)
      ON CONFLICT(user_id, threshold_type, symbol) DO UPDATE SET
        value = excluded.value, active = 1
    `).run(userId, thresholdType, symbol || null, value);
  }

  // === Proposals ===

  getProposal(proposalId: number): Proposal | null {
    const row = this.db.prepare(`
      SELECT id, user_id as userId, proposal_type as proposalType,
             status, symbol, side, account_type as accountType,
             order_type as orderType, quantity, price, leverage,
             stop_loss as stopLoss, take_profit as takeProfit,
             rationale, analysis_id as analysisId,
             telegram_message_id as telegramMessageId,
             approved_at as approvedAt, executed_at as executedAt,
             execution_result_json as executionResultJson,
             expires_at as expiresAt, created_at as createdAt
      FROM investment_proposals WHERE id = ?
    `).get(proposalId) as Proposal | undefined;
    return row || null;
  }

  getPendingProposals(userId: string): Proposal[] {
    return this.db.prepare(`
      SELECT id, user_id as userId, proposal_type as proposalType,
             status, symbol, side, account_type as accountType,
             order_type as orderType, quantity, price, leverage,
             stop_loss as stopLoss, take_profit as takeProfit,
             rationale, analysis_id as analysisId,
             telegram_message_id as telegramMessageId,
             approved_at as approvedAt, executed_at as executedAt,
             execution_result_json as executionResultJson,
             expires_at as expiresAt, created_at as createdAt
      FROM investment_proposals
      WHERE user_id = ? AND status = 'pending'
      ORDER BY created_at DESC
    `).all(userId) as Proposal[];
  }

  insertProposal(userId: string, proposalType: string, symbol: string,
                  side: string, accountType: string, orderType: string,
                  quantity: number, price?: number, leverage?: number,
                  stopLoss?: number, takeProfit?: number, rationale?: string,
                  analysisId?: number, expiresAt?: number): number {
    const result = this.db.prepare(`
      INSERT INTO investment_proposals
        (user_id, proposal_type, symbol, side, account_type, order_type,
         quantity, price, leverage, stop_loss, take_profit, rationale,
         analysis_id, expires_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(userId, proposalType, symbol, side, accountType, orderType,
           quantity, price ?? null, leverage ?? null, stopLoss ?? null,
           takeProfit ?? null, rationale ?? null, analysisId ?? null,
           expiresAt ?? null);
    return Number(result.lastInsertRowid);
  }

  updateProposalStatus(proposalId: number, status: string,
                       executionResult?: string, telegramMessageId?: number): void {
    const now = Math.floor(Date.now() / 1000);
    if (status === 'approved') {
      this.db.prepare(
        'UPDATE investment_proposals SET status = ?, approved_at = ? WHERE id = ?'
      ).run(status, now, proposalId);
    } else if (status === 'executed' || status === 'failed') {
      this.db.prepare(
        'UPDATE investment_proposals SET status = ?, executed_at = ?, execution_result_json = ? WHERE id = ?'
      ).run(status, now, executionResult || null, proposalId);
    } else {
      this.db.prepare(
        'UPDATE investment_proposals SET status = ? WHERE id = ?'
      ).run(status, proposalId);
    }
    if (telegramMessageId) {
      this.db.prepare(
        'UPDATE investment_proposals SET telegram_message_id = ? WHERE id = ?'
      ).run(telegramMessageId, proposalId);
    }
  }

  expirePendingProposals(): number {
    const now = Math.floor(Date.now() / 1000);
    const result = this.db.prepare(
      "UPDATE investment_proposals SET status = 'expired' WHERE status = 'pending' AND expires_at IS NOT NULL AND expires_at < ?"
    ).run(now);
    return result.changes;
  }

  // === DCA ===

  getDcaSchedules(userId?: string): DcaSchedule[] {
    let query = `
      SELECT id, user_id as userId, symbol, account_type as accountType,
             amount_usd as amountUsd, cron_expression as cronExpression,
             active, last_executed_at as lastExecutedAt,
             total_invested as totalInvested, total_quantity as totalQuantity,
             created_at as createdAt
      FROM investment_dca_schedules WHERE active = 1
    `;
    const params: any[] = [];
    if (userId) {
      query += ' AND user_id = ?';
      params.push(userId);
    }
    return this.db.prepare(query).all(...params) as DcaSchedule[];
  }
}
