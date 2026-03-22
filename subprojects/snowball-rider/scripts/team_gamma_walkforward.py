#!/usr/bin/env python3
"""Team Gamma: Walk-Forward Consensus Optimization for BTC EMA/RSI strategy.

Anchored walk-forward with 5 windows. Finds consensus parameters that are
independently selected as optimal across multiple training windows and
produce positive OOS returns across multiple test windows.
"""

from __future__ import annotations
import sys
import os
import json
import time
from itertools import product
from collections import defaultdict, Counter
from datetime import datetime

# Import run_backtest from grid_search.py
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from grid_search import run_backtest, filter_crashes, INITIAL_CAPITAL


# ── Window definitions (anchored: all start from 2019-09) ──────────────────
WINDOWS = [
    {"name": "W1", "train_start": "2019-09-01", "train_end": "2021-06-30",
     "test_start": "2021-07-01", "test_end": "2022-06-30",
     "desc": "2yr train, 1yr test"},
    {"name": "W2", "train_start": "2019-09-01", "train_end": "2022-06-30",
     "test_start": "2022-07-01", "test_end": "2023-06-30",
     "desc": "2.75yr train, 1yr test"},
    {"name": "W3", "train_start": "2019-09-01", "train_end": "2023-06-30",
     "test_start": "2023-07-01", "test_end": "2024-06-30",
     "desc": "3.75yr train, 1yr test"},
    {"name": "W4", "train_start": "2019-09-01", "train_end": "2024-06-30",
     "test_start": "2024-07-01", "test_end": "2025-06-30",
     "desc": "4.75yr train, 1yr test"},
    {"name": "W5", "train_start": "2019-09-01", "train_end": "2025-06-30",
     "test_start": "2025-07-01", "test_end": "2026-03-22",
     "desc": "5.75yr train, 9mo test"},
]

# ── Parameter grid ─────────────────────────────────────────────────────────
EMA_FAST_VALUES = [8, 10, 12, 14, 16]
EMA_SLOW_VALUES = [20, 24, 26, 28, 30, 32]
RSI_PERIOD_VALUES = [14, 17, 21, 25]
RSI_THRESHOLDS = [(45, 55), (50, 50), (55, 45)]  # (rsi_long, rsi_short)
SL_VALUES = [-50, -60, -70, -80]
TP_VALUES = [5, 10, 15, 20]
LEVERAGE_VALUES = [2, 3]
ALLOCATION_VALUES = [0.3, 0.4, 0.5, 0.6]

# Warmup candles needed before any period start
WARMUP_CANDLES = 200


def param_key(ef, es, rp, rl, rs, sl, tp, lev, alloc):
    """Hashable key for a parameter set."""
    return (ef, es, rp, rl, rs, sl, tp, lev, alloc)


def param_dict(ef, es, rp, rl, rs, sl, tp, lev, alloc):
    """Human-readable dict for a parameter set."""
    return {
        "ema_fast": ef, "ema_slow": es, "rsi_period": rp,
        "rsi_long": rl, "rsi_short": rs,
        "sl_pct": sl, "tp_pct": tp, "leverage": lev, "allocation": alloc,
    }


def filter_candles_by_date(candles, start_date, end_date):
    """Filter candles to [start_date, end_date] inclusive."""
    return [c for c in candles if start_date <= c["date"] <= end_date]


def get_candles_with_warmup(all_candles, target_start, target_end):
    """Get candles including warmup before target_start, up to target_end."""
    # Find target_start index
    target_idx = None
    for i, c in enumerate(all_candles):
        if c["date"] >= target_start:
            target_idx = i
            break
    if target_idx is None:
        return []

    # Include WARMUP_CANDLES before target_start
    warmup_start = max(0, target_idx - WARMUP_CANDLES)
    # Find target_end index
    end_idx = len(all_candles) - 1
    for i, c in enumerate(all_candles):
        if c["date"] > target_end:
            end_idx = i - 1
            break

    return all_candles[warmup_start:end_idx + 1]


