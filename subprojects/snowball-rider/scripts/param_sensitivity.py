#!/usr/bin/env python3
"""Parameter sensitivity analysis for Strategy B.

Base config: 3x 40% SL-60% TP10% EMA12/26 RSI21>50<50
Varies ONE parameter at a time, flags overfitting if ±1 step causes >50% change.
"""

from __future__ import annotations
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from grid_search import run_backtest, filter_crashes, INITIAL_CAPITAL

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
CACHE_PATH = os.path.join(DATA_DIR, 'btcusdt_1d_klines.json')

# Base config for Strategy B
BASE = dict(
    leverage=3,
    allocation=0.4,
    sl_pct=-60,
    tp_pct=10,
    ema_fast=12,
    ema_slow=26,
    rsi_period=21,
    rsi_long=50,
    rsi_short=50,
)

# Parameter sweep ranges (base value marked with **)
SWEEPS = {
    "ema_fast":   [8, 9, 10, 11, 12, 13, 14, 15, 16],
    "ema_slow":   [20, 22, 24, 26, 28, 30, 32],
    "rsi_period": [14, 17, 21, 25, 28],
    "rsi_long":   [45, 47, 50, 53, 55],
    "rsi_short":  [45, 47, 50, 53, 55],
    "sl_pct":     [-40, -45, -50, -55, -60, -65, -70, -75, -80],
    "tp_pct":     [5, 7, 10, 13, 15, 20],
    "allocation": [0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
    "leverage":   [1, 2, 3, 4, 5],
}


def load_candles() -> list[dict]:
    with open(CACHE_PATH) as f:
        return json.load(f)


def run_one(candles: list[dict], overrides: dict) -> dict:
    params = {**BASE, **overrides}
    return run_backtest(
        candles,
        leverage=params["leverage"],
        allocation=params["allocation"],
        sl_pct=params["sl_pct"],
        tp_pct=params["tp_pct"],
        ema_fast=params["ema_fast"],
        ema_slow=params["ema_slow"],
        rsi_period=params["rsi_period"],
        rsi_long=params["rsi_long"],
        rsi_short=params["rsi_short"],
    )


def fmt_dollar(v: float) -> str:
    if v >= 1_000_000:
        return f"${v:,.0f}"
    elif v >= 1000:
        return f"${v:,.0f}"
    else:
        return f"${v:,.2f}"


def main():
    print("=" * 100)
    print("  PARAMETER SENSITIVITY ANALYSIS — Strategy B")
    print(f"  Base: 3x 40% SL-60% TP10% EMA12/26 RSI21>50<50")
    print(f"  Initial capital: ${INITIAL_CAPITAL:,.0f} | Funding: ON | Crash excluded")
    print("=" * 100)

    candles = load_candles()
    filtered = filter_crashes(candles)
    print(f"  Data: {len(filtered)} candles (crash-filtered from {len(candles)})\n")

    # Run base config first
    base_result = run_one(filtered, {})
    base_wallet = base_result["final_wallet"]
    print(f"  BASE RESULT: Final=${base_wallet:,.2f}  CAGR={base_result['cagr_pct']:+.2f}%  "
          f"MaxDD={base_result['max_drawdown_pct']:.2f}%  Calmar={base_result['calmar']:.3f}  "
          f"Trades={base_result['trade_count']}  WR={base_result['win_rate']:.1f}%")
    print()

    overfitting_flags = []

    for param_name, values in SWEEPS.items():
        base_val = BASE[param_name]
        base_idx = values.index(base_val)

        print("=" * 100)
        print(f"  PARAM: {param_name}  (base = {base_val})")
        print("-" * 100)

        # Header
        if param_name == "allocation":
            print(f"  {'Value':>8}  {'Final$':>14}  {'CAGR':>8}  {'MaxDD':>8}  {'Calmar':>8}  "
                  f"{'Trades':>7}  {'WR':>6}  {'vs Base':>10}  {'Flag':>6}")
        elif param_name in ("sl_pct", "tp_pct"):
            print(f"  {'Value':>8}  {'Final$':>14}  {'CAGR':>8}  {'MaxDD':>8}  {'Calmar':>8}  "
                  f"{'Trades':>7}  {'WR':>6}  {'vs Base':>10}  {'Flag':>6}")
        else:
            print(f"  {'Value':>8}  {'Final$':>14}  {'CAGR':>8}  {'MaxDD':>8}  {'Calmar':>8}  "
                  f"{'Trades':>7}  {'WR':>6}  {'vs Base':>10}  {'Flag':>6}")

        print(f"  {'--------':>8}  {'----------':>14}  {'------':>8}  {'------':>8}  {'------':>8}  "
              f"{'-----':>7}  {'----':>6}  {'--------':>10}  {'----':>6}")

        results_for_param = []

        for val in values:
            r = run_one(filtered, {param_name: val})
            wallet = r["final_wallet"]
            pct_change = ((wallet / base_wallet) - 1) * 100 if base_wallet > 0 else 0

            # Distance from base in steps
            step_dist = abs(values.index(val) - base_idx)
            is_base = (val == base_val)

            # Flag ±1 step with >50% change
            flag = ""
            if step_dist == 1 and abs(pct_change) > 50:
                flag = "OVERFIT"
                overfitting_flags.append((param_name, val, pct_change))

            marker = " **" if is_base else ""

            if param_name == "allocation":
                val_str = f"{val:.0%}"
            elif param_name in ("sl_pct",):
                val_str = f"{val}%"
            elif param_name in ("tp_pct",):
                val_str = f"{val}%"
            else:
                val_str = str(val)

            print(f"  {val_str:>8}  {fmt_dollar(wallet):>14}  {r['cagr_pct']:>+7.2f}%  "
                  f"{r['max_drawdown_pct']:>7.2f}%  {r['calmar']:>8.3f}  "
                  f"{r['trade_count']:>7}  {r['win_rate']:>5.1f}%  {pct_change:>+9.1f}%  {flag:>6}{marker}")

            results_for_param.append({
                "param": param_name,
                "value": val,
                "final_wallet": wallet,
                "cagr": r["cagr_pct"],
                "max_drawdown": r["max_drawdown_pct"],
                "calmar": r["calmar"],
                "trade_count": r["trade_count"],
                "win_rate": r["win_rate"],
                "pct_vs_base": pct_change,
                "is_base": is_base,
            })

        # Stability metric: std dev of final_wallet across sweep
        wallets = [x["final_wallet"] for x in results_for_param]
        import statistics
        if len(wallets) > 1:
            mean_w = statistics.mean(wallets)
            std_w = statistics.stdev(wallets)
            cv = (std_w / mean_w * 100) if mean_w > 0 else 0
            print(f"\n  Stability: mean=${mean_w:,.0f}  std=${std_w:,.0f}  CV={cv:.1f}%")
        print()

    # Summary
    print("=" * 100)
    print("  OVERFITTING FLAGS (±1 step causing >50% wallet change)")
    print("=" * 100)
    if overfitting_flags:
        for param, val, pct in overfitting_flags:
            direction = "increase" if pct > 0 else "decrease"
            print(f"  WARNING: {param}={val} causes {pct:+.1f}% {direction} vs base")
    else:
        print("  NONE — all parameters stable at ±1 step")

    print()
    print("=" * 100)
    print("  SENSITIVITY RANKING (by coefficient of variation)")
    print("=" * 100)

    # Rank parameters by CV
    param_cvs = []
    for param_name, values in SWEEPS.items():
        results = []
        for val in values:
            r = run_one(filtered, {param_name: val})
            results.append(r["final_wallet"])
        mean_w = statistics.mean(results)
        std_w = statistics.stdev(results)
        cv = (std_w / mean_w * 100) if mean_w > 0 else 0
        param_cvs.append((param_name, cv, min(results), max(results), mean_w))

    param_cvs.sort(key=lambda x: x[1], reverse=True)
    print(f"  {'Parameter':>12}  {'CV':>8}  {'Min$':>12}  {'Max$':>12}  {'Mean$':>12}  {'Sensitivity':>12}")
    print(f"  {'----------':>12}  {'------':>8}  {'------':>12}  {'------':>12}  {'------':>12}  {'----------':>12}")
    for param, cv, mn, mx, mean in param_cvs:
        sensitivity = "HIGH" if cv > 100 else ("MEDIUM" if cv > 50 else "LOW")
        print(f"  {param:>12}  {cv:>7.1f}%  {fmt_dollar(mn):>12}  {fmt_dollar(mx):>12}  {fmt_dollar(mean):>12}  {sensitivity:>12}")

    print()


if __name__ == "__main__":
    main()
