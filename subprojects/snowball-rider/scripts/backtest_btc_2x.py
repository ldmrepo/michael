#!/usr/bin/env python3
"""BTC 2x leverage backtest — MaxDD reduction study.

Tests multiple leverage/allocation combinations:
- 3x 100% (baseline)
- 2x 100%
- 2x 50% (half allocation)
- 1x 100% (no leverage, spot equivalent)

All with crash excluded + funding included (realistic scenario).
"""

from __future__ import annotations
import sys
import os
import json
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from snowball_rider.indicators import compute_ema, compute_rsi


CRASH_THRESHOLD = 0.30


def fetch_all_klines(symbol: str = "BTCUSDT", interval: str = "1d") -> list[dict]:
    cache_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f'{symbol.lower()}_{interval}_klines.json')

    if os.path.exists(cache_path):
        age = time.time() - os.path.getmtime(cache_path)
        if age < 86400:
            with open(cache_path) as f:
                candles = json.load(f)
            print(f"  Cached {symbol}: {len(candles)} candles")
            return candles

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
    filtered = []
    for c in candles:
        intraday_drop = (c["high"] - c["low"]) / c["high"] if c["high"] > 0 else 0
        oc_drop = (c["open"] - c["close"]) / c["open"] if c["open"] > 0 else 0
        if c["date"] in crash_dates or intraday_drop > CRASH_THRESHOLD or oc_drop > CRASH_THRESHOLD:
            continue
        filtered.append(c)
    return filtered


@dataclass
class Trade:
    entry_date: str
    exit_date: str
    side: str
    entry_price: float
    exit_price: float
    leveraged_pnl_pct: float
    wallet_before: float
    wallet_after: float
    exit_reason: str
    days_held: int = 0


@dataclass
class Config:
    ema_fast: int = 12
    ema_slow: int = 26
    rsi_period: int = 21
    rsi_long_threshold: float = 50.0
    rsi_short_threshold: float = 50.0
    leverage: int = 2
    allocation: float = 1.0       # fraction of wallet to allocate
    sl_pct: float = -60.0         # stop-loss in leveraged PnL %
    tp_activation_pct: float = 10.0
    tp_ema_fast: int = 7
    tp_ema_slow: int = 14
    tp_cross_days: int = 2
    fee_rate: float = 0.0005
    initial_capital: float = 818.0
    include_funding: bool = True
    funding_rate_daily: float = 0.0003