def run_grid_on_candles(candles, label=""):
    """Run full parameter grid on given candles, return list of (key, result)."""
    total = (len(EMA_FAST_VALUES) * len(EMA_SLOW_VALUES) * len(RSI_PERIOD_VALUES)
             * len(RSI_THRESHOLDS) * len(SL_VALUES) * len(TP_VALUES)
             * len(LEVERAGE_VALUES) * len(ALLOCATION_VALUES))

    results = []
    count = 0

    for ef, es, rp, (rl, rs), sl, tp, lev, alloc in product(
        EMA_FAST_VALUES, EMA_SLOW_VALUES, RSI_PERIOD_VALUES, RSI_THRESHOLDS,
        SL_VALUES, TP_VALUES, LEVERAGE_VALUES, ALLOCATION_VALUES
    ):
        if ef >= es:  # EMA fast must be < slow
            continue
        count += 1
        if count % 2000 == 0:
            print(f"    {label} Progress: {count}/{total}", flush=True)

        r = run_backtest(
            candles, leverage=lev, allocation=alloc,
            sl_pct=sl, tp_pct=tp,
            ema_fast=ef, ema_slow=es,
            rsi_period=rp, rsi_long=rl, rsi_short=rs
        )
        key = param_key(ef, es, rp, rl, rs, sl, tp, lev, alloc)
        results.append((key, r))

    print(f"    {label} Done: {count} backtests", flush=True)
    return results


