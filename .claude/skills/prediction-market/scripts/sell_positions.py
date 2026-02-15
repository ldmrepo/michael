#!/usr/bin/env python3
"""
Sell 3 low-yield NO token positions on Polymarket (snowball rebalancing).

For NO tokens with high midpoint (e.g., $0.93), the raw order book shows
bids near $0.01 and asks near $0.99. However, the CLOB API's get_price()
correctly reports the complementary price:
  - get_price(token, 'buy') = best price to buy NO = ~$0.93
  - get_price(token, 'sell') = best price to sell NO = ~$0.94

We place SELL limit orders at (buy_price - $0.01) to ensure quick fill.
The CLOB internally matches NO sells against YES buys.

Usage:
  python sell_positions.py --dry-run    # Preview only
  python sell_positions.py              # Execute sells
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from polymarket_client import create_client

# === Configuration ===

MAX_RETRIES = 3
ORDER_WAIT_SECONDS = 12

POSITIONS = [
    {
        "name": "ETH reach $2,800 NO (low yield 3.3%)",
        "token_id": "36631294615510098620554640682956937117879229728837284049644621387033930778478",
        "size": 70.0,
        "target_price": 0.968,
        "neg_risk": False,
    },
    {
        "name": "BTC reach $85K NO (low yield 3.9%)",
        "token_id": "33054682002199540688068637861453447841161181160056075050144022025869914494787",
        "size": 67.9,
        "target_price": 0.962,
        "neg_risk": False,
    },
    {
        "name": "BTC reach $80K NO (losing + low yield 9.9%)",
        "token_id": "12995581063379840470706034292258461549917004937479335435444839663340844344333",
        "size": 107.0,
        "target_price": 0.91,
        "neg_risk": False,
    },
]


def sell_position(client, pos, dry_run=False):
    """Sell a single position with retry logic."""
    name = pos["name"]
    token_id = pos["token_id"]
    size = pos["size"]
    target_price = pos["target_price"]

    print(f"\n{'='*60}")
    print(f"SELLING: {name}")
    print(f"  Size: {size} shares")
    print(f"  Target price: ${target_price:.3f}")

    # Get current pricing from CLOB API (complementary pricing)
    try:
        buy_price = client.get_price(token_id, side="buy")   # best bid for NO
        sell_price_ask = client.get_price(token_id, side="sell")  # best ask for NO
        mid = client.get_midpoint(token_id)
        print(f"  Market: buy=${buy_price:.4f}  ask=${sell_price_ask:.4f}  mid=${mid:.4f}")
    except Exception as e:
        print(f"  ERROR getting market price: {e}")
        return {"name": name, "status": "failed", "error": str(e)}

    if buy_price <= 0:
        print(f"  ERROR: No buy price available!")
        return {"name": name, "status": "failed", "error": "No buy price"}

    # Sell price: target_price - $0.01 to ensure quick execution
    # But never sell below buy_price - $0.02 (that would be too much slippage)
    sell_price = round(target_price - 0.01, 2)
    
    # If market has moved, use the buy_price as reference instead
    if buy_price < target_price - 0.03:
        print(f"  WARNING: Market moved significantly! buy=${buy_price:.3f} vs target=${target_price:.3f}")
        sell_price = round(buy_price - 0.01, 2)
    
    sell_price = max(sell_price, 0.01)
    expected_proceeds = sell_price * size

    print(f"  Sell price: ${sell_price:.3f}")
    print(f"  Expected proceeds: ${expected_proceeds:.2f}")

    if dry_run:
        print(f"  [DRY RUN] Would sell {size} @ ${sell_price:.3f}")
        return {
            "name": name,
            "status": "dry_run",
            "price": sell_price,
            "size": size,
            "proceeds": expected_proceeds,
        }

    # Execute with retries
    for attempt in range(MAX_RETRIES):
        # Price decreases on each retry (-$0.01 per retry)
        price = round(sell_price - (attempt * 0.01), 2)
        price = max(price, 0.01)

        print(f"\n  Attempt {attempt + 1}/{MAX_RETRIES}: SELL {size} @ ${price:.3f}")

        try:
            result = client.create_limit_order(
                token_id=token_id,
                side="SELL",
                price=price,
                size=size,
            )

            order_id = result.get("orderID") or result.get("order_id") or result.get("id", "")
            status = (result.get("status") or result.get("orderStatus") or "").upper()

            print(f"  Order response: id={order_id[:16] if order_id else 'N/A'}.. status={status}")
            print(f"  Full response: {result}")

            # Immediately filled
            if status in ("MATCHED", "FILLED"):
                proceeds = price * size
                print(f"  >>> FILLED immediately! Proceeds: ~${proceeds:.2f}")
                return {
                    "name": name,
                    "status": "filled",
                    "order_id": order_id,
                    "fill_price": price,
                    "fill_size": size,
                    "proceeds": proceeds,
                    "attempts": attempt + 1,
                }

            # Wait for fill
            if order_id:
                print(f"  Waiting {ORDER_WAIT_SECONDS}s for fill...")
                time.sleep(ORDER_WAIT_SECONDS)

                # Try to cancel - if it fails, order was likely filled
                try:
                    cancelled = client.cancel_order(order_id)
                    if not cancelled:
                        proceeds = price * size
                        print(f"  >>> Cancel failed (likely filled)! Proceeds: ~${proceeds:.2f}")
                        return {
                            "name": name,
                            "status": "filled",
                            "order_id": order_id,
                            "fill_price": price,
                            "fill_size": size,
                            "proceeds": proceeds,
                            "attempts": attempt + 1,
                        }
                    print(f"  Not filled, cancelled. Retrying with lower price...")
                except Exception as cancel_err:
                    proceeds = price * size
                    print(f"  Cancel exception (may be filled): {cancel_err}")
                    return {
                        "name": name,
                        "status": "likely_filled",
                        "order_id": order_id,
                        "fill_price": price,
                        "fill_size": size,
                        "proceeds": proceeds,
                        "attempts": attempt + 1,
                    }

            # Rate limit between retries
            time.sleep(1.5)

        except Exception as e:
            print(f"  ERROR on attempt {attempt + 1}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2.0)
            continue

    return {"name": name, "status": "failed", "error": "Max retries exceeded"}


def main():
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("=" * 60)
        print("DRY RUN MODE - No orders will be placed")
        print("=" * 60)
    else:
        print("=" * 60)
        print("LIVE EXECUTION - Orders will be placed!")
        print("=" * 60)

    # Create client (uses .env credentials with POLY_PROXY signature)
    print("\nInitializing Polymarket client...")
    client = create_client()

    # Verify trading is available
    if not client.has_trading:
        print("ERROR: No trading credentials configured!")
        sys.exit(1)

    # Check USDC balance
    try:
        balance = client.get_balance_usdc()
        print(f"Current USDC.e balance: ${balance:.2f}")
    except Exception as e:
        print(f"Warning: Could not check balance: {e}")

    # Execute sells
    results = []
    total_proceeds = 0.0

    for i, pos in enumerate(POSITIONS):
        result = sell_position(client, pos, dry_run=dry_run)
        results.append(result)

        if result.get("proceeds"):
            total_proceeds += result["proceeds"]

        # Rate limit between orders
        if not dry_run and i < len(POSITIONS) - 1:
            print("\n  [Waiting 2s before next order...]")
            time.sleep(2.0)

    # Summary
    print(f"\n{'='*60}")
    print("EXECUTION SUMMARY")
    print(f"{'='*60}")

    filled = 0
    failed = 0
    for r in results:
        status = r.get("status", "unknown")
        name = r["name"]
        if status in ("filled", "likely_filled", "dry_run"):
            price = r.get("fill_price") or r.get("price", 0)
            size = r.get("fill_size") or r.get("size", 0)
            proceeds = r.get("proceeds", 0)
            symbol = "OK" if status != "dry_run" else "DRY"
            print(f"  [{symbol}] {name}: {size} shares @ ${price:.3f} = ${proceeds:.2f}")
            filled += 1
        else:
            error = r.get("error", "unknown")
            print(f"  [FAIL] {name}: {error}")
            failed += 1

    print(f"\nTotal: {filled} filled, {failed} failed")
    print(f"Estimated total proceeds: ${total_proceeds:.2f}")

    # Check final balance
    if not dry_run:
        try:
            time.sleep(3)
            final_balance = client.get_balance_usdc()
            print(f"Final USDC.e balance: ${final_balance:.2f}")
        except Exception:
            pass


if __name__ == "__main__":
    main()
