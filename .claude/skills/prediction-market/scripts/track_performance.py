#!/usr/bin/env python3
"""
Portfolio Performance Tracker for Polymarket

Tracks historical performance, calculates return metrics,
and provides attribution analysis.

Usage:
    python track_performance.py --snapshot      # Take daily snapshot
    python track_performance.py --report        # Full performance report
    python track_performance.py --attribution   # Attribution analysis
    python track_performance.py --accuracy      # Recommendation accuracy
    python track_performance.py --brier         # Brier score calibration analysis
    python track_performance.py --feedback      # Prediction accuracy feedback
    python track_performance.py --json          # JSON output for any mode
    python track_performance.py --days 30       # Lookback period (default: all)
"""

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import db_utils
from config import DB_PATH, GAMMA_API_BASE
from output_format import success, error, report, table
from polymarket_client import create_client


# === DB Schema for snapshots ===

SNAPSHOT_SCHEMA = """
CREATE TABLE IF NOT EXISTS pm_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL UNIQUE,
    total_invested REAL DEFAULT 0,
    total_value REAL DEFAULT 0,
    cash_balance REAL DEFAULT 0,
    unrealized_pnl REAL DEFAULT 0,
    realized_pnl REAL DEFAULT 0,
    position_count INTEGER DEFAULT 0,
    deposited_total REAL DEFAULT 0,
    created_at INTEGER DEFAULT (strftime('%s','now'))
);
CREATE INDEX IF NOT EXISTS idx_pm_snapshots_date ON pm_snapshots(snapshot_date DESC);
"""


PREDICTION_OUTCOMES_SCHEMA = """
CREATE TABLE IF NOT EXISTS pm_prediction_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL,
    predicted_prob REAL NOT NULL,
    market_prob REAL NOT NULL,
    actual_outcome INTEGER,
    resolved_at INTEGER,
    created_at INTEGER DEFAULT (strftime('%s','now'))
);
CREATE INDEX IF NOT EXISTS idx_pm_prediction_outcomes_market ON pm_prediction_outcomes(market_id);
"""


def ensure_snapshot_schema(conn):
    """Create pm_snapshots table if not exists"""
    conn.executescript(SNAPSHOT_SCHEMA)


def ensure_prediction_outcomes_schema(conn):
    """Create pm_prediction_outcomes table if not exists"""
    conn.executescript(PREDICTION_OUTCOMES_SCHEMA)


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def get_current_prices_for_positions(client, positions: List[Dict]) -> Dict[str, Dict]:
    """Fetch current Gamma API prices for all markets referenced by positions.

    Returns dict keyed by market_id with {yes_price, no_price, question, tags, end_date}.
    """
    market_cache: Dict[str, Dict] = {}
    for pos in positions:
        mid = pos["market_id"]
        if mid in market_cache:
            continue
        try:
            market = client.get_market(mid)
            outcome_prices = market.get("outcomePrices", "[]")
            if isinstance(outcome_prices, str):
                outcome_prices = json.loads(outcome_prices)
            yes_price = float(outcome_prices[0]) if len(outcome_prices) > 0 else 0.0
            no_price = float(outcome_prices[1]) if len(outcome_prices) > 1 else 1.0 - yes_price

            tags_raw = market.get("tags", [])
            if isinstance(tags_raw, str):
                try:
                    tags_raw = json.loads(tags_raw)
                except Exception:
                    tags_raw = []

            market_cache[mid] = {
                "yes_price": yes_price,
                "no_price": no_price,
                "question": market.get("question", ""),
                "tags": tags_raw,
                "end_date": market.get("endDate", ""),
            }
            time.sleep(0.3)
        except Exception as e:
            market_cache[mid] = {
                "yes_price": 0.0,
                "no_price": 0.0,
                "question": "",
                "tags": [],
                "end_date": "",
                "error": str(e),
            }
    return market_cache


def position_current_price(pos: Dict, market_info: Dict) -> float:
    """Get current price for a position based on its side."""
    if pos["side"] == "YES":
        return market_info.get("yes_price", 0.0)
    else:
        return market_info.get("no_price", 0.0)


def position_unrealized_pnl(pos: Dict, current_price: float) -> float:
    """Calculate unrealized PnL for an open position."""
    return (current_price - pos["entry_price"]) * pos["size"]


def position_cost(pos: Dict) -> float:
    """Total cost basis for a position."""
    return pos["entry_price"] * pos["size"]


def position_value(pos: Dict, current_price: float) -> float:
    """Current market value for a position."""
    return current_price * pos["size"]


# ─────────────────────────────────────────────
#  Mode 1: Daily Snapshot
# ─────────────────────────────────────────────

