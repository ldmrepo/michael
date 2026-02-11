#!/usr/bin/env python3
"""
Cross-Platform Arbitrage Monitor

Detects price discrepancies between Polymarket and Kalshi:
  --threshold 3.0     Only show 3%+ spread
  --once              Single scan
  --continuous        Continuous monitoring
  --interval 300      Check every 5 minutes
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

import requests

from config import GAMMA_API_BASE, KALSHI_API_BASE, API_TIMEOUT_SECONDS
from polymarket_client import create_client
from output_format import success, error, alerts, table


# Polymarket fee: ~2% on winnings (varies)
PM_FEE_PCT = 2.0
# Kalshi fee: varies, estimate ~7% on profits for small amounts
KALSHI_FEE_PCT = 7.0


def get_kalshi_markets(limit: int = 100) -> List[Dict]:
    """Fetch active markets from Kalshi public API"""
    try:
        url = f"{KALSHI_API_BASE}/markets"
        params = {"limit": limit, "status": "open"}
        resp = requests.get(url, params=params, timeout=API_TIMEOUT_SECONDS)
        resp.raise_for_status()
        data = resp.json()
        return data.get("markets", [])
    except Exception as e:
        print(f"Warning: Kalshi API error: {e}", file=sys.stderr)
        return []


def similarity_score(text1: str, text2: str) -> float:
    """Calculate text similarity between two market questions"""
    # Normalize
    t1 = text1.lower().strip().rstrip("?")
    t2 = text2.lower().strip().rstrip("?")
    return SequenceMatcher(None, t1, t2).ratio()


def match_markets(
    pm_markets: List[Dict], kalshi_markets: List[Dict], min_similarity: float = 0.5
) -> List[Tuple[Dict, Dict, float]]:
    """Match Polymarket markets with Kalshi markets by question similarity"""
    matches = []

    for pm in pm_markets:
        pm_question = pm.get("question", "")
        if not pm_question:
            continue

        best_match = None
        best_score = 0

        for k in kalshi_markets:
            k_title = k.get("title", "") or k.get("subtitle", "")
            if not k_title:
                continue

            score = similarity_score(pm_question, k_title)
            if score > best_score:
                best_score = score
                best_match = k

        if best_match and best_score >= min_similarity:
            matches.append((pm, best_match, best_score))

    return matches


def extract_kalshi_price(market: Dict) -> Tuple[float, float]:
    """Extract YES/NO prices from Kalshi market data"""
    yes_price = 0
    no_price = 0

    # Kalshi uses yes_bid/yes_ask or last_price
    yes_bid = market.get("yes_bid", 0) or 0
    yes_ask = market.get("yes_ask", 0) or 0
    last_price = market.get("last_price", 0) or 0

    if yes_bid and yes_ask:
        yes_price = (yes_bid + yes_ask) / 2 / 100  # Kalshi prices in cents
    elif last_price:
        yes_price = last_price / 100

    no_price = 1.0 - yes_price if yes_price > 0 else 0
    return yes_price, no_price


def calculate_arb(
    pm_yes: float, pm_no: float,
    k_yes: float, k_no: float,
) -> Dict:
    """
    Calculate arbitrage opportunity.

    Possible arb strategies:
    1. Buy YES on cheaper platform, sell YES (or buy NO) on expensive platform
    2. Buy NO on cheaper platform, sell NO (or buy YES) on expensive platform
    """
    results = {"has_arb": False, "best_strategy": None, "strategies": []}

    # Strategy 1: PM YES + Kalshi NO
    cost_1 = pm_yes + k_no
    if cost_1 < 1.0:
        gross_profit_1 = 1.0 - cost_1
        net_profit_1 = gross_profit_1 - (gross_profit_1 * (PM_FEE_PCT + KALSHI_FEE_PCT) / 100)
        if net_profit_1 > 0:
            results["strategies"].append({
                "description": f"Buy YES on Polymarket (${pm_yes:.3f}) + Buy NO on Kalshi (${k_no:.3f})",
                "total_cost": round(cost_1, 4),
                "gross_profit_pct": round(gross_profit_1 / cost_1 * 100, 2),
                "net_profit_pct": round(net_profit_1 / cost_1 * 100, 2),
            })

    # Strategy 2: Kalshi YES + PM NO
    cost_2 = k_yes + pm_no
    if cost_2 < 1.0:
        gross_profit_2 = 1.0 - cost_2
        net_profit_2 = gross_profit_2 - (gross_profit_2 * (PM_FEE_PCT + KALSHI_FEE_PCT) / 100)
        if net_profit_2 > 0:
            results["strategies"].append({
                "description": f"Buy YES on Kalshi (${k_yes:.3f}) + Buy NO on Polymarket (${pm_no:.3f})",
                "total_cost": round(cost_2, 4),
                "gross_profit_pct": round(gross_profit_2 / cost_2 * 100, 2),
                "net_profit_pct": round(net_profit_2 / cost_2 * 100, 2),
            })

    # Strategy 3: Same platform spread (PM only)
    pm_total = pm_yes + pm_no
    if pm_total < 0.98:  # significant spread
        results["strategies"].append({
            "description": f"PM spread: YES ${pm_yes:.3f} + NO ${pm_no:.3f} = ${pm_total:.3f}",
            "total_cost": round(pm_total, 4),
            "gross_profit_pct": round((1.0 - pm_total) / pm_total * 100, 2),
            "net_profit_pct": round(((1.0 - pm_total) - (1.0 - pm_total) * PM_FEE_PCT / 100) / pm_total * 100, 2),
        })

    if results["strategies"]:
        results["has_arb"] = True
        results["best_strategy"] = max(results["strategies"], key=lambda s: s["net_profit_pct"])

    return results


def scan_arbitrage(threshold: float = 3.0, limit: int = 50) -> List[Dict]:
    """Scan for arbitrage opportunities"""
    client = create_client()

    # Fetch markets from both platforms
    pm_markets = client.get_markets(active=True, limit=limit, order="volume24hr")
    kalshi_markets = get_kalshi_markets(limit=limit)

    opportunities = []

    if kalshi_markets:
        # Cross-platform matching
        matches = match_markets(pm_markets, kalshi_markets)

        for pm_market, k_market, similarity in matches:
            # Parse prices
            pm_prices_raw = pm_market.get("outcomePrices", "")
            if isinstance(pm_prices_raw, str):
                try:
                    pm_prices = json.loads(pm_prices_raw)
                except (json.JSONDecodeError, TypeError):
                    continue
            else:
                pm_prices = pm_prices_raw or []

            if len(pm_prices) < 2:
                continue

            pm_yes = float(pm_prices[0])
            pm_no = float(pm_prices[1])
            k_yes, k_no = extract_kalshi_price(k_market)

            if k_yes <= 0:
                continue

            spread_pct = abs(pm_yes - k_yes) * 100
            arb = calculate_arb(pm_yes, pm_no, k_yes, k_no)

            if arb["has_arb"] and arb["best_strategy"]["net_profit_pct"] >= threshold:
                opportunities.append({
                    "pm_question": pm_market.get("question", "")[:60],
                    "kalshi_title": (k_market.get("title", "") or "")[:60],
                    "similarity": round(similarity, 2),
                    "pm_yes": round(pm_yes, 3),
                    "pm_no": round(pm_no, 3),
                    "kalshi_yes": round(k_yes, 3),
                    "kalshi_no": round(k_no, 3),
                    "spread_pct": round(spread_pct, 1),
                    "best_strategy": arb["best_strategy"]["description"],
                    "net_profit_pct": arb["best_strategy"]["net_profit_pct"],
                })

    # Also check PM internal spreads
    for m in pm_markets:
        prices_raw = m.get("outcomePrices", "")
        if isinstance(prices_raw, str):
            try:
                prices = json.loads(prices_raw)
            except (json.JSONDecodeError, TypeError):
                continue
        else:
            prices = prices_raw or []

        if len(prices) < 2:
            continue

        yes_p = float(prices[0])
        no_p = float(prices[1])
        total = yes_p + no_p

        if total < 0.97:  # >3% spread opportunity
            profit_pct = ((1.0 - total) / total) * 100
            net_profit = profit_pct - (profit_pct * PM_FEE_PCT / 100)
            if net_profit >= threshold:
                opportunities.append({
                    "pm_question": m.get("question", "")[:60],
                    "kalshi_title": "(PM internal spread)",
                    "similarity": 1.0,
                    "pm_yes": round(yes_p, 3),
                    "pm_no": round(no_p, 3),
                    "kalshi_yes": 0,
                    "kalshi_no": 0,
                    "spread_pct": round((1.0 - total) * 100, 1),
                    "best_strategy": f"Buy YES+NO on PM (${total:.3f})",
                    "net_profit_pct": round(net_profit, 2),
                })

    opportunities.sort(key=lambda x: x["net_profit_pct"], reverse=True)
    return opportunities


def main():
    parser = argparse.ArgumentParser(description="Cross-Platform Arbitrage Monitor")
    parser.add_argument("--threshold", type=float, default=3.0, help="Min net profit %")
    parser.add_argument("--limit", type=int, default=50, help="Markets to scan per platform")
    parser.add_argument("--once", action="store_true", help="Single scan")
    parser.add_argument("--continuous", action="store_true", help="Continuous monitoring")
    parser.add_argument("--interval", type=int, default=300, help="Scan interval (seconds)")
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()

    if not args.once and not args.continuous:
        args.once = True

    try:
        if args.once:
            opps = scan_arbitrage(args.threshold, args.limit)

            if args.json:
                success(
                    data={"opportunities": opps, "count": len(opps)},
                    message=f"Found {len(opps)} arbitrage opportunities",
                )
            else:
                if not opps:
                    print(f"No arbitrage opportunities found (threshold: {args.threshold}%)")
                    return

                headers = ["PM Market", "PM YES", "Kalshi YES", "Spread%", "Net Profit%", "Strategy"]
                rows = [
                    [
                        o["pm_question"][:40],
                        f"${o['pm_yes']:.3f}",
                        f"${o['kalshi_yes']:.3f}" if o["kalshi_yes"] > 0 else "N/A",
                        f"{o['spread_pct']:.1f}%",
                        f"{o['net_profit_pct']:.2f}%",
                        o["best_strategy"][:40],
                    ]
                    for o in opps
                ]
                print(table(headers, rows, f"Arbitrage Opportunities (>={args.threshold}% net)"))
                print(f"\nFound {len(opps)} opportunities")

        elif args.continuous:
            print(f"Scanning for arbitrage every {args.interval}s (threshold: {args.threshold}%)")
            print("Press Ctrl+C to stop\n")

            while True:
                opps = scan_arbitrage(args.threshold, args.limit)
                timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")

                if opps:
                    for o in opps:
                        print(
                            f"[{timestamp}] ARB {o['net_profit_pct']:.2f}%: "
                            f"{o['pm_question'][:50]} | {o['best_strategy'][:40]}"
                        )
                else:
                    print(f"[{timestamp}] No opportunities found")

                time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nMonitoring stopped")
    except Exception as e:
        error(str(e), code="ARB_ERROR")


if __name__ == "__main__":
    main()
