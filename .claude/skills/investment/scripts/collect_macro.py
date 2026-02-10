#!/usr/bin/env python3
"""Collect macro economic data from FRED"""

import sys
import json
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import FRED_API_KEY, FRED_BASE, FRED_SERIES, API_TIMEOUT_SECONDS
from db_utils import get_connection, insert_research
from output_format import success, error


def fetch_fred_series(series_id: str, limit: int = 5) -> list:
    """Fetch latest observations from FRED"""
    if not FRED_API_KEY:
        return []

    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit,
    }
    resp = requests.get(FRED_BASE, params=params, timeout=API_TIMEOUT_SECONDS)
    resp.raise_for_status()
    observations = resp.json().get("observations", [])
    return [{
        "date": o["date"],
        "value": float(o["value"]) if o["value"] != "." else None,
    } for o in observations]


def main():
    try:
        conn = get_connection()
        results = {}

        if not FRED_API_KEY:
            error("FRED_API_KEY not set", "MISSING_API_KEY")
            return

        for name, series_id in FRED_SERIES.items():
            try:
                data = fetch_fred_series(series_id)
                if data:
                    insert_research(conn, "fred", "macro",
                                    json.dumps({"series": name, "data": data}, ensure_ascii=False))
                    results[name] = data[0] if data else None
            except Exception as e:
                results[f"{name}_error"] = str(e)

        conn.close()
        success(results, f"FRED data collected: {len(results)} series")

    except Exception as e:
        error(str(e), "COLLECT_MACRO_ERROR")


if __name__ == "__main__":
    main()
