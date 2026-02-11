"""
Database utilities for Prediction Market skill
Uses shared memory.db (same as other skills)
Tables prefixed with pm_ to avoid collisions
"""

import json
import sqlite3
import time
from typing import Any, Dict, List, Optional

from config import DB_PATH, PROJECT_DATA_DIR


# === Schema ===

SCHEMA_SQL = """
-- Monitored markets
CREATE TABLE IF NOT EXISTS pm_markets (
    id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    slug TEXT,
    outcomes TEXT,
    end_date TEXT,
    tags TEXT,
    active INTEGER DEFAULT 1,
    volume REAL DEFAULT 0,
    liquidity REAL DEFAULT 0,
    created_at INTEGER DEFAULT (strftime('%s','now')),
    updated_at INTEGER DEFAULT (strftime('%s','now'))
);

-- Price snapshots (time series)
CREATE TABLE IF NOT EXISTS pm_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL,
    yes_price REAL,
    no_price REAL,
    volume_24h REAL,
    liquidity REAL,
    recorded_at INTEGER DEFAULT (strftime('%s','now')),
    FOREIGN KEY (market_id) REFERENCES pm_markets(id)
);

-- Position tracking
CREATE TABLE IF NOT EXISTS pm_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'default',
    market_id TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('YES','NO')),
    size REAL NOT NULL,
    entry_price REAL NOT NULL,
    current_price REAL,
    status TEXT DEFAULT 'open' CHECK(status IN ('open','closed','settled')),
    pnl REAL,
    opened_at INTEGER DEFAULT (strftime('%s','now')),
    closed_at INTEGER,
    FOREIGN KEY (market_id) REFERENCES pm_markets(id)
);

-- Trade history
CREATE TABLE IF NOT EXISTS pm_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL,
    side TEXT NOT NULL,
    order_type TEXT,
    price REAL NOT NULL,
    size REAL NOT NULL,
    fee REAL DEFAULT 0,
    order_id TEXT,
    executed_at INTEGER DEFAULT (strftime('%s','now'))
);

CREATE INDEX IF NOT EXISTS idx_pm_prices_market
    ON pm_prices(market_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_pm_positions_status
    ON pm_positions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_pm_trades_market
    ON pm_trades(market_id, executed_at DESC);
"""


# === Connection ===

def get_connection() -> sqlite3.Connection:
    """Get connection to shared memory.db with schema ensured"""
    PROJECT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_SQL)
    return conn


# === Markets ===

def upsert_market(
    conn: sqlite3.Connection,
    market_id: str,
    question: str,
    slug: str = "",
    outcomes: Optional[List[str]] = None,
    end_date: str = "",
    tags: Optional[List[str]] = None,
    active: bool = True,
    volume: float = 0,
    liquidity: float = 0,
) -> None:
    """Insert or update a market"""
    now = int(time.time())
    conn.execute("""
        INSERT INTO pm_markets (id, question, slug, outcomes, end_date, tags, active, volume, liquidity, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            question = excluded.question,
            slug = excluded.slug,
            outcomes = excluded.outcomes,
            end_date = excluded.end_date,
            tags = excluded.tags,
            active = excluded.active,
            volume = excluded.volume,
            liquidity = excluded.liquidity,
            updated_at = excluded.updated_at
    """, (
        market_id,
        question,
        slug,
        json.dumps(outcomes or ["Yes", "No"]),
        end_date,
        json.dumps(tags or []),
        1 if active else 0,
        volume,
        liquidity,
        now,
        now,
    ))
    conn.commit()


def get_market(conn: sqlite3.Connection, market_id: str) -> Optional[Dict]:
    """Get a single market by ID"""
    row = conn.execute("SELECT * FROM pm_markets WHERE id = ?", (market_id,)).fetchone()
    return dict(row) if row else None


