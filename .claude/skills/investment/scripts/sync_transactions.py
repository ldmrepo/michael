#!/usr/bin/env python3
"""Sync Binance trade history to DB"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from binance_client import BinanceClient
from db_utils import get_connection, insert_transaction
from output_format import success, error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", default="default")
    parser.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",")]

    try:
        client = BinanceClient()
        conn = get_connection()

        # Get existing order IDs to avoid duplicates
        existing = set()
        rows = conn.execute(
            "SELECT order_id FROM investment_transactions WHERE user_id = ? AND order_id IS NOT NULL",
            (args.user_id,)
        ).fetchall()
        existing = {r["order_id"] for r in rows}

        total_new = 0
        for symbol in symbols:
            try:
                trades = client.get_spot_trades(symbol, limit=args.limit)
                for t in trades:
                    oid = str(t.get("orderId", ""))
                    if oid in existing:
                        continue
                    insert_transaction(
                        conn, args.user_id, "binance", "spot", symbol,
                        side="BUY" if t["isBuyer"] else "SELL",
                        order_type="MARKET",
                        quantity=float(t["qty"]),
                        price=float(t["price"]),
                        fee=float(t.get("commission", 0)),
                        fee_asset=t.get("commissionAsset"),
                        order_id=oid,
                        source="manual",
                        executed_at=int(t["time"] / 1000)
                    )
                    existing.add(oid)
                    total_new += 1
            except Exception as e:
                # Skip symbols that may not exist
                pass

        conn.close()
        success({"new_transactions": total_new, "symbols": symbols},
                f"Synced {total_new} new transactions")

    except Exception as e:
        error(str(e), "SYNC_TRANSACTIONS_ERROR")


if __name__ == "__main__":
    main()