def main():
    t0 = time.time()
    print("=" * 100)
    print("  TEAM GAMMA: Walk-Forward Consensus Optimization")
    print(f"  Initial Capital: ${INITIAL_CAPITAL}")
    print("=" * 100)

    # Load and filter data
    data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'btcusdt_1d_klines.json')
    with open(data_path) as f:
        all_candles = json.load(f)
    all_candles = filter_crashes(all_candles)
    print(f"  Data: {len(all_candles)} candles ({all_candles[0]['date']} to {all_candles[-1]['date']})")
    print()

    # ── Per-window: train grid search → top 10 → OOS test ─────────────────
    # Store: for each window, the top-10 param keys and their train/test results
    window_results = []

    # For vote matrix: all param keys that were ever top-10 in any window
    all_top10_keys = set()

    # For each window, store test results for ALL param sets (for vote matrix later)
    window_test_results = {}  # window_name -> {param_key: test_result}

    for w in WINDOWS:
        print(f"{'─' * 100}")
        print(f"  {w['name']}: {w['desc']}")
        print(f"  Train: {w['train_start']} → {w['train_end']}")
        print(f"  Test:  {w['test_start']} → {w['test_end']}")
        print(f"{'─' * 100}")

        # ── TRAIN phase ──
        train_candles = get_candles_with_warmup(all_candles, w['train_start'], w['train_end'])
        print(f"  [TRAIN] {len(train_candles)} candles (incl. warmup)")
        train_results = run_grid_on_candles(train_candles, label=f"{w['name']}-TRAIN")

        # Filter: not liquidated, beats B&H, positive calmar
        viable_train = [(k, r) for k, r in train_results
                        if not r['liquidated'] and r['beats_bnh'] and r['calmar'] > 0]
        print(f"  [TRAIN] Viable (not liquidated, beats B&H): {len(viable_train)}")

        if len(viable_train) == 0:
            print(f"  [TRAIN] WARNING: No viable sets found, using top 10 by calmar overall")
            viable_train = [(k, r) for k, r in train_results
                            if not r['liquidated'] and r['calmar'] > 0]

        # Top 10 by Calmar
        viable_train.sort(key=lambda x: x[1]['calmar'], reverse=True)
        top10_train = viable_train[:10]

        print(f"\n  [TRAIN] Top 10 by Calmar:")
        print(f"  {'#':>3} {'EMA':>7} {'RSI':>12} {'SL':>5} {'TP':>4} {'Lev':>3} {'Alloc':>5} {'Calmar':>7} {'CAGR':>7} {'MaxDD':>7} {'Return':>8}")
        for idx, (key, r) in enumerate(top10_train, 1):
            ef, es, rp, rl, rs, sl, tp, lev, alloc = key
            print(f"  {idx:3d} {ef:>2}/{es:<3} {rp:>2}>{rl:<2}<{rs:<2} {sl:>5}% {tp:>4}% {lev:>3}x {alloc:>5.0%} {r['calmar']:>7.2f} {r['cagr_pct']:>+6.1f}% {r['max_drawdown_pct']:>6.1f}% {r['total_return_pct']:>+7.1f}%")

        top10_keys = [k for k, _ in top10_train]
        all_top10_keys.update(top10_keys)

        # ── TEST phase (OOS) ──
        test_candles = get_candles_with_warmup(all_candles, w['test_start'], w['test_end'])
        print(f"\n  [TEST] {len(test_candles)} candles (incl. warmup)")

        # Run ALL params on test (needed for vote matrix)
        test_results = run_grid_on_candles(test_candles, label=f"{w['name']}-TEST")
        test_map = {k: r for k, r in test_results}
        window_test_results[w['name']] = test_map

        # Show OOS results for top-10
        oos_profitable = []
        print(f"\n  [TEST/OOS] Top 10 parameter sets — OOS performance:")
        print(f"  {'#':>3} {'EMA':>7} {'RSI':>12} {'SL':>5} {'TP':>4} {'Lev':>3} {'Alloc':>5} {'Return':>8} {'Calmar':>7} {'MaxDD':>7} {'Trades':>6} {'OOS?':>5}")
        for idx, key in enumerate(top10_keys, 1):
            r = test_map.get(key)
            if r is None:
                print(f"  {idx:3d} [no test result]")
                continue
            ef, es, rp, rl, rs, sl, tp, lev, alloc = key
            is_oos = r['total_return_pct'] > 0 and not r['liquidated']
            marker = " YES" if is_oos else "  NO"
            print(f"  {idx:3d} {ef:>2}/{es:<3} {rp:>2}>{rl:<2}<{rs:<2} {sl:>5}% {tp:>4}% {lev:>3}x {alloc:>5.0%} {r['total_return_pct']:>+7.1f}% {r['calmar']:>7.2f} {r['max_drawdown_pct']:>6.1f}% {r['trade_count']:>6} {marker}")
            if is_oos:
                oos_profitable.append(key)

        window_results.append({
            "window": w,
            "top10_keys": top10_keys,
            "oos_profitable_keys": oos_profitable,
            "oos_count": len(oos_profitable),
        })
        print(f"\n  [RESULT] {w['name']}: {len(oos_profitable)}/10 OOS-profitable")
        print()

    # ── CONSENSUS ANALYSIS ─────────────────────────────────────────────────
    print()
    print("=" * 100)
    print("  CONSENSUS ANALYSIS")
    print("=" * 100)

    # Collect all OOS-profitable param values per parameter
    param_names = ["ema_fast", "ema_slow", "rsi_period", "rsi_long", "rsi_short",
                   "sl_pct", "tp_pct", "leverage", "allocation"]

    # For each parameter, count value occurrences across windows in OOS-profitable sets
    # Key: (param_name, value) -> list of window names where it appeared
    param_value_windows = defaultdict(set)  # (param_name, value) -> {window_names}
    param_value_counts = defaultdict(int)   # (param_name, value) -> total count across all windows

    for wr in window_results:
        wname = wr["window"]["name"]
        for key in wr["oos_profitable_keys"]:
            ef, es, rp, rl, rs, sl, tp, lev, alloc = key
            vals = dict(zip(param_names, [ef, es, rp, rl, rs, sl, tp, lev, alloc]))
            for pname, pval in vals.items():
                param_value_windows[(pname, pval)].add(wname)
                param_value_counts[(pname, pval)] += 1

    print("\n  Parameter Value Frequency in OOS-Profitable Sets:")
    print(f"  {'Parameter':<14} {'Value':>8} {'Windows':>8} {'Count':>6} {'Window List':<30} {'Consensus?':<10}")
    print(f"  {'─'*14} {'─'*8} {'─'*8} {'─'*6} {'─'*30} {'─'*10}")

    consensus_params = {}
    for pname in param_names:
        # Collect all (value, window_count, total_count) for this param
        entries = []
        # Find all values seen for this param
        all_values = set()
        for (pn, pv), wins in param_value_windows.items():
            if pn == pname:
                all_values.add(pv)
                entries.append((pv, len(wins), param_value_counts[(pn, pv)], wins))

        entries.sort(key=lambda x: (-x[1], -x[2]))

        for val, nwins, count, wins in entries:
            win_list = ",".join(sorted(wins))
            is_consensus = "*** YES" if nwins >= 4 else ("  maybe" if nwins >= 3 else "")
            print(f"  {pname:<14} {val:>8} {nwins:>8} {count:>6} {win_list:<30} {is_consensus}")

        # Best value for consensus: most windows, then most count
        if entries:
            best = entries[0]
            consensus_params[pname] = best[0]

        print()

    print("\n  CONSENSUS PARAMETER SET (most frequent across OOS-profitable sets):")
    print(f"  {'─' * 60}")
    for pname in param_names:
        val = consensus_params.get(pname, "N/A")
        nwins = len(param_value_windows.get((pname, val), set()))
        print(f"  {pname:<14} = {val:>8}  (appeared in {nwins}/5 windows)")
    print(f"  {'─' * 60}")

    # ── VOTE MATRIX ────────────────────────────────────────────────────────
    print()
    print("=" * 100)
    print("  VOTE MATRIX: Top-10 Parameter Sets x Test Windows")
    print("=" * 100)

    # Build sorted list of all unique top-10 keys
    all_top10_list = sorted(all_top10_keys)
    window_names = [w["name"] for w in WINDOWS]

    # Count how many test windows each param set is profitable in
    robustness = {}
    for key in all_top10_list:
        profitable_windows = 0
        for wname in window_names:
            test_map = window_test_results.get(wname, {})
            r = test_map.get(key)
            if r and r['total_return_pct'] > 0 and not r['liquidated']:
                profitable_windows += 1
        robustness[key] = profitable_windows

    # Sort by robustness (most profitable windows first)
    all_top10_sorted = sorted(all_top10_list, key=lambda k: (-robustness[k], k))

    # Print matrix header
    print(f"\n  {'#':>3} {'EMA':>7} {'RSI':>12} {'SL':>5} {'TP':>4} {'Lev':>3} {'Alloc':>5}", end="")
    for wn in window_names:
        print(f" {wn+'-OOS':>10}", end="")
    print(f" {'Robust':>8}")
    print(f"  {'─'*3} {'─'*7} {'─'*12} {'─'*5} {'─'*4} {'─'*3} {'─'*5}", end="")
    for _ in window_names:
        print(f" {'─'*10}", end="")
    print(f" {'─'*8}")

    robust_sets = []
    for idx, key in enumerate(all_top10_sorted, 1):
        ef, es, rp, rl, rs, sl, tp, lev, alloc = key
        print(f"  {idx:3d} {ef:>2}/{es:<3} {rp:>2}>{rl:<2}<{rs:<2} {sl:>5}% {tp:>4}% {lev:>3}x {alloc:>5.0%}", end="")
        for wn in window_names:
            test_map = window_test_results.get(wn, {})
            r = test_map.get(key)
            if r is None:
                print(f" {'N/A':>10}", end="")
            elif r['liquidated']:
                print(f" {'LIQD':>10}", end="")
            else:
                ret = r['total_return_pct']
                marker = "+" if ret > 0 else ""
                print(f" {marker}{ret:>8.1f}%", end="")
        rob = robustness[key]
        marker = " ***" if rob >= 4 else (" **" if rob >= 3 else "")
        print(f" {rob:>4}/5{marker}")

        if rob >= 4:
            robust_sets.append((key, rob))

    # ── ROBUST PARAMETER SETS ──────────────────────────────────────────────
    print()
    print("=" * 100)
    print("  ROBUST PARAMETER SETS (profitable in 4+ test windows)")
    print("=" * 100)

    if robust_sets:
        for key, rob in robust_sets:
            ef, es, rp, rl, rs, sl, tp, lev, alloc = key
            pd = param_dict(ef, es, rp, rl, rs, sl, tp, lev, alloc)
            # Count how many train windows it appeared as top-10
            train_appearances = sum(
                1 for wr in window_results if key in wr["top10_keys"]
            )
            print(f"\n  Parameter set: EMA {ef}/{es}, RSI {rp}>{rl}<{rs}, SL={sl}%, TP={tp}%, Lev={lev}x, Alloc={alloc:.0%}")
            print(f"  >> Independently selected as optimal in {train_appearances}/5 training windows")
            print(f"  >> Produced positive OOS returns in {rob}/5 test windows")

            # Show per-window detail
            for wn in window_names:
                test_map = window_test_results.get(wn, {})
                r = test_map.get(key)
                if r:
                    print(f"     {wn}: return={r['total_return_pct']:+.1f}%, calmar={r['calmar']:.2f}, maxDD={r['max_drawdown_pct']:.1f}%, trades={r['trade_count']}, wr={r['win_rate']:.0f}%")
    else:
        print("  No parameter sets were profitable in 4+ test windows.")
        print("  Showing sets profitable in 3+ windows:")
        semi_robust = [(k, r) for k, r in robustness.items() if r >= 3 and k in all_top10_keys]
        semi_robust.sort(key=lambda x: -x[1])
        for key, rob in semi_robust[:10]:
            ef, es, rp, rl, rs, sl, tp, lev, alloc = key
            train_appearances = sum(
                1 for wr in window_results if key in wr["top10_keys"]
            )
            print(f"\n  Parameter set: EMA {ef}/{es}, RSI {rp}>{rl}<{rs}, SL={sl}%, TP={tp}%, Lev={lev}x, Alloc={alloc:.0%}")
            print(f"  >> Independently selected as optimal in {train_appearances}/5 training windows")
            print(f"  >> Produced positive OOS returns in {rob}/5 test windows")
            for wn in window_names:
                test_map = window_test_results.get(wn, {})
                r = test_map.get(key)
                if r:
                    print(f"     {wn}: return={r['total_return_pct']:+.1f}%, calmar={r['calmar']:.2f}, maxDD={r['max_drawdown_pct']:.1f}%, trades={r['trade_count']}, wr={r['win_rate']:.0f}%")

    # ── RUN CONSENSUS SET ON FULL DATA ─────────────────────────────────────
    print()
    print("=" * 100)
    print("  CONSENSUS SET — Full-Period Backtest")
    print("=" * 100)

    if consensus_params:
        cp = consensus_params
        print(f"\n  Running consensus parameters on full data:")
        print(f"  EMA: {cp['ema_fast']}/{cp['ema_slow']}, RSI: {cp['rsi_period']}>{cp['rsi_long']}<{cp['rsi_short']}")
        print(f"  SL: {cp['sl_pct']}%, TP: {cp['tp_pct']}%, Leverage: {cp['leverage']}x, Allocation: {cp['allocation']:.0%}")

        r = run_backtest(
            all_candles, leverage=cp['leverage'], allocation=cp['allocation'],
            sl_pct=cp['sl_pct'], tp_pct=cp['tp_pct'],
            ema_fast=cp['ema_fast'], ema_slow=cp['ema_slow'],
            rsi_period=cp['rsi_period'], rsi_long=cp['rsi_long'], rsi_short=cp['rsi_short']
        )
        print(f"\n  Final Wallet:    ${r['final_wallet']:,.2f}")
        print(f"  Total Return:    {r['total_return_pct']:+.1f}%")
        print(f"  CAGR:            {r['cagr_pct']:+.1f}%")
        print(f"  Max Drawdown:    {r['max_drawdown_pct']:.1f}%")
        print(f"  Calmar Ratio:    {r['calmar']:.2f}")
        print(f"  Trades:          {r['trade_count']}")
        print(f"  Win Rate:        {r['win_rate']:.0f}%")
        print(f"  Beats B&H:       {r['beats_bnh']}")
        print(f"  Liquidated:      {r['liquidated']}")
        print(f"  B&H Return:      {r['bnh_return_pct']:+.1f}%")

    # ── MATHEMATICAL STATEMENT ─────────────────────────────────────────────
    print()
    print("=" * 100)
    print("  MATHEMATICAL CONCLUSION")
    print("=" * 100)

    if robust_sets:
        for key, rob in robust_sets:
            ef, es, rp, rl, rs, sl, tp, lev, alloc = key
            train_appearances = sum(
                1 for wr in window_results if key in wr["top10_keys"]
            )
            print(f"\n  Parameter set P = {{EMA {ef}/{es}, RSI {rp}>{rl}<{rs}, SL={sl}%, TP={tp}%, Lev={lev}x, Alloc={alloc:.0%}}}")
            print(f"  was independently selected as optimal in {train_appearances}/5 training windows")
            print(f"  and produced positive OOS returns in {rob}/5 test windows.")
    else:
        print("\n  No single parameter set achieved 4+/5 OOS robustness.")
        print("  Consensus parameters (by most frequent OOS-profitable values):")
        if consensus_params:
            cp = consensus_params
            consensus_key = param_key(
                cp['ema_fast'], cp['ema_slow'], cp['rsi_period'],
                cp['rsi_long'], cp['rsi_short'],
                cp['sl_pct'], cp['tp_pct'], cp['leverage'], cp['allocation']
            )
            # Check how many windows the assembled consensus is profitable in
            consensus_rob = 0
            for wn in window_names:
                test_map = window_test_results.get(wn, {})
                r = test_map.get(consensus_key)
                if r and r['total_return_pct'] > 0 and not r['liquidated']:
                    consensus_rob += 1
            print(f"\n  Assembled consensus P = {consensus_params}")
            print(f"  OOS-profitable in {consensus_rob}/5 test windows when assembled.")

        if semi_robust:
            best_key, best_rob = semi_robust[0]
            ef, es, rp, rl, rs, sl, tp, lev, alloc = best_key
            train_appearances = sum(
                1 for wr in window_results if best_key in wr["top10_keys"]
            )
            print(f"\n  Best available: P = {{EMA {ef}/{es}, RSI {rp}>{rl}<{rs}, SL={sl}%, TP={tp}%, Lev={lev}x, Alloc={alloc:.0%}}}")
            print(f"  was independently selected as optimal in {train_appearances}/5 training windows")
            print(f"  and produced positive OOS returns in {best_rob}/5 test windows.")

    elapsed = time.time() - t0
    print(f"\n  Total runtime: {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print("=" * 100)


if __name__ == "__main__":
    main()
