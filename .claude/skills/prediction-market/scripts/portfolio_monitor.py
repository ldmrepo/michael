#!/usr/bin/env python3
"""
Portfolio Monitor for Automated Alerts

Lightweight monitoring script designed to be called by Michael's scheduler.
Checks positions for alert conditions and outputs Telegram-formatted messages.

Alert Conditions:
  - Market settled/closed (action needed)
  - Price near certainty (>97% or <3% — capital locked)
  - Expiring within 24h
  - Large P&L movement (>5% change from entry)
  - Stop loss triggered (>20% loss)
  - New high-EV opportunities (from scan)

Usage:
  python portfolio_monitor.py                    # Check all alerts
  python portfolio_monitor.py --json             # JSON output
  python portfolio_monitor.py --settled-only     # Only check settled markets
  python portfolio_monitor.py --expiring 48      # Alert if expiring within N hours
  python portfolio_monitor.py --pnl-threshold 10 # Alert if P&L > N%
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List

import db_utils
from config import DB_PATH
from output_format import error, report, success
from polymarket_client import create_client


# === Alert Types ===

ALERT_SETTLED = "SETTLED"
ALERT_NEAR_CERTAIN = "NEAR_CERTAIN"
ALERT_EXPIRING = "EXPIRING"
ALERT_STOP_LOSS = "STOP_LOSS"
ALERT_BIG_GAIN = "BIG_GAIN"
ALERT_CAPITAL_LOCKED = "CAPITAL_LOCKED"


def check_alerts(
    expiring_hours: float = 24.0,
    pnl_threshold: float = 10.0,
    capital_lock_threshold: float = 0.96,
) -> Dict:
    """
    Check all positions for alert conditions.
    Returns structured alert data.
    """
    conn = db_utils.get_connection()
    client = create_client()

    positions = db_utils.get_positions(conn, status="open")
    if not positions:
        conn.close()
        return {"alerts": [], "portfolio": {"positions": 0, "invested": 0, "cash": 0}}

    # Build slug map from pm_markets for reliable Gamma lookups
    market_ids = list(set(p["market_id"] for p in positions))
    slug_map = {}
    for mid in market_ids:
        row = conn.execute("SELECT slug FROM pm_markets WHERE id = ?", (mid,)).fetchone()
        if row and row["slug"]:
            slug_map[mid] = row["slug"]

    # Fetch live prices
    market_data = {}
    for mid in market_ids:
        try:
            slug = slug_map.get(mid)
            if slug:
                result = client._gamma_get("/markets", {"slug": slug})
            else:
                result = client._gamma_get("/markets", {"condition_id": mid})
            if result and isinstance(result, list) and len(result) > 0:
                market = result[0]
                prices_raw = market.get("outcomePrices", "")
                if isinstance(prices_raw, str):
                    try:
                        prices = json.loads(prices_raw)
                    except (json.JSONDecodeError, TypeError):
                        prices = []
                else:
                    prices = prices_raw or []

                yes_price = float(prices[0]) if len(prices) > 0 else 0
                no_price = float(prices[1]) if len(prices) > 1 else 0

                end_date_str = market.get("endDate", "")
                hours_to_expiry = None
                if end_date_str:
                    try:
                        end_dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                        hours_to_expiry = max((end_dt - datetime.now(timezone.utc)).total_seconds() / 3600, 0)
                    except Exception:
                        pass

                market_data[mid] = {
                    "question": market.get("question", ""),
                    "yes_price": yes_price,
                    "no_price": no_price,
                    "active": market.get("active", False),
                    "closed": market.get("closed", False),
                    "hours_to_expiry": hours_to_expiry,
                }
            time.sleep(0.3)
        except Exception as e:
            print(f"  [WARN] Failed to fetch {mid[:20]}: {e}", file=sys.stderr)

    alerts = []
    total_invested = 0
    total_value = 0
    locked_capital = 0

    for pos in positions:
        mid = pos["market_id"]
        mdata = market_data.get(mid)
        if not mdata:
            continue

        side = pos["side"]
        entry_price = pos["entry_price"]
        size = pos["size"]
        invested = entry_price * size
        total_invested += invested

        current_price = mdata["yes_price"] if side == "YES" else mdata.get("no_price", 0)
        current_value = current_price * size
        total_value += current_value
        pnl = current_value - invested
        pnl_pct = (pnl / invested * 100) if invested > 0 else 0

        question = mdata.get("question", mid[:40])[:55]
        hours_left = mdata.get("hours_to_expiry")

        # Check: Market settled/closed
        if mdata.get("closed", False) or not mdata.get("active", True):
            alerts.append({
                "type": ALERT_SETTLED,
                "severity": "high",
                "market_id": mid,
                "question": question,
                "side": side,
                "invested": round(invested, 2),
                "message": f"Market settled! Invested ${invested:.2f}",
            })
            continue

        # Check: Near certainty (capital locked)
        if current_price > capital_lock_threshold:
            max_profit_pct = ((1.0 - current_price) / current_price * 100)
            locked_capital += invested
            if max_profit_pct < 3:
                alerts.append({
                    "type": ALERT_NEAR_CERTAIN,
                    "severity": "medium",
                    "market_id": mid,
                    "question": question,
                    "side": side,
                    "current_price": round(current_price, 4),
                    "invested": round(invested, 2),
                    "max_profit_pct": round(max_profit_pct, 1),
                    "message": f"Price ${current_price:.2f} — max profit {max_profit_pct:.1f}%, capital locked",
                })
        elif current_price < (1 - capital_lock_threshold):
            alerts.append({
                "type": ALERT_NEAR_CERTAIN,
                "severity": "high",
                "market_id": mid,
                "question": question,
                "side": side,
                "current_price": round(current_price, 4),
                "invested": round(invested, 2),
                "message": f"Price ${current_price:.2f} near zero — likely total loss",
            })

        # Check: Expiring soon
        if hours_left is not None and hours_left < expiring_hours:
            severity = "high" if hours_left < 6 else "medium"
            alerts.append({
                "type": ALERT_EXPIRING,
                "severity": severity,
                "market_id": mid,
                "question": question,
                "side": side,
                "hours_left": round(hours_left, 1),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 1),
                "message": f"Expires in {hours_left:.0f}h — P&L ${pnl:+.2f} ({pnl_pct:+.1f}%)",
            })

        # Check: Stop loss
        if pnl_pct < -20:
            alerts.append({
                "type": ALERT_STOP_LOSS,
                "severity": "high",
                "market_id": mid,
                "question": question,
                "side": side,
                "entry_price": round(entry_price, 4),
                "current_price": round(current_price, 4),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 1),
                "message": f"STOP LOSS: P&L {pnl_pct:+.1f}% (${pnl:+.2f})",
            })

        # Check: Big gain
        elif pnl_pct > pnl_threshold:
            alerts.append({
                "type": ALERT_BIG_GAIN,
                "severity": "low",
                "market_id": mid,
                "question": question,
                "side": side,
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 1),
                "message": f"Big gain: P&L {pnl_pct:+.1f}% (${pnl:+.2f})",
            })

    # Get cash balance
    try:
        cash = client.get_balance_usdc()
    except Exception:
        cash = 0

    conn.close()

    # Sort alerts by severity
    severity_order = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(key=lambda a: severity_order.get(a["severity"], 3))

    total_pnl = total_value - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "alerts": alerts,
        "alert_counts": {
            "high": sum(1 for a in alerts if a["severity"] == "high"),
            "medium": sum(1 for a in alerts if a["severity"] == "medium"),
            "low": sum(1 for a in alerts if a["severity"] == "low"),
        },
        "portfolio": {
            "positions": len(positions),
            "invested": round(total_invested, 2),
            "current_value": round(total_value, 2),
            "cash": round(cash, 2),
            "total": round(total_value + cash, 2),
            "unrealized_pnl": round(total_pnl, 2),
            "unrealized_pnl_pct": round(total_pnl_pct, 1),
            "locked_capital": round(locked_capital, 2),
        },
    }


def format_telegram(result: Dict) -> str:
    """Format alerts for Telegram notification"""
    alerts = result["alerts"]
    portfolio = result["portfolio"]

    lines = []

    # Header with portfolio summary
    pnl = portfolio["unrealized_pnl"]
    pnl_pct = portfolio["unrealized_pnl_pct"]
    sign = "+" if pnl >= 0 else ""
    lines.append(f"*PM Portfolio Monitor*")
    lines.append(f"NAV: ${portfolio['total']:,.2f} | P&L: {sign}${pnl:.2f} ({sign}{pnl_pct:.1f}%)")
    lines.append(f"Positions: {portfolio['positions']} | Cash: ${portfolio['cash']:,.2f}")

    if not alerts:
        lines.append("\nAll positions within parameters.")
        return "\n".join(lines)

    # Group by severity
    high = [a for a in alerts if a["severity"] == "high"]
    medium = [a for a in alerts if a["severity"] == "medium"]
    low = [a for a in alerts if a["severity"] == "low"]

    if high:
        lines.append(f"\n*URGENT ({len(high)})*:")
        for a in high:
            lines.append(f"  {a['question']}")
            lines.append(f"  {a['message']}")

    if medium:
        lines.append(f"\n*WATCH ({len(medium)})*:")
        for a in medium[:5]:
            lines.append(f"  {a['question'][:45]}: {a['message'][:40]}")

    if low:
        lines.append(f"\n_Info ({len(low)})_:")
        for a in low[:3]:
            lines.append(f"  {a['question'][:45]}: {a['message'][:40]}")

    if portfolio["locked_capital"] > 50:
        lines.append(f"\nLocked capital: ${portfolio['locked_capital']:,.2f}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Portfolio Monitor")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--telegram", action="store_true", help="Telegram format (default)")
    parser.add_argument("--settled-only", action="store_true", help="Only check settled markets")
    parser.add_argument("--expiring", type=float, default=24.0,
                        help="Alert if expiring within N hours (default: 24)")
    parser.add_argument("--pnl-threshold", type=float, default=10.0,
                        help="Alert if P&L exceeds N%% (default: 10)")

    args = parser.parse_args()

    try:
        result = check_alerts(
            expiring_hours=args.expiring,
            pnl_threshold=args.pnl_threshold,
        )
    except Exception as e:
        error(f"Monitor failed: {e}", code="MONITOR_ERROR")
        return

    if args.settled_only:
        result["alerts"] = [a for a in result["alerts"] if a["type"] == ALERT_SETTLED]

    if args.json:
        success(data=result, message="monitor_complete")
    else:
        telegram_text = format_telegram(result)
        report(telegram_text, data={
            "alert_counts": result["alert_counts"],
            "portfolio": result["portfolio"],
        })


if __name__ == "__main__":
    main()
