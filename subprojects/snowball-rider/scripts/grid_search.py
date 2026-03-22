#!/usr/bin/env python3
"""Grid search for optimal BTC strategy parameters.

Usage:
  python grid_search.py                    # All leverages
  python grid_search.py --leverage 3       # Single leverage
  python grid_search.py --leverage 2 3     # Multiple
  python grid_search.py --top 20           # Show top 20
"""

from __future__ import annotations
import sys
import os
import json
import time
import argparse
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional
from itertools import product

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from snowball_rider.indicators import compute_ema, compute_rsi


CRASH_THRESHOLD = 0.30
INITIAL_CAPITAL = 818.0


def fetch_all_klines(symbol: str = "BTCUSDT", interval: str = "1d") -> list[dict]:
    cache_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f'{symbol.lower()}_{interval}_klines.json')
    if os.path.exists(cache_path):
        age = time.time() - os.path.getmtime(cache_path)
        if age < 86400:
            with open(cache_path) as f:
                return json.load(f)
    url = "https://fapi.binance.com/fapi/v1/klines"
    all_klines = []
    end_time = None
    while True:
        params = {"symbol": symbol, "interval": interval, "limit": 1500}
        if end_time is not None:
            params["endTime"] = end_time
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        all_klines = data + all_klines
        end_time = data[0][0] - 1
        if len(data) < 1500:
            break
        time.sleep(0.2)
    seen = set()
    unique = []
    for k in all_klines:
        if k[0] not in seen:
            seen.add(k[0])
            unique.append(k)
    unique.sort(key=lambda x: x[0])
    candles = [{
        "open_time": int(k[0]), "open": float(k[1]), "high": float(k[2]),
        "low": float(k[3]), "close": float(k[4]), "volume": float(k[5]),
        "date": datetime.fromtimestamp(int(k[0])/1000, tz=timezone.utc).strftime('%Y-%m-%d'),
    } for k in unique]
    with open(cache_path, 'w') as f:
        json.dump(candles, f)
    return candles


def filter_crashes(candles: list[dict]) -> list[dict]:
    crash_dates = {"2020-03-12", "2020-03-13"}
    return [c for c in candles
            if c["date"] not in crash_dates
            and (c["high"] - c["low"]) / c["high"] <= CRASH_THRESHOLD
            and (c["open"] - c["close"]) / c["open"] <= CRASH_THRESHOLD]


