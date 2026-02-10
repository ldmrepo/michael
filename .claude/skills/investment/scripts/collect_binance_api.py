#!/usr/bin/env python3
"""Collect Binance derivatives data via API"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import DEFAULT_TRACKED_SYMBOLS
from binance_client import BinanceClient
from db_utils import get_connection, insert_research
from output_format import success, error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default=",".join(DEFAULT_TRACKED_SYMBOLS))
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",")]

    try:
        client = BinanceClient()
        conn = get_connection()
        results = {}

        for symbol in symbols:
            data = {}

            try:
                fr = client.get_funding_rate(symbol, limit=3)
                data["funding_rate"] = [{
                    "rate": f.get("fundingRate"),
                    "time": f.get("fundingTime"),
                } for f in fr]
            except Exception:
                pass

            try:
                oi = client.get_open_interest(symbol)
                data["open_interest"] = {
                    "amount": oi.get("openInterest"),
                    "symbol": oi.get("symbol"),
                }
            except Exception:
                pass

            try:
                ls = client.get_long_short_ratio(symbol, period="1h", limit=5)
                data["long_short_ratio"] = [{
                    "ratio": r.get("longShortRatio"),
                    "long_account": r.get("longAccount"),
                    "short_account": r.get("shortAccount"),
                    "timestamp": r.get("timestamp"),
                } for r in ls]
            except Exception:
                pass

            try:
                tv = client.get_taker_volume(symbol, period="1h", limit=5)
                data["taker_volume"] = [{
                    "buy_sell_ratio": r.get("buySellRatio"),
                    "buy_vol": r.get("buyVol"),
                    "sell_vol": r.get("sellVol"),
                    "timestamp": r.get("timestamp"),
                } for r in tv]
            except Exception:
                pass

            if data:
                insert_research(conn, "binance_api", "derivatives",
                                json.dumps(data, ensure_ascii=False), symbol=symbol)
                results[symbol] = list(data.keys())

        conn.close()
        success(results, f"Binance data collected for {len(results)} symbols")

    except Exception as e:
        error(str(e), "COLLECT_BINANCE_ERROR")


if __name__ == "__main__":
    main()
