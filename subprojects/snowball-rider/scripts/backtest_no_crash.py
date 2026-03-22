#!/usr/bin/env python3
"""Backtest excluding extreme crash days (>30% single-day drop).

Tests BTC and XRP with best-known parameters from previous session:
- XRP: EMA10/30 RSI21>55<45 SL50% TP15% 3x
- BTC: EMA12/26 RSI21>50<50 SL60% TP10% 3x

Runs 4 scenarios per symbol:
1. Full data (baseline)
2. Exclude crash days (>30% drop)
3. Full data + funding
4. Exclude crash + funding
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


# ── Crash dates to exclude (>30% single-day drop) ──
CRASH_DATES = {
    # BTC
    "2020-03-12",  # COVID crash -56%
    "2020-03-13",  # COVID aftershock
    # XRP
    "2020-03-12",  # COVID crash XRP -46%
    "2020-03-13",
}

# Additional: any day with >30% intraday drop (high→low)
CRASH_THRESHOLD = 0.30  # 30%


def fetch_all_klines(symbol: str, interval: str = "1d") -> list[dict]:
    """Fetch ALL daily klines from Binance Futures, paginating backward."""
    cache_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f'{symbol.lower()}_{interval}_klines.json')

    # Use cache if < 1 day old
    if os.path.exists(cache_path):
        age = time.time() - os.path.getmtime(cache_path)
        if age < 86400:
            with open(cache_path) as f:
                candles = json.load(f)
            print(f"  Using cached {symbol} data ({len(candles)} candles)")
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
        oldest_open_time = data[0][0]
        end_time = oldest_open_time - 1

        oldest_date = datetime.fromtimestamp(oldest_open_time/1000, tz=timezone.utc).strftime('%Y-%m-%d')
        print(f"  Fetched {len(data)} candles, total: {len(all_klines)}, oldest: {oldest_date}")

        if len(data) < 1500:
            break
        time.sleep(0.2)

    # Deduplicate
    seen = set()
    unique = []
    for k in all_klines:
        ot = k[0]
        if ot not in seen:
            seen.add(ot)
            unique.append(k)
    unique.sort(key=lambda x: x[0])

    candles = []
    for k in unique:
        candles.append({
            "open_time": int(k[0]),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "date": datetime.fromtimestamp(int(k[0])/1000, tz=timezone.utc).strftime('%Y-%m-%d'),
        })

    with open(cache_path, 'w') as f:
        json.dump(candles, f)
    print(f"  Cached to {cache_path}")
    return candles


def filter_crashes(candles: list[dict], threshold: float = CRASH_THRESHOLD) -> tuple[list[dict], list[str]]:
    """Remove days with extreme intraday drops. Returns (filtered, removed_dates)."""
    filtered = []
    removed = []
    for c in candles:
        # Check intraday drop (high → low)
        intraday_drop = (c["high"] - c["low"]) / c["high"] if c["high"] > 0 else 0
        # Check open → close drop
        oc_drop = (c["open"] - c["close"]) / c["open"] if c["open"] > 0 else 0

        if c["date"] in CRASH_DATES or intraday_drop > threshold or oc_drop > threshold:
            removed.append(f"{c['date']} (intraday: -{intraday_drop*100:.1f}%, O→C: -{oc_drop*100:.1f}%)")
        else:
            filtered.append(c)
    return filtered, removed


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


@dataclass
class Config:
    ema_fast: int = 10
    ema_slow: int = 30
    rsi_period: int = 21
    rsi_long_threshold: float = 55.0
    rsi_short_threshold: float = 45.0
    leverage: int = 3
    sl_pct: float = -50.0
    tp_activation_pct: float = 15.0
    tp_ema_fast: int = 7
    tp_ema_slow: int = 14
    tp_cross_days: int = 2
    fee_rate: float = 0.0005
    initial_capital: float = 1000.0
    include_funding: bool = False
    funding_rate_daily: float = 0.0003  # ~0.01% per 8h


def run_backtest(candles: list[dict], config: Config) -> dict:
    """Strict SL at exact level (perfect execution). Funding optional."""
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
    position_side: Optional[str] = None
    entry_price = 0.0
    entry_date = ""
    entry_idx = 0
    tp_activated = False
    tp_cross_count = 0
    equity_curve = []
    warmup = max(config.ema_slow, config.rsi_period, config.tp_ema_slow) + 1

    for i in range(n):
        # Equity tracking
        if in_position:
            if position_side == "LONG":
                unrealized = ((closes[i] / entry_price) - 1) * 100 * config.leverage
            else:
                unrealized = ((entry_price / closes[i]) - 1) * 100 * config.leverage
            current_equity = wallet * (1 + unrealized / 100)
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

            # Check liquidation (leveraged loss >= 100%)
            if intraday_worst <= -100:
                fee_cost = config.fee_rate * config.leverage * 2 * 100
                trades.append(Trade(entry_date=entry_date, exit_date=dates[i],
                    side=position_side, entry_price=entry_price, exit_price=closes[i],
                    leveraged_pnl_pct=-100.0, wallet_before=wallet, wallet_after=0,
                    exit_reason="LIQUIDATED"))
                wallet = 0
                in_position = False
                tp_activated = False
                tp_cross_count = 0
                continue

            # SL check (strict: capped at exactly sl_pct)
            if intraday_worst <= config.sl_pct:
                fee_cost = config.fee_rate * config.leverage * 2 * 100
                net_pnl = config.sl_pct - fee_cost
                wallet_after = wallet * (1 + net_pnl / 100)
                if wallet_after < 0:
                    wallet_after = 0
                trades.append(Trade(entry_date=entry_date, exit_date=dates[i],
                    side=position_side, entry_price=entry_price, exit_price=closes[i],
                    leveraged_pnl_pct=net_pnl, wallet_before=wallet, wallet_after=wallet_after,
                    exit_reason="STOP_LOSS"))
                wallet = wallet_after
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
                    # Funding already deducted daily from wallet (line 284-286)
                    # Do NOT double-count here
                    net_pnl = close_pnl - fee_cost
                    wallet_after = wallet * (1 + net_pnl / 100)
                    trades.append(Trade(entry_date=entry_date, exit_date=dates[i],
                        side=position_side, entry_price=entry_price, exit_price=closes[i],
                        leveraged_pnl_pct=net_pnl, wallet_before=wallet, wallet_after=wallet_after,
                        exit_reason="TP_EMA_CROSS"))
                    wallet = wallet_after
                    in_position = False
                    tp_activated = False
                    tp_cross_count = 0
                    continue

            # Daily funding deduction
            if config.include_funding:
                daily_funding = wallet * config.leverage * config.funding_rate_daily
                wallet -= daily_funding

            continue

        # ── ENTRY ──
        if wallet <= 1:  # minimum viable
            continue

        if ema_fast[i] > ema_slow[i] and rsi[i] > config.rsi_long_threshold:
            entry_price = closes[i]
            entry_date = dates[i]
            entry_idx = i
            position_side = "LONG"
            in_position = True
            tp_activated = False
            tp_cross_count = 0
            continue

        if ema_fast[i] < ema_slow[i] and rsi[i] < config.rsi_short_threshold:
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
        # Funding already deducted daily from wallet
        net_pnl = close_pnl - fee_cost
        wallet_after = wallet * (1 + net_pnl / 100)
        trades.append(Trade(entry_date=entry_date, exit_date=dates[-1],
            side=position_side, entry_price=entry_price, exit_price=closes[-1],
            leveraged_pnl_pct=net_pnl, wallet_before=wallet, wallet_after=wallet_after,
            exit_reason="END_OF_DATA"))
        wallet = wallet_after

    # Stats
    total_return = (wallet / config.initial_capital - 1) * 100
    start_date = datetime.strptime(dates[warmup], "%Y-%m-%d")
    end_date = datetime.strptime(dates[-1], "%Y-%m-%d")
    years = (end_date - start_date).days / 365.25
    cagr = ((wallet / config.initial_capital) ** (1 / years) - 1) * 100 if years > 0 and wallet > 0 else 0
    winning = [t for t in trades if t.leveraged_pnl_pct > 0]
    losing = [t for t in trades if t.leveraged_pnl_pct <= 0]

    # Buy-and-hold comparison
    bnh_start = closes[warmup]
    bnh_end = closes[-1]
    bnh_return = (bnh_end / bnh_start - 1) * 100

    return {
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
        "data_start": dates[0],
        "data_end": dates[-1],
        "trade_start": dates[warmup],
        "buy_and_hold_pct": bnh_return,
        "trades": trades,
    }


def print_results(label: str, r: dict) -> None:
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    print(f"  Data: {r['data_start']} to {r['data_end']} ({r['years']:.1f} years)")
    print(f"  Initial:      ${r['initial_capital']:,.0f}")
    print(f"  Final:        ${r['final_wallet']:,.2f}")
    print(f"  Total Return: {r['total_return_pct']:+,.1f}%")
    print(f"  CAGR:         {r['cagr_pct']:+,.1f}%")
    print(f"  Max Drawdown: {r['max_drawdown_pct']:.1f}%")
    print(f"  Buy & Hold:   {r['buy_and_hold_pct']:+,.1f}%")
    print(f"  ---")
    print(f"  Trades: {r['total_trades']} (W:{r['winning_trades']} L:{r['losing_trades']} WR:{r['win_rate']:.0f}%)")
    print(f"  Avg Win:  {r['avg_win_pct']:+.1f}%  Avg Loss: {r['avg_loss_pct']:+.1f}%")
    print(f"  Best:     {r['best_trade_pct']:+.1f}%  Worst:    {r['worst_trade_pct']:+.1f}%")

    # Trade list
    print(f"\n  {'#':>3} {'Entry':>10} {'Exit':>10} {'Side':>5} {'Entry$':>10} {'Exit$':>10} {'PnL%':>8} {'Wallet':>12} {'Reason'}")
    print(f"  {'---':>3} {'----------':>10} {'----------':>10} {'-----':>5} {'----------':>10} {'----------':>10} {'--------':>8} {'------------':>12} {'------'}")
    for idx, t in enumerate(r["trades"], 1):
        print(f"  {idx:3d} {t.entry_date:>10} {t.exit_date:>10} {t.side:>5} "
              f"{t.entry_price:10.2f} {t.exit_price:10.2f} {t.leveraged_pnl_pct:+8.1f}% "
              f"${t.wallet_after:11,.2f} {t.exit_reason}")


def main():
    print("=" * 70)
    print("  BACKTEST: Crash Days Excluded")
    print("  Threshold: >30% single-day intraday drop removed")
    print("=" * 70)

    symbols = {
        "BTCUSDT": Config(
            ema_fast=12, ema_slow=26, rsi_period=21,
            rsi_long_threshold=50, rsi_short_threshold=50,
            leverage=3, sl_pct=-60, tp_activation_pct=10,
            tp_ema_fast=7, tp_ema_slow=14, tp_cross_days=2,
            initial_capital=1000,
        ),
        "XRPUSDT": Config(
            ema_fast=10, ema_slow=30, rsi_period=21,
            rsi_long_threshold=55, rsi_short_threshold=45,
            leverage=3, sl_pct=-50, tp_activation_pct=15,
            tp_ema_fast=7, tp_ema_slow=14, tp_cross_days=2,
            initial_capital=1000,
        ),
    }

    for symbol, cfg in symbols.items():
        print(f"\n\n{'#'*70}")
        print(f"  {symbol}  —  EMA({cfg.ema_fast}/{cfg.ema_slow}) RSI({cfg.rsi_period}) "
              f"SL{cfg.sl_pct}% TP{cfg.tp_activation_pct}% {cfg.leverage}x")
        print(f"{'#'*70}")

        print(f"\n  Fetching {symbol} data...")
        candles = fetch_all_klines(symbol)
        print(f"  Total: {len(candles)} candles ({candles[0]['date']} ~ {candles[-1]['date']})")

        # Filter crash days
        filtered, removed = filter_crashes(candles)
        print(f"\n  Removed {len(removed)} crash day(s):")
        for r in removed:
            print(f"    - {r}")
        print(f"  Remaining: {len(filtered)} candles")

        # ── Scenario 1: Full data, no funding ──
        cfg.include_funding = False
        r1 = run_backtest(candles, cfg)
        print_results(f"{symbol} — Full Data (no funding)", r1)

        # ── Scenario 2: Crash excluded, no funding ──
        r2 = run_backtest(filtered, cfg)
        print_results(f"{symbol} — Crash Excluded (no funding)", r2)

        # ── Scenario 3: Full data + funding ──
        cfg.include_funding = True
        r3 = run_backtest(candles, cfg)
        print_results(f"{symbol} — Full Data + Funding", r3)

        # ── Scenario 4: Crash excluded + funding ──
        r4 = run_backtest(filtered, cfg)
        print_results(f"{symbol} — Crash Excluded + Funding", r4)

        # Summary comparison
        print(f"\n{'='*70}")
        print(f"  {symbol} COMPARISON SUMMARY")
        print(f"{'='*70}")
        print(f"  {'Scenario':<35} {'Final$':>12} {'Return':>10} {'CAGR':>8} {'MaxDD':>8} {'Trades':>7}")
        print(f"  {'-'*35} {'-'*12} {'-'*10} {'-'*8} {'-'*8} {'-'*7}")
        for label, r in [
            ("Full data, no funding", r1),
            ("Crash excluded, no funding", r2),
            ("Full data + funding", r3),
            ("Crash excluded + funding", r4),
            ("Buy & Hold (no leverage)", {"final_wallet": 1000*(1+r1["buy_and_hold_pct"]/100),
                                          "total_return_pct": r1["buy_and_hold_pct"],
                                          "cagr_pct": ((1+r1["buy_and_hold_pct"]/100)**(1/r1["years"])-1)*100 if r1["years"]>0 else 0,
                                          "max_drawdown_pct": 0, "total_trades": 0}),
        ]:
            print(f"  {label:<35} ${r['final_wallet']:>11,.2f} {r['total_return_pct']:>+9.1f}% {r['cagr_pct']:>+7.1f}% {r['max_drawdown_pct']:>7.1f}% {r['total_trades']:>7}")


if __name__ == "__main__":
    main()
