#!/usr/bin/env python3
"""Collect DeFi data from DefiLlama"""

import sys
import json
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import DEFILLAMA_TVL_URL, DEFILLAMA_CHAINS_URL, API_TIMEOUT_SECONDS
from db_utils import get_connection, insert_research
from output_format import success, error


def collect_tvl():
    """Fetch top protocols by TVL"""
    resp = requests.get(DEFILLAMA_TVL_URL, timeout=API_TIMEOUT_SECONDS)
    resp.raise_for_status()
    protocols = resp.json()

    # Top 20 by TVL
    top = sorted(protocols, key=lambda p: p.get("tvl") or 0, reverse=True)[:20]
    return [{
        "name": p.get("name"),
        "symbol": p.get("symbol"),
        "tvl": p.get("tvl"),
        "chain": p.get("chain"),
        "change_1d": p.get("change_1d"),
        "change_7d": p.get("change_7d"),
        "category": p.get("category"),
    } for p in top]


def collect_chains():
    """Fetch chain TVLs"""
    resp = requests.get(DEFILLAMA_CHAINS_URL, timeout=API_TIMEOUT_SECONDS)
    resp.raise_for_status()
    chains = resp.json()

    return [{
        "name": c.get("name") or c.get("gecko_id"),
        "tvl": c.get("tvl"),
    } for c in chains[:15]]


def main():
    try:
        conn = get_connection()
        results = {}

        try:
            tvl_data = collect_tvl()
            insert_research(conn, "defillama", "onchain",
                            json.dumps({"protocols": tvl_data}, ensure_ascii=False))
            results["protocols"] = len(tvl_data)
        except Exception as e:
            results["tvl_error"] = str(e)

        try:
            chains_data = collect_chains()
            insert_research(conn, "defillama", "onchain",
                            json.dumps({"chains": chains_data}, ensure_ascii=False))
            results["chains"] = len(chains_data)
        except Exception as e:
            results["chains_error"] = str(e)

        conn.close()
        success(results, "DeFi data collected")

    except Exception as e:
        error(str(e), "COLLECT_DEFI_ERROR")


if __name__ == "__main__":
    main()
