#!/usr/bin/env python3
"""Check Binance futures positions and open orders (TP/SL) for BTC, ETH, SOL."""

import hmac, hashlib, time, os, sys
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("BINANCE_API_KEY", "")
API_SECRET = os.environ.get("BINANCE_API_SECRET", "")
FAPI = "https://fapi.binance.com"

if not API_KEY or not API_SECRET:
    print("ERROR: BINANCE_API_KEY and BINANCE_API_SECRET required"); sys.exit(1)


def signed_req(method, path, params=None):
    params = params or {}
    params["timestamp"] = int(time.time() * 1000)
    query = "&".join(f"{k}={v}" for k, v in params.items())
    sig = hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    headers = {"X-MBX-APIKEY": API_KEY}
    return requests.request(method, f"{FAPI}{path}?{query}&signature={sig}", headers=headers).json()


def main():
    # === 1. FUTURES ACCOUNT SUMMARY ===
    acct = signed_req("GET", "/fapi/v2/account")
    if "totalWalletBalance" not in acct:
        print(f"Account error: {acct}"); sys.exit(1)

    print("=" * 70)
    print("FUTURES ACCOUNT SUMMARY")
    print("=" * 70)
    print(f"  Wallet Balance:      ${float(acct['totalWalletBalance']):>12.2f}")
    print(f"  Unrealized PnL:      ${float(acct['totalUnrealizedProfit']):>+12.2f}")
    print(f"  Margin Balance:      ${float(acct['totalMarginBalance']):>12.2f}")
    print(f"  Available Balance:   ${float(acct['availableBalance']):>12.2f}")

    # === 2. OPEN POSITIONS ===
    positions = signed_req("GET", "/fapi/v2/positionRisk")
    if isinstance(positions, dict) and "code" in positions:
        print(f"Position error: {positions}"); sys.exit(1)

    open_pos = [p for p in positions if float(p.get("positionAmt", 0)) != 0]

    print()
    print("=" * 70)
    print("OPEN FUTURES POSITIONS")
    print("=" * 70)

    if not open_pos:
        print("  No open positions.")
    else:
        for p in open_pos:
            amt = float(p["positionAmt"])
            side = "LONG" if amt > 0 else "SHORT"
            entry = float(p["entryPrice"])
            mark = float(p["markPrice"])
            lev = int(float(p["leverage"]))
            notional = abs(float(p["notional"]))
            upnl = float(p["unRealizedProfit"])
            liq = float(p.get("liquidationPrice", 0))
            margin_type = p.get("marginType", "cross").upper()
            equity = notional / lev

            roe = (upnl / equity * 100) if equity > 0 else 0
            pnl_pct = ((mark - entry) / entry * 100) if entry > 0 else 0
            if side == "SHORT":
                pnl_pct = -pnl_pct

            print(f"\n  {p['symbol']} | {side} | {lev}x | {margin_type}")
            print(f"  {'─' * 50}")
            print(f"    Position Size:   {abs(amt):.4f} ({side})")
            print(f"    Entry Price:     ${entry:,.2f}")
            print(f"    Mark Price:      ${mark:,.2f}")
            print(f"    Price Change:    {pnl_pct:+.2f}%")
            print(f"    Notional Value:  ${notional:,.2f}")
            print(f"    Margin (equity): ${equity:,.2f}")
            print(f"    Unrealized PnL:  ${upnl:+,.2f} (ROE: {roe:+.2f}%)")
            if liq > 0:
                dist = abs(mark - liq) / mark * 100
                print(f"    Liquidation:     ${liq:,.2f} ({dist:.1f}% away)")

    # === 3. OPEN ORDERS FOR BTC, ETH, SOL ===
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    print()
    print("=" * 70)
    print("OPEN ORDERS (BTCUSDT, ETHUSDT, SOLUSDT)")
    print("=" * 70)

    any_orders = False
    for sym in symbols:
        orders = signed_req("GET", "/fapi/v1/openOrders", {"symbol": sym})
        if isinstance(orders, dict) and "code" in orders:
            print(f"  {sym}: Error - {orders.get('msg', orders)}")
            continue
        if not orders:
            print(f"\n  {sym}: No open orders")
            continue

        any_orders = True
        print(f"\n  {sym} ({len(orders)} orders)")
        print(f"  {'Type':<22} {'Side':<6} {'Price':>12} {'Stop':>12} {'Qty':>12} {'Status':<10}")
        print(f"  {'─' * 76}")

        for o in sorted(orders, key=lambda x: float(x.get("stopPrice", 0) or x.get("price", 0))):
            otype = o.get("type", "?")
            side = o.get("side", "?")
            price = float(o.get("price", 0))
            stop = float(o.get("stopPrice", 0))
            qty = float(o.get("origQty", 0))
            status = o.get("status", "?")
            close_pos = o.get("closePosition", False)

            # Label for clarity
            label = otype
            if otype == "TAKE_PROFIT_MARKET":
                label = "TAKE_PROFIT_MKT"
            elif otype == "STOP_MARKET":
                label = "STOP_LOSS_MKT"
            elif otype == "TRAILING_STOP_MARKET":
                label = "TRAILING_STOP"

            if close_pos:
                label += " (close)"

            price_str = f"${price:,.2f}" if price > 0 else "MARKET"
            stop_str = f"${stop:,.2f}" if stop > 0 else "-"
            qty_str = f"{qty:.4f}" if qty > 0 else "ALL"

            print(f"  {label:<22} {side:<6} {price_str:>12} {stop_str:>12} {qty_str:>12} {status:<10}")

    if not any_orders:
        print("\n  No open orders found for any symbol.")

    print()


if __name__ == "__main__":
    main()
