"""
Database Utilities for Investment Skill
Direct Python sqlite3 access to data/memory.db
"""

import sqlite3
import json
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    """Get a connection to the project's SQLite database, ensuring tables exist"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    _ensure_tables(conn)
    return conn


def _ensure_tables(conn: sqlite3.Connection):
    """Create investment tables if they don't exist"""
    conn.executescript("""
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
        );

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
        );

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
        );

        CREATE TABLE IF NOT EXISTS investment_research (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            category TEXT NOT NULL,
            symbol TEXT,
            data_json TEXT NOT NULL,
            collected_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE INDEX IF NOT EXISTS idx_research_source
            ON investment_research(source, collected_at DESC);
        CREATE INDEX IF NOT EXISTS idx_research_category
            ON investment_research(category, collected_at DESC);

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
        );

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
        );

        CREATE TABLE IF NOT EXISTS investment_risk_thresholds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            threshold_type TEXT NOT NULL,
            symbol TEXT,
            value REAL NOT NULL,
            active INTEGER DEFAULT 1,
            created_at INTEGER DEFAULT (strftime('%s','now')),
            UNIQUE(user_id, threshold_type, symbol)
        );

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
        );

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
        );
    """)


# === Holdings ===

def upsert_holding(conn: sqlite3.Connection, user_id: str, exchange: str,
                   account_type: str, symbol: str, quantity: float,
                   avg_entry_price: float = None, current_price: float = None,
                   unrealized_pnl: float = None, leverage: int = None,
                   liquidation_price: float = None, position_side: str = "BOTH"):
    """Insert or update a holding"""
    conn.execute("""
        INSERT INTO investment_holdings
            (user_id, exchange, account_type, symbol, quantity, avg_entry_price,
             current_price, unrealized_pnl, leverage, liquidation_price, position_side, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, strftime('%s','now'))
        ON CONFLICT(user_id, exchange, account_type, symbol, position_side) DO UPDATE SET
            quantity = excluded.quantity,
            avg_entry_price = COALESCE(excluded.avg_entry_price, avg_entry_price),
            current_price = COALESCE(excluded.current_price, current_price),
            unrealized_pnl = COALESCE(excluded.unrealized_pnl, unrealized_pnl),
            leverage = COALESCE(excluded.leverage, leverage),
            liquidation_price = COALESCE(excluded.liquidation_price, liquidation_price),
            updated_at = strftime('%s','now')
    """, (user_id, exchange, account_type, symbol, quantity,
          avg_entry_price, current_price, unrealized_pnl, leverage,
          liquidation_price, position_side))
    conn.commit()


def get_holdings(conn: sqlite3.Connection, user_id: str,
                 account_type: str = None) -> List[Dict[str, Any]]:
    """Get holdings for a user"""
    query = "SELECT * FROM investment_holdings WHERE user_id = ?"
    params: list = [user_id]
    if account_type:
        query += " AND account_type = ?"
        params.append(account_type)
    query += " ORDER BY current_price * quantity DESC"
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def clear_holdings(conn: sqlite3.Connection, user_id: str,
                   exchange: str = "binance", account_type: str = None):
    """Clear holdings (before full sync)"""
    query = "DELETE FROM investment_holdings WHERE user_id = ? AND exchange = ?"
    params: list = [user_id, exchange]
    if account_type:
        query += " AND account_type = ?"
        params.append(account_type)
    conn.execute(query, params)
    conn.commit()


# === Transactions ===

