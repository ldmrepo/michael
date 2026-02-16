#!/usr/bin/env python3
"""Binance account status check - spot balances and futures positions."""

import hmac
import hashlib
import time
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("BINANCE_API_KEY", "")
API_SECRET = os.environ.get("BINANCE_API_SECRET", "")

if not API_KEY or not API_SECRET:
    print("ERROR: BINANCE_API_KEY and BINANCE_API_SECRET must be set in .env")
    sys.exit(1)


def signed_request(base, method, path, params=None):
    params = params or {}
    params["timestamp"] = int(time.time() * 1000)
    query = "&".join(f"{k}={v}" for k, v in params.items())
    sig = hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    query += f"&signature={sig}"
    headers = {"X-MBX-APIKEY": API_KEY}
    url = f"{base}{path}?{query}"
    resp = requests.request(method, url, headers=headers)
    return resp.json()


def get_price(symbol):
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    resp = requests.get(url).json()
    return float(resp.get("price", 0))


def main():
    # === 1. SPOT ACCOUNT ===
    print("=" * 60)
    print("SPOT ACCOUNT BALANCES")
    print("=" * 60)

    spot = signed_request("https://api.binance.com", "GET", "/api/v3/account")
    total_spot_usd = 0.0

    if "balances" not in spot:
        print(f"Error: {spot}")
    else:
        spot_assets = []
        for b in spot["balances"]:
            free = float(b["free"])
            locked = float(b["locked"])
            total = free + locked
            if total > 0.0:
                asset = b["asset"]
                if asset in ("USDT", "USDC", "BUSD", "FDUSD"):
                    price = 1.0
                else:
                    try:
                        price = get_price(f"{asset}USDT")
                    except Exception:
                        price = 0.0
                value_usd = total * price
                total_spot_usd += value_usd
                spot_assets.append(
                    {
                        "asset": asset,
                        "free": free,
                        "locked": locked,
                        "total": total,
                        "price": price,
                        "value_usd": value_usd,
                    }
                )

        spot_assets.sort(key=lambda x: x["value_usd"], reverse=True)

        header = f"{'Asset':<8} {'Free':>12} {'Locked':>12} {'Total':>12} {'Price':>10} {'Value(USD)':>12}"
        print(header)
        print("-" * 68)
        for a in spot_assets:
            print(
                f"{a['asset']:<8} {a['free']:>12.6f} {a['locked']:>12.6f} "
                f"{a['total']:>12.6f} {a['price']:>10.2f} {a['value_usd']:>12.2f}"
            )
        print("-" * 68)
        print(f"{'TOTAL SPOT':>56} {total_spot_usd:>12.2f}")

    # === 2. FUTURES ACCOUNT ===
    print()
    print("=" * 60)
    print("FUTURES ACCOUNT")
    print("=" * 60)

    futures = signed_request("https://fapi.binance.com", "GET", "/fapi/v2/account")
    futures_wallet = 0.0
    futures_unrealized = 0.0
    available_futures = 0.0

    if "totalWalletBalance" not in futures:
        print(f"Error: {futures}")
    else:
        futures_wallet = float(futures["totalWalletBalance"])
        futures_unrealized = float(futures["totalUnrealizedProfit"])
        available_futures = float(futures["availableBalance"])

        print(f"Total Wallet Balance:    ${futures_wallet:>12.2f}")
        print(f"Total Unrealized PnL:    ${futures_unrealized:>+12.2f}")
        print(f"Total Margin Balance:    ${float(futures['totalMarginBalance']):>12.2f}")
        print(f"Available Balance:       ${available_futures:>12.2f}")
        print(f"Total Cross Wallet:      ${float(futures.get('totalCrossWalletBalance', 0)):>12.2f}")
        cross_unpnl = futures.get("totalCrossUnPnL", futures.get("totalCrossUnRealizedProfit", 0))
        print(f"Total Cross UnPnL:       ${float(cross_unpnl):>12.2f}")

    # === 3. FUTURES POSITIONS ===
    print()
    print("=" * 60)
    print("FUTURES OPEN POSITIONS")
    print("=" * 60)

    positions = signed_request(
        "https://fapi.binance.com", "GET", "/fapi/v2/positionRisk"
    )

    if isinstance(positions, dict) and "code" in positions:
        print(f"Error: {positions}")
    else:
        open_positions = [
            p for p in positions if float(p.get("positionAmt", 0)) != 0
        ]

        if not open_positions:
            print("No open futures positions.")
        else:
            total_futures_equity = 0.0
            total_unrealized_pos = 0.0

            header = (
                f"{'Symbol':<10} {'Side':<6} {'Size':>10} {'Entry':>10} "
                f"{'Mark':>10} {'Lev':>4} {'Margin':>10} {'UnPnL':>10} {'ROE%':>8}"
            )
            print(header)
            print("-" * 90)

            for p in open_positions:
                symbol = p["symbol"]
                amt = float(p["positionAmt"])
                side = "LONG" if amt > 0 else "SHORT"
                entry = float(p["entryPrice"])
                mark = float(p["markPrice"])
                leverage = int(float(p["leverage"]))
                notional = abs(float(p["notional"]))
                unrealized = float(p["unRealizedProfit"])
                margin_type = p.get("marginType", "cross")
                isolated_margin = float(p.get("isolatedMargin", 0))

                equity = notional / leverage
                total_futures_equity += equity
                total_unrealized_pos += unrealized

                roe = (unrealized / equity * 100) if equity > 0 else 0

                margin_display = (
                    isolated_margin if margin_type == "isolated" else equity
                )

                print(
                    f"{symbol:<10} {side:<6} {abs(amt):>10.4f} {entry:>10.2f} "
                    f"{mark:>10.2f} {leverage:>3}x {margin_display:>10.2f} "
                    f"{unrealized:>+10.2f} {roe:>+7.2f}%"
                )

                liq_price = float(p.get("liquidationPrice", 0))
                if liq_price > 0:
                    print(
                        f"           Margin: {margin_type.upper()} | "
                        f"Liq Price: ${liq_price:.2f} | Notional: ${notional:.2f}"
                    )

            print("-" * 90)
            print(f"{'Futures Equity (margin)':>36} {total_futures_equity:>10.2f}")
            print(f"{'Total Unrealized PnL':>36} {total_unrealized_pos:>+10.2f}")
            print(
                f"{'Futures Value (equity + PnL)':>36} "
                f"{total_futures_equity + total_unrealized_pos:>10.2f}"
            )

    # === 4. TOTAL SUMMARY ===
    print()
    print("=" * 60)
    print("TOTAL ACCOUNT SUMMARY")
    print("=" * 60)

    futures_margin_balance = futures_wallet + futures_unrealized

    print(f"Spot Total:              ${total_spot_usd:>12.2f}")
    print(f"Futures Wallet Balance:  ${futures_wallet:>12.2f}")
    print(f"Futures Unrealized PnL:  ${futures_unrealized:>+12.2f}")
    print(f"Futures Margin Balance:  ${futures_margin_balance:>12.2f}")
    print(f"Futures Available:       ${available_futures:>12.2f}")
    print(f"-------------------------------------")
    print(f"TOTAL EQUITY:            ${total_spot_usd + futures_margin_balance:>12.2f}")


if __name__ == "__main__":
    main()
