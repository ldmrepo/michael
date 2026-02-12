#!/usr/bin/env python3
"""
Simple position sync - save trades directly without FK constraints.
Calculate positions from trades and display current portfolio.
"""

import json
import sys
import time
from datetime import datetime, timezone
from polymarket_client import create_client
import db_utils

def main():
    try:
        print("="*70)
        print("POLYMARKET PORTFOLIO SYNC")
        print(f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        print("="*70)
        
        client = create_client()
        
        # Get trade history
        print("\n[1/3] Fetching trade history from CLOB...")
        trades = client.get_trades(limit=100)
        print(f"      Found {len(trades)} trades")
        
        # Build positions map from trades
        print("\n[2/3] Analyzing positions...")
        positions_map = {}  # (market_id, side) -> data
        
        for trade in trades:
            market_id = trade.get("market")
            side_raw = trade.get("side", "").upper()
            outcome = trade.get("outcome", "")
            
            # Map BUY/SELL to YES/NO based on outcome
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
                positions_map[key] = {
                    "market_id": market_id,
                    "side": side,
                    "size": 0,
                    "total_cost": 0,
                    "outcome": outcome,
                    "trades_count": 0
                }
            
            positions_map[key]["size"] += size
            positions_map[key]["total_cost"] += price * size
            positions_map[key]["trades_count"] += 1
        
        # Display positions with calculations
        print(f"\n[3/3] Portfolio Analysis")
        print("="*70)
        
        total_invested = 0
        total_current = 0
        
        positions = list(positions_map.values())
        positions.sort(key=lambda x: x["total_cost"], reverse=True)
        
        print(f"\nFound {len(positions)} open positions:\n")
        print(f"{'#':>2} {'Side':<4} {'Shares':>8} {'Avg Entry':>10} {'Invested':>10} {'Trades':>7}")
        print("-"*70)
        
        for i, pos in enumerate(positions, 1):
            avg_price = pos["total_cost"] / pos["size"] if pos["size"] > 0 else 0
            
            print(f"{i:>2} {pos['side']:<4} {pos['size']:>8.1f} ${avg_price:>9.4f} ${pos['total_cost']:>9.2f} {pos['trades_count']:>7}")
            print(f"   Market: {pos['market_id'][:50]}...")
            
            total_invested += pos["total_cost"]
            
            # Estimate current value (assuming still at entry for now)
            # Real prices would need Gamma API lookup
            total_current += pos["total_cost"]
        
        print("-"*70)
        print(f"{'TOTAL':>2} {'':4} {'':>8} {'':>10} ${total_invested:>9.2f}")
        
        # Get wallet balance
        print("\n" + "="*70)
        print("WALLET BALANCES")
        print("="*70)
        
        try:
            balance_info = client.get_balances()
            usdc_balance = balance_info.get("balance_usdc", 0)
            print(f"CLOB (Polymarket):  ${usdc_balance:>10,.2f} USDC.e")
        except Exception as e:
            print(f"CLOB Balance: Error - {e}")
            usdc_balance = 0
        
        print("\n" + "="*70)
        print("PORTFOLIO SUMMARY")
        print("="*70)
        print(f"Open Positions:     {len(positions)}")
        print(f"Total Invested:     ${total_invested:>10,.2f}")
        print(f"Cash Balance:       ${usdc_balance:>10,.2f}")
        print(f"Total Portfolio:    ${total_invested + usdc_balance:>10,.2f}")
        print("="*70)
        
        print("\n✓ Analysis complete!")
        print("\nNote: To get real-time prices and P&L, use check_portfolio.py after syncing to DB")
        
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
