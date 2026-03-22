"""SQLite state store — positions, candles, config."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

_db: sqlite3.Connection | None = None
_db_path: Path = Path("data/state.db")
_db_lock = threading.Lock()


def init_db(path: Path | str = "") -> None:
    global _db, _db_path
    if _db is not None:
        _db.close()
    if path:
        _db_path = Path(path)
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    _db = sqlite3.connect(str(_db_path), check_same_thread=False)
    _db.execute("PRAGMA journal_mode=wal")
    _db.executescript("""
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            entry_price REAL NOT NULL,
            qty REAL NOT NULL,
            leverage INTEGER DEFAULT 2,
            status TEXT DEFAULT 'OPEN',
            opened_at TEXT DEFAULT (datetime('now')),
            closed_at TEXT,
            exit_price REAL,
            pnl REAL
        );
        CREATE TABLE IF NOT EXISTS candles (
            symbol TEXT NOT NULL,
            interval TEXT NOT NULL,
            open_time INTEGER NOT NULL,
            open REAL, high REAL, low REAL, close REAL, volume REAL,
            closed INTEGER DEFAULT 1,
            PRIMARY KEY (symbol, interval, open_time)
        );
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        );
    """)
    # Safe migration: add closed column if missing (existing rows default to 1 = closed)
    cols = [row[1] for row in _db.execute("PRAGMA table_info(candles)").fetchall()]
    if "closed" not in cols:
        _db.execute("ALTER TABLE candles ADD COLUMN closed INTEGER DEFAULT 1")
        _db.commit()


def _conn() -> sqlite3.Connection:
    if _db is None:
        init_db()
    assert _db is not None
    return _db


# ── Positions ──

def get_open_position() -> dict | None:
    c = _conn()
    c.row_factory = sqlite3.Row
    row = c.execute("SELECT * FROM positions WHERE status='OPEN' ORDER BY id DESC LIMIT 1").fetchone()
    return dict(row) if row else None


def save_position(symbol: str, side: str, entry_price: float, qty: float, leverage: int = 2) -> int:
    with _db_lock:
        c = _conn()
        # Close any stale OPEN positions before inserting (enforce single OPEN invariant)
        # Mark with pnl=NULL and exit_price=0 to flag as force-closed (auditable)
        stale = c.execute("SELECT id, entry_price FROM positions WHERE status='OPEN'").fetchall()
        if stale:
            for row in stale:
                c.execute(
                    "UPDATE positions SET status='FORCE_CLOSED', closed_at=datetime('now'), exit_price=0, pnl=NULL WHERE id=?",
                    (row[0],),
                )
        cur = c.execute(
            "INSERT INTO positions (symbol, side, entry_price, qty, leverage) VALUES (?,?,?,?,?)",
            (symbol, side, entry_price, qty, leverage),
        )
        c.commit()
        return cur.lastrowid or 0


def close_position(pos_id: int, exit_price: float, pnl: float) -> None:
    with _db_lock:
        c = _conn()
        c.execute(
            "UPDATE positions SET status='CLOSED', closed_at=datetime('now'), exit_price=?, pnl=? WHERE id=? AND status='OPEN'",
            (exit_price, pnl, pos_id),
        )
        c.commit()


# ── Candles ──

def upsert_candle(symbol: str, interval: str, open_time: int, o: float, h: float, l: float, c_: float, vol: float, closed: bool = True) -> None:
    with _db_lock:
        conn = _conn()
        conn.execute(
            """INSERT OR REPLACE INTO candles (symbol, interval, open_time, open, high, low, close, volume, closed)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (symbol, interval, open_time, o, h, l, c_, vol, 1 if closed else 0),
        )
        conn.commit()


def get_candles(symbol: str, interval: str, limit: int = 100, closed_only: bool = False) -> list[dict]:
    conn = _conn()
    conn.row_factory = sqlite3.Row
    if closed_only:
        rows = conn.execute(
            "SELECT * FROM candles WHERE symbol=? AND interval=? AND closed=1 ORDER BY open_time DESC LIMIT ?",
            (symbol, interval, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM candles WHERE symbol=? AND interval=? ORDER BY open_time DESC LIMIT ?",
            (symbol, interval, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


# ── Config ──

def get_config(key: str) -> str | None:
    c = _conn()
    row = c.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def set_config(key: str, value: str) -> None:
    with _db_lock:
        c = _conn()
        c.execute(
            "INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, datetime('now'))",
            (key, value),
        )
        c.commit()
