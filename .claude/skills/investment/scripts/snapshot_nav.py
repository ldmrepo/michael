#!/usr/bin/env python3
"""Daily NAV snapshot"""

import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from binance_client import BinanceClient
from db_utils import get_connection, get_holdings, upsert_snapshot
from output_format import success, error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", default="default")
    args = parser.parse_args()

    try:
        conn = get_connection()
        client = BinanceClient()

        holdings = get_holdings(conn, args.user_id)
        if not holdings:
            success({"total_value_usd": 0}, "No holdings found")
            return

        spot_value = 0.0
        futures_value = 0.0
        unrealized_pnl = 0.0
        holdings_summary = []

        for h in holdings:
            price = h.get("current_price") or 0
            qty = h.get("quantity") or 0
            value = price * qty
            pnl = h.get("unrealized_pnl") or 0

            if h["account_type"] == "spot":
                spot_value += value
            else:
                futures_value += value
                unrealized_pnl += pnl

            holdings_summary.append({
                "symbol": h["symbol"],
                "account_type": h["account_type"],
                "quantity": qty,
                "value_usd": round(value, 2),
            })

        total_value = spot_value + futures_value

        # BTC price
        try:
            btc_data = client.get_spot_price("BTCUSDT")
            btc_price = float(btc_data["price"]) if isinstance(btc_data, dict) else 0
        except Exception:
            btc_price = 0

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        upsert_snapshot(
            conn, args.user_id, today,
            total_value_usd=round(total_value, 2),
            spot_value_usd=round(spot_value, 2),
            futures_value_usd=round(futures_value, 2),
            unrealized_pnl_usd=round(unrealized_pnl, 2),
            btc_price=btc_price,
            holdings_json=json.dumps(holdings_summary, ensure_ascii=False)
        )

        conn.close()
        success({
            "date": today,
            "total_value_usd": round(total_value, 2),
            "spot_value_usd": round(spot_value, 2),
            "futures_value_usd": round(futures_value, 2),
            "btc_price": btc_price,
        }, f"Snapshot saved: ${total_value:,.2f}")

    except Exception as e:
        error(str(e), "SNAPSHOT_NAV_ERROR")


if __name__ == "__main__":
    main()
