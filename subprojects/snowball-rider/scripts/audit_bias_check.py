#!/usr/bin/env python3
"""Audit Team 3: Bias & Statistical Validity Check.

Tests:
  1. Random strategy benchmark (selection bias)
  2. Reversed data test (structural artifact)
  3. Shuffled candles test (timing edge)
  4. Half-period tests (period dependence)
  5. Indicator verification (EMA/RSI correctness)
  6. Trade count reasonableness
"""

from __future__ import annotations

import sys
import os
import json
import random
import copy
import math

# Setup paths
PROJ_ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(PROJ_ROOT, 'scripts'))
sys.path.insert(0, os.path.join(PROJ_ROOT, 'src'))

from grid_search import run_backtest
import grid_search
from snowball_rider.indicators import compute_ema, compute_rsi

# Set initial capital
grid_search.INITIAL_CAPITAL = 818.0
INITIAL_CAPITAL = 818.0

# Load candles
DATA_PATH = os.path.join(PROJ_ROOT, 'data', 'btcusdt_1d_klines.json')
with open(DATA_PATH) as f:
    CANDLES = json.load(f)

# "Consensus" strategy parameters (typical grid search winner defaults)
CONSENSUS = dict(
    leverage=2,
    allocation=0.5,
    sl_pct=-50,
    tp_pct=15,
    ema_fast=12,
    ema_slow=26,
    rsi_period=21,
    rsi_long=50,
    rsi_short=50,
)

SEPARATOR = "=" * 80


def print_header(test_num: int, title: str):
    print(f"\n{SEPARATOR}")
    print(f"  TEST {test_num}: {title}")
    print(SEPARATOR)


def verdict(label: str, passed: bool | None, detail: str = ""):
    if passed is True:
        tag = "PASS"
    elif passed is False:
        tag = "FAIL"
    else:
        tag = "WARNING"
    suffix = f" -- {detail}" if detail else ""
    print(f"  [{tag}] {label}{suffix}")
    return tag


