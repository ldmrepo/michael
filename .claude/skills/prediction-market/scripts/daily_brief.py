#!/usr/bin/env python3
"""
Daily briefing for Prediction Market portfolio
Aggregates portfolio, price changes, expiring markets, and opportunities
"""

import argparse
import json
import time
from datetime import datetime, timedelta, timezone

import db_utils
import output_format


def get_price_changes_24h(conn, watchlist):
    """Get significant price changes in the last 24 hours"""
    cutoff = int(time.time()) - 86400
    changes = []

    for market in watchlist:
        mid = market["id"]
        # Get current and 24h-ago prices
        current = conn.execute(
            "SELECT * FROM pm_prices WHERE market_id = ? ORDER BY recorded_at DESC, id DESC LIMIT 1",
            (mid,)
        ).fetchone()
        if not current:
            continue

        old = conn.execute(
            "SELECT * FROM pm_prices WHERE market_id = ? AND recorded_at <= ? ORDER BY recorded_at DESC, id DESC LIMIT 1",
            (mid, cutoff)
        ).fetchone()
        if not old:
            continue

        yes_now = current["yes_price"] or 0
        yes_old = old["yes_price"] or 0
        if yes_old > 0:
            change_pct = ((yes_now - yes_old) / yes_old) * 100
            if abs(change_pct) >= 3:  # 3%+ change
                changes.append({
                    "market_id": mid,
                    "question": market["question"][:60],
                    "yes_price": round(yes_now, 3),
                    "prev_price": round(yes_old, 3),
                    "change_pct": round(change_pct, 1),
                    "volume_24h": current["volume_24h"] or 0,
                })

    # Sort by absolute change
    changes.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return changes[:10]


def get_expiring_markets(conn, days=7):
    """Get markets expiring within N days"""
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=days)
    cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    rows = conn.execute(
        """SELECT * FROM pm_markets
           WHERE active = 1 AND end_date != '' AND end_date <= ?
           ORDER BY end_date ASC LIMIT 10""",
        (cutoff_str,)
    ).fetchall()
    return [dict(r) for r in rows]


def generate_brief(conn, user_id="default"):
    """Generate the daily briefing data"""
    # Portfolio summary
    portfolio = db_utils.get_portfolio_summary(conn, user_id)

    # Watchlist
    watchlist = db_utils.get_watchlist(conn)

    # Open positions with market info
    open_positions = db_utils.get_positions(conn, user_id, "open")
    positions_detail = []
    for pos in open_positions:
        market = db_utils.get_market(conn, pos["market_id"])
        latest = db_utils.get_latest_price(conn, pos["market_id"])
        positions_detail.append({
            "market_id": pos["market_id"],
            "question": (market["question"][:50] if market else "Unknown")[:50],
            "side": pos["side"],
            "size": pos["size"],
            "entry_price": pos["entry_price"],
            "current_price": latest["yes_price"] if latest and pos["side"] == "YES" else (latest["no_price"] if latest else None),
        })

    # Price changes
    price_changes = get_price_changes_24h(conn, watchlist)

    # Expiring markets
    expiring = get_expiring_markets(conn, days=7)
    expiring_summary = [
        {
            "question": m["question"][:50],
            "end_date": m["end_date"][:10],
            "market_id": m["id"],
        }
        for m in expiring
    ]

    # Recent high-prob scan count (markets with YES/NO > 0.85)
    high_prob_count = 0
    for m in watchlist:
        latest = db_utils.get_latest_price(conn, m["id"])
        if latest:
            yes_p = latest["yes_price"] or 0
            no_p = latest["no_price"] or 0
            if yes_p >= 0.85 or no_p >= 0.85:
                high_prob_count += 1

    # Format report text
    report_lines = []
    report_lines.append("📊 Prediction Market Daily Brief\n")

    # Portfolio
    report_lines.append(
        f"💰 포지션: {portfolio['open_positions']}개 | "
        f"투자: ${portfolio['total_invested']:,.0f} | "
        f"실현 P&L: ${portfolio['realized_pnl']:+,.2f}"
    )
    if portfolio['closed_positions'] > 0:
        report_lines.append(
            f"📈 승률: {portfolio['win_rate']}% "
            f"({portfolio['win_count']}W / {portfolio['loss_count']}L)"
        )
    report_lines.append(f"🎯 워치리스트: {len(watchlist)} 마켓\n")

    # Positions
    if positions_detail:
        report_lines.append("📋 오픈 포지션:")
        for p in positions_detail:
            cp = p["current_price"]
            cp_str = f"${cp:.2f}" if cp is not None else "N/A"
            pnl = ""
            if cp is not None:
                diff = (cp - p["entry_price"]) * p["size"]
                pnl = f" | P&L: ${diff:+.2f}"
            report_lines.append(
                f"  {p['side']} {p['size']:.0f} @ ${p['entry_price']:.2f} → {cp_str}{pnl}"
            )
            report_lines.append(f"    {p['question']}")
        report_lines.append("")

    # Price changes
    if price_changes:
        report_lines.append("📈 주요 변동 (24h):")
        for c in price_changes[:5]:
            arrow = "▲" if c["change_pct"] > 0 else "▼"
            report_lines.append(
                f"  {arrow} {c['change_pct']:+.1f}% \"{c['question']}\" YES ${c['yes_price']:.2f}"
            )
        report_lines.append("")

    # Expiring
    if expiring_summary:
        report_lines.append("⏰ 만기 임박 (7일):")
        for e in expiring_summary[:5]:
            report_lines.append(f"  • \"{e['question']}\" - {e['end_date']}")
        report_lines.append("")

    # Opportunities
    if high_prob_count > 0:
        report_lines.append(f"🔍 고확률 기회: {high_prob_count}개 (YES/NO > 85%)")

    report_text = "\n".join(report_lines)

    data = {
        "portfolio": portfolio,
        "positions": positions_detail,
        "watchlist_count": len(watchlist),
        "price_changes": price_changes,
        "expiring_markets": expiring_summary,
        "high_prob_opportunities": high_prob_count,
    }

    return report_text, data


def main():
    parser = argparse.ArgumentParser(description="PM Daily Briefing")
    parser.add_argument("--user-id", default="default")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    try:
        conn = db_utils.get_connection()
        report_text, data = generate_brief(conn, args.user_id)
        conn.close()

        if args.json:
            output_format.report(report_text, data=data)
        else:
            print(report_text)
    except Exception as e:
        if args.json:
            output_format.error(str(e), code="BRIEF_ERROR")
        else:
            print(f"Error: {e}")
            raise


if __name__ == "__main__":
    main()
