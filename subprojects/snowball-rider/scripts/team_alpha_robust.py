#!/usr/bin/env python3
"""Team Alpha: Robust (Minimax) Optimization for BTC EMA/RSI Strategy.

For each candidate parameter set P, compute the MINIMUM final_wallet across
ALL neighboring parameter sets (±1 step each parameter). The parameter set
whose worst neighbor performs best is the most robust.

Ranking: PRIMARY=robustness_score (must beat B&H $6907),
         SECONDARY=stability_ratio, TERTIARY=calmar ratio.
"""

from __future__ import annotations
import sys
import os
import json
import time
from itertools import product

# Import run_backtest from grid_search.py
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from grid_search import run_backtest, filter_crashes

INITIAL_CAPITAL = 818.0
BNH_BENCHMARK = 6907.0  # Buy & Hold reference

# ── Parameter grids (ordered lists for neighbor lookup) ──
EMA_FAST_GRID   = [8, 10, 12, 14, 16]
EMA_SLOW_GRID   = [20, 24, 26, 28, 30, 32]
RSI_PERIOD_GRID = [14, 17, 21, 25]
RSI_PAIR_GRID   = [(45, 55), (47, 53), (50, 50), (53, 47), (55, 45)]
SL_PCT_GRID     = [-40, -50, -60, -70, -80]
TP_PCT_GRID     = [5, 10, 15, 20]
LEVERAGE_GRID   = [2, 3, 4]
ALLOCATION_GRID = [0.3, 0.4, 0.5, 0.6]

PARAM_GRIDS = {
    'ema_fast':   EMA_FAST_GRID,
    'ema_slow':   EMA_SLOW_GRID,
    'rsi_period': RSI_PERIOD_GRID,
    'rsi_pair':   RSI_PAIR_GRID,
    'sl_pct':     SL_PCT_GRID,
    'tp_pct':     TP_PCT_GRID,
    'leverage':   LEVERAGE_GRID,
    'allocation': ALLOCATION_GRID,
}


def get_neighbors(grid: list, idx: int) -> list[int]:
    """Return indices of ±1 step neighbors (excluding self)."""
    neighbors = []
    if idx > 0:
        neighbors.append(idx - 1)
    if idx < len(grid) - 1:
        neighbors.append(idx + 1)
    return neighbors


def run_single(candles, params: dict) -> dict:
    """Run backtest with a parameter dict."""
    return run_backtest(
        candles,
        leverage=params['leverage'],
        allocation=params['allocation'],
        sl_pct=params['sl_pct'],
        tp_pct=params['tp_pct'],
        ema_fast=params['ema_fast'],
        ema_slow=params['ema_slow'],
        rsi_period=params['rsi_period'],
        rsi_long=params['rsi_long'],
        rsi_short=params['rsi_short'],
    )


def params_from_indices(indices: dict) -> dict:
    """Convert grid indices to actual parameter values."""
    rsi_pair = RSI_PAIR_GRID[indices['rsi_pair']]
    return {
        'ema_fast':   EMA_FAST_GRID[indices['ema_fast']],
        'ema_slow':   EMA_SLOW_GRID[indices['ema_slow']],
        'rsi_period': RSI_PERIOD_GRID[indices['rsi_period']],
        'rsi_long':   rsi_pair[0],
        'rsi_short':  rsi_pair[1],
        'sl_pct':     SL_PCT_GRID[indices['sl_pct']],
        'tp_pct':     TP_PCT_GRID[indices['tp_pct']],
        'leverage':   LEVERAGE_GRID[indices['leverage']],
        'allocation': ALLOCATION_GRID[indices['allocation']],
    }


