#!/usr/bin/env python3
"""
Fetch stock quote using yfinance library.
More reliable than direct Yahoo Finance API calls.

Usage:
    python fetch-stock.py AAPL
    python fetch-stock.py 005930.KS  # Samsung Electronics
    python fetch-stock.py AAPL MSFT GOOGL  # Multiple symbols
"""

import sys
import json
import yfinance as yf


def fetch_stock(symbol: str) -> dict:
    """Fetch stock data for a single symbol."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info

        # Get fast_info for real-time data (more reliable)
        fast = ticker.fast_info

        # Determine if Korean stock
        is_korean = symbol.endswith('.KS') or symbol.endswith('.KQ')

        return {
            "symbol": symbol.upper(),
            "name": info.get("shortName") or info.get("longName") or symbol,
            "price": fast.last_price if hasattr(fast, 'last_price') else info.get("regularMarketPrice"),
            "previousClose": fast.previous_close if hasattr(fast, 'previous_close') else info.get("regularMarketPreviousClose"),
            "change": info.get("regularMarketChange"),
            "changePercent": info.get("regularMarketChangePercent"),
            "currency": info.get("currency", "KRW" if is_korean else "USD"),
            "exchange": info.get("exchange"),
            "marketState": info.get("marketState"),
            "dayHigh": info.get("dayHigh") or info.get("regularMarketDayHigh"),
            "dayLow": info.get("dayLow") or info.get("regularMarketDayLow"),
            "volume": info.get("volume") or info.get("regularMarketVolume"),
            "marketCap": info.get("marketCap"),
            "source": "yfinance"
        }
    except Exception as e:
        return {"error": f"Failed to fetch {symbol}: {str(e)}"}


def fetch_stocks(symbols: list) -> list:
    """Fetch stock data for multiple symbols."""
    results = []
    for symbol in symbols:
        result = fetch_stock(symbol)
        results.append(result)
    return results


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: fetch-stock.py SYMBOL [SYMBOL2 ...]"}))
        sys.exit(1)

    symbols = sys.argv[1:]

    if len(symbols) == 1:
        # Single symbol - return object
        result = fetch_stock(symbols[0])
        print(json.dumps(result))
    else:
        # Multiple symbols - return array
        results = fetch_stocks(symbols)
        print(json.dumps(results))


if __name__ == "__main__":
    main()
