#!/usr/bin/env python3
"""
Portfolio Check — Current positions, live prices, P&L, and wallet balances.

Usage:
  python check_portfolio.py           # Full portfolio report
  python check_portfolio.py --json    # JSON output
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone

import db_utils
from polymarket_client import create_client
from config import POLYMARKET_PROXY_WALLET


def get_live_prices_gamma(client, market_ids, conn=None):
    """Fetch current prices from Gamma API using slug (stored in DB).

    The market_ids stored in DB are condition_ids which don't work with
    Gamma's ?id= parameter. Instead, use slug from pm_markets table.
    """
    prices = {}
    for mid in market_ids:
        try:
            # Get slug from DB
            slug = None
            if conn:
                row = conn.execute("SELECT slug, question FROM pm_markets WHERE id = ?", (mid,)).fetchone()
                if row:
                    slug = row["slug"]

            # Query by slug (reliable) or fall back to condition_id
            market = None
            if slug:
                result = client._gamma_get("/markets", {"slug": slug})
                if result and isinstance(result, list) and len(result) > 0:
                    market = result[0]

            if not market:
                # Fallback: try condition_id
                try:
                    result = client._gamma_get("/markets", {"condition_id": mid})
                    if result and isinstance(result, list) and len(result) > 0:
                        market = result[0]
                except Exception:
                    pass

            if market:
                prices_raw = market.get("outcomePrices", "")
                if isinstance(prices_raw, str):
                    try:
                        p = json.loads(prices_raw)
                    except (json.JSONDecodeError, TypeError):
                        p = []
                else:
                    p = prices_raw or []

                yes_price = float(p[0]) if len(p) > 0 else 0
                no_price = float(p[1]) if len(p) > 1 else 0

                prices[mid] = {
                    "yes_price": yes_price,
                    "no_price": no_price,
                    "question": market.get("question", ""),
                    "active": market.get("active", False),
                    "closed": market.get("closed", False),
                    "end_date": market.get("endDate", ""),
                    "volume_24h": float(market.get("volume24hr", 0) or 0),
                    "liquidity": float(market.get("liquidity", 0) or 0),
                }
            time.sleep(0.2)  # Rate limit
        except Exception as e:
            print(f"  [WARN] Failed to fetch price for {mid}: {e}", file=sys.stderr)
    return prices


def main():
    parser = argparse.ArgumentParser(description="Polymarket Portfolio Check")
    parser.add_argument("--user-id", default="default")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    # 1. Get positions from DB
    conn = db_utils.get_connection()
    open_positions = db_utils.get_positions(conn, args.user_id, "open")
    closed_positions = db_utils.get_positions(conn, args.user_id, "closed")
    settled_positions = db_utils.get_positions(conn, args.user_id, "settled")

    # 2. Get unique market IDs
    market_ids = list(set(p["market_id"] for p in open_positions))

    # 3. Fetch live prices from Gamma API
    client = create_client()
    print("Fetching live prices from Gamma API...", file=sys.stderr)
    live_prices = get_live_prices_gamma(client, market_ids, conn=conn)

    # 4. Get wallet balances
    print("Fetching wallet balances...", file=sys.stderr)
    wallet = {}
    try:
        from wallet_utils import check_balances
        eoa_balance = check_balances()
        wallet["eoa"] = eoa_balance
    except Exception as e:
        wallet["eoa_error"] = str(e)

    try:
        proxy_balance = {}
        if POLYMARKET_PROXY_WALLET:
            from wallet_utils import check_balances as cb
            proxy_balance = cb(POLYMARKET_PROXY_WALLET)
        wallet["proxy"] = proxy_balance
    except Exception as e:
        wallet["proxy_error"] = str(e)

    # CLOB balance (Polymarket internal)
    try:
        clob_balance = client.get_balances()
        wallet["clob"] = clob_balance
    except Exception as e:
        wallet["clob_error"] = str(e)

    # 5. Calculate P&L for each open position
    positions_report = []
    total_invested = 0
    total_current_value = 0
    total_unrealized_pnl = 0

    for pos in open_positions:
        mid = pos["market_id"]
        live = live_prices.get(mid, {})

        side = pos["side"]
        size = pos["size"]
        entry_price = pos["entry_price"]
        invested = entry_price * size

        if side == "YES":
            current_price = live.get("yes_price", pos.get("current_price") or entry_price)
        else:
            current_price = live.get("no_price", pos.get("current_price") or entry_price)

        current_value = current_price * size
        unrealized_pnl = current_value - invested
        pnl_pct = (unrealized_pnl / invested * 100) if invested > 0 else 0

        # Days to expiry
        end_date_str = live.get("end_date", "")
        days_to_expiry = None
        if end_date_str:
            try:
                end_dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                days_to_expiry = max((end_dt - datetime.now(timezone.utc)).days, 0)
            except Exception:
                pass

        # Max profit if settled at $1
        max_profit = (1.0 - entry_price) * size if side in ("YES", "NO") else 0
        max_roi_pct = ((1.0 - entry_price) / entry_price * 100) if entry_price > 0 else 0

        position_data = {
            "market_id": mid,
            "question": live.get("question", pos.get("market_id", "Unknown"))[:70],
            "side": side,
            "size": size,
            "entry_price": round(entry_price, 4),
            "current_price": round(current_price, 4),
            "invested": round(invested, 2),
            "current_value": round(current_value, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "pnl_pct": round(pnl_pct, 1),
            "max_profit": round(max_profit, 2),
            "max_roi_pct": round(max_roi_pct, 1),
            "days_to_expiry": days_to_expiry,
            "active": live.get("active", None),
            "closed": live.get("closed", None),
        }
        positions_report.append(position_data)

        total_invested += invested
        total_current_value += current_value
        total_unrealized_pnl += unrealized_pnl

    # Sort by invested amount descending
    positions_report.sort(key=lambda x: x["invested"], reverse=True)

    # 6. Closed positions summary
    realized_pnl = sum(p.get("pnl", 0) or 0 for p in closed_positions)
    win_count = sum(1 for p in closed_positions if (p.get("pnl", 0) or 0) > 0)
    loss_count = sum(1 for p in closed_positions if (p.get("pnl", 0) or 0) < 0)

    # 7. Extract USDC cash balance
    cash_usdc = wallet.get("clob", {}).get("balance_usdc", 0)
    proxy_usdc_e = wallet.get("proxy", {}).get("usdc_e_balance", 0)
    eoa_usdc_e = wallet.get("eoa", {}).get("usdc_e_balance", 0)
    eoa_pol = wallet.get("eoa", {}).get("pol_balance", 0)

    # Total portfolio value
    total_portfolio = total_current_value + cash_usdc

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "open_positions_count": len(open_positions),
        "closed_positions_count": len(closed_positions),
        "total_invested": round(total_invested, 2),
        "total_current_value": round(total_current_value, 2),
        "total_unrealized_pnl": round(total_unrealized_pnl, 2),
        "unrealized_pnl_pct": round(total_unrealized_pnl / total_invested * 100, 1) if total_invested > 0 else 0,
        "realized_pnl": round(realized_pnl, 2),
        "win_count": win_count,
        "loss_count": loss_count,
        "cash_usdc": round(cash_usdc, 2),
        "total_portfolio_value": round(total_portfolio, 2),
        "positions": positions_report,
        "wallet": wallet,
    }

    if args.json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        # Pretty print
        print(f"\n{'='*70}")
        print(f"  POLYMARKET PORTFOLIO STATUS")
        print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"{'='*70}")

        print(f"\n  WALLET BALANCES:")
        print(f"  {'─'*40}")
        print(f"  CLOB (Polymarket):  ${cash_usdc:>10,.2f} USDC.e")
        print(f"  Proxy Wallet:       ${proxy_usdc_e:>10,.6f} USDC.e")
        print(f"  EOA:                ${eoa_usdc_e:>10,.6f} USDC.e")
        print(f"  EOA:                {eoa_pol:>10,.4f} POL")

        print(f"\n  PORTFOLIO SUMMARY:")
        print(f"  {'─'*40}")
        print(f"  Open Positions:     {len(open_positions)}")
        print(f"  Total Invested:     ${total_invested:>10,.2f}")
        print(f"  Current Value:      ${total_current_value:>10,.2f}")
        print(f"  Unrealized P&L:     ${total_unrealized_pnl:>+10,.2f} ({summary['unrealized_pnl_pct']:+.1f}%)")
        print(f"  Cash:               ${cash_usdc:>10,.2f}")
        print(f"  {'─'*40}")
        print(f"  TOTAL PORTFOLIO:    ${total_portfolio:>10,.2f}")

        if closed_positions:
            print(f"\n  CLOSED POSITIONS:")
            print(f"  Realized P&L:       ${realized_pnl:>+10,.2f}")
            print(f"  Win/Loss:           {win_count}W / {loss_count}L")
            wr = round(win_count / (win_count + loss_count) * 100, 1) if (win_count + loss_count) > 0 else 0
            print(f"  Win Rate:           {wr}%")

        if positions_report:
            print(f"\n  {'─'*70}")
            print(f"  OPEN POSITIONS ({len(positions_report)}):")
            print(f"  {'─'*70}")
            print(f"  {'#':>2} {'Side':<4} {'Size':>5} {'Entry':>7} {'Now':>7} {'Invested':>9} {'P&L':>9} {'P&L%':>7} {'Days':>5}")
            print(f"  {'─'*70}")

            for i, p in enumerate(positions_report, 1):
                days_str = str(p["days_to_expiry"]) if p["days_to_expiry"] is not None else "?"
                pnl_str = f"${p['unrealized_pnl']:>+7,.2f}"
                status = ""
                if p.get("closed"):
                    status = " [CLOSED]"
                elif not p.get("active"):
                    status = " [INACTIVE]"

                print(f"  {i:>2} {p['side']:<4} {p['size']:>5.0f} ${p['entry_price']:.4f} ${p['current_price']:.4f} ${p['invested']:>8,.2f} {pnl_str} {p['pnl_pct']:>+6.1f}% {days_str:>5}")
                # Truncate question for display
                q = p["question"][:65]
                print(f"     {q}{status}")

            print(f"  {'─'*70}")
            print(f"  {'TOTAL':>7} {'':4} {'':5} {'':7} {'':7} ${total_invested:>8,.2f} ${total_unrealized_pnl:>+7,.2f} {summary['unrealized_pnl_pct']:>+6.1f}%")
        else:
            print(f"\n  No open positions found in database.")
            print(f"  Positions may need to be synced from Polymarket.")

        print(f"\n{'='*70}\n")

    conn.close()


if __name__ == "__main__":
    main()
