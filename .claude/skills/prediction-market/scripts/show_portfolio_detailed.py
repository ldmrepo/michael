#!/usr/bin/env python3
"""
Detailed portfolio analysis with live prices and P&L.
Fetches market info and current prices from Gamma API.
"""

import json
import sys
import time
from datetime import datetime, timezone
from polymarket_client import create_client

def fetch_market_info_batch(client, market_ids, batch_size=5):
    """Fetch market info in batches to avoid rate limits"""
    markets = {}
    
    print(f"\nFetching market details for {len(market_ids)} markets...")
    
    for i in range(0, len(market_ids), batch_size):
        batch = market_ids[i:i+batch_size]
        print(f"  Batch {i//batch_size + 1}/{(len(market_ids) + batch_size - 1)//batch_size}...", end=" ")
        
        for market_id in batch:
            try:
                # Try getting all markets and filter
                result = client.get_markets(active=True, limit=1000)
                found = None
                for m in result:
                    if m.get("id") == market_id:
                        found = m
                        break
                
                if found:
                    markets[market_id] = found
                    print(".", end="", flush=True)
                else:
                    print("x", end="", flush=True)
                
                time.sleep(0.3)  # Rate limit
            except Exception as e:
                print(f"E", end="", flush=True)
        
        print()  # Newline after batch
    
    print(f"Successfully fetched {len(markets)}/{len(market_ids)} markets\n")
    return markets

def main():
    try:
        print("="*80)
        print("POLYMARKET PORTFOLIO - DETAILED ANALYSIS")
        print(f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        print("="*80)
        
        client = create_client()
        
        # Get trade history
        print("\n[1/4] Fetching trade history...")
        trades = client.get_trades(limit=100)
        
        # Build positions map
        print("[2/4] Analyzing positions...")
        positions_map = {}
        
        for trade in trades:
            market_id = trade.get("market")
            side_raw = trade.get("side", "").upper()
            outcome = trade.get("outcome", "")
            
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
                }
            
            positions_map[key]["size"] += size
            positions_map[key]["total_cost"] += price * size
        
        # Get unique market IDs
        market_ids = list(set(p["market_id"] for p in positions_map.values()))
        
        # Fetch market info
        print(f"[3/4] Fetching live market data...")
        markets = fetch_market_info_batch(client, market_ids)
        
        # Calculate P&L
        print("[4/4] Calculating P&L...")
        
        positions = []
        total_invested = 0
        total_current = 0
        total_pnl = 0
        
        for (market_id, side), pos_data in positions_map.items():
            avg_entry = pos_data["total_cost"] / pos_data["size"] if pos_data["size"] > 0 else 0
            invested = pos_data["total_cost"]
            
            market_info = markets.get(market_id, {})
            question = market_info.get("question", "Unknown Market")
            
            # Parse current prices
            prices_raw = market_info.get("outcomePrices", "")
            if isinstance(prices_raw, str):
                try:
                    prices = json.loads(prices_raw)
                except:
                    prices = []
            else:
                prices = prices_raw or []
            
            yes_price = float(prices[0]) if len(prices) > 0 else avg_entry
            no_price = float(prices[1]) if len(prices) > 1 else avg_entry
            
            current_price = yes_price if side == "YES" else no_price
            current_value = current_price * pos_data["size"]
            pnl = current_value - invested
            pnl_pct = (pnl / invested * 100) if invested > 0 else 0
            
            # Days to expiry
            end_date = market_info.get("endDate", "")
            days_left = None
            if end_date:
                try:
                    end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                    days_left = max((end_dt - datetime.now(timezone.utc)).days, 0)
                except:
                    pass
            
            # Liquidity
            liquidity = float(market_info.get("liquidity", 0) or 0)
            
            positions.append({
                "question": question,
                "side": side,
                "shares": pos_data["size"],
                "entry": avg_entry,
                "current": current_price,
                "invested": invested,
                "value": current_value,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "days_left": days_left,
                "liquidity": liquidity,
                "active": market_info.get("active", True),
            })
            
            total_invested += invested
            total_current += current_value
            total_pnl += pnl
        
        # Sort by invested amount
        positions.sort(key=lambda x: x["invested"], reverse=True)
        
        # Display results
        print("\n" + "="*80)
        print("OPEN POSITIONS")
        print("="*80)
        
        for i, p in enumerate(positions, 1):
            status = ""
            if not p["active"]:
                status = " [INACTIVE]"
            
            print(f"\n#{i} {p['question'][:72]}{status}")
            print(f"   Side: {p['side']:<4}  Shares: {p['shares']:>6.1f}  Entry: ${p['entry']:.4f}  Now: ${p['current']:.4f}")
            print(f"   Invested: ${p['invested']:>7.2f}  Value: ${p['value']:>7.2f}  P&L: ${p['pnl']:>+7.2f} ({p['pnl_pct']:>+6.1f}%)")
            days_str = f"{p['days_left']}d" if p['days_left'] is not None else "?"
            print(f"   Expires: {days_str:<6}  Liquidity: ${p['liquidity']:>,.0f}")
        
        # Get wallet balance
        print("\n" + "="*80)
        print("WALLET & SUMMARY")
        print("="*80)
        
        try:
            balance_info = client.get_balances()
            cash = balance_info.get("balance_usdc", 0)
        except:
            cash = 0
        
        total_portfolio = total_current + cash
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
        
        print(f"\nCash (USDC.e):      ${cash:>10,.2f}")
        print(f"Invested:           ${total_invested:>10,.2f}")
        print(f"Current Value:      ${total_current:>10,.2f}")
        print(f"Unrealized P&L:     ${total_pnl:>+10,.2f} ({total_pnl_pct:>+6.1f}%)")
        print(f"{'─'*40}")
        print(f"Total Portfolio:    ${total_portfolio:>10,.2f}")
        print("\n" + "="*80)
        
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
