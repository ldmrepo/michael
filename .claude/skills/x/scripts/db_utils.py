"""
Database Utilities for X/Twitter Skill
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
    """Create social tables if they don't exist"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS social_research (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            category TEXT NOT NULL,
            data_json TEXT NOT NULL,
            collected_at INTEGER DEFAULT (strftime('%s','now'))
        );

        CREATE INDEX IF NOT EXISTS idx_social_research_source
            ON social_research(source, collected_at DESC);
        CREATE INDEX IF NOT EXISTS idx_social_research_category
            ON social_research(category, collected_at DESC);
    """)


def insert_research(conn: sqlite3.Connection, source: str, category: str,
                    data_json: str):
    """Insert social research data"""
    conn.execute("""
        INSERT INTO social_research (source, category, data_json)
        VALUES (?, ?, ?)
    """, (source, category, data_json))
    conn.commit()


def get_latest_research(conn: sqlite3.Connection, category: str = None,
                        hours: int = 24) -> List[Dict[str, Any]]:
    """Get recent social research data"""
    cutoff = int(time.time()) - (hours * 3600)
    query = "SELECT * FROM social_research WHERE collected_at > ?"
    params: list = [cutoff]
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY collected_at DESC"
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def cleanup_old_research(conn: sqlite3.Connection, days: int = 30) -> int:
    """Delete social research data older than specified days. Returns count of deleted rows."""
    cutoff = int(time.time()) - (days * 86400)
    cursor = conn.execute(
        "DELETE FROM social_research WHERE collected_at < ?", (cutoff,)
    )
    conn.commit()
    return cursor.rowcount
