#!/usr/bin/env python3
"""
Polymarket Market Scanner

Scans for profitable opportunities:
  --high-prob     90%+ high-probability bond-like opportunities
  --new           New markets (last 24 hours)
  --high-volume   Top markets by 24h volume
  --tag <tag>     Filter by tag (crypto, politics, sports, etc.)
  --save          Save discovered markets to DB watchlist
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone

from config import DEFAULT_MARKET_LIMIT
from polymarket_client import create_client
from output_format import success, error, table
import db_utils


def parse_outcomes_prices(market: dict) -> tuple:
    """Extract YES/NO prices from market data"""
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
    return yes_price, no_price


def calculate_roi(price: float, end_date_str: str) -> dict:
    """Calculate ROI metrics for a high-prob market"""
    if price <= 0 or price >= 1:
        return {"roi_pct": 0, "annualized_roi": 0, "days_to_expiry": 0}

    profit_per_contract = 1.0 - price
    roi_pct = (profit_per_contract / price) * 100

    days_to_expiry = 0
    annualized_roi = 0
    if end_date_str:
        try:
            end_dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            days_to_expiry = max((end_dt - now).days, 1)
            annualized_roi = roi_pct * (365 / days_to_expiry)
        except (ValueError, TypeError):
            pass

    return {
        "roi_pct": round(roi_pct, 2),
        "annualized_roi": round(annualized_roi, 1),
        "days_to_expiry": days_to_expiry,
    }


def scan_high_prob(client, threshold: float = 0.90, limit: int = 50, pages: int = 1) -> list:
    """Scan for high-probability markets (bond-like opportunities).
    Use pages > 1 to scan beyond the 100-market Gamma API limit."""
    markets = []
    page_size = min(limit, 100)  # Gamma API max per page = 100
    for page in range(pages):
        batch = client.get_markets(active=True, limit=page_size, offset=page * page_size, order="volume24hr")
        if not batch:
            break
        markets.extend(batch)
    results = []

    for m in markets:
        yes_price, no_price = parse_outcomes_prices(m)
        # High prob on either side
        high_price = max(yes_price, no_price)
        if high_price < threshold:
            continue

        high_side = "YES" if yes_price >= no_price else "NO"
        roi = calculate_roi(high_price, m.get("endDate", ""))

        # Extract token IDs for order execution
        clob_ids = m.get("clobTokenIds", [])
        # YES=index 0, NO=index 1
        token_id = clob_ids[1] if high_side == "NO" and len(clob_ids) > 1 else (clob_ids[0] if clob_ids else "")

        results.append({
            "id": m.get("conditionId", m.get("id", "")),
            "question": m.get("question", "")[:80],
            "side": high_side,
            "price": round(high_price, 4),
            "token_id": token_id,
            "roi_pct": roi["roi_pct"],
            "annualized_roi": roi["annualized_roi"],
            "days_to_expiry": roi["days_to_expiry"],
            "volume_24h": float(m.get("volume24hr", 0) or 0),
            "liquidity": float(m.get("liquidityNum", m.get("liquidity", 0)) or 0),
        })

    results.sort(key=lambda x: x["annualized_roi"], reverse=True)
    return results


def scan_new_markets(client, hours: int = 24, limit: int = 50) -> list:
    """Scan for recently created markets"""
    markets = client.get_markets(active=True, limit=limit, order="startDate", ascending=False)
    cutoff = time.time() - (hours * 3600)
    results = []

    for m in markets:
        # Check creation time
        start_date = m.get("startDate", "")
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                if start_dt.timestamp() < cutoff:
                    continue
            except (ValueError, TypeError):
                continue

        yes_price, no_price = parse_outcomes_prices(m)

        results.append({
            "id": m.get("id", ""),
            "question": m.get("question", "")[:80],
            "yes_price": round(yes_price, 4),
            "no_price": round(no_price, 4),
            "volume_24h": float(m.get("volume24hr", 0) or 0),
            "liquidity": float(m.get("liquidity", 0) or 0),
            "start_date": start_date[:10] if start_date else "",
            "end_date": (m.get("endDate", "") or "")[:10],
        })

    return results


def scan_high_volume(client, limit: int = 30) -> list:
    """Scan top markets by 24h volume"""
    markets = client.get_markets(active=True, limit=limit, order="volume24hr")
    results = []

    for m in markets:
        yes_price, no_price = parse_outcomes_prices(m)
        vol = float(m.get("volume24hr", 0) or 0)
        if vol <= 0:
            continue

        results.append({
            "id": m.get("id", ""),
            "question": m.get("question", "")[:80],
            "yes_price": round(yes_price, 4),
            "no_price": round(no_price, 4),
            "volume_24h": vol,
            "volume_total": float(m.get("volume", 0) or 0),
            "liquidity": float(m.get("liquidity", 0) or 0),
            "end_date": (m.get("endDate", "") or "")[:10],
        })

    return results


def scan_by_tag(client, tag: str, limit: int = 50) -> list:
    """Scan markets filtered by tag"""
    markets = client.get_markets(tag=tag, active=True, limit=limit, order="volume24hr")
    results = []

    for m in markets:
        yes_price, no_price = parse_outcomes_prices(m)
        results.append({
            "id": m.get("id", ""),
            "question": m.get("question", "")[:80],
            "yes_price": round(yes_price, 4),
            "no_price": round(no_price, 4),
            "volume_24h": float(m.get("volume24hr", 0) or 0),
            "liquidity": float(m.get("liquidity", 0) or 0),
            "tags": m.get("tags", []),
            "end_date": (m.get("endDate", "") or "")[:10],
        })

    return results


def save_to_watchlist(markets: list) -> int:
    """Save discovered markets to DB watchlist"""
    conn = db_utils.get_connection()
    saved = 0
    for m in markets:
        market_id = m.get("id", "")
        if not market_id:
            continue
        db_utils.upsert_market(
            conn,
            market_id=market_id,
            question=m.get("question", ""),
            volume=m.get("volume_24h", 0),
            liquidity=m.get("liquidity", 0),
        )
        saved += 1
    conn.close()
    return saved


def main():
    parser = argparse.ArgumentParser(description="Polymarket Market Scanner")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--high-prob", action="store_true", help="90%+ high-probability markets")
    group.add_argument("--new", action="store_true", help="New markets (last 24h)")
    group.add_argument("--high-volume", action="store_true", help="Top markets by volume")
    group.add_argument("--tag", type=str, help="Filter by tag")
    group.add_argument("--search", type=str, help="Search markets by text")

    parser.add_argument("--threshold", type=float, default=0.90, help="Probability threshold for --high-prob")
    parser.add_argument("--hours", type=int, default=24, help="Hours lookback for --new")
    parser.add_argument("--limit", type=int, default=50, help="Max results")
    parser.add_argument("--pages", type=int, default=1, help="Pages to scan for --high-prob (each=100 markets)")
    parser.add_argument("--save", action="store_true", help="Save to DB watchlist")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")

    args = parser.parse_args()

    try:
        client = create_client()

        if args.high_prob:
            results = scan_high_prob(client, args.threshold, args.limit, args.pages)
            mode = "high_probability"
        elif args.new:
            results = scan_new_markets(client, args.hours, args.limit)
            mode = "new_markets"
        elif args.high_volume:
            results = scan_high_volume(client, args.limit)
            mode = "high_volume"
        elif args.tag:
            results = scan_by_tag(client, args.tag, args.limit)
            mode = f"tag:{args.tag}"
        elif args.search:
            results = []
            raw = client.search_markets(args.search, args.limit)
            for m in raw:
                yes_price, no_price = parse_outcomes_prices(m)
                results.append({
                    "id": m.get("id", ""),
                    "question": m.get("question", "")[:80],
                    "yes_price": round(yes_price, 4),
                    "no_price": round(no_price, 4),
                    "volume_24h": float(m.get("volume24hr", 0) or 0),
                    "liquidity": float(m.get("liquidity", 0) or 0),
                })
            mode = f"search:{args.search}"
        else:
            error("No scan mode specified")
            return

        if args.save and results:
            saved = save_to_watchlist(results)
            save_msg = f" ({saved} saved to watchlist)"
        else:
            save_msg = ""

        if args.json:
            success(
                data={"mode": mode, "count": len(results), "markets": results},
                message=f"Found {len(results)} markets{save_msg}",
            )
        else:
            # Pretty print
            if not results:
                print(f"No markets found for mode: {mode}")
                return

            if args.high_prob:
                headers = ["Question", "Side", "Price", "ROI%", "Ann.ROI%", "Days", "Vol24h", "Liq"]
                rows = [
                    [
                        r["question"][:50],
                        r["side"],
                        f"${r['price']:.2f}",
                        f"{r['roi_pct']:.1f}%",
                        f"{r['annualized_roi']:.0f}%",
                        r["days_to_expiry"],
                        f"${r['volume_24h']:,.0f}",
                        f"${r['liquidity']:,.0f}",
                    ]
                    for r in results
                ]
                print(table(headers, rows, f"High Probability Markets (>={args.threshold*100:.0f}%)"))
            elif args.high_volume:
                headers = ["Question", "YES", "NO", "Vol24h", "VolTotal", "Liq", "Ends"]
                rows = [
                    [
                        r["question"][:50],
                        f"${r['yes_price']:.2f}",
                        f"${r['no_price']:.2f}",
                        f"${r['volume_24h']:,.0f}",
                        f"${r['volume_total']:,.0f}",
                        f"${r['liquidity']:,.0f}",
                        r["end_date"],
                    ]
                    for r in results
                ]
                print(table(headers, rows, "Top Markets by 24h Volume"))
            else:
                headers = ["Question", "YES", "NO", "Vol24h", "Liq", "Ends"]
                rows = [
                    [
                        r["question"][:50],
                        f"${r.get('yes_price', 0):.2f}",
                        f"${r.get('no_price', 0):.2f}",
                        f"${r.get('volume_24h', 0):,.0f}",
                        f"${r.get('liquidity', 0):,.0f}",
                        r.get("end_date", ""),
                    ]
                    for r in results
                ]
                print(table(headers, rows, f"Markets ({mode})"))

            print(f"\nTotal: {len(results)} markets{save_msg}")

    except Exception as e:
        error(str(e), code="SCAN_ERROR")


if __name__ == "__main__":
    main()
