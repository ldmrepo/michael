#!/usr/bin/env python3
"""
Sell 3 risky positions (Tier 1 risk reduction) + Buy BTC $55K NO (Option A reinvestment).

Step 1: SELL Khamenei NO (94 shares)
Step 2: SELL BTC $60K NO (13.5 shares)
Step 3: SELL BTC $80K NO (16 shares)
Step 4: BUY BTC $55K NO (~100 shares with recovered cash)

Usage:
  python sell_risk_positions.py --dry-run    # Preview only
  python sell_risk_positions.py              # Execute
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from polymarket_client import create_client

MAX_RETRIES = 3
ORDER_WAIT_SECONDS = 12

# === SELL positions (Tier 1 risk reduction) ===
SELLS = [
    {
        "name": "Khamenei Out NO (R:R 1:5.5, worst risk)",
        "token_id": "46746822541461330721074821991383617225657173789584499857683753079229786702095",
        "size": 94.0,
        "neg_risk": False,
    },
    {
        "name": "BTC dip $60K Feb NO (R:R 1:4.1)",
        "token_id": "108429706881050535136553495584290453237980841377573952900810709890585276168668",
        "size": 13.5,
        "neg_risk": False,
    },
    {
        "name": "BTC reach $80K Feb NO (R:R 1:5.9)",
        "token_id": "12995581063379840470706034292258461549917004937479335435444839663340844344333",
        "size": 16.0,
        "neg_risk": False,
    },
]

# === BUY position (Option A reinvestment) ===
BUY = {
    "name": "BTC dip $55K Feb NO (93% confidence, safe snowball)",
    "token_id": "14508138056322224915688949573192229922802851672435344101150518068118489796467",
    "neg_risk": False,
}


def get_sell_price(client, token_id):
    """Get optimal sell price for a NO token."""
    buy_price = client.get_price(token_id, side="buy")
    sell_price_ask = client.get_price(token_id, side="sell")
    mid = client.get_midpoint(token_id)

    if isinstance(buy_price, dict):
        buy_price = float(buy_price.get("price", 0))
    if isinstance(sell_price_ask, dict):
        sell_price_ask = float(sell_price_ask.get("price", 0))
    if isinstance(mid, dict):
        mid = float(mid.get("mid", 0))

    buy_price = float(buy_price)
    sell_price_ask = float(sell_price_ask)
    mid = float(mid)

    return buy_price, sell_price_ask, mid


def sell_position(client, pos, dry_run=False):
    """Sell a single position with retry logic."""
    name = pos["name"]
    token_id = pos["token_id"]
    size = pos["size"]

    print(f"\n{'='*60}")
    print(f"SELLING: {name}")
    print(f"  Size: {size} shares")

    try:
        buy_price, sell_ask, mid = get_sell_price(client, token_id)
        print(f"  Market: buy=${buy_price:.4f}  ask=${sell_ask:.4f}  mid=${mid:.4f}")
    except Exception as e:
        print(f"  ERROR getting market price: {e}")
        return {"name": name, "status": "failed", "error": str(e)}

    if buy_price <= 0:
        print(f"  ERROR: No buy price available!")
        return {"name": name, "status": "failed", "error": "No buy price"}

    # Sell at buy_price - $0.01 for quick execution
    sell_price = round(buy_price - 0.01, 2)
    sell_price = max(sell_price, 0.01)
    expected_proceeds = sell_price * size

    print(f"  Sell price: ${sell_price:.3f}")
    print(f"  Expected proceeds: ${expected_proceeds:.2f}")

    if dry_run:
        print(f"  [DRY RUN] Would sell {size} @ ${sell_price:.3f}")
        return {
            "name": name, "status": "dry_run",
            "price": sell_price, "size": size, "proceeds": expected_proceeds,
        }

    for attempt in range(MAX_RETRIES):
        price = round(sell_price - (attempt * 0.01), 2)
        price = max(price, 0.01)

        print(f"\n  Attempt {attempt + 1}/{MAX_RETRIES}: SELL {size} @ ${price:.3f}")

        try:
            result = client.create_limit_order(
                token_id=token_id, side="SELL", price=price, size=size,
            )

            order_id = result.get("orderID") or result.get("order_id") or result.get("id", "")
            status = (result.get("status") or result.get("orderStatus") or "").upper()

            print(f"  Order: id={order_id[:16] if order_id else 'N/A'}.. status={status}")

            if status in ("MATCHED", "FILLED"):
                proceeds = price * size
                print(f"  >>> FILLED! Proceeds: ~${proceeds:.2f}")
                return {
                    "name": name, "status": "filled", "order_id": order_id,
                    "fill_price": price, "fill_size": size, "proceeds": proceeds,
                }

            if order_id:
                print(f"  Waiting {ORDER_WAIT_SECONDS}s for fill...")
                time.sleep(ORDER_WAIT_SECONDS)

                try:
                    cancelled = client.cancel_order(order_id)
                    if not cancelled:
                        proceeds = price * size
                        print(f"  >>> Cancel failed (likely filled)! Proceeds: ~${proceeds:.2f}")
                        return {
                            "name": name, "status": "filled", "order_id": order_id,
                            "fill_price": price, "fill_size": size, "proceeds": proceeds,
                        }
                    print(f"  Not filled, cancelled. Retrying lower...")
                except Exception as cancel_err:
                    proceeds = price * size
                    print(f"  Cancel exception (may be filled): {cancel_err}")
                    return {
                        "name": name, "status": "likely_filled", "order_id": order_id,
                        "fill_price": price, "fill_size": size, "proceeds": proceeds,
                    }

            time.sleep(1.5)

        except Exception as e:
            print(f"  ERROR on attempt {attempt + 1}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2.0)
            continue

    return {"name": name, "status": "failed", "error": "Max retries exceeded"}


def buy_position(client, token_id, name, budget, dry_run=False):
    """Buy NO tokens with recovered cash."""
    print(f"\n{'='*60}")
    print(f"BUYING: {name}")
    print(f"  Budget: ${budget:.2f}")

    try:
        buy_price, sell_ask, mid = get_sell_price(client, token_id)
        print(f"  Market: buy=${buy_price:.4f}  ask=${sell_ask:.4f}  mid=${mid:.4f}")
    except Exception as e:
        print(f"  ERROR getting market price: {e}")
        return {"name": name, "status": "failed", "error": str(e)}

    if sell_ask <= 0:
        print(f"  ERROR: No ask price available!")
        return {"name": name, "status": "failed", "error": "No ask price"}

    # Buy at ask + $0.01 for quick execution
    buy_at = round(sell_ask + 0.01, 2)
    buy_at = min(buy_at, 0.99)
    size = round(budget / buy_at, 1)

    cost = buy_at * size
    potential_profit = size * (1 - buy_at)

    print(f"  Buy price: ${buy_at:.3f}")
    print(f"  Size: {size} shares")
    print(f"  Cost: ${cost:.2f}")
    print(f"  Potential profit (if win): +${potential_profit:.2f}")

    if dry_run:
        print(f"  [DRY RUN] Would buy {size} @ ${buy_at:.3f}")
        return {
            "name": name, "status": "dry_run",
            "price": buy_at, "size": size, "cost": cost,
        }

    for attempt in range(MAX_RETRIES):
        price = round(buy_at + (attempt * 0.01), 2)
        price = min(price, 0.99)

        print(f"\n  Attempt {attempt + 1}/{MAX_RETRIES}: BUY {size} @ ${price:.3f}")

        try:
            result = client.create_limit_order(
                token_id=token_id, side="BUY", price=price, size=size,
            )

            order_id = result.get("orderID") or result.get("order_id") or result.get("id", "")
            status = (result.get("status") or result.get("orderStatus") or "").upper()

            print(f"  Order: id={order_id[:16] if order_id else 'N/A'}.. status={status}")

            if status in ("MATCHED", "FILLED"):
                print(f"  >>> FILLED! Cost: ~${price * size:.2f}")
                return {
                    "name": name, "status": "filled", "order_id": order_id,
                    "fill_price": price, "fill_size": size, "cost": price * size,
                }

            if order_id:
                print(f"  Waiting {ORDER_WAIT_SECONDS}s for fill...")
                time.sleep(ORDER_WAIT_SECONDS)

                try:
                    cancelled = client.cancel_order(order_id)
                    if not cancelled:
                        print(f"  >>> Cancel failed (likely filled)! Cost: ~${price * size:.2f}")
                        return {
                            "name": name, "status": "filled", "order_id": order_id,
                            "fill_price": price, "fill_size": size, "cost": price * size,
                        }
                    print(f"  Not filled, cancelled. Retrying higher...")
                except Exception as cancel_err:
                    print(f"  Cancel exception (may be filled): {cancel_err}")
                    return {
                        "name": name, "status": "likely_filled", "order_id": order_id,
                        "fill_price": price, "fill_size": size, "cost": price * size,
                    }

            time.sleep(1.5)

        except Exception as e:
            print(f"  ERROR on attempt {attempt + 1}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2.0)
            continue

    return {"name": name, "status": "failed", "error": "Max retries exceeded"}


def main():
    dry_run = "--dry-run" in sys.argv

    mode = "DRY RUN" if dry_run else "LIVE EXECUTION"
    print(f"{'='*60}")
    print(f"{mode} — Tier 1 Risk Reduction + Option A Reinvestment")
    print(f"{'='*60}")

    client = create_client()

    if not client.has_trading:
        print("ERROR: No trading credentials configured!")
        sys.exit(1)

    try:
        balance = client.get_balance_usdc()
        print(f"\nStarting USDC.e balance: ${balance:.2f}")
    except Exception as e:
        print(f"Warning: Could not check balance: {e}")
        balance = 0

    # === Phase 1: SELL risky positions ===
    print(f"\n{'='*60}")
    print("PHASE 1: SELL risky positions (risk reduction)")
    print(f"{'='*60}")

    sell_results = []
    total_proceeds = 0.0

    for i, pos in enumerate(SELLS):
        result = sell_position(client, pos, dry_run=dry_run)
        sell_results.append(result)

        if result.get("proceeds"):
            total_proceeds += result["proceeds"]

        if not dry_run and i < len(SELLS) - 1:
            print("\n  [Waiting 3s before next order...]")
            time.sleep(3.0)

    print(f"\n  Phase 1 total proceeds: ${total_proceeds:.2f}")

    # === Phase 2: BUY safe position ===
    print(f"\n{'='*60}")
    print("PHASE 2: BUY BTC $55K NO (reinvestment)")
    print(f"{'='*60}")

    # Use ~95% of proceeds for reinvestment
    buy_budget = total_proceeds * 0.95
    if buy_budget < 10:
        print(f"  Insufficient proceeds (${total_proceeds:.2f}). Skipping buy.")
        buy_result = {"name": BUY["name"], "status": "skipped"}
    else:
        if not dry_run:
            # Wait for sells to settle
            print("  [Waiting 5s for sell settlement...]")
            time.sleep(5.0)

        buy_result = buy_position(
            client, BUY["token_id"], BUY["name"], buy_budget, dry_run=dry_run
        )

    # === Summary ===
    print(f"\n{'='*60}")
    print("EXECUTION SUMMARY")
    print(f"{'='*60}")

    print("\n  SELLS:")
    for r in sell_results:
        status = r.get("status", "unknown")
        name = r["name"]
        if status in ("filled", "likely_filled", "dry_run"):
            price = r.get("fill_price") or r.get("price", 0)
            size = r.get("fill_size") or r.get("size", 0)
            proceeds = r.get("proceeds", 0)
            tag = "OK" if status != "dry_run" else "DRY"
            print(f"    [{tag}] {name}: {size} @ ${price:.3f} = ${proceeds:.2f}")
        else:
            print(f"    [FAIL] {name}: {r.get('error', 'unknown')}")

    print(f"\n  BUY:")
    bs = buy_result.get("status", "unknown")
    if bs in ("filled", "likely_filled", "dry_run"):
        bp = buy_result.get("fill_price") or buy_result.get("price", 0)
        bsz = buy_result.get("fill_size") or buy_result.get("size", 0)
        bc = buy_result.get("cost") or (bp * bsz)
        tag = "OK" if bs != "dry_run" else "DRY"
        print(f"    [{tag}] {BUY['name']}: {bsz} @ ${bp:.3f} = ${bc:.2f}")
    else:
        print(f"    [{bs.upper()}] {BUY['name']}")

    print(f"\n  Total sold: ${total_proceeds:.2f}")
    print(f"  Total bought: ${buy_result.get('cost', 0):.2f}")
    print(f"  Net cash change: ${total_proceeds - buy_result.get('cost', 0):.2f}")

    if not dry_run:
        try:
            time.sleep(3)
            final_balance = client.get_balance_usdc()
            print(f"\n  Final USDC.e balance: ${final_balance:.2f}")
        except Exception:
            pass


if __name__ == "__main__":
    main()
