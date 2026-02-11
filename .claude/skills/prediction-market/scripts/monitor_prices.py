#!/usr/bin/env python3
"""
Polymarket Price Monitor

Monitors price changes for watched markets:
  --market-id <id>    Monitor specific market
  --watchlist         Monitor all DB watchlist markets
  --threshold 5       Alert on 5%+ price change
  --interval 60       Check every 60 seconds
  --once              Single check (for cron)
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone

from polymarket_client import create_client
from output_format import success, error, alerts, table
import db_utils


def check_market_price(client, market_id: str, conn=None) -> dict:
    """Check current price and compare with last recorded"""
    try:
        # Get current market data
        markets = client.get_markets(active=True, limit=200)
        market = None
        for m in markets:
            if m.get("id") == market_id or m.get("slug") == market_id:
                market = m
                break

        if not market:
            # Try direct lookup
            try:
                market = client.get_market(market_id)
            except Exception:
                return {"error": f"Market not found: {market_id}"}

        # Parse prices
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
        volume_24h = float(market.get("volume24hr", 0) or 0)
        liquidity = float(market.get("liquidity", 0) or 0)

        result = {
            "market_id": market.get("id", market_id),
            "question": market.get("question", "")[:80],
            "yes_price": round(yes_price, 4),
            "no_price": round(no_price, 4),
            "volume_24h": volume_24h,
            "liquidity": liquidity,
            "change_pct": 0,
            "alert": False,
        }

        # Compare with last recorded price
        if conn:
            last = db_utils.get_latest_price(conn, market.get("id", market_id))
            if last and last.get("yes_price"):
                old_price = last["yes_price"]
                if old_price > 0:
                    change = ((yes_price - old_price) / old_price) * 100
                    result["change_pct"] = round(change, 2)
                    result["prev_price"] = round(old_price, 4)

            # Record new price
            db_utils.record_price(
                conn,
                market_id=market.get("id", market_id),
                yes_price=yes_price,
                no_price=no_price,
                volume_24h=volume_24h,
                liquidity=liquidity,
            )

        return result

    except Exception as e:
        return {"error": str(e), "market_id": market_id}


def monitor_once(client, market_ids: list, threshold: float, conn=None) -> list:
    """Single monitoring pass"""
    results = []
    alert_list = []

    for mid in market_ids:
        result = check_market_price(client, mid, conn)
        if "error" in result:
            results.append(result)
            continue

        # Check threshold
        if abs(result.get("change_pct", 0)) >= threshold:
            result["alert"] = True
            direction = "UP" if result["change_pct"] > 0 else "DOWN"
            alert_list.append({
                "type": "price_change",
                "market_id": result["market_id"],
                "question": result["question"],
                "direction": direction,
                "change_pct": result["change_pct"],
                "current_price": result["yes_price"],
                "prev_price": result.get("prev_price", 0),
            })

        results.append(result)

    return results, alert_list


def main():
    parser = argparse.ArgumentParser(description="Polymarket Price Monitor")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--market-id", type=str, help="Monitor specific market ID")
    source.add_argument("--watchlist", action="store_true", help="Monitor all watchlist markets")

    parser.add_argument("--threshold", type=float, default=5.0, help="Alert threshold (%)")
    parser.add_argument("--interval", type=int, default=60, help="Check interval (seconds)")
    parser.add_argument("--once", action="store_true", help="Single check then exit")
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()

    try:
        client = create_client()
        conn = db_utils.get_connection()

        # Determine markets to monitor
        if args.market_id:
            market_ids = [args.market_id]
        else:
            watchlist = db_utils.get_watchlist(conn)
            if not watchlist:
                error("Watchlist is empty. Use scan_markets.py --save to add markets.", code="EMPTY_WATCHLIST")
                return
            market_ids = [m["id"] for m in watchlist]

        if args.once:
            results, alert_list = monitor_once(client, market_ids, args.threshold, conn)

            if args.json:
                if alert_list:
                    alerts(alert_list, message=f"Found {len(alert_list)} alerts")
                else:
                    success(
                        data={"markets": results, "alerts": []},
                        message=f"Checked {len(results)} markets, no alerts",
                    )
            else:
                # Pretty print
                headers = ["Question", "YES", "NO", "Change", "Vol24h", "Liq"]
                rows = []
                for r in results:
                    if "error" in r:
                        rows.append([r.get("market_id", "?")[:50], "ERROR", r["error"][:30], "", "", ""])
                        continue

                    change_str = f"{r['change_pct']:+.2f}%" if r.get("change_pct") else "N/A"
                    if r.get("alert"):
                        change_str = f"** {change_str} **"

                    rows.append([
                        r["question"][:50],
                        f"${r['yes_price']:.2f}",
                        f"${r['no_price']:.2f}",
                        change_str,
                        f"${r['volume_24h']:,.0f}",
                        f"${r['liquidity']:,.0f}",
                    ])

                print(table(headers, rows, "Price Monitor"))
                if alert_list:
                    print(f"\n** {len(alert_list)} ALERTS (>={args.threshold}% change) **")
                    for a in alert_list:
                        print(f"  {a['direction']} {a['change_pct']:+.2f}%: {a['question']}")
                print(f"\nChecked {len(results)} markets at {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")

        else:
            # Continuous monitoring
            print(f"Monitoring {len(market_ids)} markets every {args.interval}s (threshold: {args.threshold}%)")
            print("Press Ctrl+C to stop\n")

            while True:
                results, alert_list = monitor_once(client, market_ids, args.threshold, conn)

                timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
                if alert_list:
                    for a in alert_list:
                        print(f"[{timestamp}] ALERT {a['direction']} {a['change_pct']:+.2f}%: {a['question']}")
                else:
                    checked = len([r for r in results if "error" not in r])
                    print(f"[{timestamp}] Checked {checked} markets - no alerts")

                time.sleep(args.interval)

        conn.close()

    except KeyboardInterrupt:
        print("\nMonitoring stopped")
    except Exception as e:
        error(str(e), code="MONITOR_ERROR")


if __name__ == "__main__":
    main()
