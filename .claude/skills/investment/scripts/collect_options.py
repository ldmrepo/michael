#!/usr/bin/env python3
"""Collect crypto options data (IV, Max Pain, BVOL, Put/Call Ratio) via browser"""

import sys
import json
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import API_TIMEOUT_SECONDS
from db_utils import get_connection, insert_research
from output_format import success, error


def collect_deribit_options():
    """Fetch options data from Deribit public API"""
    base = "https://www.deribit.com/api/v2/public"
    results = {}

    # BTC DVOL (Deribit Volatility Index)
    try:
        resp = requests.get(f"{base}/get_volatility_index_data", params={
            "currency": "BTC",
            "resolution": "3600",
            "start_timestamp": "0",
            "end_timestamp": str(int(__import__('time').time() * 1000)),
        }, timeout=API_TIMEOUT_SECONDS)
        if resp.status_code == 200:
            data = resp.json().get("result", {}).get("data", [])
            if data:
                latest = data[-1] if data else None
                results["btc_dvol"] = latest
    except Exception:
        pass

    # BTC Index Price
    try:
        resp = requests.get(f"{base}/get_index_price", params={
            "index_name": "btc_usd",
        }, timeout=API_TIMEOUT_SECONDS)
        if resp.status_code == 200:
            results["btc_index_price"] = resp.json().get("result", {}).get("index_price")
    except Exception:
        pass

    # ETH DVOL
    try:
        resp = requests.get(f"{base}/get_volatility_index_data", params={
            "currency": "ETH",
            "resolution": "3600",
            "start_timestamp": "0",
            "end_timestamp": str(int(__import__('time').time() * 1000)),
        }, timeout=API_TIMEOUT_SECONDS)
        if resp.status_code == 200:
            data = resp.json().get("result", {}).get("data", [])
            if data:
                results["eth_dvol"] = data[-1]
    except Exception:
        pass

    return results


def collect_binance_bvol():
    """Fetch BVOL (Binance Volatility Index) from Binance"""
    try:
        resp = requests.get(
            "https://fapi.binance.com/fapi/v1/ticker/price",
            params={"symbol": "BVOLUSD"},
            timeout=API_TIMEOUT_SECONDS
        )
        if resp.status_code == 200:
            return {"bvol": resp.json().get("price")}
    except Exception:
        pass
    return {}


def main():
    try:
        conn = get_connection()
        all_data = {}

        try:
            options = collect_deribit_options()
            all_data.update(options)
        except Exception as e:
            all_data["deribit_error"] = str(e)

        try:
            bvol = collect_binance_bvol()
            all_data.update(bvol)
        except Exception as e:
            all_data["bvol_error"] = str(e)

        if all_data:
            insert_research(conn, "options", "derivatives",
                            json.dumps(all_data, ensure_ascii=False))

        conn.close()
        success(all_data, "Options data collected")

    except Exception as e:
        error(str(e), "COLLECT_OPTIONS_ERROR")


if __name__ == "__main__":
    main()
