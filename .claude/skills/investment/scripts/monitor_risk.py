#!/usr/bin/env python3
"""Monitor portfolio risk metrics"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from binance_client import BinanceClient
from db_utils import get_connection, get_holdings, insert_alert
from output_format import alerts as output_alerts, error


def check_concentration(holdings: list, max_pct: float = 50.0) -> list:
    """Check if any single position exceeds concentration limit"""
    alerts = []
    total = sum((h.get("current_price", 0) or 0) * (h.get("quantity", 0) or 0) for h in holdings)
    if total <= 0:
        return alerts

    for h in holdings:
        value = (h.get("current_price", 0) or 0) * (h.get("quantity", 0) or 0)
        pct = (value / total) * 100
        if pct > max_pct and h["symbol"] != "USDT":
            alerts.append({
                "type": "concentration",
                "severity": "warning",
                "symbol": h["symbol"],
                "message": f"{h['symbol']} is {pct:.1f}% of portfolio (limit: {max_pct}%)",
                "data": {"pct": round(pct, 1), "value": round(value, 2), "total": round(total, 2)},
            })
    return alerts


def check_liquidation_proximity(holdings: list, buffer_pct: float = 10.0) -> list:
    """Check if futures positions are close to liquidation"""
    alerts = []
    for h in holdings:
        if h["account_type"] != "futures":
            continue
        liq = h.get("liquidation_price")
        price = h.get("current_price")
        if not liq or not price or liq <= 0:
            continue

        distance_pct = abs(price - liq) / price * 100
        if distance_pct < buffer_pct:
            severity = "critical" if distance_pct < 5 else "warning"
            alerts.append({
                "type": "liquidation_proximity",
                "severity": severity,
                "symbol": h["symbol"],
                "message": f"{h['symbol']} liquidation at ${liq:,.2f} ({distance_pct:.1f}% away)",
                "data": {"price": price, "liquidation": liq, "distance_pct": round(distance_pct, 1)},
            })
    return alerts


def check_mdd(conn, user_id: str, max_mdd_pct: float = 20.0) -> list:
    """Check maximum drawdown from peak NAV"""
    alerts = []
    rows = conn.execute(
        "SELECT total_value_usd FROM investment_snapshots WHERE user_id = ? ORDER BY date DESC LIMIT 30",
        (user_id,)
    ).fetchall()

    if len(rows) < 2:
        return alerts

    values = [r["total_value_usd"] for r in reversed(rows)]
    peak = values[0]
    max_dd = 0

    for v in values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    if max_dd > max_mdd_pct:
        alerts.append({
            "type": "mdd_exceeded",
            "severity": "critical" if max_dd > 30 else "warning",
            "symbol": None,
            "message": f"MDD {max_dd:.1f}% exceeds limit {max_mdd_pct}%",
            "data": {"mdd": round(max_dd, 1), "peak": peak, "current": values[-1]},
        })
    return alerts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", default="default")
    args = parser.parse_args()

    try:
        conn = get_connection()
        holdings = get_holdings(conn, args.user_id)
        all_alerts = []

        all_alerts.extend(check_concentration(holdings))
        all_alerts.extend(check_liquidation_proximity(holdings))
        all_alerts.extend(check_mdd(conn, args.user_id))

        for a in all_alerts:
            insert_alert(conn, args.user_id, a["type"], a["severity"],
                         a["message"], symbol=a.get("symbol"),
                         data_json=json.dumps(a.get("data", {})))

        conn.close()
        output_alerts(all_alerts, f"Risk check: {len(all_alerts)} alerts")

    except Exception as e:
        error(str(e), "MONITOR_RISK_ERROR")


if __name__ == "__main__":
    main()
