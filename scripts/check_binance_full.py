#!/usr/bin/env python3
"""Binance Spot + Futures account overview."""

import hmac
import hashlib
import os
import sys
import time
import urllib.parse

import requests
from dotenv import load_dotenv

# Load .env
ENV_PATH = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(ENV_PATH)

API_KEY = os.environ.get('BINANCE_API_KEY', '')
API_SECRET = os.environ.get('BINANCE_API_SECRET', '')

if not API_KEY or not API_SECRET:
    print("ERROR: BINANCE_API_KEY or BINANCE_API_SECRET not set in .env")
    sys.exit(1)

SPOT_BASE = 'https://api.binance.com'
FUTURES_BASE = 'https://fapi.binance.com'


def signed_request(base_url: str, method: str, path: str, params: dict | None = None) -> dict:
    """Make a signed request to Binance API."""
    params = params or {}
    params['timestamp'] = int(time.time() * 1000)
    query = urllib.parse.urlencode(params)
    sig = hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    query += f'&signature={sig}'
    headers = {'X-MBX-APIKEY': API_KEY}
    url = f'{base_url}{path}?{query}'
    resp = requests.request(method, url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_price(symbol: str) -> float:
    """Get current price for a symbol."""
    resp = requests.get(f'{SPOT_BASE}/api/v3/ticker/price', params={'symbol': symbol}, timeout=5)
    if resp.status_code == 200:
        return float(resp.json()['price'])
    return 0.0


def fmt_usd(val: float) -> str:
    """Format as USD string."""
    return f"${val:,.2f}"


def fmt_pct(val: float) -> str:
    """Format as percentage string with sign."""
    sign = '+' if val >= 0 else ''
    return f"{sign}{val:.2f}%"


def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ── 1. SPOT ACCOUNT ──────────────────────────────────────────

print_section("SPOT ACCOUNT BALANCES")

spot_account = signed_request(SPOT_BASE, 'GET', '/api/v3/account')
balances = []
total_spot_usd = 0.0

for asset in spot_account['balances']:
    free = float(asset['free'])
    locked = float(asset['locked'])
    total = free + locked
    if total <= 0:
        continue

    symbol = asset['asset']
    if symbol in ('USDT', 'USDC', 'BUSD', 'FDUSD'):
        price = 1.0
    else:
        price = get_price(f"{symbol}USDT")
        if price == 0:
            price = get_price(f"{symbol}USDC")

    value_usd = total * price
    total_spot_usd += value_usd
    balances.append({
        'asset': symbol,
        'free': free,
        'locked': locked,
        'total': total,
        'price': price,
        'value_usd': value_usd,
    })

# Sort by value descending
balances.sort(key=lambda x: x['value_usd'], reverse=True)

print(f"\n{'Asset':<8} {'Free':>12} {'Locked':>12} {'Total':>12} {'Price':>10} {'Value (USD)':>12}")
print(f"{'-'*8} {'-'*12} {'-'*12} {'-'*12} {'-'*10} {'-'*12}")
for b in balances:
    print(f"{b['asset']:<8} {b['free']:>12.6f} {b['locked']:>12.6f} {b['total']:>12.6f} {b['price']:>10.2f} {fmt_usd(b['value_usd']):>12}")
print(f"\n  Total Spot Value: {fmt_usd(total_spot_usd)}")


# ── 2. FUTURES ACCOUNT BALANCE ────────────────────────────────

print_section("FUTURES ACCOUNT SUMMARY")

futures_account = signed_request(FUTURES_BASE, 'GET', '/fapi/v2/account')

total_wallet = float(futures_account.get('totalWalletBalance', 0))
total_unrealized = float(futures_account.get('totalUnrealizedProfit', 0))
available = float(futures_account.get('availableBalance', 0))
total_margin = float(futures_account.get('totalMarginBalance', 0))
total_maint_margin = float(futures_account.get('totalMaintMargin', 0))

print(f"\n  Wallet Balance:        {fmt_usd(total_wallet)}")
print(f"  Unrealized PnL:        {fmt_usd(total_unrealized)}")
print(f"  Margin Balance:        {fmt_usd(total_margin)}")
print(f"  Available Balance:     {fmt_usd(available)}")
print(f"  Maintenance Margin:    {fmt_usd(total_maint_margin)}")


# ── 3. FUTURES OPEN POSITIONS ─────────────────────────────────

print_section("FUTURES OPEN POSITIONS")

positions_raw = signed_request(FUTURES_BASE, 'GET', '/fapi/v2/positionRisk')
open_positions = []

for pos in positions_raw:
    notional = abs(float(pos.get('notional', 0)))
    if notional == 0:
        continue

    symbol = pos['symbol']
    side = 'LONG' if float(pos.get('positionAmt', 0)) > 0 else 'SHORT'
    entry_price = float(pos.get('entryPrice', 0))
    mark_price = float(pos.get('markPrice', 0))
    unrealized_pnl = float(pos.get('unRealizedProfit', 0))
    leverage = int(float(pos.get('leverage', 1)))
    liq_price = float(pos.get('liquidationPrice', 0))
    margin_type = pos.get('marginType', 'cross')
    position_amt = float(pos.get('positionAmt', 0))
    equity = notional / leverage  # actual capital deployed

    # PnL percentage based on equity
    pnl_pct = (unrealized_pnl / equity * 100) if equity > 0 else 0

    open_positions.append({
        'symbol': symbol,
        'side': side,
        'amount': abs(position_amt),
        'entry': entry_price,
        'mark': mark_price,
        'pnl': unrealized_pnl,
        'pnl_pct': pnl_pct,
        'leverage': leverage,
        'notional': notional,
        'equity': equity,
        'liq_price': liq_price,
        'margin': margin_type,
    })

if open_positions:
    print(f"\n{'Symbol':<12} {'Side':<6} {'Amount':>10} {'Entry':>10} {'Mark':>10} {'PnL':>10} {'PnL%':>8} {'Lev':>4} {'Equity':>10} {'Liq Price':>12} {'Margin':<8}")
    print(f"{'-'*12} {'-'*6} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*4} {'-'*10} {'-'*12} {'-'*8}")
    total_futures_equity = 0
    total_futures_pnl = 0
    for p in open_positions:
        total_futures_equity += p['equity']
        total_futures_pnl += p['pnl']
        liq_str = f"{p['liq_price']:.2f}" if p['liq_price'] > 0 else "N/A"
        print(f"{p['symbol']:<12} {p['side']:<6} {p['amount']:>10.4f} {p['entry']:>10.2f} {p['mark']:>10.2f} {fmt_usd(p['pnl']):>10} {fmt_pct(p['pnl_pct']):>8} {p['leverage']:>4}x {fmt_usd(p['equity']):>10} {liq_str:>12} {p['margin']:<8}")
    print(f"\n  Total Futures Equity (notional/leverage): {fmt_usd(total_futures_equity)}")
    print(f"  Total Unrealized PnL:                     {fmt_usd(total_futures_pnl)}")
else:
    print("\n  No open futures positions.")


# ── 4. FUTURES OPEN ORDERS ────────────────────────────────────

print_section("FUTURES OPEN ORDERS (SL/TP)")

open_orders = signed_request(FUTURES_BASE, 'GET', '/fapi/v1/openOrders')

if open_orders:
    print(f"\n{'Symbol':<12} {'Side':<6} {'Type':<20} {'Price':>10} {'Stop':>10} {'Qty':>10} {'Time'}")
    print(f"{'-'*12} {'-'*6} {'-'*20} {'-'*10} {'-'*10} {'-'*10} {'-'*20}")
    for o in open_orders:
        symbol = o.get('symbol', '')
        side = o.get('side', '')
        order_type = o.get('type', '')
        price = float(o.get('price', 0))
        stop_price = float(o.get('stopPrice', 0))
        qty = float(o.get('origQty', 0))
        ts = o.get('time', 0)
        time_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(ts / 1000)) if ts else ''

        price_str = f"{price:.2f}" if price > 0 else "MARKET"
        stop_str = f"{stop_price:.2f}" if stop_price > 0 else "-"

        print(f"{symbol:<12} {side:<6} {order_type:<20} {price_str:>10} {stop_str:>10} {qty:>10.4f} {time_str}")
else:
    print("\n  No open futures orders.")


# ── 5. TOTAL SUMMARY ─────────────────────────────────────────

print_section("TOTAL PORTFOLIO SUMMARY")

# Futures total = wallet balance (which includes margin + available)
total_all = total_spot_usd + total_margin

print(f"\n  Spot Total:            {fmt_usd(total_spot_usd)}")
print(f"  Futures Margin:        {fmt_usd(total_margin)} (wallet {fmt_usd(total_wallet)} + unrealized {fmt_usd(total_unrealized)})")
print(f"  ──────────────────────────────")
print(f"  Grand Total:           {fmt_usd(total_all)}")
print()
