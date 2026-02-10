#!/usr/bin/env python3
"""Sync Binance spot+futures balances to DB"""

import sys
import argparse
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from binance_client import BinanceClient
from db_utils import get_connection, upsert_holding, clear_holdings
from output_format import success, error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", default="default")
    args = parser.parse_args()

    try:
        client = BinanceClient()
        conn = get_connection()

        # Get current prices
        prices_raw = client.get_spot_price()
        prices = {p["symbol"]: float(p["price"]) for p in prices_raw} if isinstance(prices_raw, list) else {}

        # Spot balances
        spot_balances = client.get_spot_balances()
        clear_holdings(conn, args.user_id, "binance", "spot")

        spot_count = 0
        for b in spot_balances:
            asset = b["asset"]
            qty = float(b["free"]) + float(b["locked"])
            if qty <= 0:
                continue
            symbol = f"{asset}USDT"
            price = prices.get(symbol, 0)
            if asset == "USDT":
                price = 1.0
                symbol = "USDT"
            upsert_holding(conn, args.user_id, "binance", "spot", symbol, qty,
                           current_price=price)
            spot_count += 1

        # Futures positions
        futures_positions = client.get_futures_positions()
        clear_holdings(conn, args.user_id, "binance", "futures")

        futures_count = 0
        for p in futures_positions:
            symbol = p["symbol"]
            qty = abs(float(p.get("positionAmt", 0)))
            if qty == 0:
                continue
            entry = float(p.get("entryPrice", 0))
            unrealized = float(p.get("unrealizedProfit", 0))
            leverage = int(p.get("leverage", 1))
            liq_price = float(p.get("liquidationPrice", 0))
            pos_side = p.get("positionSide", "BOTH")
            price = prices.get(symbol, float(p.get("markPrice", 0)))

            upsert_holding(conn, args.user_id, "binance", "futures", symbol, qty,
                           avg_entry_price=entry, current_price=price,
                           unrealized_pnl=unrealized, leverage=leverage,
                           liquidation_price=liq_price, position_side=pos_side)
            futures_count += 1

        # Futures wallet balance
        futures_balances = client.get_futures_balances()
        for fb in futures_balances:
            if fb["asset"] == "USDT" and float(fb.get("balance", 0)) > 0:
                upsert_holding(conn, args.user_id, "binance", "futures", "USDT",
                               float(fb["balance"]), current_price=1.0)

        conn.close()
        success({"spot_count": spot_count, "futures_count": futures_count},
                f"Synced {spot_count} spot + {futures_count} futures positions")

    except Exception as e:
        error(str(e), "SYNC_BALANCE_ERROR")


if __name__ == "__main__":
    main()