def run_backtest(candles: list[dict], leverage: int, allocation: float,
                 sl_pct: float, tp_pct: float,
                 ema_fast: int = 12, ema_slow: int = 26,
                 rsi_period: int = 21, rsi_long: float = 50, rsi_short: float = 50,
                 tp_ema_fast: int = 7, tp_ema_slow: int = 14, tp_cross_days: int = 2,
                 ) -> dict:
    closes = [c["close"] for c in candles]
    lows = [c["low"] for c in candles]
    highs = [c["high"] for c in candles]
    dates = [c["date"] for c in candles]
    n = len(closes)

    ema_f = compute_ema(closes, ema_fast)
    ema_s = compute_ema(closes, ema_slow)
    rsi = compute_rsi(closes, rsi_period)
    ema_tf = compute_ema(closes, tp_ema_fast)
    ema_ts = compute_ema(closes, tp_ema_slow)

    fee_rate = 0.0005
    funding_daily = 0.0003

    wallet = INITIAL_CAPITAL
    peak_wallet = wallet
    max_drawdown = 0.0
    trade_count = 0
    win_count = 0
    loss_count = 0
    liquidated = False

    in_position = False
    position_side = ""
    entry_price = 0.0
    entry_idx = 0
    allocated = 0.0
    tp_activated = False
    tp_cross_count = 0
    warmup = max(ema_slow, rsi_period, tp_ema_slow) + 1

    for i in range(n):
        # Equity
        if in_position:
            if position_side == "LONG":
                unrealized = ((closes[i] / entry_price) - 1) * 100 * leverage
            else:
                unrealized = ((entry_price / closes[i]) - 1) * 100 * leverage
            current_equity = (wallet - allocated) + allocated * (1 + unrealized / 100)
        else:
            current_equity = wallet

        if current_equity > peak_wallet:
            peak_wallet = current_equity
        dd = (peak_wallet - current_equity) / peak_wallet * 100 if peak_wallet > 0 else 0
        if dd > max_drawdown:
            max_drawdown = dd

        if i < warmup:
            continue
        if any(v is None for v in [ema_f[i], ema_s[i], rsi[i], ema_tf[i], ema_ts[i]]):
            continue

        if in_position:
            if position_side == "LONG":
                intraday_worst = ((lows[i] / entry_price) - 1) * 100 * leverage
                close_pnl = ((closes[i] / entry_price) - 1) * 100 * leverage
            else:
                intraday_worst = ((entry_price / highs[i]) - 1) * 100 * leverage
                close_pnl = ((entry_price / closes[i]) - 1) * 100 * leverage

            # Liquidation
            if intraday_worst <= -100:
                wallet = wallet - allocated
                if wallet < 0:
                    wallet = 0
                trade_count += 1
                loss_count += 1
                in_position = False
                tp_activated = False
                tp_cross_count = 0
                if wallet <= 10:
                    liquidated = True
                    break
                continue

            # SL
            if intraday_worst <= sl_pct:
                fee_cost = fee_rate * leverage * 2 * 100
                net_pnl = sl_pct - fee_cost
                old_wallet = wallet
                wallet = (old_wallet - allocated) + allocated * (1 + net_pnl / 100)
                if wallet < 0:
                    wallet = 0
                trade_count += 1
                loss_count += 1
                in_position = False
                tp_activated = False
                tp_cross_count = 0
                if wallet <= 10:
                    liquidated = True
                    break
                continue

            # TP activation
            if close_pnl >= tp_pct:
                tp_activated = True

            if tp_activated:
                if position_side == "LONG" and ema_tf[i] < ema_ts[i]:
                    tp_cross_count += 1
                elif position_side == "SHORT" and ema_tf[i] > ema_ts[i]:
                    tp_cross_count += 1
                else:
                    tp_cross_count = 0

                if tp_cross_count >= tp_cross_days:
                    fee_cost = fee_rate * leverage * 2 * 100
                    net_pnl = close_pnl - fee_cost
                    old_wallet = wallet
                    wallet = (old_wallet - allocated) + allocated * (1 + net_pnl / 100)
                    trade_count += 1
                    if net_pnl > 0:
                        win_count += 1
                    else:
                        loss_count += 1
                    in_position = False
                    tp_activated = False
                    tp_cross_count = 0
                    continue

            # Daily funding
            daily_funding = allocated * leverage * funding_daily
            wallet -= daily_funding
            continue

        # ENTRY
        if wallet <= 10:
            break

        if ema_f[i] > ema_s[i] and rsi[i] > rsi_long:
            allocated = wallet * allocation
            entry_price = closes[i]
            entry_idx = i
            position_side = "LONG"
            in_position = True
            tp_activated = False
            tp_cross_count = 0
            continue

        if ema_f[i] < ema_s[i] and rsi[i] < rsi_short:
            allocated = wallet * allocation
            entry_price = closes[i]
            entry_idx = i
            position_side = "SHORT"
            in_position = True
            tp_activated = False
            tp_cross_count = 0
            continue

    # Close open at end
    if in_position and wallet > 0:
        if position_side == "LONG":
            close_pnl = ((closes[-1] / entry_price) - 1) * 100 * leverage
        else:
            close_pnl = ((entry_price / closes[-1]) - 1) * 100 * leverage
        fee_cost = fee_rate * leverage * 2 * 100
        net_pnl = close_pnl - fee_cost
        old_wallet = wallet
        wallet = (old_wallet - allocated) + allocated * (1 + net_pnl / 100)
        trade_count += 1
        if net_pnl > 0:
            win_count += 1
        else:
            loss_count += 1

    total_return = (wallet / INITIAL_CAPITAL - 1) * 100
    start_date = datetime.strptime(dates[warmup], "%Y-%m-%d")
    end_date = datetime.strptime(dates[-1], "%Y-%m-%d")
    years = (end_date - start_date).days / 365.25
    cagr = ((wallet / INITIAL_CAPITAL) ** (1 / years) - 1) * 100 if years > 0 and wallet > 0 else 0
    win_rate = win_count / trade_count * 100 if trade_count > 0 else 0

    # Buy & hold
    bnh_return = (closes[-1] / closes[warmup] - 1) * 100

    # Calmar ratio (CAGR / MaxDD)
    calmar = cagr / max_drawdown if max_drawdown > 0 else 0

    return {
        "leverage": leverage,
        "allocation": allocation,
        "sl_pct": sl_pct,
        "tp_pct": tp_pct,
        "final_wallet": wallet,
        "total_return_pct": total_return,
        "cagr_pct": cagr,
        "max_drawdown_pct": max_drawdown,
        "calmar": calmar,
        "trade_count": trade_count,
        "win_rate": win_rate,
        "liquidated": liquidated,
        "bnh_return_pct": bnh_return,
        "years": years,
        "beats_bnh": total_return > bnh_return,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--leverage", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args()

    print("=" * 90)
    print(f"  BTC Grid Search — Leverage: {args.leverage}")
    print(f"  Initial: ${INITIAL_CAPITAL} | Crash excluded | Funding included")
    print("=" * 90)

    candles = fetch_all_klines("BTCUSDT")
    filtered = filter_crashes(candles)
    print(f"  Data: {len(filtered)} candles")

    # Parameter grid
    leverages = args.leverage
    allocations = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    sl_pcts = [-30, -40, -50, -60, -70, -80]
    tp_pcts = [5, 10, 15, 20, 30]

    # EMA variants
    ema_pairs = [(12, 26), (10, 30), (20, 50)]
    rsi_pairs = [(21, 50, 50), (14, 55, 45), (21, 55, 45)]

    total = len(leverages) * len(allocations) * len(sl_pcts) * len(tp_pcts) * len(ema_pairs) * len(rsi_pairs)
    print(f"  Combinations: {total}")
    print()

    results = []
    count = 0

    for lev, alloc, sl, tp, (ef, es), (rp, rl, rs) in product(
        leverages, allocations, sl_pcts, tp_pcts, ema_pairs, rsi_pairs
    ):
        count += 1
        if count % 500 == 0:
            print(f"  Progress: {count}/{total} ({count/total*100:.0f}%)")

        r = run_backtest(filtered, leverage=lev, allocation=alloc,
                         sl_pct=sl, tp_pct=tp,
                         ema_fast=ef, ema_slow=es,
                         rsi_period=rp, rsi_long=rl, rsi_short=rs)
        r["ema"] = f"{ef}/{es}"
        r["rsi_cfg"] = f"{rp}>{rl}<{rs}"
        results.append(r)

    print(f"  Done: {count} backtests\n")

    # Filter: not liquidated, positive return, beats B&H
    viable = [r for r in results if not r["liquidated"] and r["final_wallet"] > INITIAL_CAPITAL]
    beats_bnh = [r for r in viable if r["beats_bnh"]]

    print(f"  Total: {len(results)}")
    print(f"  Viable (positive return): {len(viable)}")
    print(f"  Beats Buy & Hold: {len(beats_bnh)}")

    # Sort by Calmar ratio (risk-adjusted return)
    print(f"\n{'='*90}")
    print(f"  TOP {args.top} by CALMAR RATIO (CAGR/MaxDD) — beats B&H only")
    print(f"{'='*90}")
    by_calmar = sorted(beats_bnh, key=lambda x: x["calmar"], reverse=True)[:args.top]
    print(f"  {'#':>3} {'Lev':>3} {'Alloc':>5} {'SL':>5} {'TP':>4} {'EMA':>6} {'RSI':>10} {'Final$':>10} {'CAGR':>7} {'MaxDD':>7} {'Calmar':>7} {'Trades':>6} {'WR':>5}")
    print(f"  {'---':>3} {'---':>3} {'-----':>5} {'-----':>5} {'----':>4} {'------':>6} {'----------':>10} {'----------':>10} {'-------':>7} {'-------':>7} {'-------':>7} {'------':>6} {'-----':>5}")
    for idx, r in enumerate(by_calmar, 1):
        print(f"  {idx:3d} {r['leverage']:>3}x {r['allocation']:>5.0%} {r['sl_pct']:>5.0f}% {r['tp_pct']:>4.0f}% {r['ema']:>6} {r['rsi_cfg']:>10} ${r['final_wallet']:>9,.0f} {r['cagr_pct']:>+6.1f}% {r['max_drawdown_pct']:>6.1f}% {r['calmar']:>7.2f} {r['trade_count']:>6} {r['win_rate']:>4.0f}%")

    # Sort by CAGR
    print(f"\n{'='*90}")
    print(f"  TOP {args.top} by CAGR — beats B&H only")
    print(f"{'='*90}")
    by_cagr = sorted(beats_bnh, key=lambda x: x["cagr_pct"], reverse=True)[:args.top]
    print(f"  {'#':>3} {'Lev':>3} {'Alloc':>5} {'SL':>5} {'TP':>4} {'EMA':>6} {'RSI':>10} {'Final$':>10} {'CAGR':>7} {'MaxDD':>7} {'Calmar':>7} {'Trades':>6} {'WR':>5}")
    print(f"  {'---':>3} {'---':>3} {'-----':>5} {'-----':>5} {'----':>4} {'------':>6} {'----------':>10} {'----------':>10} {'-------':>7} {'-------':>7} {'-------':>7} {'------':>6} {'-----':>5}")
    for idx, r in enumerate(by_cagr, 1):
        print(f"  {idx:3d} {r['leverage']:>3}x {r['allocation']:>5.0%} {r['sl_pct']:>5.0f}% {r['tp_pct']:>4.0f}% {r['ema']:>6} {r['rsi_cfg']:>10} ${r['final_wallet']:>9,.0f} {r['cagr_pct']:>+6.1f}% {r['max_drawdown_pct']:>6.1f}% {r['calmar']:>7.2f} {r['trade_count']:>6} {r['win_rate']:>4.0f}%")

    # Sort by MaxDD ascending (safest)
    print(f"\n{'='*90}")
    print(f"  TOP {args.top} by LOWEST MaxDD — beats B&H only")
    print(f"{'='*90}")
    by_mdd = sorted(beats_bnh, key=lambda x: x["max_drawdown_pct"])[:args.top]
    print(f"  {'#':>3} {'Lev':>3} {'Alloc':>5} {'SL':>5} {'TP':>4} {'EMA':>6} {'RSI':>10} {'Final$':>10} {'CAGR':>7} {'MaxDD':>7} {'Calmar':>7} {'Trades':>6} {'WR':>5}")
    print(f"  {'---':>3} {'---':>3} {'-----':>5} {'-----':>5} {'----':>4} {'------':>6} {'----------':>10} {'----------':>10} {'-------':>7} {'-------':>7} {'-------':>7} {'------':>6} {'-----':>5}")
    for idx, r in enumerate(by_mdd, 1):
        print(f"  {idx:3d} {r['leverage']:>3}x {r['allocation']:>5.0%} {r['sl_pct']:>5.0f}% {r['tp_pct']:>4.0f}% {r['ema']:>6} {r['rsi_cfg']:>10} ${r['final_wallet']:>9,.0f} {r['cagr_pct']:>+6.1f}% {r['max_drawdown_pct']:>6.1f}% {r['calmar']:>7.2f} {r['trade_count']:>6} {r['win_rate']:>4.0f}%")

    # Save results
    save_path = os.path.join(os.path.dirname(__file__), '..', 'data',
                             f'grid_results_lev{"_".join(str(l) for l in args.leverage)}.json')
    save_data = [{k: v for k, v in r.items()} for r in results]
    with open(save_path, 'w') as f:
        json.dump(save_data, f, indent=2, default=str)
    print(f"\n  Saved {len(results)} results to {save_path}")


if __name__ == "__main__":
    main()
