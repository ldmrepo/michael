#!/usr/bin/env python3
"""Collect Binance Smart Money / Copy Trading data (browser)"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from patchright.sync_api import sync_playwright
from config import BINANCE_SMART_MONEY_URL, PAGE_LOAD_TIMEOUT
from browser_utils import BrowserFactory, StealthUtils
from db_utils import get_connection, insert_research
from output_format import success, error


def scrape_smart_money(page) -> dict:
    """Scrape Smart Money data from Binance"""
    page.goto("https://www.binance.com/en/copy-trading/lead-details",
              wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
    StealthUtils.random_delay(3000, 5000)

    data = {}

    try:
        # Try to extract top traders data
        traders_data = page.evaluate("""() => {
            const cards = document.querySelectorAll('[class*="trader"], [class*="lead"], [class*="copy"]');
            const result = [];
            cards.forEach((card, i) => {
                if (i >= 10) return;
                const text = card.textContent || '';
                result.push(text.substring(0, 200));
            });
            return result;
        }""")
        data["top_traders"] = traders_data
    except Exception:
        pass

    try:
        # Try to get trading signals/insights
        page.goto("https://www.binance.com/en/trading-insight",
                   wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
        StealthUtils.random_delay(2000, 4000)

        insights = page.evaluate("""() => {
            const items = document.querySelectorAll('[class*="insight"], [class*="signal"], [class*="smart"]');
            const result = [];
            items.forEach((item, i) => {
                if (i >= 10) return;
                result.push(item.textContent.trim().substring(0, 300));
            });
            return result;
        }""")
        data["trading_insights"] = insights
    except Exception:
        pass

    return data


def main():
    playwright = None
    context = None

    try:
        playwright = sync_playwright().start()
        context = BrowserFactory.launch_persistent_context(playwright, headless=True)
        page = context.new_page()

        data = scrape_smart_money(page)

        if data:
            conn = get_connection()
            insert_research(conn, "binance_browser", "sentiment",
                            json.dumps(data, ensure_ascii=False))
            conn.close()

        success({"fields": list(data.keys())}, "Smart Money data collected")

    except Exception as e:
        error(str(e), "COLLECT_SMART_MONEY_ERROR")
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
