#!/usr/bin/env python3
"""Execute DCA (Dollar Cost Averaging) orders"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import MAX_ORDER_USD
from binance_client import BinanceClient
from db_utils import (
    get_connection, get_active_dca_schedules, update_dca_executed,
    insert_transaction
)
from output_format import success, error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", default="default")
    parser.add_argument("--dca-id", type=int, help="Execute specific DCA schedule")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        conn = get_connection()
        client = BinanceClient()

        schedules = get_active_dca_schedules(conn, args.user_id)
        if args.dca_id:
            schedules = [s for s in schedules if s["id"] == args.dca_id]

        if not schedules:
            success({"executed": 0}, "No active DCA schedules")
            return

        executed = []
        for sched in schedules:
            symbol = sched["symbol"]
            amount_usd = sched["amount_usd"]

            # Safety check: DCA amount limit
            if amount_usd > MAX_ORDER_USD:
                executed.append({
                    "dca_id": sched["id"],
                    "symbol": symbol,
                    "error": f"DCA amount ${amount_usd:,.2f} exceeds limit ${MAX_ORDER_USD:,.2f}",
                })
                continue

            try:
                if args.dry_run:
                    executed.append({
                        "dca_id": sched["id"],
                        "symbol": symbol,
                        "amount_usd": amount_usd,
                        "dry_run": True,
                    })
                    continue

                # Market buy with quote quantity
                if sched.get("account_type", "spot") == "spot":
                    result = client.create_spot_order(
                        symbol=symbol,
                        side="BUY",
                        order_type="MARKET",
                        quote_quantity=amount_usd,
                    )
                else:
                    # For futures, calculate quantity from price
                    price_data = client.get_futures_ticker(symbol)
                    price = float(price_data["price"]) if isinstance(price_data, dict) else 0
                    if price <= 0:
                        continue
                    qty = amount_usd / price
                    result = client.create_futures_order(
                        symbol=symbol, side="BUY", order_type="MARKET", quantity=qty
                    )

                fill_qty = float(result.get("executedQty", 0))
                fill_price = float(result.get("avgPrice") or result.get("price", 0))

                # Update DCA stats
                update_dca_executed(conn, sched["id"], amount_usd, fill_qty)

                # Record transaction
                insert_transaction(
                    conn, args.user_id, "binance",
                    sched.get("account_type", "spot"),
                    symbol, "BUY", "MARKET",
                    fill_qty, fill_price,
                    order_id=str(result.get("orderId", "")),
                    source="dca",
                )

                executed.append({
                    "dca_id": sched["id"],
                    "symbol": symbol,
                    "amount_usd": amount_usd,
                    "fill_qty": fill_qty,
                    "fill_price": fill_price,
                })

            except Exception as e:
                executed.append({
                    "dca_id": sched["id"],
                    "symbol": symbol,
                    "error": str(e),
                })

        conn.close()
        success({"executed": executed}, f"DCA: {len(executed)} orders processed")

    except Exception as e:
        error(str(e), "DCA_ERROR")


if __name__ == "__main__":
    main()
