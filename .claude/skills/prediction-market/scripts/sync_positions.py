#!/usr/bin/env python3
"""
Sync positions from Polymarket CLOB to local database.
"""

import json
import sys
import time
from polymarket_client import create_client
import db_utils

def fetch_market_info(client, token_id):
    """Fetch market details from Gamma API using clob_token_ids (asset_id).

    The CLOB trade's 'asset_id' field maps to Gamma's 'clob_token_ids' param.
    This returns exactly 1 matching market, unlike condition_id which returns many.
    """
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
        
        # Process trades to build positions
        print("=== BUILDING POSITIONS FROM TRADES ===\n")
        positions_map = {}  # (market_id, side) -> accumulated size & avg entry price
        
        for trade in trades:
            market_id = trade.get("market", "")
            asset_id = trade.get("asset_id", "")
            side_raw = trade.get("side", "").upper()
            outcome = trade.get("outcome", "")

            # Map side: "BUY" means buying outcome shares
            # For negative markets (outcome=No), BUY No = betting on NO
            if side_raw == "BUY":
                side = "YES" if outcome == "Yes" else "NO"
            else:
                side = "NO" if outcome == "Yes" else "YES"

            price = float(trade.get("price", 0))
            size = float(trade.get("size", 0))

            if not market_id:
                continue

            key = (market_id, side)
            if key not in positions_map:
                positions_map[key] = {"size": 0, "total_cost": 0, "trades": [], "asset_id": asset_id}

            positions_map[key]["size"] += size
            positions_map[key]["total_cost"] += price * size
            positions_map[key]["trades"].append(trade)
        
        print(f"Found {len(positions_map)} unique positions\n")
        
        # Save positions to database with market info
        for (market_id, side), data in positions_map.items():
            if data["size"] <= 0:
                continue
            
            avg_entry_price = data["total_cost"] / data["size"] if data["size"] > 0 else 0
            
            print(f"Market ID: {market_id[:40]}...")
            print(f"  Side: {side}")
            print(f"  Size: {data['size']:.1f}")
            print(f"  Avg Entry: ${avg_entry_price:.4f}")
            print(f"  Invested: ${data['total_cost']:.2f}")
            
            # Fetch market details via asset_id (clob_token_ids in Gamma API)
            asset_id = data.get("asset_id", "")
            market_info = fetch_market_info(client, asset_id) if asset_id else None
            question = "Unknown"
            if market_info:
                question = market_info.get("question", "Unknown")
                print(f"  Question: {question[:60]}...")

            # Save market to DB (always - even as placeholder to satisfy FK)
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

            time.sleep(0.3)  # Rate limit
            
            # Record position in DB
            try:
                pos_id = db_utils.upsert_position(
                    conn,
                    market_id=market_id,
                    side=side,
                    size=data["size"],
                    entry_price=avg_entry_price,
                    user_id="default",
                    current_price=avg_entry_price,  # Will be updated by price monitor
                    status="open"
                )
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