def get_watchlist(conn: sqlite3.Connection) -> List[Dict]:
    """Get all active monitored markets"""
    rows = conn.execute(
        "SELECT * FROM pm_markets WHERE active = 1 ORDER BY updated_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def remove_from_watchlist(conn: sqlite3.Connection, market_id: str) -> None:
    """Deactivate a market from watchlist"""
    conn.execute("UPDATE pm_markets SET active = 0 WHERE id = ?", (market_id,))
    conn.commit()


# === Prices ===

def record_price(
    conn: sqlite3.Connection,
    market_id: str,
    yes_price: float,
    no_price: float = 0,
    volume_24h: float = 0,
    liquidity: float = 0,
) -> None:
    """Record a price snapshot"""
    if no_price == 0 and yes_price > 0:
        no_price = round(1.0 - yes_price, 4)

    conn.execute("""
        INSERT INTO pm_prices (market_id, yes_price, no_price, volume_24h, liquidity)
        VALUES (?, ?, ?, ?, ?)
    """, (market_id, yes_price, no_price, volume_24h, liquidity))
    conn.commit()


def get_latest_price(conn: sqlite3.Connection, market_id: str) -> Optional[Dict]:
    """Get most recent price for a market"""
    row = conn.execute(
        "SELECT * FROM pm_prices WHERE market_id = ? ORDER BY recorded_at DESC, id DESC LIMIT 1",
        (market_id,)
    ).fetchone()
    return dict(row) if row else None


def get_price_history(
    conn: sqlite3.Connection,
    market_id: str,
    limit: int = 100,
) -> List[Dict]:
    """Get price history for a market"""
    rows = conn.execute(
        "SELECT * FROM pm_prices WHERE market_id = ? ORDER BY recorded_at DESC, id DESC LIMIT ?",
        (market_id, limit)
    ).fetchall()
    return [dict(r) for r in rows]


# === Positions ===

def upsert_position(
    conn: sqlite3.Connection,
    market_id: str,
    side: str,
    size: float,
    entry_price: float,
    user_id: str = "default",
    current_price: Optional[float] = None,
    status: str = "open",
) -> int:
    """Create or update a position"""
    # Check if open position exists for this market+side
    existing = conn.execute(
        "SELECT id FROM pm_positions WHERE market_id = ? AND side = ? AND user_id = ? AND status = 'open'",
        (market_id, side.upper(), user_id)
    ).fetchone()

    if existing:
        # Update existing position (average in)
        conn.execute("""
            UPDATE pm_positions SET
                size = size + ?,
                entry_price = (entry_price * size + ? * ?) / (size + ?),
                current_price = ?,
                updated_at = strftime('%s','now')
            WHERE id = ?
        """, (size, entry_price, size, size, current_price, existing["id"]))
        conn.commit()
        return existing["id"]
    else:
        cursor = conn.execute("""
            INSERT INTO pm_positions (user_id, market_id, side, size, entry_price, current_price, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, market_id, side.upper(), size, entry_price, current_price, status))
        conn.commit()
        return cursor.lastrowid


def close_position(conn: sqlite3.Connection, position_id: int, exit_price: float) -> None:
    """Close a position and calculate PnL"""
    pos = conn.execute("SELECT * FROM pm_positions WHERE id = ?", (position_id,)).fetchone()
    if not pos:
        return

    # PnL: (exit - entry) * size for YES, (entry - exit) * size for NO
    if pos["side"] == "YES":
        pnl = (exit_price - pos["entry_price"]) * pos["size"]
    else:
        pnl = (pos["entry_price"] - exit_price) * pos["size"]

    now = int(time.time())
    conn.execute("""
        UPDATE pm_positions SET
            status = 'closed',
            current_price = ?,
            pnl = ?,
            closed_at = ?
        WHERE id = ?
    """, (exit_price, round(pnl, 4), now, position_id))
    conn.commit()


def get_positions(
    conn: sqlite3.Connection,
    user_id: str = "default",
    status: str = "open",
) -> List[Dict]:
    """Get positions filtered by status"""
    rows = conn.execute(
        "SELECT * FROM pm_positions WHERE user_id = ? AND status = ? ORDER BY opened_at DESC",
        (user_id, status)
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_positions(conn: sqlite3.Connection, user_id: str = "default") -> List[Dict]:
    """Get all positions regardless of status"""
    rows = conn.execute(
        "SELECT * FROM pm_positions WHERE user_id = ? ORDER BY opened_at DESC",
        (user_id,)
    ).fetchall()
    return [dict(r) for r in rows]


# === Trades ===

def record_trade(
    conn: sqlite3.Connection,
    market_id: str,
    side: str,
    price: float,
    size: float,
    order_type: str = "limit",
    fee: float = 0,
    order_id: str = "",
) -> int:
    """Record a trade execution"""
    cursor = conn.execute("""
        INSERT INTO pm_trades (market_id, side, order_type, price, size, fee, order_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (market_id, side.upper(), order_type, price, size, fee, order_id))
    conn.commit()
    return cursor.lastrowid


def get_trades(
    conn: sqlite3.Connection,
    market_id: Optional[str] = None,
    limit: int = 50,
) -> List[Dict]:
    """Get trade history"""
    if market_id:
        rows = conn.execute(
            "SELECT * FROM pm_trades WHERE market_id = ? ORDER BY executed_at DESC, id DESC LIMIT ?",
            (market_id, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM pm_trades ORDER BY executed_at DESC, id DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# === Stats ===

def get_portfolio_summary(conn: sqlite3.Connection, user_id: str = "default") -> Dict:
    """Get portfolio summary stats"""
    open_positions = get_positions(conn, user_id, "open")
    closed_positions = get_positions(conn, user_id, "closed")

    total_invested = sum(p["entry_price"] * p["size"] for p in open_positions)
    total_pnl = sum(p.get("pnl", 0) or 0 for p in closed_positions)
    win_count = sum(1 for p in closed_positions if (p.get("pnl", 0) or 0) > 0)
    loss_count = sum(1 for p in closed_positions if (p.get("pnl", 0) or 0) < 0)

    return {
        "open_positions": len(open_positions),
        "closed_positions": len(closed_positions),
        "total_invested": round(total_invested, 2),
        "realized_pnl": round(total_pnl, 2),
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": round(win_count / (win_count + loss_count) * 100, 1) if (win_count + loss_count) > 0 else 0,
    }
