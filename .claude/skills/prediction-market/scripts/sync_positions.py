#!/usr/bin/env python3
"""
Sync positions from Polymarket CLOB to local database.

Key fix: Properly nets BUY and SELL trades to calculate actual remaining positions.
Previous version accumulated BUY-only, resulting in ghost positions.

Logic:
  - BUY a side → +size (adding shares)
  - SELL a side → -size (removing shares)
  - Net position = sum of all BUY - sum of all SELL for each (market_id, side)
  - Only positions with net size > 0.1 are considered open
  - Positions with net size <= 0.1 are marked closed
"""

import sys
import time
from polymarket_client import create_client
import db_utils


def fetch_market_info(client, token_id):
    """Fetch market details from Gamma API using clob_token_ids (asset_id)."""
    try:
        result = client._gamma_get("/markets", {"clob_token_ids": token_id})
        if result and isinstance(result, list) and len(result) > 0:
            return result[0]
    except Exception as e:
        print(f"    [WARN] Gamma API lookup failed: {e}", file=sys.stderr)
    return None


def main():
    try:
        print("Connecting to Polymarket CLOB API...")
        client = create_client()

        # Get trade history to reconstruct positions
        print("Fetching trade history...")
        trades = client.get_trades(limit=100)
        print(f"Found {len(trades)} recent trades\n")

        # Connect to database
        conn = db_utils.get_connection()

        # Process trades to build NET positions
        print("=== BUILDING NET POSITIONS FROM TRADES ===\n")
        # Key: (market_id, outcome_side) → {net_size, weighted_cost, asset_id, trades}
        # outcome_side is YES or NO (the outcome token we hold)
        positions_map = {}

        for trade in trades:
            market_id = trade.get("market", "")
            asset_id = trade.get("asset_id", "")
            side_raw = trade.get("side", "").upper()  # BUY or SELL (trade direction)
            outcome = trade.get("outcome", "")  # Yes or No (outcome token)

            price = float(trade.get("price", 0))
            size = float(trade.get("size", 0))

            if not market_id or size <= 0:
                continue

            # Determine which outcome token we're holding
            # BUY Yes → holding YES tokens
            # BUY No → holding NO tokens
            # SELL Yes → reducing YES tokens
            # SELL No → reducing NO tokens
            if outcome == "Yes":
                outcome_side = "YES"
            else:
                outcome_side = "NO"

            key = (market_id, outcome_side)
            if key not in positions_map:
                positions_map[key] = {
                    "buy_size": 0,
                    "sell_size": 0,
                    "buy_cost": 0,  # total cost of buys
                    "asset_id": asset_id,
                    "trades": [],
                }

            if side_raw == "BUY":
                positions_map[key]["buy_size"] += size
                positions_map[key]["buy_cost"] += price * size
            elif side_raw == "SELL":
                positions_map[key]["sell_size"] += size

            positions_map[key]["trades"].append(trade)

        # Calculate net positions
        open_positions = []
        closed_positions = []

        for (market_id, outcome_side), data in positions_map.items():
            net_size = data["buy_size"] - data["sell_size"]
            if net_size < 0.1:
                closed_positions.append((market_id, outcome_side, net_size, data))
            else:
                avg_entry = data["buy_cost"] / data["buy_size"] if data["buy_size"] > 0 else 0
                open_positions.append((market_id, outcome_side, net_size, avg_entry, data))

        print(f"Total unique (market, side) combinations: {len(positions_map)}")
        print(f"  Open (net > 0): {len(open_positions)}")
        print(f"  Closed (net ≤ 0): {len(closed_positions)}\n")

        # Step 1: Close all existing open positions in DB (clean slate)
        existing_open = conn.execute(
            "SELECT id FROM pm_positions WHERE status = 'open'"
        ).fetchall()
        if existing_open:
            now = int(time.time())
            conn.execute(
                "UPDATE pm_positions SET status = 'closed', closed_at = ? WHERE status = 'open'",
                (now,)
            )
            conn.commit()
            print(f"  Closed {len(existing_open)} stale DB positions\n")

        # Step 2: Insert accurate open positions
        print("=== SAVING OPEN POSITIONS ===\n")
        for market_id, side, net_size, avg_entry, data in open_positions:
            invested = avg_entry * net_size

            print(f"Market: {market_id[:40]}...")
            print(f"  Side: {side}, Net Size: {net_size:.1f} (bought {data['buy_size']:.1f}, sold {data['sell_size']:.1f})")
            print(f"  Avg Entry: ${avg_entry:.4f}, Invested: ${invested:.2f}")

            # Fetch market details
            asset_id = data.get("asset_id", "")
            market_info = fetch_market_info(client, asset_id) if asset_id else None
            question = "Unknown"
            if market_info:
                question = market_info.get("question", "Unknown")
                print(f"  Question: {question[:60]}...")

            # Save market to DB
            try:
                db_utils.upsert_market(
                    conn,
                    market_id=market_id,
                    question=question,
                    slug=market_info.get("slug", "") if market_info else "",
                    outcomes=market_info.get("outcomes", ["Yes", "No"]) if market_info else ["Yes", "No"],
                    end_date=market_info.get("endDate", "") if market_info else "",
                    tags=market_info.get("tags", []) if market_info else [],
                    active=market_info.get("active", True) if market_info else True,
                    volume=float(market_info.get("volume", 0) or 0) if market_info else 0,
                    liquidity=float(market_info.get("liquidity", 0) or 0) if market_info else 0,
                )
            except Exception as e:
                print(f"    [WARN] Failed to save market: {e}")

            time.sleep(0.3)  # Rate limit for Gamma API

            # Insert new open position (fresh, not upsert to avoid doubling)
            try:
                cursor = conn.execute("""
                    INSERT INTO pm_positions (user_id, market_id, side, size, entry_price, current_price, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'open')
                """, ("default", market_id, side, round(net_size, 2), round(avg_entry, 4), round(avg_entry, 4)))
                conn.commit()
                pos_id = cursor.lastrowid
                print(f"  ✓ Saved as position ID {pos_id}\n")
            except Exception as e:
                print(f"  ✗ Error saving: {e}\n")
                import traceback
                traceback.print_exc()

        # Show summary
        summary = db_utils.get_portfolio_summary(conn, "default")
        print("=" * 60)
        print("PORTFOLIO SUMMARY:")
        print(f"  Open Positions: {summary['open_positions']}")
        print(f"  Total Invested: ${summary['total_invested']:,.2f}")
        print(f"  Realized P&L: ${summary['realized_pnl']:,.2f}")
        print(f"  Win Rate: {summary['win_rate']}%")
        print("=" * 60)

        conn.close()
        print("\n✓ Sync complete!")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
