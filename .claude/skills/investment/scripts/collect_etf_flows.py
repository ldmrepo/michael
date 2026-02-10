#!/usr/bin/env python3
"""Collect Bitcoin/Ethereum ETF flow data from Farside Investors (browser)"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from patchright.sync_api import sync_playwright
from config import FARSIDE_ETF_URL, FARSIDE_ETH_ETF_URL, PAGE_LOAD_TIMEOUT
from browser_utils import BrowserFactory, StealthUtils
from db_utils import get_connection, insert_research
from output_format import success, error


def scrape_farside_table(page, url: str) -> list:
    """Scrape ETF flow table from Farside"""
    page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
    StealthUtils.random_delay(2000, 4000)

    # Try to find the main data table
    rows_data = []
    try:
        # Wait for table to load
        page.wait_for_selector("table", timeout=15000)

        # Extract table data using JavaScript
        data = page.evaluate("""() => {
            const tables = document.querySelectorAll('table');
            if (tables.length === 0) return [];

            const table = tables[0];
            const rows = table.querySelectorAll('tr');
            const result = [];

            for (let i = 0; i < Math.min(rows.length, 15); i++) {
                const cells = rows[i].querySelectorAll('td, th');
                const row = [];
                cells.forEach(cell => row.push(cell.textContent.trim()));
                if (row.length > 0) result.push(row);
            }
            return result;
        }""")
        rows_data = data
    except Exception as e:
        rows_data = [{"error": str(e)}]

    return rows_data


def main():
    playwright = None
    context = None

    try:
        playwright = sync_playwright().start()
        context = BrowserFactory.launch_persistent_context(playwright, headless=True)
        page = context.new_page()
        results = {}

        # BTC ETF
        try:
            btc_data = scrape_farside_table(page, FARSIDE_ETF_URL)
            if btc_data:
                conn = get_connection()
                insert_research(conn, "farside", "etf",
                                json.dumps({"btc_etf_flows": btc_data}, ensure_ascii=False),
                                symbol="BTC")
                conn.close()
                results["btc_etf_rows"] = len(btc_data)
        except Exception as e:
            results["btc_etf_error"] = str(e)

        # ETH ETF
        try:
            eth_data = scrape_farside_table(page, FARSIDE_ETH_ETF_URL)
            if eth_data:
                conn = get_connection()
                insert_research(conn, "farside", "etf",
                                json.dumps({"eth_etf_flows": eth_data}, ensure_ascii=False),
                                symbol="ETH")
                conn.close()
                results["eth_etf_rows"] = len(eth_data)
        except Exception as e:
            results["eth_etf_error"] = str(e)

        success(results, "ETF flow data collected")

    except Exception as e:
        error(str(e), "COLLECT_ETF_ERROR")
    finally:
        if context:
            try:
                context.close()
            except Exception:
                pass
        if playwright:
            try:
                playwright.stop()
            except Exception:
                pass


if __name__ == "__main__":
    main()