def insert_transaction(conn: sqlite3.Connection, user_id: str, exchange: str,
                       account_type: str, symbol: str, side: str, order_type: str,
                       quantity: float, price: float, fee: float = 0,
                       fee_asset: str = None, realized_pnl: float = None,
                       order_id: str = None, source: str = "manual",
                       executed_at: int = None):
    """Insert a transaction record"""
    executed_at = executed_at or int(time.time())
    conn.execute("""
        INSERT INTO investment_transactions
            (user_id, exchange, account_type, symbol, side, order_type,
             quantity, price, fee, fee_asset, realized_pnl, order_id, source, executed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, exchange, account_type, symbol, side, order_type,
          quantity, price, fee, fee_asset, realized_pnl, order_id, source, executed_at))
    conn.commit()


# === Snapshots ===

def upsert_snapshot(conn: sqlite3.Connection, user_id: str, date: str,
                    total_value_usd: float, spot_value_usd: float = None,
                    futures_value_usd: float = None, unrealized_pnl_usd: float = None,
                    btc_price: float = None, holdings_json: str = None):
    """Insert or update a daily snapshot"""
    conn.execute("""
        INSERT INTO investment_snapshots
            (user_id, date, total_value_usd, spot_value_usd, futures_value_usd,
             unrealized_pnl_usd, btc_price, holdings_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, date) DO UPDATE SET
            total_value_usd = excluded.total_value_usd,
            spot_value_usd = excluded.spot_value_usd,
            futures_value_usd = excluded.futures_value_usd,
            unrealized_pnl_usd = excluded.unrealized_pnl_usd,
            btc_price = excluded.btc_price,
            holdings_json = excluded.holdings_json
    """, (user_id, date, total_value_usd, spot_value_usd, futures_value_usd,
          unrealized_pnl_usd, btc_price, holdings_json))
    conn.commit()


# === Research ===

def insert_research(conn: sqlite3.Connection, source: str, category: str,
                    data_json: str, symbol: str = None):
    """Insert research data"""
    conn.execute("""
        INSERT INTO investment_research (source, category, symbol, data_json)
        VALUES (?, ?, ?, ?)
    """, (source, category, symbol, data_json))
    conn.commit()


def get_latest_research(conn: sqlite3.Connection, category: str = None,
                        hours: int = 24) -> List[Dict[str, Any]]:
    """Get recent research data"""
    cutoff = int(time.time()) - (hours * 3600)
    query = "SELECT * FROM investment_research WHERE collected_at > ?"
    params: list = [cutoff]
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY collected_at DESC"
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def cleanup_old_research(conn: sqlite3.Connection, days: int = 30) -> int:
    """Delete research data older than specified days. Returns count of deleted rows."""
    cutoff = int(time.time()) - (days * 86400)
    cursor = conn.execute(
        "DELETE FROM investment_research WHERE collected_at < ?", (cutoff,)
    )
    conn.commit()
    return cursor.rowcount


# === Risk Alerts ===

def insert_alert(conn: sqlite3.Connection, user_id: str, alert_type: str,
                 severity: str, message: str, symbol: str = None,
                 data_json: str = None):
    """Insert a risk alert"""
    conn.execute("""
        INSERT INTO investment_risk_alerts
            (user_id, alert_type, severity, symbol, message, data_json)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, alert_type, severity, symbol, message, data_json))
    conn.commit()


def get_thresholds(conn: sqlite3.Connection, user_id: str,
                   active_only: bool = True) -> List[Dict[str, Any]]:
    """Get risk thresholds"""
    query = "SELECT * FROM investment_risk_thresholds WHERE user_id = ?"
    params: list = [user_id]
    if active_only:
        query += " AND active = 1"
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


# === Proposals ===

def insert_proposal(conn: sqlite3.Connection, user_id: str, proposal_type: str,
                    symbol: str, side: str, account_type: str, order_type: str,
                    quantity: float, price: float = None, leverage: int = None,
                    stop_loss: float = None, take_profit: float = None,
                    rationale: str = None, analysis_id: int = None,
                    expires_at: int = None) -> int:
    """Insert a trade proposal, returns proposal id"""
    cursor = conn.execute("""
        INSERT INTO investment_proposals
            (user_id, proposal_type, symbol, side, account_type, order_type,
             quantity, price, leverage, stop_loss, take_profit, rationale,
             analysis_id, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, proposal_type, symbol, side, account_type, order_type,
          quantity, price, leverage, stop_loss, take_profit, rationale,
          analysis_id, expires_at))
    conn.commit()
    return cursor.lastrowid


def get_proposal(conn: sqlite3.Connection, proposal_id: int) -> Optional[Dict[str, Any]]:
    """Get a proposal by id"""
    row = conn.execute(
        "SELECT * FROM investment_proposals WHERE id = ?", (proposal_id,)
    ).fetchone()
    return dict(row) if row else None


def update_proposal_status(conn: sqlite3.Connection, proposal_id: int,
                           status: str, execution_result: str = None):
    """Update proposal status"""
    now = int(time.time())
    if status == "approved":
        conn.execute(
            "UPDATE investment_proposals SET status = ?, approved_at = ? WHERE id = ?",
            (status, now, proposal_id))
    elif status in ("executed", "failed"):
        conn.execute(
            "UPDATE investment_proposals SET status = ?, executed_at = ?, execution_result_json = ? WHERE id = ?",
            (status, now, execution_result, proposal_id))
    else:
        conn.execute(
            "UPDATE investment_proposals SET status = ? WHERE id = ?",
            (status, proposal_id))
    conn.commit()


# === DCA Schedules ===

def get_active_dca_schedules(conn: sqlite3.Connection, user_id: str = None) -> List[Dict[str, Any]]:
    """Get active DCA schedules"""
    query = "SELECT * FROM investment_dca_schedules WHERE active = 1"
    params: list = []
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def update_dca_executed(conn: sqlite3.Connection, dca_id: int,
                        amount_usd: float, quantity: float):
    """Update DCA schedule after execution"""
    conn.execute("""
        UPDATE investment_dca_schedules SET
            last_executed_at = strftime('%s','now'),
            total_invested = total_invested + ?,
            total_quantity = total_quantity + ?
        WHERE id = ?
    """, (amount_usd, quantity, dca_id))
    conn.commit()
