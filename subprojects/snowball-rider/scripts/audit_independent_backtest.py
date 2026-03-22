#!/usr/bin/env python3
"""Independent Audit Team 2: Completely independent backtest reimplementation.

This script reimplements the EMA/RSI indicators and backtest engine from scratch,
then compares results with grid_search.py to verify correctness.

All indicator calculations and backtest logic are implemented independently
without importing from snowball_rider.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime


# ============================================================================
# INDEPENDENT INDICATOR IMPLEMENTATIONS (from scratch)
# ============================================================================

def indie_ema(values: list[float], period: int) -> list[float | None]:
    """Compute EMA from scratch.

    - First (period-1) values are None (not enough data).
    - Seed value at index (period-1) = SMA of first `period` values.
    - Subsequent values use multiplier = 2/(period+1).
    """
    result: list[float | None] = []
    k = 2.0 / (period + 1.0)
    prev_ema: float | None = None

    for idx in range(len(values)):
        if idx + 1 < period:
            result.append(None)
            continue

        if prev_ema is None:
            # Seed: SMA of values[0..period-1]
            sma = sum(values[idx + 1 - period: idx + 1]) / period
            prev_ema = sma
            result.append(prev_ema)
        else:
            ema_val = (values[idx] - prev_ema) * k + prev_ema
            prev_ema = ema_val
            result.append(ema_val)

    return result


def indie_rsi(closes: list[float], period: int) -> list[float | None]:
    """Compute RSI from scratch using SMA-based smoothing.

    - deltas[0] = 0 (no previous close)
    - For each index i, use rolling window of `period` deltas ending at i.
    - avg_gain = mean of gains in window, avg_loss = mean of losses in window.
    - RS = avg_gain / avg_loss, RSI = 100 - 100/(1+RS).
    """
    if not closes:
        return []

    n = len(closes)

    # Compute price changes; delta[0] = 0
    deltas = [0.0] * n
    for i in range(1, n):
        deltas[i] = closes[i] - closes[i - 1]

    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]

    result: list[float | None] = []
    for i in range(n):
        if i + 1 < period:
            result.append(None)
            continue

        window_gains = gains[i + 1 - period: i + 1]
        window_losses = losses[i + 1 - period: i + 1]
        avg_g = sum(window_gains) / period
        avg_l = sum(window_losses) / period

        if avg_l <= 0:
            result.append(100.0)
        else:
            rs = avg_g / avg_l
            rsi_val = 100.0 - (100.0 / (1.0 + rs))
            result.append(rsi_val)

    return result


# ============================================================================
# INDEPENDENT BACKTEST ENGINE (from scratch)
# ============================================================================

def indie_backtest(
    candles: list[dict],
    leverage: int = 2,
    allocation: float = 0.6,
    sl_pct: float = -70.0,
    tp_pct: float = 20.0,
    ema_fast: int = 10,
    ema_slow: int = 26,
    rsi_period: int = 21,
    rsi_long: float = 45.0,
    rsi_short: float = 55.0,
    tp_ema_fast: int = 7,
    tp_ema_slow: int = 14,
    tp_cross_days: int = 2,
    initial_capital: float = 818.0,
    fee_rate: float = 0.0005,
    funding_daily: float = 0.0003,
    verbose: bool = True,
) -> dict:
    """Run backtest with completely independent implementation."""

    # Extract OHLCV arrays
    closes = [c["close"] for c in candles]
    lows = [c["low"] for c in candles]
    highs = [c["high"] for c in candles]
    dates = [c["date"] for c in candles]
    n = len(closes)

    # Compute indicators independently
    ema_f = indie_ema(closes, ema_fast)
    ema_s = indie_ema(closes, ema_slow)
    rsi = indie_rsi(closes, rsi_period)
    ema_tf = indie_ema(closes, tp_ema_fast)
    ema_ts = indie_ema(closes, tp_ema_slow)

    # State
    wallet = initial_capital
    peak_wallet = wallet
    max_dd = 0.0

    in_pos = False
    side = ""
    entry_px = 0.0
    alloc = 0.0
    tp_active = False
    tp_cross = 0
    entry_date = ""

    trade_count = 0
    win_count = 0
    loss_count = 0
    liquidated = False

    trades: list[dict] = []

    warmup = max(ema_slow, rsi_period, tp_ema_slow) + 1

    for i in range(n):
        # Track equity for drawdown
        if in_pos:
            if side == "LONG":
                unreal = ((closes[i] / entry_px) - 1.0) * 100.0 * leverage
            else:
                unreal = ((entry_px / closes[i]) - 1.0) * 100.0 * leverage
            equity = (wallet - alloc) + alloc * (1.0 + unreal / 100.0)
        else:
            equity = wallet

        if equity > peak_wallet:
            peak_wallet = equity
        if peak_wallet > 0:
            dd = (peak_wallet - equity) / peak_wallet * 100.0
            if dd > max_dd:
                max_dd = dd

        # Skip warmup
        if i < warmup:
            continue
        if any(v is None for v in [ema_f[i], ema_s[i], rsi[i], ema_tf[i], ema_ts[i]]):
            continue

        # === IN POSITION ===
        if in_pos:
            if side == "LONG":
                intraday_worst = ((lows[i] / entry_px) - 1.0) * 100.0 * leverage
                close_pnl = ((closes[i] / entry_px) - 1.0) * 100.0 * leverage
            else:
                intraday_worst = ((entry_px / highs[i]) - 1.0) * 100.0 * leverage
                close_pnl = ((entry_px / closes[i]) - 1.0) * 100.0 * leverage

            # Liquidation check
            if intraday_worst <= -100.0:
                old_w = wallet
                wallet = wallet - alloc
                if wallet < 0:
                    wallet = 0
                trade_count += 1
                loss_count += 1
                if verbose:
                    trades.append({
                        "entry_date": entry_date,
                        "exit_date": dates[i],
                        "side": side,
                        "entry_price": entry_px,
                        "exit_price": lows[i] if side == "LONG" else highs[i],
                        "pnl_pct": -100.0,
                        "wallet_after": wallet,
                        "reason": "LIQUIDATION",
                    })
                in_pos = False
                tp_active = False
                tp_cross = 0
                if wallet <= 10:
                    liquidated = True
                    break
                continue

            # Stop loss check
            if intraday_worst <= sl_pct:
                fee_cost = fee_rate * leverage * 2 * 100
                net_pnl = sl_pct - fee_cost
                old_w = wallet
                wallet = (old_w - alloc) + alloc * (1.0 + net_pnl / 100.0)
                if wallet < 0:
                    wallet = 0
                trade_count += 1
                loss_count += 1
                if verbose:
                    trades.append({
                        "entry_date": entry_date,
                        "exit_date": dates[i],
                        "side": side,
                        "entry_price": entry_px,
                        "exit_price": closes[i],
                        "pnl_pct": net_pnl,
                        "wallet_after": wallet,
                        "reason": "SL",
                    })
                in_pos = False
                tp_active = False
                tp_cross = 0
                if wallet <= 10:
                    liquidated = True
                    break
                continue

            # TP activation
            if close_pnl >= tp_pct:
                tp_active = True

            # TP cross counting
            if tp_active:
                if side == "LONG" and ema_tf[i] < ema_ts[i]:
                    tp_cross += 1
                elif side == "SHORT" and ema_tf[i] > ema_ts[i]:
                    tp_cross += 1
                else:
                    tp_cross = 0

                if tp_cross >= tp_cross_days:
                    fee_cost = fee_rate * leverage * 2 * 100
                    net_pnl = close_pnl - fee_cost
                    old_w = wallet
                    wallet = (old_w - alloc) + alloc * (1.0 + net_pnl / 100.0)
                    trade_count += 1
                    if net_pnl > 0:
                        win_count += 1
                    else:
                        loss_count += 1
                    if verbose:
                        trades.append({
                            "entry_date": entry_date,
                            "exit_date": dates[i],
                            "side": side,
                            "entry_price": entry_px,
                            "exit_price": closes[i],
                            "pnl_pct": net_pnl,
                            "wallet_after": wallet,
                            "reason": "TP",
                        })
                    in_pos = False
                    tp_active = False
                    tp_cross = 0
                    continue

            # Daily funding
            daily_fund = alloc * leverage * funding_daily
            wallet -= daily_fund
            continue

        # === NOT IN POSITION ===
        if wallet <= 10:
            break

        # Entry LONG
        if ema_f[i] > ema_s[i] and rsi[i] > rsi_long:
            alloc = wallet * allocation
            entry_px = closes[i]
            side = "LONG"
            in_pos = True
            tp_active = False
            tp_cross = 0
            entry_date = dates[i]
            continue

        # Entry SHORT
        if ema_f[i] < ema_s[i] and rsi[i] < rsi_short:
            alloc = wallet * allocation
            entry_px = closes[i]
            side = "SHORT"
            in_pos = True
            tp_active = False
            tp_cross = 0
            entry_date = dates[i]
            continue

    # Close open position at end of data
    if in_pos and wallet > 0:
        if side == "LONG":
            close_pnl = ((closes[-1] / entry_px) - 1.0) * 100.0 * leverage
        else:
            close_pnl = ((entry_px / closes[-1]) - 1.0) * 100.0 * leverage
        fee_cost = fee_rate * leverage * 2 * 100
        net_pnl = close_pnl - fee_cost
        old_w = wallet
        wallet = (old_w - alloc) + alloc * (1.0 + net_pnl / 100.0)
        trade_count += 1
        if net_pnl > 0:
            win_count += 1
        else:
            loss_count += 1
        if verbose:
            trades.append({
                "entry_date": entry_date,
                "exit_date": dates[-1],
                "side": side,
                "entry_price": entry_px,
                "exit_price": closes[-1],
                "pnl_pct": net_pnl,
                "wallet_after": wallet,
                "reason": "END",
            })

    total_return = (wallet / initial_capital - 1.0) * 100.0
    start_date = datetime.strptime(dates[warmup], "%Y-%m-%d")
    end_date = datetime.strptime(dates[-1], "%Y-%m-%d")
    years = (end_date - start_date).days / 365.25
    if years > 0 and wallet > 0:
        cagr = ((wallet / initial_capital) ** (1.0 / years) - 1.0) * 100.0
    else:
        cagr = 0.0
    win_rate = win_count / trade_count * 100.0 if trade_count > 0 else 0.0

    return {
        "final_wallet": wallet,
        "total_return_pct": total_return,
        "cagr_pct": cagr,
        "max_drawdown_pct": max_dd,
        "trade_count": trade_count,
        "win_rate": win_rate,
        "win_count": win_count,
        "loss_count": loss_count,
        "liquidated": liquidated,
        "trades": trades,
        "years": years,
    }


# ============================================================================
# MAIN: Run independent backtest and compare with grid_search.py
# ============================================================================

def main():
    print("=" * 90)
    print("  INDEPENDENT AUDIT TEAM 2: Backtest Reimplementation Comparison")
    print("=" * 90)

    # Load cached data (no crash filtering, as specified)
    data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'btcusdt_1d_klines.json')
    with open(data_path) as f:
        candles = json.load(f)
    print(f"\n  Data loaded: {len(candles)} candles")
    print(f"  Date range: {candles[0]['date']} to {candles[-1]['date']}")

    # Parameters (matching the audit specification)
    params = dict(
        leverage=2,
        allocation=0.6,
        sl_pct=-70.0,
        tp_pct=20.0,
        ema_fast=10,
        ema_slow=26,
        rsi_period=21,
        rsi_long=45.0,
        rsi_short=55.0,
        tp_ema_fast=7,
        tp_ema_slow=14,
        tp_cross_days=2,
        initial_capital=818.0,
        fee_rate=0.0005,
        funding_daily=0.0003,
    )

    print(f"\n  Parameters:")
    print(f"    Leverage: {params['leverage']}x | Allocation: {params['allocation']:.0%}")
    print(f"    SL: {params['sl_pct']}% | TP: {params['tp_pct']}%")
    print(f"    EMA: {params['ema_fast']}/{params['ema_slow']} | RSI({params['rsi_period']}): >{params['rsi_long']} / <{params['rsi_short']}")
    print(f"    TP EMA: {params['tp_ema_fast']}/{params['tp_ema_slow']} | TP cross days: {params['tp_cross_days']}")
    print(f"    Initial capital: ${params['initial_capital']}")

    # ========================================================================
    # Run independent backtest
    # ========================================================================
    print(f"\n{'=' * 90}")
    print("  PHASE 1: Independent Backtest")
    print(f"{'=' * 90}")

    indie_result = indie_backtest(candles, **params, verbose=True)

    print(f"\n  --- Trade Log ---")
    print(f"  {'#':>3} {'Entry Date':>12} {'Exit Date':>12} {'Side':>6} {'Entry$':>12} {'Exit$':>12} {'PnL%':>10} {'Wallet':>12} {'Reason':>8}")
    print(f"  {'---':>3} {'----------':>12} {'---------':>12} {'----':>6} {'------':>12} {'-----':>12} {'----':>10} {'------':>12} {'------':>8}")
    for idx, t in enumerate(indie_result["trades"], 1):
        print(f"  {idx:3d} {t['entry_date']:>12} {t['exit_date']:>12} {t['side']:>6} "
              f"${t['entry_price']:>11,.2f} ${t['exit_price']:>11,.2f} "
              f"{t['pnl_pct']:>+9.2f}% ${t['wallet_after']:>11,.2f} {t['reason']:>8}")

    print(f"\n  --- Summary ---")
    print(f"  Final wallet:  ${indie_result['final_wallet']:,.2f}")
    print(f"  Total return:  {indie_result['total_return_pct']:+.2f}%")
    print(f"  CAGR:          {indie_result['cagr_pct']:+.2f}%")
    print(f"  Max drawdown:  {indie_result['max_drawdown_pct']:.2f}%")
    print(f"  Trade count:   {indie_result['trade_count']}")
    print(f"  Win rate:      {indie_result['win_rate']:.1f}% ({indie_result['win_count']}W / {indie_result['loss_count']}L)")
    print(f"  Liquidated:    {indie_result['liquidated']}")

    # ========================================================================
    # Run grid_search.py for comparison
    # ========================================================================
    print(f"\n{'=' * 90}")
    print("  PHASE 2: grid_search.py Reference Backtest")
    print(f"{'=' * 90}")

    sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
    from grid_search import run_backtest
    import grid_search
    grid_search.INITIAL_CAPITAL = 818.0

    ref_result = run_backtest(
        candles,
        leverage=2,
        allocation=0.6,
        sl_pct=-70,
        tp_pct=20,
        ema_fast=10,
        ema_slow=26,
        rsi_period=21,
        rsi_long=45,
        rsi_short=55,
    )

    print(f"\n  --- Reference Summary ---")
    print(f"  Final wallet:  ${ref_result['final_wallet']:,.2f}")
    print(f"  Total return:  {ref_result['total_return_pct']:+.2f}%")
    print(f"  CAGR:          {ref_result['cagr_pct']:+.2f}%")
    print(f"  Max drawdown:  {ref_result['max_drawdown_pct']:.2f}%")
    print(f"  Trade count:   {ref_result['trade_count']}")
    print(f"  Win rate:      {ref_result['win_rate']:.1f}%")
    print(f"  Liquidated:    {ref_result['liquidated']}")

    # ========================================================================
    # Comparison
    # ========================================================================
    print(f"\n{'=' * 90}")
    print("  PHASE 3: Comparison")
    print(f"{'=' * 90}")

    indie_w = indie_result["final_wallet"]
    ref_w = ref_result["final_wallet"]
    if ref_w != 0:
        diff_pct = abs(indie_w - ref_w) / ref_w * 100
    else:
        diff_pct = 0.0 if indie_w == 0 else float('inf')

    metrics = [
        ("Final Wallet", f"${indie_w:,.2f}", f"${ref_w:,.2f}", diff_pct),
        ("Total Return", f"{indie_result['total_return_pct']:+.2f}%", f"{ref_result['total_return_pct']:+.2f}%",
         abs(indie_result['total_return_pct'] - ref_result['total_return_pct'])),
        ("Trade Count", str(indie_result['trade_count']), str(ref_result['trade_count']),
         abs(indie_result['trade_count'] - ref_result['trade_count'])),
        ("Win Rate", f"{indie_result['win_rate']:.1f}%", f"{ref_result['win_rate']:.1f}%",
         abs(indie_result['win_rate'] - ref_result['win_rate'])),
        ("Max Drawdown", f"{indie_result['max_drawdown_pct']:.2f}%", f"{ref_result['max_drawdown_pct']:.2f}%",
         abs(indie_result['max_drawdown_pct'] - ref_result['max_drawdown_pct'])),
        ("CAGR", f"{indie_result['cagr_pct']:+.2f}%", f"{ref_result['cagr_pct']:+.2f}%",
         abs(indie_result['cagr_pct'] - ref_result['cagr_pct'])),
    ]

    print(f"\n  {'Metric':<20} {'Independent':>20} {'grid_search':>20} {'Diff':>15}")
    print(f"  {'------':<20} {'-----------':>20} {'-----------':>20} {'----':>15}")
    for name, indie_v, ref_v, diff in metrics:
        print(f"  {name:<20} {indie_v:>20} {ref_v:>20} {diff:>14.4f}")

    # Final verdict
    TOLERANCE = 0.01  # 0.01% tolerance
    print(f"\n  Wallet difference: {diff_pct:.6f}%")
    if diff_pct <= TOLERANCE and indie_result['trade_count'] == ref_result['trade_count']:
        print(f"\n  >>> MATCH <<< (difference {diff_pct:.6f}% <= {TOLERANCE}% tolerance)")
    else:
        print(f"\n  >>> MISMATCH <<< (difference {diff_pct:.6f}%)")
        if indie_result['trade_count'] != ref_result['trade_count']:
            print(f"      Trade count differs: {indie_result['trade_count']} vs {ref_result['trade_count']}")

    print(f"\n{'=' * 90}")


if __name__ == "__main__":
    main()
