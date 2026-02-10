#!/usr/bin/env python3
"""Calculate and execute portfolio rebalancing"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import MAX_ORDER_USD
from binance_client import BinanceClient
from db_utils import get_connection, get_holdings, insert_proposal
from output_format import success, error


def calculate_rebalance(holdings: list, targets: dict) -> list:
    """Calculate trades needed for target allocation"""
    total = sum((h.get("current_price", 0) or 0) * (h.get("quantity", 0) or 0)
                for h in holdings if h["account_type"] == "spot")
    if total <= 0:
        return []

    current_alloc = {}
    for h in holdings:
        if h["account_type"] != "spot":
            continue
        value = (h.get("current_price", 0) or 0) * (h.get("quantity", 0) or 0)
        current_alloc[h["symbol"]] = {
            "value": value,
            "pct": value / total * 100,
            "price": h.get("current_price", 0) or 0,
            "quantity": h.get("quantity", 0) or 0,
        }

    trades = []
    for symbol, target_pct in targets.items():
        current = current_alloc.get(symbol, {"value": 0, "pct": 0, "price": 0})
        diff_pct = target_pct - current["pct"]

        if abs(diff_pct) < 2:  # Skip if within 2% tolerance
            continue

        diff_value = total * diff_pct / 100
        price = current.get("price", 0)
        if price <= 0:
            continue

        qty = abs(diff_value / price)
        side = "BUY" if diff_pct > 0 else "SELL"

        trades.append({
            "symbol": symbol,
            "side": side,
            "quantity": round(qty, 6),
            "est_value": round(abs(diff_value), 2),
            "current_pct": round(current["pct"], 1),
            "target_pct": target_pct,
        })

    return trades


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", default="default")
    parser.add_argument("--targets", required=True,
                        help='JSON string: {"BTCUSDT": 50, "ETHUSDT": 30, "USDT": 20}')
    parser.add_argument("--execute", action="store_true",
                        help="Create proposals (otherwise just calculate)")
    args = parser.parse_args()

    try:
        targets = json.loads(args.targets)
        conn = get_connection()
        holdings = get_holdings(conn, args.user_id)

        trades = calculate_rebalance(holdings, targets)

        if not trades:
            success({"trades": [], "message": "Portfolio is balanced"}, "No rebalancing needed")
            return

        if args.execute:
            proposals = []
            skipped = []
            for t in trades:
                if t["est_value"] > MAX_ORDER_USD:
                    skipped.append({
                        "symbol": t["symbol"],
                        "side": t["side"],
                        "est_value": t["est_value"],
                        "reason": f"Exceeds MAX_ORDER_USD (${MAX_ORDER_USD:,.2f})",
                    })
                    continue
                pid = insert_proposal(
                    conn, args.user_id, "rebalance", t["symbol"],
                    t["side"], "spot", "MARKET", t["quantity"],
                    rationale=f"Rebalance: {t['current_pct']}% → {t['target_pct']}%"
                )
                proposals.append({"proposal_id": pid, **t})

            conn.close()
            msg = f"Created {len(proposals)} rebalance proposals"
            if skipped:
                msg += f", skipped {len(skipped)} (exceed limit)"
            success({"proposals": proposals, "skipped": skipped}, msg)
        else:
            conn.close()
            success({"trades": trades}, f"Calculated {len(trades)} trades")

    except Exception as e:
        error(str(e), "REBALANCE_ERROR")


if __name__ == "__main__":
    main()