def run_backtest(candles: list[dict], config: Config) -> dict:
    closes = [c["close"] for c in candles]
    lows = [c["low"] for c in candles]
    highs = [c["high"] for c in candles]
    dates = [c["date"] for c in candles]
    n = len(closes)

    ema_fast = compute_ema(closes, config.ema_fast)
    ema_slow = compute_ema(closes, config.ema_slow)
    rsi = compute_rsi(closes, config.rsi_period)
    ema_tp_fast = compute_ema(closes, config.tp_ema_fast)
    ema_tp_slow = compute_ema(closes, config.tp_ema_slow)

    wallet = config.initial_capital
    peak_wallet = wallet
    max_drawdown = 0.0
    trades: list[Trade] = []
    in_position = False
    position_side: str = ""
    entry_price = 0.0
    entry_date = ""
    entry_idx = 0
    allocated = 0.0  # amount allocated to position
    tp_activated = False
    tp_cross_count = 0
    equity_curve = []
    warmup = max(config.ema_slow, config.rsi_period, config.tp_ema_slow) + 1

    for i in range(n):
        # Equity tracking
        if in_position:
            if position_side == "LONG":
                unrealized_pct = ((closes[i] / entry_price) - 1) * 100 * config.leverage
            else:
                unrealized_pct = ((entry_price / closes[i]) - 1) * 100 * config.leverage
            # Only allocated portion is at risk
            unallocated = wallet - allocated
            current_equity = unallocated + allocated * (1 + unrealized_pct / 100)
        else:
            current_equity = wallet

        equity_curve.append({"date": dates[i], "equity": current_equity})
        if current_equity > peak_wallet:
            peak_wallet = current_equity
        dd = (peak_wallet - current_equity) / peak_wallet * 100 if peak_wallet > 0 else 0
        if dd > max_drawdown:
            max_drawdown = dd

        if i < warmup:
            continue
        if any(v is None for v in [ema_fast[i], ema_slow[i], rsi[i], ema_tp_fast[i], ema_tp_slow[i]]):
            continue

        # ── EXIT ──
        if in_position:
            if position_side == "LONG":
                intraday_worst = ((lows[i] / entry_price) - 1) * 100 * config.leverage
                close_pnl = ((closes[i] / entry_price) - 1) * 100 * config.leverage
            else:
                intraday_worst = ((entry_price / highs[i]) - 1) * 100 * config.leverage
                close_pnl = ((entry_price / closes[i]) - 1) * 100 * config.leverage

            # Liquidation check
            if intraday_worst <= -100:
                wallet = wallet - allocated  # lose entire allocated amount
                trades.append(Trade(entry_date=entry_date, exit_date=dates[i],
                    side=position_side, entry_price=entry_price, exit_price=closes[i],
                    leveraged_pnl_pct=-100.0, wallet_before=wallet+allocated, wallet_after=wallet,
                    exit_reason="LIQUIDATED", days_held=i-entry_idx))
                in_position = False
                tp_activated = False
                tp_cross_count = 0
                continue

            # SL check (strict: capped at exactly sl_pct)
            if intraday_worst <= config.sl_pct:
                fee_cost = config.fee_rate * config.leverage * 2 * 100
                net_pnl = config.sl_pct - fee_cost
                pnl_amount = allocated * net_pnl / 100
                old_wallet = wallet
                wallet = wallet + pnl_amount  # wallet already excludes allocated, add back with PnL
                # Wait, need to reconsider. wallet = unallocated + allocated. On exit:
                # wallet = unallocated + allocated * (1 + net_pnl/100)
                wallet = (old_wallet - allocated) + allocated * (1 + net_pnl / 100)
                if wallet < 0:
                    wallet = 0
                trades.append(Trade(entry_date=entry_date, exit_date=dates[i],
                    side=position_side, entry_price=entry_price, exit_price=closes[i],
                    leveraged_pnl_pct=net_pnl, wallet_before=old_wallet, wallet_after=wallet,
                    exit_reason="STOP_LOSS", days_held=i-entry_idx))
                in_position = False
                tp_activated = False
                tp_cross_count = 0
                continue

            # TP check
            if close_pnl >= config.tp_activation_pct:
                tp_activated = True

            if tp_activated:
                if position_side == "LONG" and ema_tp_fast[i] < ema_tp_slow[i]:
                    tp_cross_count += 1
                elif position_side == "SHORT" and ema_tp_fast[i] > ema_tp_slow[i]:
                    tp_cross_count += 1
                else:
                    tp_cross_count = 0

                if tp_cross_count >= config.tp_cross_days:
                    fee_cost = config.fee_rate * config.leverage * 2 * 100
                    net_pnl = close_pnl - fee_cost
                    old_wallet = wallet
                    wallet = (old_wallet - allocated) + allocated * (1 + net_pnl / 100)
                    trades.append(Trade(entry_date=entry_date, exit_date=dates[i],
                        side=position_side, entry_price=entry_price, exit_price=closes[i],
                        leveraged_pnl_pct=net_pnl, wallet_before=old_wallet, wallet_after=wallet,
                        exit_reason="TP_EMA_CROSS", days_held=i-entry_idx))
                    in_position = False
                    tp_activated = False
                    tp_cross_count = 0
                    continue

            # Daily funding on allocated portion
            if config.include_funding:
                daily_funding = allocated * config.leverage * config.funding_rate_daily
                wallet -= daily_funding

            continue

        # ── ENTRY ──
        if wallet <= 10:
            continue

        if ema_fast[i] > ema_slow[i] and rsi[i] > config.rsi_long_threshold:
            allocated = wallet * config.allocation
            entry_price = closes[i]
            entry_date = dates[i]
            entry_idx = i
            position_side = "LONG"
            in_position = True
            tp_activated = False
            tp_cross_count = 0
            continue

        if ema_fast[i] < ema_slow[i] and rsi[i] < config.rsi_short_threshold:
            allocated = wallet * config.allocation
            entry_price = closes[i]
            entry_date = dates[i]
            entry_idx = i
            position_side = "SHORT"
            in_position = True
            tp_activated = False
            tp_cross_count = 0
            continue

    # Close open position at end
    if in_position:
        if position_side == "LONG":
            close_pnl = ((closes[-1] / entry_price) - 1) * 100 * config.leverage
        else:
            close_pnl = ((entry_price / closes[-1]) - 1) * 100 * config.leverage
        fee_cost = config.fee_rate * config.leverage * 2 * 100
        net_pnl = close_pnl - fee_cost
        old_wallet = wallet
        wallet = (old_wallet - allocated) + allocated * (1 + net_pnl / 100)
        trades.append(Trade(entry_date=entry_date, exit_date=dates[-1],
            side=position_side, entry_price=entry_price, exit_price=closes[-1],
            leveraged_pnl_pct=net_pnl, wallet_before=old_wallet, wallet_after=wallet,
            exit_reason="END_OF_DATA", days_held=len(closes)-1-entry_idx))
        in_position = False

    # Stats
    total_return = (wallet / config.initial_capital - 1) * 100
    start_date = datetime.strptime(dates[warmup], "%Y-%m-%d")
    end_date = datetime.strptime(dates[-1], "%Y-%m-%d")
    years = (end_date - start_date).days / 365.25
    cagr = ((wallet / config.initial_capital) ** (1 / years) - 1) * 100 if years > 0 and wallet > 0 else 0
    winning = [t for t in trades if t.leveraged_pnl_pct > 0]
    losing = [t for t in trades if t.leveraged_pnl_pct <= 0]

    bnh_start = closes[warmup]
    bnh_end = closes[-1]
    bnh_return = (bnh_end / bnh_start - 1) * 100

    avg_days = sum(t.days_held for t in trades) / len(trades) if trades else 0

    return {
        "leverage": config.leverage,
        "allocation": config.allocation,
        "initial_capital": config.initial_capital,
        "final_wallet": wallet,
        "total_return_pct": total_return,
        "cagr_pct": cagr,
        "years": years,
        "max_drawdown_pct": max_drawdown,
        "total_trades": len(trades),
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "win_rate": len(winning) / len(trades) * 100 if trades else 0,
        "avg_win_pct": sum(t.leveraged_pnl_pct for t in winning) / len(winning) if winning else 0,
        "avg_loss_pct": sum(t.leveraged_pnl_pct for t in losing) / len(losing) if losing else 0,
        "best_trade_pct": max((t.leveraged_pnl_pct for t in trades), default=0),
        "worst_trade_pct": min((t.leveraged_pnl_pct for t in trades), default=0),
        "avg_days_held": avg_days,
        "data_start": dates[0],
        "data_end": dates[-1],
        "trade_start": dates[warmup],
        "buy_and_hold_pct": bnh_return,
        "trades": trades,
    }