def main():
    t0 = time.time()

    print("=" * 100)
    print("  TEAM ALPHA — ROBUST (MINIMAX) OPTIMIZATION")
    print("  Method: For each P, robustness_score = min(wallet) across ALL ±1 neighbors")
    print(f"  Initial capital: ${INITIAL_CAPITAL:.0f} | B&H benchmark: ${BNH_BENCHMARK:.0f}")
    print("=" * 100)

    # ── Load data ──
    data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'btcusdt_1d_klines.json')
    with open(data_path) as f:
        candles = json.load(f)
    filtered = filter_crashes(candles)
    print(f"  Data: {len(candles)} raw -> {len(filtered)} filtered candles")
    print(f"  Date range: {filtered[0]['date']} to {filtered[-1]['date']}")

    # ── Compute total grid size ──
    total_center = (len(EMA_FAST_GRID) * len(EMA_SLOW_GRID) * len(RSI_PERIOD_GRID) *
                    len(RSI_PAIR_GRID) * len(SL_PCT_GRID) * len(TP_PCT_GRID) *
                    len(LEVERAGE_GRID) * len(ALLOCATION_GRID))
    print(f"  Center points: {total_center:,}")

    # ── Phase 1: Cache ALL backtests (each unique param combo) ──
    # Use a tuple key for memoization
    print(f"\n  Phase 1: Running all backtests with memoization...")

    cache = {}

    def cached_backtest(params: dict) -> dict:
        key = (params['ema_fast'], params['ema_slow'], params['rsi_period'],
               params['rsi_long'], params['rsi_short'],
               params['sl_pct'], params['tp_pct'],
               params['leverage'], params['allocation'])
        if key not in cache:
            cache[key] = run_single(filtered, params)
        return cache[key]

    # ── Phase 2: Iterate all center points, compute robustness ──
    print(f"  Phase 2: Computing robustness scores...")

    param_names = ['ema_fast', 'ema_slow', 'rsi_period', 'rsi_pair',
                   'sl_pct', 'tp_pct', 'leverage', 'allocation']
    grid_sizes = {
        'ema_fast':   len(EMA_FAST_GRID),
        'ema_slow':   len(EMA_SLOW_GRID),
        'rsi_period': len(RSI_PERIOD_GRID),
        'rsi_pair':   len(RSI_PAIR_GRID),
        'sl_pct':     len(SL_PCT_GRID),
        'tp_pct':     len(TP_PCT_GRID),
        'leverage':   len(LEVERAGE_GRID),
        'allocation': len(ALLOCATION_GRID),
    }

    results = []
    count = 0
    skipped = 0

    for ef_i, es_i, rp_i, rsi_i, sl_i, tp_i, lev_i, alloc_i in product(
        range(grid_sizes['ema_fast']),
        range(grid_sizes['ema_slow']),
        range(grid_sizes['rsi_period']),
        range(grid_sizes['rsi_pair']),
        range(grid_sizes['sl_pct']),
        range(grid_sizes['tp_pct']),
        range(grid_sizes['leverage']),
        range(grid_sizes['allocation']),
    ):
        count += 1
        if count % 2000 == 0:
            elapsed = time.time() - t0
            print(f"    Progress: {count:,}/{total_center:,} ({count/total_center*100:.1f}%) "
                  f"| cache hits: {len(cache):,} | elapsed: {elapsed:.0f}s")

        center_indices = {
            'ema_fast': ef_i, 'ema_slow': es_i, 'rsi_period': rp_i,
            'rsi_pair': rsi_i, 'sl_pct': sl_i, 'tp_pct': tp_i,
            'leverage': lev_i, 'allocation': alloc_i,
        }

        center_params = params_from_indices(center_indices)

        # Skip if ema_fast >= ema_slow (invalid)
        if center_params['ema_fast'] >= center_params['ema_slow']:
            skipped += 1
            continue

        # Run center backtest
        center_result = cached_backtest(center_params)

        # Skip if center is liquidated or doesn't beat B&H
        if center_result['liquidated'] or center_result['final_wallet'] < BNH_BENCHMARK:
            continue

        center_wallet = center_result['final_wallet']

        # ── Compute ALL neighbors (±1 step, one param at a time) ──
        neighbor_wallets = []
        all_neighbors_beat_bnh = True

        for pname in param_names:
            current_idx = center_indices[pname]
            neighbor_indices = get_neighbors(PARAM_GRIDS[pname], current_idx)

            for n_idx in neighbor_indices:
                # Build neighbor param set
                n_indices = center_indices.copy()
                n_indices[pname] = n_idx
                n_params = params_from_indices(n_indices)

                # Skip invalid ema combos
                if n_params['ema_fast'] >= n_params['ema_slow']:
                    # Invalid neighbor — treat as non-viable (skip this center)
                    all_neighbors_beat_bnh = False
                    break

                n_result = cached_backtest(n_params)

                if n_result['liquidated'] or n_result['final_wallet'] < BNH_BENCHMARK:
                    all_neighbors_beat_bnh = False
                    break

                neighbor_wallets.append(n_result['final_wallet'])

            if not all_neighbors_beat_bnh:
                break

        if not all_neighbors_beat_bnh:
            continue

        if not neighbor_wallets:
            continue

        # Robustness score = min wallet across ALL neighbors
        robustness_score = min(neighbor_wallets)
        stability_ratio = robustness_score / center_wallet if center_wallet > 0 else 0
        num_neighbors = len(neighbor_wallets)

        results.append({
            'params': center_params,
            'center_wallet': center_wallet,
            'center_cagr': center_result['cagr_pct'],
            'center_mdd': center_result['max_drawdown_pct'],
            'center_calmar': center_result['calmar'],
            'center_trades': center_result['trade_count'],
            'center_winrate': center_result['win_rate'],
            'robustness_score': robustness_score,
            'stability_ratio': stability_ratio,
            'num_neighbors': num_neighbors,
            'min_neighbor_wallet': robustness_score,
            'mean_neighbor_wallet': sum(neighbor_wallets) / len(neighbor_wallets),
        })

    elapsed = time.time() - t0
    print(f"\n  Completed: {count:,} centers evaluated, {skipped:,} skipped (invalid EMA)")
    print(f"  Unique backtests run: {len(cache):,}")
    print(f"  Robust candidates (center + ALL neighbors beat B&H): {len(results)}")
    print(f"  Time: {elapsed:.1f}s")

    if not results:
        print("\n  NO ROBUST PARAMETER SETS FOUND where center AND all neighbors beat B&H!")
        print("  Consider relaxing the B&H threshold or expanding the grid.")
        return

    # ── Rank: PRIMARY=robustness_score, SECONDARY=stability_ratio, TERTIARY=calmar ──
    results.sort(key=lambda x: (x['robustness_score'], x['stability_ratio'], x['center_calmar']),
                 reverse=True)

    # ── Print TOP 20 ──
    top_n = min(20, len(results))
    print(f"\n{'='*130}")
    print(f"  TOP {top_n} ROBUST PARAMETER SETS")
    print(f"  Ranked by: robustness_score (min neighbor wallet) > stability_ratio > calmar")
    print(f"  Constraint: center AND ALL ±1 neighbors must beat B&H ${BNH_BENCHMARK:.0f}")
    print(f"{'='*130}")

    header = (f"  {'#':>3} {'Lev':>3} {'Alloc':>5} {'SL':>5} {'TP':>4} "
              f"{'EF':>3} {'ES':>3} {'RSI_P':>5} {'RL':>3} {'RS':>3} "
              f"{'Center$':>10} {'CAGR':>7} {'MDD':>6} {'Calmar':>7} "
              f"{'Robust$':>10} {'Stab':>6} {'#Nbr':>5} {'Trades':>6} {'WR':>5}")
    print(header)
    print("  " + "-" * (len(header) - 2))

    for idx, r in enumerate(results[:top_n], 1):
        p = r['params']
        print(f"  {idx:3d} {p['leverage']:>3}x {p['allocation']:>5.0%} {p['sl_pct']:>5.0f}% {p['tp_pct']:>4.0f}% "
              f"{p['ema_fast']:>3} {p['ema_slow']:>3} {p['rsi_period']:>5} {p['rsi_long']:>3.0f} {p['rsi_short']:>3.0f} "
              f"${r['center_wallet']:>9,.0f} {r['center_cagr']:>+6.1f}% {r['center_mdd']:>5.1f}% {r['center_calmar']:>7.2f} "
              f"${r['robustness_score']:>9,.0f} {r['stability_ratio']:>5.2f} {r['num_neighbors']:>5} {r['center_trades']:>6} {r['center_winrate']:>4.0f}%")

    # ── Mathematical proof for top results ──
    print(f"\n{'='*130}")
    print(f"  MATHEMATICAL PROOF OF ROBUSTNESS")
    print(f"{'='*130}")

    for idx, r in enumerate(results[:top_n], 1):
        p = r['params']
        param_str = (f"EMA({p['ema_fast']},{p['ema_slow']}), RSI({p['rsi_period']},{p['rsi_long']:.0f},{p['rsi_short']:.0f}), "
                     f"SL={p['sl_pct']:.0f}%, TP={p['tp_pct']:.0f}%, Lev={p['leverage']}x, Alloc={p['allocation']:.0%}")
        print(f"\n  #{idx}: P = {{{param_str}}}")
        print(f"       For ALL p' in N(P, ±1 step), wallet(p') >= ${r['robustness_score']:,.0f} > ${BNH_BENCHMARK:,.0f} (B&H)")
        print(f"       Center wallet: ${r['center_wallet']:,.0f} | Stability ratio: {r['stability_ratio']:.3f} "
              f"| Neighbors evaluated: {r['num_neighbors']}")
        print(f"       Mean neighbor wallet: ${r['mean_neighbor_wallet']:,.0f} | "
              f"CAGR: {r['center_cagr']:+.1f}% | MaxDD: {r['center_mdd']:.1f}% | Calmar: {r['center_calmar']:.2f}")

    # ── Summary statistics ──
    print(f"\n{'='*130}")
    print(f"  SUMMARY")
    print(f"{'='*130}")
    print(f"  Total center points evaluated: {count:,}")
    print(f"  Unique backtests computed: {len(cache):,}")
    print(f"  Robust candidates found: {len(results)}")
    if results:
        best = results[0]
        print(f"  Best robustness score: ${best['robustness_score']:,.0f}")
        print(f"  Best center wallet:    ${best['center_wallet']:,.0f}")
        print(f"  Best stability ratio:  {best['stability_ratio']:.3f}")

        # Leverage distribution
        lev_dist = {}
        for r in results:
            lev = r['params']['leverage']
            lev_dist[lev] = lev_dist.get(lev, 0) + 1
        print(f"  Leverage distribution: {dict(sorted(lev_dist.items()))}")

        # Allocation distribution
        alloc_dist = {}
        for r in results:
            alloc = r['params']['allocation']
            alloc_dist[alloc] = alloc_dist.get(alloc, 0) + 1
        print(f"  Allocation distribution: {dict(sorted(alloc_dist.items()))}")

    print(f"\n  Elapsed time: {time.time() - t0:.1f}s")
    print(f"  {'='*100}")


if __name__ == "__main__":
    main()
