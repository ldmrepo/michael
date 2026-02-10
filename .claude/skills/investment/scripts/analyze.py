#!/usr/bin/env python3
"""
Aggregate research data and produce analysis JSON for Claude Agent
Outputs a structured report that TypeScript analysis-engine feeds to Claude
"""

import sys
import json
import argparse
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from db_utils import get_connection, get_latest_research, get_holdings, cleanup_old_research
from output_format import report, error


def aggregate_research(conn, hours: int = 24) -> dict:
    """Aggregate all recent research into a structured summary"""
    data = {}

    # Market data
    market = get_latest_research(conn, "market", hours)
    if market:
        for r in market:
            try:
                parsed = json.loads(r["data_json"])
                source = r["source"]
                if source not in data:
                    data[source] = parsed
                else:
                    if isinstance(data[source], list):
                        data[source].extend(parsed if isinstance(parsed, list) else [parsed])
                    else:
                        data[source] = parsed
            except Exception:
                pass

    # Derivatives
    derivatives = get_latest_research(conn, "derivatives", hours)
    data["derivatives"] = []
    for r in derivatives:
        try:
            parsed = json.loads(r["data_json"])
            data["derivatives"].append({
                "source": r["source"],
                "symbol": r.get("symbol"),
                "data": parsed,
            })
        except Exception:
            pass

    # Macro
    macro = get_latest_research(conn, "macro", hours)
    data["macro"] = []
    for r in macro:
        try:
            data["macro"].append(json.loads(r["data_json"]))
        except Exception:
            pass

    # Sentiment
    sentiment = get_latest_research(conn, "sentiment", hours)
    data["sentiment"] = []
    for r in sentiment:
        try:
            data["sentiment"].append(json.loads(r["data_json"]))
        except Exception:
            pass

    # ETF
    etf = get_latest_research(conn, "etf", hours)
    data["etf"] = []
    for r in etf:
        try:
            data["etf"].append({
                "symbol": r.get("symbol"),
                "data": json.loads(r["data_json"]),
            })
        except Exception:
            pass

    # News
    news = get_latest_research(conn, "news", hours)
    data["news"] = []
    for r in news:
        try:
            articles = json.loads(r["data_json"])
            if isinstance(articles, list):
                data["news"].extend(articles[:10])
            else:
                data["news"].append(articles)
        except Exception:
            pass

    # On-chain/DeFi
    onchain = get_latest_research(conn, "onchain", hours)
    data["onchain"] = []
    for r in onchain:
        try:
            data["onchain"].append(json.loads(r["data_json"]))
        except Exception:
            pass

    return data


def build_analysis_prompt(research: dict, holdings: list, analysis_type: str) -> str:
    """Build the prompt that TypeScript will send to Claude"""
    holdings_summary = []
    for h in holdings:
        price = h.get("current_price") or 0
        qty = h.get("quantity") or 0
        holdings_summary.append({
            "symbol": h["symbol"],
            "type": h["account_type"],
            "qty": qty,
            "value_usd": round(price * qty, 2),
            "unrealized_pnl": h.get("unrealized_pnl"),
        })

    prompt_data = {
        "analysis_type": analysis_type,
        "timestamp": int(time.time()),
        "portfolio": holdings_summary,
        "research": research,
    }

    return json.dumps(prompt_data, ensure_ascii=False, default=str)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", default="default")
    parser.add_argument("--daily", action="store_true")
    parser.add_argument("--weekly", action="store_true")
    parser.add_argument("--hours", type=int, default=24)
    args = parser.parse_args()

    analysis_type = "weekly" if args.weekly else "daily"
    hours = args.hours if not args.weekly else 168  # 7 days for weekly

    try:
        conn = get_connection()

        # Aggregate research
        research = aggregate_research(conn, hours)
        holdings = get_holdings(conn, args.user_id)

        # Cleanup old research data (30+ days)
        deleted = cleanup_old_research(conn, days=30)
        if deleted > 0:
            import sys as _sys
            print(f"Cleaned up {deleted} old research rows", file=_sys.stderr)

        # Build prompt data
        prompt_json = build_analysis_prompt(research, holdings, analysis_type)

        conn.close()

        # Output the aggregated data as a report
        # TypeScript analysis-engine will parse this and send to Claude
        report(prompt_json, {
            "analysis_type": analysis_type,
            "research_sources": list(research.keys()),
            "holdings_count": len(holdings),
            "hours": hours,
        })

    except Exception as e:
        error(str(e), "ANALYZE_ERROR")


if __name__ == "__main__":
    main()
