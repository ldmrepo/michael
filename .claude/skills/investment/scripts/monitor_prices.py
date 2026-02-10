#!/usr/bin/env python3
"""Monitor prices against thresholds"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from binance_client import BinanceClient
from db_utils import get_connection, get_thresholds, insert_alert
from output_format import alerts as output_alerts, error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", default="default")
    args = parser.parse_args()

    try:
        client = BinanceClient()
        conn = get_connection()

        thresholds = get_thresholds(conn, args.user_id)
        if not thresholds:
            output_alerts([], "No thresholds configured")
            return

        # Get current prices
        spot_prices = client.get_spot_price()
        prices = {p["symbol"]: float(p["price"]) for p in spot_prices} if isinstance(spot_prices, list) else {}

        futures_prices = client.get_futures_ticker()
        if isinstance(futures_prices, list):
            for p in futures_prices:
                if p["symbol"] not in prices:
                    prices[p["symbol"]] = float(p["price"])

        triggered = []
        for t in thresholds:
            symbol = t.get("symbol")
            if not symbol or symbol not in prices:
                continue

            current = prices[symbol]
            threshold_val = t["value"]
            threshold_type = t["threshold_type"]

            alert = None
            if threshold_type == "price_above" and current > threshold_val:
                alert = {
                    "type": "price_above",
                    "severity": "warning",
                    "symbol": symbol,
                    "message": f"{symbol} ${current:,.2f} > threshold ${threshold_val:,.2f}",
                    "data": {"current": current, "threshold": threshold_val},
                }
            elif threshold_type == "price_below" and current < threshold_val:
                alert = {
                    "type": "price_below",
                    "severity": "warning",
                    "symbol": symbol,
                    "message": f"{symbol} ${current:,.2f} < threshold ${threshold_val:,.2f}",
                    "data": {"current": current, "threshold": threshold_val},
                }
            elif threshold_type == "price_drop_pct":
                # Check 24h change
                try:
                    ticker = client.get_spot_24hr(symbol)
                    if isinstance(ticker, dict):
                        change_pct = float(ticker.get("priceChangePercent", 0))
                        if change_pct < -threshold_val:
                            alert = {
                                "type": "price_drop_pct",
                                "severity": "critical" if change_pct < -10 else "warning",
                                "symbol": symbol,
                                "message": f"{symbol} dropped {change_pct:.1f}% (threshold: -{threshold_val}%)",
                                "data": {"change_pct": change_pct, "threshold": threshold_val, "price": current},
                            }
                except Exception:
                    pass

            if alert:
                insert_alert(conn, args.user_id, alert["type"], alert["severity"],
                             alert["message"], symbol=alert["symbol"],
                             data_json=json.dumps(alert["data"]))
                triggered.append(alert)

        conn.close()
        output_alerts(triggered, f"Checked {len(thresholds)} thresholds, {len(triggered)} triggered")

    except Exception as e:
        error(str(e), "MONITOR_PRICES_ERROR")


if __name__ == "__main__":
    main()