def take_snapshot(conn, client, json_output: bool = False):
    """Take a daily portfolio snapshot and save to DB."""
    ensure_snapshot_schema(conn)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Get open positions
    open_positions = db_utils.get_positions(conn, status="open")
    closed_positions = db_utils.get_positions(conn, status="closed")

    # Fetch current market prices
    market_cache = {}
    if open_positions:
        market_cache = get_current_prices_for_positions(client, open_positions)

    # Calculate metrics
    total_invested = sum(position_cost(p) for p in open_positions)
    total_value = 0.0
    unrealized_pnl = 0.0

    for pos in open_positions:
        info = market_cache.get(pos["market_id"], {})
        cp = position_current_price(pos, info)
        val = position_value(pos, cp)
        total_value += val
        unrealized_pnl += position_unrealized_pnl(pos, cp)

    realized_pnl = sum(p.get("pnl", 0) or 0 for p in closed_positions)
    cash_balance = client.get_balance_usdc()
    position_count = len(open_positions)

    # Estimate deposited total from existing snapshots or sum of invested + cash + realized withdrawals
    prev = conn.execute(
        "SELECT deposited_total FROM pm_snapshots ORDER BY snapshot_date DESC LIMIT 1"
    ).fetchone()
    deposited_total = prev["deposited_total"] if prev else (total_invested + cash_balance)

    # Upsert snapshot
    conn.execute("""
        INSERT INTO pm_snapshots (snapshot_date, total_invested, total_value, cash_balance,
            unrealized_pnl, realized_pnl, position_count, deposited_total)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(snapshot_date) DO UPDATE SET
            total_invested = excluded.total_invested,
            total_value = excluded.total_value,
            cash_balance = excluded.cash_balance,
            unrealized_pnl = excluded.unrealized_pnl,
            realized_pnl = excluded.realized_pnl,
            position_count = excluded.position_count,
            deposited_total = excluded.deposited_total,
            created_at = strftime('%s','now')
    """, (today, round(total_invested, 2), round(total_value, 2),
          round(cash_balance, 2), round(unrealized_pnl, 2),
          round(realized_pnl, 2), position_count, round(deposited_total, 2)))
    conn.commit()

    # Compare with previous snapshot
    prev_snap = conn.execute(
        "SELECT * FROM pm_snapshots WHERE snapshot_date < ? ORDER BY snapshot_date DESC LIMIT 1",
        (today,)
    ).fetchone()

    nav = total_value + cash_balance
    daily_change = 0.0
    daily_change_pct = 0.0
    if prev_snap:
        prev_nav = prev_snap["total_value"] + prev_snap["cash_balance"]
        daily_change = nav - prev_nav
        daily_change_pct = (daily_change / prev_nav * 100) if prev_nav > 0 else 0.0

    snapshot_data = {
        "date": today,
        "nav": round(nav, 2),
        "total_invested": round(total_invested, 2),
        "total_value": round(total_value, 2),
        "cash_balance": round(cash_balance, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "realized_pnl": round(realized_pnl, 2),
        "position_count": position_count,
        "daily_change": round(daily_change, 2),
        "daily_change_pct": round(daily_change_pct, 2),
    }

    if json_output:
        success(snapshot_data, "Snapshot saved")
    else:
        lines = [
            f"Portfolio Snapshot - {today}",
            "=" * 50,
            f"NAV (Net Asset Value):  ${nav:.2f}",
            f"  Positions Value:      ${total_value:.2f}",
            f"  Cash Balance:         ${cash_balance:.2f}",
            f"  Invested (cost):      ${total_invested:.2f}",
            f"  Unrealized P&L:       ${unrealized_pnl:+.2f}",
            f"  Realized P&L:         ${realized_pnl:+.2f}",
            f"  Open Positions:       {position_count}",
            "",
        ]
        if prev_snap:
            sign = "+" if daily_change >= 0 else ""
            lines.append(f"Daily Change:           {sign}${daily_change:.2f} ({sign}{daily_change_pct:.1f}%)")
        else:
            lines.append("Daily Change:           N/A (first snapshot)")

        report("\n".join(lines), snapshot_data)


# ─────────────────────────────────────────────
#  Mode 2: Performance Report
# ─────────────────────────────────────────────

def compute_max_drawdown(snapshots: List[Dict]) -> Tuple[float, float]:
    """Compute max drawdown and current drawdown from chronological snapshots.

    Returns (max_drawdown_pct, current_drawdown_pct).
    """
    if not snapshots:
        return 0.0, 0.0

    peak = 0.0
    max_dd = 0.0
    current_dd = 0.0

    for snap in snapshots:
        nav = snap["total_value"] + snap["cash_balance"]
        if nav > peak:
            peak = nav
        if peak > 0:
            dd = (peak - nav) / peak * 100
            max_dd = max(max_dd, dd)

    # Current drawdown
    if snapshots and peak > 0:
        last_nav = snapshots[-1]["total_value"] + snapshots[-1]["cash_balance"]
        current_dd = (peak - last_nav) / peak * 100

    return round(max_dd, 2), round(current_dd, 2)


def compute_sharpe_like(snapshots: List[Dict]) -> float:
    """Compute Sharpe-like ratio from daily NAV changes.

    Sharpe = mean(daily_return) / std(daily_return)
    """
    if len(snapshots) < 2:
        return 0.0

    daily_returns = []
    for i in range(1, len(snapshots)):
        prev_nav = snapshots[i - 1]["total_value"] + snapshots[i - 1]["cash_balance"]
        curr_nav = snapshots[i]["total_value"] + snapshots[i]["cash_balance"]
        if prev_nav > 0:
            daily_returns.append((curr_nav - prev_nav) / prev_nav)

    if not daily_returns:
        return 0.0

    mean_ret = sum(daily_returns) / len(daily_returns)
    if len(daily_returns) < 2:
        return 0.0

    variance = sum((r - mean_ret) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
    std_ret = math.sqrt(variance) if variance > 0 else 0.0

    return round(mean_ret / std_ret, 2) if std_ret > 0 else 0.0


def performance_report(conn, client, days: Optional[int] = None, json_output: bool = False):
    """Generate full performance report."""
    ensure_snapshot_schema(conn)

    # Gather positions
    open_positions = db_utils.get_positions(conn, status="open")
    closed_positions = db_utils.get_positions(conn, status="closed")
    all_positions = db_utils.get_all_positions(conn)

    # Fetch current prices for open positions
    market_cache = {}
    if open_positions:
        market_cache = get_current_prices_for_positions(client, open_positions)

    # Current portfolio value
    total_invested = sum(position_cost(p) for p in open_positions)
    total_value = 0.0
    unrealized_pnl = 0.0
    for pos in open_positions:
        info = market_cache.get(pos["market_id"], {})
        cp = position_current_price(pos, info)
        total_value += position_value(pos, cp)
        unrealized_pnl += position_unrealized_pnl(pos, cp)

    cash_balance = client.get_balance_usdc()
    nav = total_value + cash_balance
    realized_pnl = sum(p.get("pnl", 0) or 0 for p in closed_positions)

    # Deposited total from snapshots
    snap_row = conn.execute(
        "SELECT deposited_total FROM pm_snapshots ORDER BY snapshot_date DESC LIMIT 1"
    ).fetchone()
    deposited_total = snap_row["deposited_total"] if snap_row else (total_invested + cash_balance)

    # Total return
    total_return_pct = ((nav + realized_pnl - deposited_total) / deposited_total * 100) if deposited_total > 0 else 0.0

    # Win/Loss stats from closed positions
    wins = [p for p in closed_positions if (p.get("pnl", 0) or 0) > 0]
    losses = [p for p in closed_positions if (p.get("pnl", 0) or 0) < 0]
    breakeven = [p for p in closed_positions if (p.get("pnl", 0) or 0) == 0]

    win_count = len(wins)
    loss_count = len(losses)
    total_closed = win_count + loss_count
    win_rate = (win_count / total_closed * 100) if total_closed > 0 else 0.0

    avg_win = (sum(p["pnl"] for p in wins) / win_count) if win_count > 0 else 0.0
    avg_loss = (sum(p["pnl"] for p in losses) / loss_count) if loss_count > 0 else 0.0

    total_win_pnl = sum(p["pnl"] for p in wins) if wins else 0.0
    total_loss_pnl = abs(sum(p["pnl"] for p in losses)) if losses else 0.0
    profit_factor = (total_win_pnl / total_loss_pnl) if total_loss_pnl > 0 else float("inf") if total_win_pnl > 0 else 0.0

    # Best/Worst trade
    all_pnls = [(p.get("pnl", 0) or 0) for p in closed_positions]
    best_trade = max(all_pnls) if all_pnls else 0.0
    worst_trade = min(all_pnls) if all_pnls else 0.0

    # Average hold period (days)
    hold_periods = []
    for p in closed_positions:
        if p.get("opened_at") and p.get("closed_at"):
            hold_days = (p["closed_at"] - p["opened_at"]) / 86400
            hold_periods.append(hold_days)
    avg_hold_period = (sum(hold_periods) / len(hold_periods)) if hold_periods else 0.0

    # Snapshots for Sharpe and Drawdown
    query = "SELECT * FROM pm_snapshots ORDER BY snapshot_date ASC"
    params: List[Any] = []
    if days:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        query = "SELECT * FROM pm_snapshots WHERE snapshot_date >= ? ORDER BY snapshot_date ASC"
        params = [cutoff]

    snapshots = [dict(r) for r in conn.execute(query, params).fetchall()]
    sharpe = compute_sharpe_like(snapshots)
    max_dd, current_dd = compute_max_drawdown(snapshots)

    metrics = {
        "nav": round(nav, 2),
        "deposited_total": round(deposited_total, 2),
        "total_invested": round(total_invested, 2),
        "total_value": round(total_value, 2),
        "cash_balance": round(cash_balance, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "realized_pnl": round(realized_pnl, 2),
        "total_return_pct": round(total_return_pct, 2),
        "open_positions": len(open_positions),
        "closed_positions": len(closed_positions),
        "win_count": win_count,
        "loss_count": loss_count,
        "breakeven_count": len(breakeven),
        "win_rate_pct": round(win_rate, 1),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "inf",
        "best_trade": round(best_trade, 2),
        "worst_trade": round(worst_trade, 2),
        "avg_hold_period_days": round(avg_hold_period, 1),
        "sharpe_like_ratio": sharpe,
        "max_drawdown_pct": max_dd,
        "current_drawdown_pct": current_dd,
        "snapshot_count": len(snapshots),
    }

    if json_output:
        success(metrics, "Performance report")
        return

    pf_display = f"{profit_factor:.2f}" if profit_factor != float("inf") else "inf"

    lines = [
        "PORTFOLIO PERFORMANCE REPORT",
        "=" * 60,
        "",
        "--- Portfolio Overview ---",
        f"  NAV:                  ${nav:.2f}",
        f"  Deposited:            ${deposited_total:.2f}",
        f"  Positions Value:      ${total_value:.2f}",
        f"  Cash Balance:         ${cash_balance:.2f}",
        f"  Total Return:         {total_return_pct:+.2f}%",
        "",
        "--- P&L ---",
        f"  Unrealized P&L:       ${unrealized_pnl:+.2f}",
        f"  Realized P&L:         ${realized_pnl:+.2f}",
        f"  Combined P&L:         ${unrealized_pnl + realized_pnl:+.2f}",
        "",
        "--- Trade Statistics ---",
        f"  Open Positions:       {len(open_positions)}",
        f"  Closed Positions:     {len(closed_positions)}",
        f"  Win Rate:             {win_rate:.1f}% ({win_count}W / {loss_count}L)",
        f"  Avg Win:              ${avg_win:+.2f}",
        f"  Avg Loss:             ${avg_loss:+.2f}",
        f"  Profit Factor:        {pf_display}",
        f"  Best Trade:           ${best_trade:+.2f}",
        f"  Worst Trade:          ${worst_trade:+.2f}",
        f"  Avg Hold Period:      {avg_hold_period:.1f} days",
        "",
        "--- Risk Metrics ---",
        f"  Sharpe-like Ratio:    {sharpe:.2f}" + (" (need more snapshots)" if len(snapshots) < 5 else ""),
        f"  Max Drawdown:         {max_dd:.2f}%" + (" (need more snapshots)" if len(snapshots) < 2 else ""),
        f"  Current Drawdown:     {current_dd:.2f}%",
        f"  Snapshots Available:  {len(snapshots)}",
    ]

    report("\n".join(lines), metrics)


# ─────────────────────────────────────────────
#  Mode 3: Attribution Analysis
# ─────────────────────────────────────────────

def attribution_analysis(conn, client, days: Optional[int] = None, json_output: bool = False):
    """Break down returns by category, direction, size, hold period."""
    ensure_snapshot_schema(conn)

    all_positions = db_utils.get_all_positions(conn)
    if not all_positions:
        if json_output:
            success({"message": "No positions found"}, "No data")
        else:
            report("No positions found for attribution analysis.")
        return

    # Fetch market info for all positions
    market_cache = get_current_prices_for_positions(client, all_positions)

    # Build enriched position list with PnL
    enriched = []
    for pos in all_positions:
        info = market_cache.get(pos["market_id"], {})
        cost = position_cost(pos)

        if pos["status"] == "closed":
            pnl = pos.get("pnl", 0) or 0
        else:
            cp = position_current_price(pos, info)
            pnl = position_unrealized_pnl(pos, cp)

        hold_days = 0
        if pos.get("opened_at"):
            end_ts = pos.get("closed_at") or int(time.time())
            hold_days = (end_ts - pos["opened_at"]) / 86400

        # Filter by days if specified
        if days and pos.get("opened_at"):
            cutoff_ts = int(time.time()) - days * 86400
            if pos["opened_at"] < cutoff_ts and pos["status"] != "open":
                continue

        tags = info.get("tags", [])
        category = tags[0] if tags else "uncategorized"

        enriched.append({
            "market_id": pos["market_id"],
            "question": info.get("question", "")[:60],
            "side": pos["side"],
            "cost": cost,
            "pnl": pnl,
            "status": pos["status"],
            "hold_days": hold_days,
            "category": category,
            "tags": tags,
        })

    if not enriched:
        if json_output:
            success({"message": "No positions in lookback period"}, "No data")
        else:
            report("No positions found in the specified lookback period.")
        return

    # --- By Category ---
    by_category: Dict[str, Dict] = {}
    for p in enriched:
        cat = p["category"]
        if cat not in by_category:
            by_category[cat] = {"count": 0, "total_pnl": 0.0, "total_cost": 0.0}
        by_category[cat]["count"] += 1
        by_category[cat]["total_pnl"] += p["pnl"]
        by_category[cat]["total_cost"] += p["cost"]

    # --- By Direction (YES/NO) ---
    by_direction: Dict[str, Dict] = {"YES": {"count": 0, "total_pnl": 0.0, "total_cost": 0.0},
                                     "NO": {"count": 0, "total_pnl": 0.0, "total_cost": 0.0}}
    for p in enriched:
        d = p["side"]
        by_direction[d]["count"] += 1
        by_direction[d]["total_pnl"] += p["pnl"]
        by_direction[d]["total_cost"] += p["cost"]

    # --- By Position Size ---
    size_buckets = {"Small (<$20)": {"count": 0, "total_pnl": 0.0},
                    "Medium ($20-50)": {"count": 0, "total_pnl": 0.0},
                    "Large (>$50)": {"count": 0, "total_pnl": 0.0}}
    for p in enriched:
        if p["cost"] < 20:
            bucket = "Small (<$20)"
        elif p["cost"] <= 50:
            bucket = "Medium ($20-50)"
        else:
            bucket = "Large (>$50)"
        size_buckets[bucket]["count"] += 1
        size_buckets[bucket]["total_pnl"] += p["pnl"]

    # --- By Hold Period ---
    hold_buckets = {"Short (<3d)": {"count": 0, "total_pnl": 0.0},
                    "Medium (3-14d)": {"count": 0, "total_pnl": 0.0},
                    "Long (>14d)": {"count": 0, "total_pnl": 0.0}}
    for p in enriched:
        if p["hold_days"] < 3:
            bucket = "Short (<3d)"
        elif p["hold_days"] <= 14:
            bucket = "Medium (3-14d)"
        else:
            bucket = "Long (>14d)"
        hold_buckets[bucket]["count"] += 1
        hold_buckets[bucket]["total_pnl"] += p["pnl"]

    # --- Monthly Timeline ---
    monthly: Dict[str, Dict] = {}
    for p in enriched:
        # Use the position's open date for monthly grouping
        pos_match = [x for x in all_positions if x["market_id"] == p["market_id"] and x["side"] == p["side"]]
        if pos_match and pos_match[0].get("opened_at"):
            month_key = datetime.fromtimestamp(pos_match[0]["opened_at"], tz=timezone.utc).strftime("%Y-%m")
        else:
            month_key = "unknown"
        if month_key not in monthly:
            monthly[month_key] = {"count": 0, "total_pnl": 0.0, "total_cost": 0.0}
        monthly[month_key]["count"] += 1
        monthly[month_key]["total_pnl"] += p["pnl"]
        monthly[month_key]["total_cost"] += p["cost"]

    attribution_data = {
        "by_category": {k: {"count": v["count"], "pnl": round(v["total_pnl"], 2),
                            "roi_pct": round(v["total_pnl"] / v["total_cost"] * 100, 1) if v["total_cost"] > 0 else 0}
                        for k, v in sorted(by_category.items(), key=lambda x: x[1]["total_pnl"], reverse=True)},
        "by_direction": {k: {"count": v["count"], "pnl": round(v["total_pnl"], 2),
                             "roi_pct": round(v["total_pnl"] / v["total_cost"] * 100, 1) if v["total_cost"] > 0 else 0}
                         for k, v in by_direction.items()},
        "by_size": {k: {"count": v["count"], "pnl": round(v["total_pnl"], 2)} for k, v in size_buckets.items()},
        "by_hold_period": {k: {"count": v["count"], "pnl": round(v["total_pnl"], 2)} for k, v in hold_buckets.items()},
        "monthly": {k: {"count": v["count"], "pnl": round(v["total_pnl"], 2),
                         "invested": round(v["total_cost"], 2)}
                    for k, v in sorted(monthly.items())},
        "total_positions": len(enriched),
    }

    if json_output:
        success(attribution_data, "Attribution analysis")
        return

    lines = [
        "ATTRIBUTION ANALYSIS",
        "=" * 60,
        "",
    ]

    # Category table
    cat_rows = [[cat, d["count"], f"${d['pnl']:+.2f}", f"{d['roi_pct']:+.1f}%"]
                for cat, d in attribution_data["by_category"].items()]
    lines.append(table(["Category", "Count", "P&L", "ROI%"], cat_rows, "By Category"))
    lines.append("")

    # Direction table
    dir_rows = [[d, attribution_data["by_direction"][d]["count"],
                  f"${attribution_data['by_direction'][d]['pnl']:+.2f}",
                  f"{attribution_data['by_direction'][d]['roi_pct']:+.1f}%"]
                 for d in ["YES", "NO"]]
    lines.append(table(["Direction", "Count", "P&L", "ROI%"], dir_rows, "By Direction (YES vs NO)"))
    lines.append("")

    # Size table
    size_rows = [[sz, attribution_data["by_size"][sz]["count"],
                   f"${attribution_data['by_size'][sz]['pnl']:+.2f}"]
                  for sz in size_buckets.keys()]
    lines.append(table(["Size Bucket", "Count", "P&L"], size_rows, "By Position Size"))
    lines.append("")

    # Hold period table
    hold_rows = [[hp, attribution_data["by_hold_period"][hp]["count"],
                   f"${attribution_data['by_hold_period'][hp]['pnl']:+.2f}"]
                  for hp in hold_buckets.keys()]
    lines.append(table(["Hold Period", "Count", "P&L"], hold_rows, "By Hold Period"))
    lines.append("")

    # Monthly timeline
    month_rows = [[m, d["count"], f"${d['invested']:.2f}", f"${d['pnl']:+.2f}"]
                  for m, d in attribution_data["monthly"].items()]
    lines.append(table(["Month", "Trades", "Invested", "P&L"], month_rows, "Monthly Timeline"))

    report("\n".join(lines), attribution_data)


# ─────────────────────────────────────────────
#  Mode 4: Recommendation Accuracy
# ─────────────────────────────────────────────

def recommendation_accuracy(conn, client, days: Optional[int] = None, json_output: bool = False):
    """Track how past rebalancing recommendations performed."""
    ensure_snapshot_schema(conn)

    # Check if pm_rebalances table exists
    table_check = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='pm_rebalances'"
    ).fetchone()

    if not table_check:
        msg = "No pm_rebalances table found. Run rebalance analysis first to generate recommendations."
        if json_output:
            success({"message": msg, "recommendations": []}, msg)
        else:
            report(msg)
        return

    # Load recommendations
    query = "SELECT * FROM pm_rebalances ORDER BY created_at DESC"
    params: List[Any] = []
    if days:
        cutoff_ts = int(time.time()) - days * 86400
        query = "SELECT * FROM pm_rebalances WHERE created_at >= ? ORDER BY created_at DESC"
        params = [cutoff_ts]

    rows = [dict(r) for r in conn.execute(query, params).fetchall()]

    if not rows:
        msg = "No recommendations found in the specified period."
        if json_output:
            success({"message": msg, "recommendations": []}, msg)
        else:
            report(msg)
        return

    # Analyze each recommendation's outcome
    results = []
    exit_recs = []
    hold_recs = []

    for rec in rows:
        market_id = rec.get("market_id", "")
        action = rec.get("action", "").lower()
        rec_ts = rec.get("created_at", 0)

        # Find matching position
        pos_rows = conn.execute(
            "SELECT * FROM pm_positions WHERE market_id = ? ORDER BY opened_at DESC LIMIT 1",
            (market_id,)
        ).fetchall()
        pos = dict(pos_rows[0]) if pos_rows else None

        if not pos:
            results.append({
                "market_id": market_id,
                "action": action,
                "outcome": "no_position",
                "pnl": 0,
            })
            continue

        actual_pnl = pos.get("pnl", 0) or 0

        if pos["status"] == "open":
            # Still open — get current unrealized PnL
            try:
                market = client.get_market(market_id)
                outcome_prices = market.get("outcomePrices", "[]")
                if isinstance(outcome_prices, str):
                    outcome_prices = json.loads(outcome_prices)
                if pos["side"] == "YES":
                    cp = float(outcome_prices[0]) if outcome_prices else 0
                else:
                    cp = float(outcome_prices[1]) if len(outcome_prices) > 1 else 0
                actual_pnl = (cp - pos["entry_price"]) * pos["size"]
                time.sleep(0.3)
            except Exception:
                pass

        result_entry = {
            "market_id": market_id,
            "action": action,
            "status": pos["status"],
            "pnl": round(actual_pnl, 2),
        }
        results.append(result_entry)

        if "exit" in action or "sell" in action or "close" in action:
            exit_recs.append(result_entry)
        elif "hold" in action or "keep" in action:
            hold_recs.append(result_entry)

    # Calculate accuracy metrics
    total_recs = len(results)
    recs_with_pnl = [r for r in results if r.get("pnl", 0) != 0 or r["status"] == "closed"]

    # For exits: if recommended exit and position lost value after, that's correct
    # Simplified: if recommended exit and final PnL was negative, recommendation was good
    correct_exits = sum(1 for r in exit_recs if r["pnl"] <= 0)
    correct_holds = sum(1 for r in hold_recs if r["pnl"] > 0)

    total_evaluated = len(exit_recs) + len(hold_recs)
    total_correct = correct_exits + correct_holds
    accuracy = (total_correct / total_evaluated * 100) if total_evaluated > 0 else 0

    avg_exit_pnl = (sum(r["pnl"] for r in exit_recs) / len(exit_recs)) if exit_recs else 0
    avg_hold_pnl = (sum(r["pnl"] for r in hold_recs) / len(hold_recs)) if hold_recs else 0

    accuracy_data = {
        "total_recommendations": total_recs,
        "evaluated": total_evaluated,
        "accuracy_pct": round(accuracy, 1),
        "exit_recommendations": len(exit_recs),
        "correct_exits": correct_exits,
        "avg_pnl_on_exits": round(avg_exit_pnl, 2),
        "hold_recommendations": len(hold_recs),
        "correct_holds": correct_holds,
        "avg_pnl_on_holds": round(avg_hold_pnl, 2),
        "details": results,
    }

    if json_output:
        success(accuracy_data, "Recommendation accuracy")
        return

    lines = [
        "RECOMMENDATION ACCURACY",
        "=" * 60,
        "",
        f"Total Recommendations:   {total_recs}",
        f"Evaluated:               {total_evaluated}",
        f"Accuracy:                {accuracy:.1f}%",
        "",
        f"Exit Recommendations:    {len(exit_recs)} (correct: {correct_exits})",
        f"  Avg P&L on exits:      ${avg_exit_pnl:+.2f}",
        f"Hold Recommendations:    {len(hold_recs)} (correct: {correct_holds})",
        f"  Avg P&L on holds:      ${avg_hold_pnl:+.2f}",
    ]

    if results:
        lines.append("")
        detail_rows = [[r["market_id"][:20], r["action"], r["status"],
                         f"${r['pnl']:+.2f}"] for r in results[:20]]
        lines.append(table(["Market", "Action", "Status", "P&L"], detail_rows, "Recent Recommendations"))

    report("\n".join(lines), accuracy_data)


# ─────────────────────────────────────────────
#  Mode 5: Brier Score Analysis
# ─────────────────────────────────────────────

def brier_score_analysis(conn, client, days: Optional[int] = None, json_output: bool = False):
    """Calculate Brier score for probability estimates vs outcomes."""
    ensure_prediction_outcomes_schema(conn)

    # Check for pm_probability_estimates table (created by estimate_true_probability.py)
    has_estimates = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='pm_probability_estimates'"
    ).fetchone()

    if not has_estimates:
        msg = "No pm_probability_estimates table found. Run estimate_true_probability.py first."
        if json_output:
            success({"message": msg}, msg)
        else:
            report(msg)
        return

    # Load estimates with optional time filter
    query = "SELECT * FROM pm_probability_estimates ORDER BY created_at DESC"
    params: List[Any] = []
    if days:
        cutoff_ts = int(time.time()) - days * 86400
        query = "SELECT * FROM pm_probability_estimates WHERE created_at >= ? ORDER BY created_at DESC"
        params = [cutoff_ts]

    estimates = [dict(r) for r in conn.execute(query, params).fetchall()]

    if not estimates:
        msg = "No probability estimates found in the specified period."
        if json_output:
            success({"message": msg, "brier_score": None}, msg)
        else:
            report(msg)
        return

    # Deduplicate: keep latest estimate per market_id
    latest_by_market: Dict[str, Dict] = {}
    for est in estimates:
        mid = est.get("market_id", "")
        if mid not in latest_by_market:
            latest_by_market[mid] = est

    # Check each market for resolution status
    resolved_entries = []
    unresolved_count = 0

    for mid, est in latest_by_market.items():
        # Check if we already have an outcome recorded
        outcome_row = conn.execute(
            "SELECT * FROM pm_prediction_outcomes WHERE market_id = ? ORDER BY created_at DESC LIMIT 1",
            (mid,)
        ).fetchone()

        if outcome_row and outcome_row["actual_outcome"] is not None:
            resolved_entries.append(dict(outcome_row))
            continue

        # Check Gamma API for resolution
        try:
            market = client.get_market(mid)
            is_closed = market.get("closed", False)
            resolved_raw = market.get("resolved", False)

            if is_closed or resolved_raw:
                # Determine actual outcome: YES=1, NO=0
                outcome_prices = market.get("outcomePrices", "[]")
                if isinstance(outcome_prices, str):
                    outcome_prices = json.loads(outcome_prices)

                yes_final = float(outcome_prices[0]) if len(outcome_prices) > 0 else 0
                actual_outcome = 1 if yes_final > 0.5 else 0

                predicted_prob = float(est.get("estimated_prob", est.get("predicted_prob", 0)))
                market_prob = float(est.get("market_prob", est.get("market_price", 0)))

                # Save to outcomes table
                conn.execute("""
                    INSERT INTO pm_prediction_outcomes (market_id, predicted_prob, market_prob, actual_outcome, resolved_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (mid, predicted_prob, market_prob, actual_outcome, int(time.time())))
                conn.commit()

                resolved_entries.append({
                    "market_id": mid,
                    "predicted_prob": predicted_prob,
                    "market_prob": market_prob,
                    "actual_outcome": actual_outcome,
                })
            else:
                unresolved_count += 1
            time.sleep(0.3)
        except Exception:
            unresolved_count += 1

    if not resolved_entries:
        msg = f"No resolved markets found. {unresolved_count} markets still unresolved."
        if json_output:
            success({"message": msg, "unresolved": unresolved_count}, msg)
        else:
            report(msg)
        return

    # Calculate Brier scores
    our_brier_sum = 0.0
    market_brier_sum = 0.0
    n = len(resolved_entries)

    # Calibration buckets (0-10%, 10-20%, ..., 90-100%)
    calibration: Dict[str, Dict] = {}
    for i in range(10):
        low = i * 10
        high = (i + 1) * 10
        calibration[f"{low}-{high}%"] = {"count": 0, "predicted_sum": 0.0, "actual_sum": 0.0}

    for entry in resolved_entries:
        predicted = entry["predicted_prob"]
        market = entry["market_prob"]
        actual = entry["actual_outcome"]

        our_brier_sum += (predicted - actual) ** 2
        market_brier_sum += (market - actual) ** 2

        # Calibration bucket
        bucket_idx = min(int(predicted * 10), 9)
        low = bucket_idx * 10
        high = (bucket_idx + 1) * 10
        bucket_key = f"{low}-{high}%"
        calibration[bucket_key]["count"] += 1
        calibration[bucket_key]["predicted_sum"] += predicted
        calibration[bucket_key]["actual_sum"] += actual

    our_brier = round(our_brier_sum / n, 4)
    market_brier = round(market_brier_sum / n, 4)
    brier_advantage = round(market_brier - our_brier, 4)

    # Calibration averages
    calibration_data = {}
    for bucket, data in calibration.items():
        if data["count"] > 0:
            calibration_data[bucket] = {
                "count": data["count"],
                "avg_predicted": round(data["predicted_sum"] / data["count"], 3),
                "avg_actual": round(data["actual_sum"] / data["count"], 3),
            }

    brier_data = {
        "resolved_markets": n,
        "unresolved_markets": unresolved_count,
        "our_brier_score": our_brier,
        "market_brier_score": market_brier,
        "brier_advantage": brier_advantage,
        "interpretation": "Our estimates are better" if brier_advantage > 0 else "Market estimates are better",
        "calibration": calibration_data,
    }

    if json_output:
        success(brier_data, "Brier score analysis")
        return

    lines = [
        "BRIER SCORE CALIBRATION ANALYSIS",
        "=" * 60,
        "",
        f"Resolved Markets:      {n}",
        f"Unresolved Markets:    {unresolved_count}",
        "",
        "--- Brier Scores (lower is better) ---",
        f"  Our Brier Score:     {our_brier:.4f}" + (" (good)" if our_brier < 0.15 else " (needs improvement)" if our_brier > 0.25 else ""),
        f"  Market Brier Score:  {market_brier:.4f}",
        f"  Advantage:           {brier_advantage:+.4f}" + (" (we're better!)" if brier_advantage > 0 else " (market is better)"),
        "",
        "Reference: 0.0 = perfect, 0.25 = random guessing",
        "",
    ]

    # Calibration table
    if calibration_data:
        cal_rows = [
            [bucket, d["count"], f"{d['avg_predicted']:.3f}", f"{d['avg_actual']:.3f}"]
            for bucket, d in calibration_data.items()
        ]
        lines.append(table(["Bucket", "Count", "Avg Predicted", "Avg Actual"], cal_rows, "Calibration"))

    report("\n".join(lines), brier_data)


# ─────────────────────────────────────────────
#  Mode 6: Prediction Feedback
# ─────────────────────────────────────────────

def prediction_feedback(conn, client, days: Optional[int] = None, json_output: bool = False):
    """Review how past probability estimates compared to actual outcomes."""
    ensure_prediction_outcomes_schema(conn)

    # Check for pm_probability_estimates table
    has_estimates = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='pm_probability_estimates'"
    ).fetchone()

    if not has_estimates:
        msg = "No pm_probability_estimates table found. Run estimate_true_probability.py first."
        if json_output:
            success({"message": msg}, msg)
        else:
            report(msg)
        return

    # Load estimates with optional time filter
    query = "SELECT * FROM pm_probability_estimates ORDER BY created_at DESC"
    params: List[Any] = []
    if days:
        cutoff_ts = int(time.time()) - days * 86400
        query = "SELECT * FROM pm_probability_estimates WHERE created_at >= ? ORDER BY created_at DESC"
        params = [cutoff_ts]

    estimates = [dict(r) for r in conn.execute(query, params).fetchall()]
    if not estimates:
        msg = "No probability estimates found."
        if json_output:
            success({"message": msg}, msg)
        else:
            report(msg)
        return

    # Deduplicate: keep latest estimate per market_id
    latest_by_market: Dict[str, Dict] = {}
    for est in estimates:
        mid = est.get("market_id", "")
        if mid not in latest_by_market:
            latest_by_market[mid] = est

    # Load resolved outcomes (populate from brier_score_analysis first if needed)
    outcomes = [dict(r) for r in conn.execute(
        "SELECT * FROM pm_prediction_outcomes WHERE actual_outcome IS NOT NULL"
    ).fetchall()]

    outcome_by_market = {o["market_id"]: o for o in outcomes}

    # Also check Gamma API for newly resolved markets
    for mid, est in latest_by_market.items():
        if mid in outcome_by_market:
            continue
        try:
            market = client.get_market(mid)
            is_closed = market.get("closed", False)
            resolved_raw = market.get("resolved", False)

            if is_closed or resolved_raw:
                outcome_prices = market.get("outcomePrices", "[]")
                if isinstance(outcome_prices, str):
                    outcome_prices = json.loads(outcome_prices)
                yes_final = float(outcome_prices[0]) if len(outcome_prices) > 0 else 0
                actual_outcome = 1 if yes_final > 0.5 else 0

                predicted_prob = float(est.get("estimated_prob", est.get("predicted_prob", 0)))
                market_prob = float(est.get("market_prob", est.get("market_price", 0)))

                conn.execute("""
                    INSERT OR IGNORE INTO pm_prediction_outcomes (market_id, predicted_prob, market_prob, actual_outcome, resolved_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (mid, predicted_prob, market_prob, actual_outcome, int(time.time())))
                conn.commit()

                outcome_by_market[mid] = {
                    "market_id": mid,
                    "predicted_prob": predicted_prob,
                    "market_prob": market_prob,
                    "actual_outcome": actual_outcome,
                }
            time.sleep(0.3)
        except Exception:
            pass

    # Match estimates with outcomes
    resolved_pairs = []
    for mid, est in latest_by_market.items():
        if mid not in outcome_by_market:
            continue

        outcome = outcome_by_market[mid]
        predicted_prob = float(est.get("estimated_prob", est.get("predicted_prob", 0)))
        market_prob = float(est.get("market_prob", est.get("market_price", 0)))
        actual = outcome["actual_outcome"]

        # Edge: our predicted - market
        our_edge = predicted_prob - market_prob
        # Edge direction correct if: edge positive and actual=1, or edge negative and actual=0
        edge_correct = (our_edge > 0 and actual == 1) or (our_edge < 0 and actual == 0) or abs(our_edge) < 0.01

        # Get signal data if available
        signals = {}
        signals_raw = est.get("signals", est.get("signal_data", ""))
        if isinstance(signals_raw, str) and signals_raw:
            try:
                signals = json.loads(signals_raw)
            except (json.JSONDecodeError, TypeError):
                pass
        elif isinstance(signals_raw, dict):
            signals = signals_raw

        resolved_pairs.append({
            "market_id": mid,
            "question": est.get("question", est.get("market_question", ""))[:60],
            "predicted_prob": predicted_prob,
            "market_prob": market_prob,
            "actual_outcome": actual,
            "our_edge": round(our_edge, 4),
            "edge_correct": edge_correct,
            "brier_ours": round((predicted_prob - actual) ** 2, 4),
            "brier_market": round((market_prob - actual) ** 2, 4),
            "signals": signals,
        })

    if not resolved_pairs:
        msg = f"No resolved markets with estimates found. {len(latest_by_market)} markets still unresolved."
        if json_output:
            success({"message": msg, "total_estimates": len(latest_by_market)}, msg)
        else:
            report(msg)
        return

    # Aggregate metrics
    n = len(resolved_pairs)
    our_brier = round(sum(p["brier_ours"] for p in resolved_pairs) / n, 4)
    market_brier = round(sum(p["brier_market"] for p in resolved_pairs) / n, 4)
    edge_correct_count = sum(1 for p in resolved_pairs if p["edge_correct"])
    edge_accuracy = round(edge_correct_count / n * 100, 1)

    # Signal accuracy tracking
    signal_stats: Dict[str, Dict] = {}
    for pair in resolved_pairs:
        for signal_name, signal_value in pair["signals"].items():
            if signal_name not in signal_stats:
                signal_stats[signal_name] = {"correct": 0, "total": 0}
            signal_stats[signal_name]["total"] += 1

            # Determine if signal direction was correct
            # Positive signal value = bullish for YES, negative = bearish
            sig_val = float(signal_value) if isinstance(signal_value, (int, float, str)) else 0
            if isinstance(signal_value, str):
                try:
                    sig_val = float(signal_value)
                except (ValueError, TypeError):
                    continue

            signal_correct = (sig_val > 0 and pair["actual_outcome"] == 1) or \
                             (sig_val < 0 and pair["actual_outcome"] == 0) or \
                             abs(sig_val) < 0.01
            if signal_correct:
                signal_stats[signal_name]["correct"] += 1

    signal_accuracy = {
        name: {
            "correct": stats["correct"],
            "total": stats["total"],
            "accuracy_pct": round(stats["correct"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0,
        }
        for name, stats in sorted(signal_stats.items(), key=lambda x: -x[1].get("correct", 0) / max(x[1].get("total", 1), 1))
    }

    # Best and worst predictions
    sorted_by_brier = sorted(resolved_pairs, key=lambda p: p["brier_ours"])
    best_predictions = sorted_by_brier[:3]
    worst_predictions = sorted_by_brier[-3:][::-1]

    feedback_data = {
        "markets_resolved": n,
        "our_brier_score": our_brier,
        "market_brier_score": market_brier,
        "edge_call_accuracy_pct": edge_accuracy,
        "edge_correct_count": edge_correct_count,
        "edge_total": n,
        "signal_accuracy": signal_accuracy,
        "best_predictions": best_predictions,
        "worst_predictions": worst_predictions,
    }

    if json_output:
        success(feedback_data, "Prediction feedback")
        return

    lines = [
        "PREDICTION FEEDBACK REPORT",
        "=" * 60,
        "",
        f"Markets Resolved:     {n}",
        f"Our Brier Score:      {our_brier:.4f}" + (" (good)" if our_brier < 0.15 else ""),
        f"Market Brier Score:   {market_brier:.4f}" + (" (our estimates were better!)" if our_brier < market_brier else ""),
        f"Edge Call Accuracy:   {edge_accuracy:.1f}% ({edge_correct_count}/{n} edge directions correct)",
        "",
    ]

    # Signal accuracy
    if signal_accuracy:
        lines.append("Signal Accuracy:")
        for name, stats in signal_accuracy.items():
            lines.append(f"  {name:<20} {stats['accuracy_pct']:.1f}% correct ({stats['correct']}/{stats['total']})")
        lines.append("")

    # Best predictions
    if best_predictions:
        lines.append("Best Predictions:")
        for i, p in enumerate(best_predictions, 1):
            outcome_str = "YES" if p["actual_outcome"] == 1 else "NO"
            lines.append(f"  [{i}] {p['question']}")
            lines.append(f"      predicted {p['predicted_prob']:.2f}, market {p['market_prob']:.2f}, actual {outcome_str} (Brier: {p['brier_ours']:.4f})")
        lines.append("")

    # Worst predictions
    if worst_predictions:
        lines.append("Worst Predictions:")
        for i, p in enumerate(worst_predictions, 1):
            outcome_str = "YES" if p["actual_outcome"] == 1 else "NO"
            lines.append(f"  [{i}] {p['question']}")
            lines.append(f"      predicted {p['predicted_prob']:.2f}, market {p['market_prob']:.2f}, actual {outcome_str} (Brier: {p['brier_ours']:.4f})")

    report("\n".join(lines), feedback_data)


# ─────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Portfolio Performance Tracker")
    parser.add_argument("--snapshot", action="store_true", help="Take daily portfolio snapshot")
    parser.add_argument("--report", action="store_true", help="Full performance report")
    parser.add_argument("--attribution", action="store_true", help="Attribution analysis")
    parser.add_argument("--accuracy", action="store_true", help="Recommendation accuracy")
    parser.add_argument("--brier", action="store_true", help="Brier score calibration analysis")
    parser.add_argument("--feedback", action="store_true", help="Prediction accuracy feedback")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--days", type=int, default=None, help="Lookback period in days")
    args = parser.parse_args()

    # Default to --report if no mode specified
    if not any([args.snapshot, args.report, args.attribution, args.accuracy, args.brier, args.feedback]):
        args.report = True

    try:
        conn = db_utils.get_connection()
        ensure_snapshot_schema(conn)
        client = create_client()
    except Exception as e:
        error(f"Initialization failed: {e}", "INIT_ERROR")
        return

    try:
        if args.snapshot:
            take_snapshot(conn, client, json_output=args.json)
        elif args.report:
            performance_report(conn, client, days=args.days, json_output=args.json)
        elif args.attribution:
            attribution_analysis(conn, client, days=args.days, json_output=args.json)
        elif args.accuracy:
            recommendation_accuracy(conn, client, days=args.days, json_output=args.json)
        elif args.brier:
            brier_score_analysis(conn, client, days=args.days, json_output=args.json)
        elif args.feedback:
            prediction_feedback(conn, client, days=args.days, json_output=args.json)
    except Exception as e:
        error(f"Execution failed: {e}", "EXEC_ERROR")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