# ============================================================
# TEST 1: Random Strategy Benchmark
# ============================================================
def test_random_strategy_benchmark():
    print_header(1, "RANDOM STRATEGY BENCHMARK (Selection Bias)")
    print("  Generating 1000 random strategies within grid bounds...")

    random.seed(42)
    n_random = 1000
    beats_bnh = 0
    positive = 0
    liquidated_count = 0
    returns = []

    for i in range(n_random):
        params = dict(
            leverage=random.choice([1, 2, 3, 4, 5]),
            allocation=random.uniform(0.3, 1.0),
            sl_pct=random.uniform(-80, -30),
            tp_pct=random.uniform(5, 30),
            ema_fast=random.randint(5, 50),
            ema_slow=random.randint(5, 50),
            rsi_period=random.randint(5, 30),
            rsi_long=random.uniform(30, 70),
            rsi_short=random.uniform(30, 70),
        )
        # Ensure ema_fast < ema_slow
        if params['ema_fast'] >= params['ema_slow']:
            params['ema_fast'], params['ema_slow'] = min(params['ema_fast'], params['ema_slow']), max(params['ema_fast'], params['ema_slow']) + 1

        try:
            r = run_backtest(CANDLES, **params)
            returns.append(r['total_return_pct'])
            if r['beats_bnh']:
                beats_bnh += 1
            if r['total_return_pct'] > 0:
                positive += 1
            if r['liquidated']:
                liquidated_count += 1
        except Exception as e:
            returns.append(float('nan'))

    pct_beats = beats_bnh / n_random * 100
    pct_positive = positive / n_random * 100
    valid_returns = [r for r in returns if not math.isnan(r)]
    avg_return = sum(valid_returns) / len(valid_returns) if valid_returns else 0
    median_return = sorted(valid_returns)[len(valid_returns) // 2] if valid_returns else 0

    print(f"  Total random strategies:     {n_random}")
    print(f"  Liquidated:                  {liquidated_count} ({liquidated_count/n_random*100:.1f}%)")
    print(f"  Positive return:             {positive} ({pct_positive:.1f}%)")
    print(f"  Beat Buy & Hold:             {beats_bnh} ({pct_beats:.1f}%)")
    print(f"  Average return:              {avg_return:+.1f}%")
    print(f"  Median return:               {median_return:+.1f}%")
    print()

    # If >5% of random strategies beat B&H, the structure has selection bias
    v1 = verdict(
        "Selection bias (>5% random beat B&H)",
        pct_beats <= 5,
        f"{pct_beats:.1f}% of random strategies beat B&H"
    )

    # Also check: if >50% are positive, the structure itself is biased toward profits
    v2 = verdict(
        "Structural profit bias (>50% positive)",
        pct_positive <= 50,
        f"{pct_positive:.1f}% of random strategies profitable"
    )

    return v1, v2


# ============================================================
# TEST 2: Reversed Data Test
# ============================================================
def test_reversed_data():
    print_header(2, "REVERSED DATA TEST (Structural Artifact)")

    reversed_candles = list(reversed(CANDLES))
    # Fix dates so they're sequential (just re-index)
    for i, c in enumerate(reversed_candles):
        c = dict(c)
        reversed_candles[i] = c

    # Run consensus strategy on original
    r_orig = run_backtest(CANDLES, **CONSENSUS)
    # Run consensus strategy on reversed
    r_rev = run_backtest(reversed_candles, **CONSENSUS)

    print(f"  Original data:  final=${r_orig['final_wallet']:.2f}, return={r_orig['total_return_pct']:+.1f}%, trades={r_orig['trade_count']}")
    print(f"  Reversed data:  final=${r_rev['final_wallet']:.2f}, return={r_rev['total_return_pct']:+.1f}%, trades={r_rev['trade_count']}")
    print()

    # If strategy profits on reversed data too, it may exploit a structural artifact
    both_profitable = r_rev['total_return_pct'] > 0 and r_orig['total_return_pct'] > 0
    similar = abs(r_rev['total_return_pct'] - r_orig['total_return_pct']) < 20  # within 20% of each other

    v = verdict(
        "Reversed data profitability",
        not (both_profitable and similar),
        f"Original: {r_orig['total_return_pct']:+.1f}%, Reversed: {r_rev['total_return_pct']:+.1f}%"
    )

    if r_rev['total_return_pct'] > 0:
        verdict(
            "Reversed data is also profitable",
            None,
            "Strategy profits on reversed data -- may indicate structural artifact OR just trend-following on reversed trend"
        )

    return v


# ============================================================
# TEST 3: Shuffled Candles Test
# ============================================================
def test_shuffled_candles():
    print_header(3, "SHUFFLED CANDLES TEST (Timing Edge)")
    print("  Running 100 iterations with randomly shuffled candle order...")

    random.seed(42)
    r_orig = run_backtest(CANDLES, **CONSENSUS)
    orig_return = r_orig['total_return_pct']

    shuffled_returns = []
    shuffled_liquidated = 0

    for _ in range(100):
        shuffled = copy.deepcopy(CANDLES)
        random.shuffle(shuffled)
        try:
            r = run_backtest(shuffled, **CONSENSUS)
            shuffled_returns.append(r['total_return_pct'])
            if r['liquidated']:
                shuffled_liquidated += 1
        except Exception:
            shuffled_returns.append(0.0)

    avg_shuffled = sum(shuffled_returns) / len(shuffled_returns)
    median_shuffled = sorted(shuffled_returns)[50]
    max_shuffled = max(shuffled_returns)
    min_shuffled = min(shuffled_returns)
    positive_shuffled = sum(1 for r in shuffled_returns if r > 0)

    print(f"  Original return:           {orig_return:+.1f}%")
    print(f"  Shuffled average return:   {avg_shuffled:+.1f}%")
    print(f"  Shuffled median return:    {median_shuffled:+.1f}%")
    print(f"  Shuffled range:            [{min_shuffled:+.1f}%, {max_shuffled:+.1f}%]")
    print(f"  Shuffled positive:         {positive_shuffled}/100")
    print(f"  Shuffled liquidated:       {shuffled_liquidated}/100")
    print()

    # If shuffled average is similar to original, strategy has no timing edge
    has_timing_edge = orig_return > avg_shuffled * 2 or (orig_return > 0 and avg_shuffled <= 0)

    v1 = verdict(
        "Timing edge exists",
        has_timing_edge,
        f"Original {orig_return:+.1f}% vs shuffled avg {avg_shuffled:+.1f}%"
    )

    # Check if the original return falls within the shuffled distribution
    pct_worse = sum(1 for r in shuffled_returns if r >= orig_return) / len(shuffled_returns) * 100
    v2 = verdict(
        "Original return is statistically significant vs shuffled",
        pct_worse < 5,
        f"{pct_worse:.0f}% of shuffled runs matched or exceeded original return"
    )

    return v1, v2


# ============================================================
# TEST 4: Half-Period Tests
# ============================================================
def test_half_period():
    print_header(4, "HALF-PERIOD TESTS (Period Dependence)")

    mid = len(CANDLES) // 2
    first_half = CANDLES[:mid]
    second_half = CANDLES[mid:]

    # Get dates for context
    print(f"  Full period:    {CANDLES[0]['date']} to {CANDLES[-1]['date']} ({len(CANDLES)} candles)")
    print(f"  First half:     {first_half[0]['date']} to {first_half[-1]['date']} ({len(first_half)} candles)")
    print(f"  Second half:    {second_half[0]['date']} to {second_half[-1]['date']} ({len(second_half)} candles)")
    print()

    r_full = run_backtest(CANDLES, **CONSENSUS)
    r_first = run_backtest(first_half, **CONSENSUS)
    r_second = run_backtest(second_half, **CONSENSUS)

    print(f"  Full period:   return={r_full['total_return_pct']:+.1f}%, trades={r_full['trade_count']}, wallet=${r_full['final_wallet']:.2f}")
    print(f"  First half:    return={r_first['total_return_pct']:+.1f}%, trades={r_first['trade_count']}, wallet=${r_first['final_wallet']:.2f}")
    print(f"  Second half:   return={r_second['total_return_pct']:+.1f}%, trades={r_second['trade_count']}, wallet=${r_second['final_wallet']:.2f}")
    print()

    # Check for dramatic differences
    both_profitable = r_first['total_return_pct'] > 0 and r_second['total_return_pct'] > 0
    both_negative = r_first['total_return_pct'] < 0 and r_second['total_return_pct'] < 0
    sign_consistent = both_profitable or both_negative

    if r_first['total_return_pct'] != 0:
        ratio = abs(r_second['total_return_pct'] / r_first['total_return_pct'])
    else:
        ratio = float('inf')

    v1 = verdict(
        "Sign consistency (both halves same direction)",
        sign_consistent,
        f"First: {r_first['total_return_pct']:+.1f}%, Second: {r_second['total_return_pct']:+.1f}%"
    )

    # Check if ratio is within 10x (dramatic = >10x difference)
    magnitude_ok = 0.1 <= ratio <= 10.0
    v2 = verdict(
        "Magnitude consistency (within 10x)",
        magnitude_ok,
        f"Ratio: {ratio:.2f}x"
    )

    # Check for liquidation in either half
    v3 = verdict(
        "No liquidation in either half",
        not r_first['liquidated'] and not r_second['liquidated'],
        f"First: {'LIQUIDATED' if r_first['liquidated'] else 'OK'}, Second: {'LIQUIDATED' if r_second['liquidated'] else 'OK'}"
    )

    return v1, v2, v3


# ============================================================
# TEST 5: Indicator Verification
# ============================================================
def test_indicator_verification():
    print_header(5, "INDICATOR VERIFICATION (EMA & RSI Correctness)")

    closes = [c['close'] for c in CANDLES[:60]]  # use first 60 for verification

    # --- EMA(10) Manual vs Library ---
    period = 10
    lib_ema = compute_ema(closes, period)

    # Manual EMA computation
    manual_ema = [None] * (period - 1)
    # SMA seed
    sma_seed = sum(closes[:period]) / period
    manual_ema.append(sma_seed)
    multiplier = 2.0 / (period + 1.0)
    for i in range(period, len(closes)):
        ema_val = (closes[i] - manual_ema[-1]) * multiplier + manual_ema[-1]
        manual_ema.append(ema_val)

    print("  EMA(10) Verification (first 50 data points):")
    print(f"  {'idx':>4} {'Close':>12} {'Lib EMA':>14} {'Manual EMA':>14} {'Diff':>12} {'Match':>6}")
    ema_errors = 0
    for i in range(min(50, len(closes))):
        if lib_ema[i] is None and (i < len(manual_ema) and manual_ema[i] is None):
            continue
        if lib_ema[i] is None or i >= len(manual_ema) or manual_ema[i] is None:
            continue
        diff = abs(lib_ema[i] - manual_ema[i])
        match = "OK" if diff < 0.01 else "ERR"
        if diff >= 0.01:
            ema_errors += 1
        if i < period + 5 or ema_errors > 0:  # print first few + any errors
            print(f"  {i:4d} {closes[i]:12.2f} {lib_ema[i]:14.4f} {manual_ema[i]:14.4f} {diff:12.6f} {match:>6}")

    v_ema = verdict(
        "EMA(10) matches manual calculation",
        ema_errors == 0,
        f"{ema_errors} mismatches found in first 50 points"
    )

    # --- RSI(21) Manual vs Library ---
    rsi_period = 21
    lib_rsi = compute_rsi(closes, rsi_period)

    # Manual RSI: SMA-based (non-smoothed, matching library implementation)
    deltas = [0.0] + [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]

    manual_rsi: list[float | None] = []
    for i in range(len(closes)):
        if i + 1 < rsi_period:
            manual_rsi.append(None)
            continue
        avg_gain = sum(gains[i + 1 - rsi_period: i + 1]) / rsi_period
        avg_loss = sum(losses[i + 1 - rsi_period: i + 1]) / rsi_period
        if avg_loss <= 0:
            manual_rsi.append(100.0)
        else:
            rs = avg_gain / avg_loss
            manual_rsi.append(100.0 - (100.0 / (1.0 + rs)))

    print()
    print("  RSI(21) Verification (first 50 data points):")
    print(f"  {'idx':>4} {'Close':>12} {'Lib RSI':>12} {'Manual RSI':>12} {'Diff':>10} {'Match':>6}")
    rsi_errors = 0
    shown = 0
    for i in range(min(50, len(closes))):
        if lib_rsi[i] is None and manual_rsi[i] is None:
            continue
        if lib_rsi[i] is None or manual_rsi[i] is None:
            rsi_errors += 1
            print(f"  {i:4d} {closes[i]:12.2f} {'None':>12} {'None':>12} {'N/A':>10} {'ERR':>6}")
            continue
        diff = abs(lib_rsi[i] - manual_rsi[i])
        match = "OK" if diff < 0.01 else "ERR"
        if diff >= 0.01:
            rsi_errors += 1
        if shown < 5 or rsi_errors > 0:
            print(f"  {i:4d} {closes[i]:12.2f} {lib_rsi[i]:12.4f} {manual_rsi[i]:12.4f} {diff:10.6f} {match:>6}")
            shown += 1

    v_rsi = verdict(
        "RSI(21) matches manual calculation",
        rsi_errors == 0,
        f"{rsi_errors} mismatches found in first 50 points"
    )

    # NOTE: The library uses SMA-based RSI (re-computed every bar), not Wilder's smoothed RSI
    # This is a valid but less common implementation. Flag it as a warning.
    print()
    print("  NOTE: Library RSI uses SMA-based window (re-computed each bar),")
    print("        not Wilder's exponentially smoothed RSI. This is valid but")
    print("        differs from most charting platforms (TradingView, etc).")
    v_rsi_type = verdict(
        "RSI implementation type",
        None,
        "SMA-window RSI, not Wilder's smoothed RSI -- may diverge from standard RSI on charting platforms"
    )

    return v_ema, v_rsi, v_rsi_type


# ============================================================
# TEST 6: Trade Count Reasonableness
# ============================================================
def test_trade_count():
    print_header(6, "TRADE COUNT REASONABLENESS")

    r = run_backtest(CANDLES, **CONSENSUS)
    n_candles = len(CANDLES)
    trade_count = r['trade_count']
    years = r['years']
    trades_per_year = trade_count / years if years > 0 else 0

    print(f"  Total candles:       {n_candles}")
    print(f"  Period:              {years:.1f} years")
    print(f"  Trade count:         {trade_count}")
    print(f"  Trades/year:         {trades_per_year:.1f}")
    print()

    # Compute theoretical signal frequency
    # EMA crossover signals: count how many times EMA_fast crosses EMA_slow
    closes = [c['close'] for c in CANDLES]
    ema_f = compute_ema(closes, CONSENSUS['ema_fast'])
    ema_s = compute_ema(closes, CONSENSUS['ema_slow'])
    rsi = compute_rsi(closes, CONSENSUS['rsi_period'])

    warmup = max(CONSENSUS['ema_slow'], CONSENSUS['rsi_period']) + 1

    crossover_count = 0
    entry_signals = 0
    for i in range(warmup + 1, len(closes)):
        if ema_f[i] is None or ema_s[i] is None or ema_f[i-1] is None or ema_s[i-1] is None:
            continue
        if rsi[i] is None:
            continue
        # EMA crossover (either direction)
        prev_diff = ema_f[i-1] - ema_s[i-1]
        curr_diff = ema_f[i] - ema_s[i]
        if prev_diff * curr_diff < 0:  # sign changed = crossover
            crossover_count += 1

        # Actual entry signals (with RSI filter)
        # Long: ema_f > ema_s AND rsi > rsi_long
        # Short: ema_f < ema_s AND rsi < rsi_short
        if ema_f[i] > ema_s[i] and rsi[i] > CONSENSUS['rsi_long']:
            if not (ema_f[i-1] > ema_s[i-1] and rsi[i-1] > CONSENSUS['rsi_long']):
                entry_signals += 1
        elif ema_f[i] < ema_s[i] and rsi[i] < CONSENSUS['rsi_short']:
            if not (ema_f[i-1] < ema_s[i-1] and rsi[i-1] < CONSENSUS['rsi_short']):
                entry_signals += 1

    crossovers_per_year = crossover_count / years if years > 0 else 0
    signals_per_year = entry_signals / years if years > 0 else 0

    print(f"  EMA crossovers:      {crossover_count} ({crossovers_per_year:.1f}/year)")
    print(f"  Entry signals:       {entry_signals} ({signals_per_year:.1f}/year)")
    print(f"  Actual trades:       {trade_count} ({trades_per_year:.1f}/year)")
    print()

    # Trade count should be <= entry signals (can't trade more than signals)
    v1 = verdict(
        "Trade count <= entry signals",
        trade_count <= entry_signals + 5,  # small margin for end-of-data effects
        f"{trade_count} trades vs {entry_signals} signals"
    )

    # Reasonableness: EMA 12/26 on daily produces ~10-20 crossovers/year typically
    # With RSI filter and position management, 3-8 trades/year is reasonable
    reasonable = 1 <= trades_per_year <= 20
    v2 = verdict(
        "Trade frequency reasonable (1-20/year for daily EMA crossover)",
        reasonable,
        f"{trades_per_year:.1f} trades/year"
    )

    # Very low trade count warning
    if trades_per_year < 3:
        v3 = verdict(
            "Sufficient trades for statistical significance (>30 total)",
            trade_count >= 30,
            f"Only {trade_count} trades -- results may not be statistically significant"
        )
    else:
        v3 = verdict(
            "Sufficient trades for statistical significance (>30 total)",
            trade_count >= 30,
            f"{trade_count} total trades"
        )

    return v1, v2, v3


# ============================================================
# MAIN
# ============================================================
def main():
    print(SEPARATOR)
    print("  AUDIT TEAM 3: Bias & Statistical Validity Check")
    print(f"  Data: {len(CANDLES)} candles, {CANDLES[0]['date']} to {CANDLES[-1]['date']}")
    print(f"  Initial Capital: ${INITIAL_CAPITAL}")
    print(f"  Consensus params: {CONSENSUS}")
    print(SEPARATOR)

    all_verdicts = []

    v = test_random_strategy_benchmark()
    all_verdicts.extend(v)

    v = test_reversed_data()
    if isinstance(v, tuple):
        all_verdicts.extend(v)
    else:
        all_verdicts.append(v)

    v = test_shuffled_candles()
    all_verdicts.extend(v)

    v = test_half_period()
    all_verdicts.extend(v)

    v = test_indicator_verification()
    all_verdicts.extend(v)

    v = test_trade_count()
    all_verdicts.extend(v)

    # Summary
    print(f"\n{SEPARATOR}")
    print("  SUMMARY")
    print(SEPARATOR)
    passes = sum(1 for v in all_verdicts if v == "PASS")
    fails = sum(1 for v in all_verdicts if v == "FAIL")
    warnings = sum(1 for v in all_verdicts if v == "WARNING")
    total = len(all_verdicts)
    print(f"  PASS:    {passes}/{total}")
    print(f"  FAIL:    {fails}/{total}")
    print(f"  WARNING: {warnings}/{total}")
    print()
    if fails > 0:
        print("  OVERALL: CONCERNS FOUND -- review FAIL items above")
    elif warnings > 0:
        print("  OVERALL: MOSTLY CLEAN -- review WARNING items above")
    else:
        print("  OVERALL: ALL CLEAR")
    print(SEPARATOR)


if __name__ == "__main__":
    main()
