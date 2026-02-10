#!/usr/bin/env python3
"""Collect market data from CoinGecko and Fear & Greed Index"""

import sys
import json
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import COINGECKO_BASE, FEAR_GREED_URL, API_TIMEOUT_SECONDS
from db_utils import get_connection, insert_research
from output_format import success, error


def collect_coingecko():
    """Fetch top coins from CoinGecko"""
    url = f"{COINGECKO_BASE}/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 20,
        "page": 1,
        "sparkline": False,
        "price_change_percentage": "1h,24h,7d",
    }
    resp = requests.get(url, params=params, timeout=API_TIMEOUT_SECONDS)
    resp.raise_for_status()
    coins = resp.json()

    return [{
        "symbol": c["symbol"].upper(),
        "name": c["name"],
        "price": c["current_price"],
        "market_cap": c["market_cap"],
        "volume_24h": c["total_volume"],
        "change_1h": c.get("price_change_percentage_1h_in_currency"),
        "change_24h": c.get("price_change_percentage_24h_in_currency"),
        "change_7d": c.get("price_change_percentage_7d_in_currency"),
        "ath": c.get("ath"),
        "ath_change_pct": c.get("ath_change_percentage"),
    } for c in coins]


def collect_fear_greed():
    """Fetch Fear & Greed Index"""
    resp = requests.get(FEAR_GREED_URL, params={"limit": 7}, timeout=API_TIMEOUT_SECONDS)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    return [{
        "value": int(d["value"]),
        "classification": d["value_classification"],
        "timestamp": d["timestamp"],
    } for d in data]


def main():
    try:
        conn = get_connection()
        results = {}

        try:
            coins = collect_coingecko()
            insert_research(conn, "coingecko", "market", json.dumps(coins, ensure_ascii=False))
            results["coingecko_coins"] = len(coins)
        except Exception as e:
            results["coingecko_error"] = str(e)

        try:
            fng = collect_fear_greed()
            insert_research(conn, "alternative_me", "sentiment", json.dumps(fng, ensure_ascii=False))
            results["fear_greed"] = fng[0] if fng else None
        except Exception as e:
            results["fear_greed_error"] = str(e)

        conn.close()
        success(results, "Market data collected")

    except Exception as e:
        error(str(e), "COLLECT_MARKET_ERROR")


if __name__ == "__main__":
    main()