def print_trades(r: dict) -> None:
    print(f"\n  {'#':>3} {'Entry':>10} {'Exit':>10} {'Side':>5} {'Entry$':>10} {'Exit$':>10} {'PnL%':>8} {'Days':>5} {'Wallet':>12} {'Reason'}")
    print(f"  {'---':>3} {'----------':>10} {'----------':>10} {'-----':>5} {'----------':>10} {'----------':>10} {'--------':>8} {'-----':>5} {'------------':>12} {'------'}")
    for idx, t in enumerate(r["trades"], 1):
        print(f"  {idx:3d} {t.entry_date:>10} {t.exit_date:>10} {t.side:>5} "
              f"{t.entry_price:10.2f} {t.exit_price:10.2f} {t.leveraged_pnl_pct:+8.1f}% "
              f"{t.days_held:5d} ${t.wallet_after:11,.2f} {t.exit_reason}")


def main():
    print("=" * 70)
    print("  BTC 2x Leverage Study — MaxDD Reduction")
    print("  Initial: $818 | Crash excluded | Funding included")
    print("=" * 70)

    candles = fetch_all_klines("BTCUSDT")
    filtered = filter_crashes(candles)
    print(f"  Data: {len(filtered)} candles (crash days removed)")

    # Test configurations
    configs = [
        ("3x 100%", Config(leverage=3, allocation=1.0, sl_pct=-60, initial_capital=818)),
        ("3x 70%",  Config(leverage=3, allocation=0.7, sl_pct=-60, initial_capital=818)),
        ("2x 100%", Config(leverage=2, allocation=1.0, sl_pct=-60, initial_capital=818)),
        ("2x 70%",  Config(leverage=2, allocation=0.7, sl_pct=-60, initial_capital=818)),
        ("3x 50%",  Config(leverage=3, allocation=0.5, sl_pct=-60, initial_capital=818)),
        ("2x 50%",  Config(leverage=2, allocation=0.5, sl_pct=-60, initial_capital=818)),
    ]

    results = []
    for label, cfg in configs:
        cfg.include_funding = True
        r = run_backtest(filtered, cfg)
        results.append((label, r))

        print(f"\n{'='*70}")
        print(f"  {label}")
        print(f"{'='*70}")
        print(f"  Final:  ${r['final_wallet']:,.2f}  ({r['total_return_pct']:+,.1f}%)")
        print(f"  CAGR:   {r['cagr_pct']:+.1f}%")
        print(f"  MaxDD:  {r['max_drawdown_pct']:.1f}%")
        print(f"  Trades: {r['total_trades']} (W:{r['winning_trades']} L:{r['losing_trades']} WR:{r['win_rate']:.0f}%)")
        print(f"  Avg Win: {r['avg_win_pct']:+.1f}%  Avg Loss: {r['avg_loss_pct']:+.1f}%")
        print(f"  Avg Hold: {r['avg_days_held']:.0f} days")
        print(f"  B&H:    {r['buy_and_hold_pct']:+,.1f}%")
        print_trades(r)

    # Summary table
    print(f"\n\n{'='*70}")
    print(f"  COMPARISON SUMMARY (Crash excluded + Funding)")
    print(f"  Initial: $818")
    print(f"{'='*70}")
    print(f"  {'Config':<20} {'Final$':>12} {'Return':>10} {'CAGR':>8} {'MaxDD':>8} {'Trades':>7} {'WR':>5} {'AvgHold':>8}")
    print(f"  {'-'*20} {'-'*12} {'-'*10} {'-'*8} {'-'*8} {'-'*7} {'-'*5} {'-'*8}")
    for label, r in results:
        print(f"  {label:<20} ${r['final_wallet']:>11,.2f} {r['total_return_pct']:>+9.1f}% {r['cagr_pct']:>+7.1f}% {r['max_drawdown_pct']:>7.1f}% {r['total_trades']:>7} {r['win_rate']:>4.0f}% {r['avg_days_held']:>6.0f}d")

    # Buy & hold
    bnh = results[0][1]["buy_and_hold_pct"]
    bnh_final = 818 * (1 + bnh / 100)
    years = results[0][1]["years"]
    bnh_cagr = ((1 + bnh/100) ** (1/years) - 1) * 100
    print(f"  {'Buy & Hold':<20} ${bnh_final:>11,.2f} {bnh:>+9.1f}% {bnh_cagr:>+7.1f}%     N/A%       0   N/A      N/A")

    # Yearly breakdown for best option
    print(f"\n\n{'='*70}")
    print(f"  YEARLY BREAKDOWN — 2x 100%")
    print(f"{'='*70}")
    best = results[1][1]  # 2x 100%
    yearly = {}
    for t in best["trades"]:
        year = t.exit_date[:4]
        if year not in yearly:
            yearly[year] = {"wins": 0, "losses": 0, "pnl_pct": 0}
        if t.leveraged_pnl_pct > 0:
            yearly[year]["wins"] += 1
        else:
            yearly[year]["losses"] += 1
        yearly[year]["pnl_pct"] += t.leveraged_pnl_pct

    print(f"  {'Year':<6} {'W':>4} {'L':>4} {'WR':>6} {'Cum PnL%':>10}")
    cum = 0
    for year in sorted(yearly):
        y = yearly[year]
        total = y["wins"] + y["losses"]
        wr = y["wins"] / total * 100 if total else 0
        cum += y["pnl_pct"]
        print(f"  {year:<6} {y['wins']:>4} {y['losses']:>4} {wr:>5.0f}% {cum:>+10.1f}%")


if __name__ == "__main__":
    main()
