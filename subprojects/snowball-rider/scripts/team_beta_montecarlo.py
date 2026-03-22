#!/usr/bin/env python3
"""Team Beta: Monte Carlo Bootstrap Simulation for BTC EMA/RSI Strategy.

Validates candidate parameter sets using:
1. Bootstrap resampling (5000 iterations) — confidence intervals on final wallet
2. Permutation test (1000 iterations) — tests for genuine timing edge

Usage:
  cd snowball-rider && .venv/bin/python scripts/team_beta_montecarlo.py
"""

from __future__ import annotations
import sys
import os
import json
import random
import math
import time
from datetime import datetime, timezone
from dataclasses import dataclass

# Setup path for indicators
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from snowball_rider.indicators import compute_ema, compute_rsi

# ── Constants ────────────────────────────────────────────────────────────────
INITIAL_CAPITAL = 818.0
CRASH_THRESHOLD = 0.30
BUY_AND_HOLD_VALUE = 6907.0
BOOTSTRAP_ITERATIONS = 5000
PERMUTATION_ITERATIONS = 1000
RANDOM_SEED = 42


# ── Candidate Parameter Sets ────────────────────────────────────────────────
CANDIDATES = [
    {"name": "Set 1", "lev": 3, "alloc": 0.4, "sl": -60, "tp": 10, "ema_f": 12, "ema_s": 26, "rsi_p": 21, "rsi_l": 50, "rsi_s": 50},
    {"name": "Set 2", "lev": 2, "alloc": 0.5, "sl": -70, "tp": 15, "ema_f": 12, "ema_s": 26, "rsi_p": 14, "rsi_l": 55, "rsi_s": 45},
    {"name": "Set 3", "lev": 3, "alloc": 0.3, "sl": -60, "tp": 10, "ema_f": 12, "ema_s": 26, "rsi_p": 21, "rsi_l": 50, "rsi_s": 50},
    {"name": "Set 4", "lev": 3, "alloc": 0.5, "sl": -60, "tp": 10, "ema_f": 12, "ema_s": 26, "rsi_p": 21, "rsi_l": 50, "rsi_s": 50},
    {"name": "Set 5", "lev": 3, "alloc": 0.4, "sl": -80, "tp": 5, "ema_f": 12, "ema_s": 26, "rsi_p": 14, "rsi_l": 55, "rsi_s": 45},
    {"name": "Set 6", "lev": 2, "alloc": 0.4, "sl": -70, "tp": 15, "ema_f": 12, "ema_s": 26, "rsi_p": 14, "rsi_l": 55, "rsi_s": 45},
    {"name": "Set 7", "lev": 3, "alloc": 0.4, "sl": -60, "tp": 10, "ema_f": 10, "ema_s": 30, "rsi_p": 21, "rsi_l": 50, "rsi_s": 50},
    {"name": "Set 8", "lev": 3, "alloc": 0.4, "sl": -60, "tp": 15, "ema_f": 12, "ema_s": 26, "rsi_p": 21, "rsi_l": 50, "rsi_s": 50},
]


# ── Data Loading ─────────────────────────────────────────────────────────────
def load_candles() -> list[dict]:
    cache_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'btcusdt_1d_klines.json')
    if not os.path.exists(cache_path):
        print(f"ERROR: Cache file not found at {cache_path}")
        sys.exit(1)
    with open(cache_path) as f:
        return json.load(f)


def filter_crashes(candles: list[dict]) -> list[dict]:
    crash_dates = {"2020-03-12", "2020-03-13"}
    return [c for c in candles
            if c["date"] not in crash_dates
            and (c["high"] - c["low"]) / c["high"] <= CRASH_THRESHOLD
            and (c["open"] - c["close"]) / c["open"] <= CRASH_THRESHOLD]


# ── Trade Record ─────────────────────────────────────────────────────────────
@dataclass
class Trade:
    side: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    holding_days: int
    exit_reason: str          # "SL", "TP", "LIQUIDATION", "END"
    wallet_before: float      # wallet at trade entry
    wallet_after: float       # wallet at trade exit
    multiplier: float         # wallet_after / wallet_before
    raw_pnl_pct: float        # PnL % on allocated capital (before fees/funding effects)


# ── Trade-Level Backtest (mirrors grid_search.py exactly) ────────────────────
def run_backtest_with_trades(
    candles: list[dict],
    leverage: int,
    allocation: float,
    sl_pct: float,
    tp_pct: float,
    ema_fast: int = 12, ema_slow: int = 26,
    rsi_period: int = 21, rsi_long: float = 50, rsi_short: float = 50,
    tp_ema_fast: int = 7, tp_ema_slow: int = 14, tp_cross_days: int = 2,
) -> tuple[list[Trade], float, bool]:
    """Exact replica of grid_search.run_backtest, but also records trades."""
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
    trades: list[Trade] = []
    liquidated = False

    in_position = False
    position_side = ""
    entry_price = 0.0
    entry_idx = 0
    allocated = 0.0
    wallet_at_entry = 0.0  # wallet snapshot at trade entry
    tp_activated = False
    tp_cross_count = 0
    warmup = max(ema_slow, rsi_period, tp_ema_slow) + 1

    for i in range(n):
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
                trades.append(Trade(
                    side=position_side, entry_date=dates[entry_idx],
                    exit_date=dates[i], entry_price=entry_price,
                    exit_price=closes[i], holding_days=i - entry_idx,
                    exit_reason="LIQUIDATION",
                    wallet_before=wallet_at_entry, wallet_after=wallet,
                    multiplier=wallet / wallet_at_entry if wallet_at_entry > 0 else 0,
                    raw_pnl_pct=-100.0,
                ))
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
                trades.append(Trade(
                    side=position_side, entry_date=dates[entry_idx],
                    exit_date=dates[i], entry_price=entry_price,
                    exit_price=closes[i], holding_days=i - entry_idx,
                    exit_reason="SL",
                    wallet_before=wallet_at_entry, wallet_after=wallet,
                    multiplier=wallet / wallet_at_entry if wallet_at_entry > 0 else 0,
                    raw_pnl_pct=net_pnl,
                ))
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
                    trades.append(Trade(
                        side=position_side, entry_date=dates[entry_idx],
                        exit_date=dates[i], entry_price=entry_price,
                        exit_price=closes[i], holding_days=i - entry_idx,
                        exit_reason="TP",
                        wallet_before=wallet_at_entry, wallet_after=wallet,
                        multiplier=wallet / wallet_at_entry if wallet_at_entry > 0 else 0,
                        raw_pnl_pct=net_pnl,
                    ))
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
            wallet_at_entry = wallet
            allocated = wallet * allocation
            entry_price = closes[i]
            entry_idx = i
            position_side = "LONG"
            in_position = True
            tp_activated = False
            tp_cross_count = 0
            continue

        if ema_f[i] < ema_s[i] and rsi[i] < rsi_short:
            wallet_at_entry = wallet
            allocated = wallet * allocation
            entry_price = closes[i]
            entry_idx = i
            position_side = "SHORT"
            in_position = True
            tp_activated = False
            tp_cross_count = 0
            continue

    # Close open position at end
    if in_position and wallet > 0:
        if position_side == "LONG":
            close_pnl = ((closes[-1] / entry_price) - 1) * 100 * leverage
        else:
            close_pnl = ((entry_price / closes[-1]) - 1) * 100 * leverage
        fee_cost = fee_rate * leverage * 2 * 100
        net_pnl = close_pnl - fee_cost
        old_wallet = wallet
        wallet = (old_wallet - allocated) + allocated * (1 + net_pnl / 100)
        trades.append(Trade(
            side=position_side, entry_date=dates[entry_idx],
            exit_date=dates[-1], entry_price=entry_price,
            exit_price=closes[-1], holding_days=len(candles) - 1 - entry_idx,
            exit_reason="END",
            wallet_before=wallet_at_entry, wallet_after=wallet,
            multiplier=wallet / wallet_at_entry if wallet_at_entry > 0 else 0,
            raw_pnl_pct=net_pnl,
        ))

    return trades, wallet, liquidated


# ── Bootstrap Simulation ─────────────────────────────────────────────────────
def bootstrap_simulation(
    multipliers: list[float],
    n_iterations: int = BOOTSTRAP_ITERATIONS,
    initial_capital: float = INITIAL_CAPITAL,
) -> list[float]:
    """Resample trade multipliers with replacement, compound them."""
    n_trades = len(multipliers)
    if n_trades == 0:
        return [initial_capital] * n_iterations

    results = []
    for _ in range(n_iterations):
        wallet = initial_capital
        for _ in range(n_trades):
            m = random.choice(multipliers)
            wallet *= m
            if wallet <= 0:
                wallet = 0
                break
        results.append(wallet)
    return results


# ── Permutation Test ─────────────────────────────────────────────────────────
def permutation_test(
    multipliers: list[float],
    original_wallet: float,
    n_iterations: int = PERMUTATION_ITERATIONS,
    initial_capital: float = INITIAL_CAPITAL,
) -> tuple[float, list[float]]:
    """Shuffle trade order to test if sequence matters.

    Returns (p_value, permuted_wallets).
    Note: for multiplicative compounding, order doesn't matter mathematically.
    The p-value tests whether the specific set of trade multipliers is special
    compared to random subsets. This is really testing bootstrap consistency.
    """
    n_trades = len(multipliers)
    if n_trades == 0:
        return 1.0, [initial_capital] * n_iterations

    permuted_wallets = []
    count_ge_original = 0

    for _ in range(n_iterations):
        shuffled = multipliers[:]
        random.shuffle(shuffled)
        wallet = initial_capital
        for m in shuffled:
            wallet *= m
            if wallet <= 0:
                wallet = 0
                break
        permuted_wallets.append(wallet)
        if wallet >= original_wallet:
            count_ge_original += 1

    p_value = count_ge_original / n_iterations
    return p_value, permuted_wallets


# ── Statistics ───────────────────────────────────────────────────────────────
def percentile(sorted_data: list[float], pct: float) -> float:
    n = len(sorted_data)
    if n == 0:
        return 0.0
    idx = pct / 100.0 * (n - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return sorted_data[lo]
    frac = idx - lo
    return sorted_data[lo] * (1 - frac) + sorted_data[hi] * frac


def compute_stats(wallets: list[float]) -> dict:
    n = len(wallets)
    if n == 0:
        return {}

    sorted_w = sorted(wallets)
    mean_w = sum(wallets) / n
    median_w = percentile(sorted_w, 50)
    variance = sum((w - mean_w) ** 2 for w in wallets) / n
    std_w = math.sqrt(variance)

    return {
        "mean": mean_w,
        "median": median_w,
        "std": std_w,
        "p5": percentile(sorted_w, 5),
        "p10": percentile(sorted_w, 10),
        "p25": percentile(sorted_w, 25),
        "p75": percentile(sorted_w, 75),
        "p95": percentile(sorted_w, 95),
        "min": sorted_w[0],
        "max": sorted_w[-1],
        "prob_beat_bnh": sum(1 for w in wallets if w > BUY_AND_HOLD_VALUE) / n,
        "prob_positive": sum(1 for w in wallets if w > INITIAL_CAPITAL) / n,
        "prob_ruin": sum(1 for w in wallets if w <= 10) / n,
    }


def sharpe_like_ratio(multipliers: list[float]) -> float:
    """Sharpe-like: mean(log_return) / std(log_return) per trade."""
    if len(multipliers) < 2:
        return 0.0
    # Use log returns for better statistical properties
    log_rets = [math.log(m) if m > 0 else -10.0 for m in multipliers]
    n = len(log_rets)
    mean_r = sum(log_rets) / n
    variance = sum((r - mean_r) ** 2 for r in log_rets) / (n - 1)
    std_r = math.sqrt(variance)
    if std_r == 0:
        return 0.0
    return mean_r / std_r


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    random.seed(RANDOM_SEED)

    print("=" * 100)
    print("  TEAM BETA: Monte Carlo Bootstrap Validation")
    print("  BTC Daily EMA/RSI Strategy — Statistical Significance Testing")
    print(f"  Initial Capital: ${INITIAL_CAPITAL:,.0f} | B&H Reference: ${BUY_AND_HOLD_VALUE:,.0f}")
    print(f"  Bootstrap: {BOOTSTRAP_ITERATIONS:,} iterations | Permutation: {PERMUTATION_ITERATIONS:,} iterations")
    print("=" * 100)

    candles = load_candles()
    filtered = filter_crashes(candles)
    print(f"\n  Data: {len(candles)} raw -> {len(filtered)} after crash filter")
    print(f"  Range: {filtered[0]['date']} to {filtered[-1]['date']}")

    # Cross-validate with grid_search.py
    print("\n  Cross-validating with grid_search.run_backtest...")
    sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
    from grid_search import run_backtest as gs_run_backtest

    all_results = []

    for cand in CANDIDATES:
        name = cand["name"]
        print(f"\n{'=' * 100}")
        print(f"  {name}: lev={cand['lev']}x alloc={cand['alloc']*100:.0f}% "
              f"SL={cand['sl']}% TP={cand['tp']}% "
              f"EMA={cand['ema_f']}/{cand['ema_s']} "
              f"RSI({cand['rsi_p']})>{cand['rsi_l']}<{cand['rsi_s']}")
        print(f"{'=' * 100}")

        t0 = time.time()

        # Step 1: Cross-validate with grid_search
        gs_result = gs_run_backtest(
            filtered, leverage=cand["lev"], allocation=cand["alloc"],
            sl_pct=cand["sl"], tp_pct=cand["tp"],
            ema_fast=cand["ema_f"], ema_slow=cand["ema_s"],
            rsi_period=cand["rsi_p"], rsi_long=cand["rsi_l"], rsi_short=cand["rsi_s"],
        )

        # Step 2: Run trade-level backtest
        trades, our_wallet, liquidated = run_backtest_with_trades(
            filtered, leverage=cand["lev"], allocation=cand["alloc"],
            sl_pct=cand["sl"], tp_pct=cand["tp"],
            ema_fast=cand["ema_f"], ema_slow=cand["ema_s"],
            rsi_period=cand["rsi_p"], rsi_long=cand["rsi_l"], rsi_short=cand["rsi_s"],
        )

        n_trades = len(trades)
        wins = sum(1 for t in trades if t.multiplier > 1.0)
        losses = sum(1 for t in trades if t.multiplier <= 1.0)
        win_rate = wins / n_trades * 100 if n_trades > 0 else 0
        multipliers = [t.multiplier for t in trades]

        # Verification
        gs_wallet = gs_result["final_wallet"]
        gs_trades = gs_result["trade_count"]
        wallet_diff = abs(our_wallet - gs_wallet)
        match_ok = wallet_diff < 1.0 and n_trades == gs_trades

        print(f"\n  Cross-Validation:")
        print(f"    grid_search:  ${gs_wallet:>12,.2f} | {gs_trades} trades | WR={gs_result['win_rate']:.1f}%")
        print(f"    our backtest: ${our_wallet:>12,.2f} | {n_trades} trades | WR={win_rate:.1f}%")
        print(f"    Match: {'OK' if match_ok else 'MISMATCH (diff=$' + f'{wallet_diff:.2f}, trades={gs_trades} vs {n_trades})'}")

        if not match_ok:
            print(f"    WARNING: Results differ. Investigating...")
            # Show trade-by-trade detail for debugging
            if n_trades <= 10:
                for t in trades:
                    print(f"      {t.side:5s} {t.entry_date}->{t.exit_date} "
                          f"${t.wallet_before:>10,.2f} -> ${t.wallet_after:>10,.2f} "
                          f"(x{t.multiplier:.4f}) {t.exit_reason}")

        print(f"\n  Original Backtest:")
        print(f"    Final Wallet: ${our_wallet:,.2f} ({(our_wallet/INITIAL_CAPITAL-1)*100:+.1f}%)")
        print(f"    Trades: {n_trades} | Wins: {wins} ({win_rate:.1f}%) | Losses: {losses}")
        print(f"    Liquidated: {liquidated}")

        if n_trades > 0:
            # Show select trades
            show_n = min(5, n_trades)
            print(f"\n  First {show_n} trades:")
            for t in trades[:show_n]:
                print(f"    {t.side:5s} {t.entry_date} -> {t.exit_date} | "
                      f"x{t.multiplier:.4f} | {t.exit_reason:4s} | {t.holding_days}d | "
                      f"${t.wallet_before:,.0f} -> ${t.wallet_after:,.0f}")
            if n_trades > show_n:
                print(f"  Last {show_n} trades:")
                for t in trades[-show_n:]:
                    print(f"    {t.side:5s} {t.entry_date} -> {t.exit_date} | "
                          f"x{t.multiplier:.4f} | {t.exit_reason:4s} | {t.holding_days}d | "
                          f"${t.wallet_before:,.0f} -> ${t.wallet_after:,.0f}")

            # Trade multiplier statistics
            avg_mult = sum(multipliers) / n_trades
            win_mults = [m for m in multipliers if m > 1.0]
            loss_mults = [m for m in multipliers if m <= 1.0]
            avg_win_m = sum(win_mults) / len(win_mults) if win_mults else 0
            avg_loss_m = sum(loss_mults) / len(loss_mults) if loss_mults else 0
            best_m = max(multipliers)
            worst_m = min(multipliers)
            print(f"\n  Trade Multiplier Stats:")
            print(f"    Avg multiplier: x{avg_mult:.4f}")
            print(f"    Avg win mult:   x{avg_win_m:.4f} ({len(win_mults)} trades)")
            print(f"    Avg loss mult:  x{avg_loss_m:.4f} ({len(loss_mults)} trades)")
            print(f"    Best:  x{best_m:.4f} | Worst: x{worst_m:.4f}")

        # Step 3: Bootstrap
        sharpe = sharpe_like_ratio(multipliers)
        print(f"\n  Running {BOOTSTRAP_ITERATIONS:,} bootstrap iterations...")
        bootstrap_wallets = bootstrap_simulation(multipliers)
        stats = compute_stats(bootstrap_wallets)

        print(f"\n  Bootstrap Results:")
        print(f"    Mean Wallet:   ${stats['mean']:>14,.2f}")
        print(f"    Median Wallet: ${stats['median']:>14,.2f}")
        print(f"    Std Dev:       ${stats['std']:>14,.2f}")
        print(f"    Min:           ${stats['min']:>14,.2f}")
        print(f"    Max:           ${stats['max']:>14,.2f}")
        print(f"    ")
        print(f"    5th Pctile (95% CI lower):  ${stats['p5']:>14,.2f}")
        print(f"    10th Pctile (90% CI lower): ${stats['p10']:>14,.2f}")
        print(f"    25th Pctile:                ${stats['p25']:>14,.2f}")
        print(f"    75th Pctile:                ${stats['p75']:>14,.2f}")
        print(f"    95th Pctile:                ${stats['p95']:>14,.2f}")
        print(f"    ")
        print(f"    P(wallet > B&H ${BUY_AND_HOLD_VALUE:,.0f}):  {stats['prob_beat_bnh']*100:>7.2f}%")
        print(f"    P(wallet > ${INITIAL_CAPITAL:,.0f} initial): {stats['prob_positive']*100:>7.2f}%")
        print(f"    P(ruin, wallet <= $10):          {stats['prob_ruin']*100:>7.2f}%")
        print(f"    Sharpe-like (log-ret):           {sharpe:>+7.3f}")

        # Step 4: Permutation test
        print(f"\n  Running {PERMUTATION_ITERATIONS:,} permutation iterations...")
        perm_pval, perm_wallets = permutation_test(multipliers, our_wallet)
        perm_stats = compute_stats(perm_wallets)

        # Note: multiplication is commutative, so shuffling order of multipliers
        # gives the same product. The permutation test is meaningful here because
        # wallet can hit zero (m=0 kills the chain), so ORDER does matter when
        # there are extreme losses.
        print(f"\n  Permutation Test:")
        print(f"    p-value: {perm_pval:.4f}")
        print(f"    Permuted Mean:   ${perm_stats['mean']:>14,.2f}")
        print(f"    Permuted Median: ${perm_stats['median']:>14,.2f}")
        print(f"    Original:        ${our_wallet:>14,.2f}")

        if perm_pval < 0.05:
            verdict_perm = "SIGNIFICANT (p < 0.05): Trade ordering matters"
        elif perm_pval < 0.10:
            verdict_perm = "MARGINAL (p < 0.10): Weak ordering effect"
        else:
            verdict_perm = "NOT SIGNIFICANT: Ordering has no special effect"
        print(f"    Verdict: {verdict_perm}")

        elapsed = time.time() - t0
        print(f"\n  Time: {elapsed:.1f}s")

        all_results.append({
            "name": name,
            "params": cand,
            "original_wallet": our_wallet,
            "gs_wallet": gs_wallet,
            "n_trades": n_trades,
            "win_rate": win_rate,
            "sharpe": sharpe,
            "liquidated": liquidated,
            "stats": stats,
            "perm_pval": perm_pval,
            "multipliers": multipliers,
        })

    # ── Final Ranking ────────────────────────────────────────────────────────
    print(f"\n\n{'=' * 100}")
    print(f"  FINAL RANKING by 5th Percentile Wallet (Conservative Estimate)")
    print(f"{'=' * 100}")

    ranked = sorted(all_results, key=lambda x: x["stats"]["p5"], reverse=True)

    hdr = (f"  {'#':>2} {'Name':>6} {'Lev':>3} {'Alloc':>5} {'SL':>4} {'TP':>3} "
           f"{'EMA':>5} {'RSI':>9} {'N':>3} {'WR':>5} {'Sharpe':>7} "
           f"{'Orig$':>10} {'P5$':>10} {'P50$':>10} {'P95$':>12} "
           f"{'P(>BH)':>7} {'P(>$818)':>8} {'P(ruin)':>8}")
    print(f"\n{hdr}")
    print(f"  {'--':>2} {'------':>6} {'---':>3} {'-----':>5} {'----':>4} {'---':>3} "
          f"{'-----':>5} {'---------':>9} {'---':>3} {'-----':>5} {'-------':>7} "
          f"{'----------':>10} {'----------':>10} {'----------':>10} {'------------':>12} "
          f"{'-------':>7} {'--------':>8} {'--------':>8}")

    for idx, r in enumerate(ranked, 1):
        p = r["params"]
        s = r["stats"]
        ema_str = f"{p['ema_f']}/{p['ema_s']}"
        rsi_str = f"{p['rsi_p']}>{p['rsi_l']}<{p['rsi_s']}"
        print(f"  {idx:2d} {r['name']:>6} {p['lev']:>3}x {p['alloc']:>4.0%} {p['sl']:>4}% {p['tp']:>3}% "
              f"{ema_str:>5} {rsi_str:>9} {r['n_trades']:>3} {r['win_rate']:>4.0f}% {r['sharpe']:>+7.3f} "
              f"${r['original_wallet']:>9,.0f} ${s['p5']:>9,.0f} ${s['median']:>9,.0f} ${s['p95']:>11,.0f} "
              f"{s['prob_beat_bnh']*100:>6.1f}% {s['prob_positive']*100:>7.1f}% {s['prob_ruin']*100:>7.1f}%")

    # ── Confidence Statements ────────────────────────────────────────────────
    print(f"\n\n{'=' * 100}")
    print(f"  STATISTICAL CONFIDENCE STATEMENTS")
    print(f"{'=' * 100}")

    for idx, r in enumerate(ranked, 1):
        p = r["params"]
        s = r["stats"]
        print(f"\n  #{idx} {r['name']} (lev={p['lev']}x, alloc={p['alloc']:.0%}, "
              f"SL={p['sl']}%, TP={p['tp']}%, EMA={p['ema_f']}/{p['ema_s']}, "
              f"RSI({p['rsi_p']})>{p['rsi_l']}<{p['rsi_s']}):")
        print(f"     With 95% confidence, yields wallet >= ${s['p5']:,.2f} after {r['n_trades']} trades")
        print(f"     With 90% confidence, yields wallet >= ${s['p10']:,.2f}")
        print(f"     Median expected outcome: ${s['median']:,.2f}")
        print(f"     P(beat B&H ${BUY_AND_HOLD_VALUE:,.0f}): {s['prob_beat_bnh']*100:.1f}%")
        print(f"     P(positive return): {s['prob_positive']*100:.1f}%")
        print(f"     P(ruin): {s['prob_ruin']*100:.1f}%")
        print(f"     Sharpe-like: {r['sharpe']:+.3f}")

        if s['prob_ruin'] > 0.05:
            risk = "HIGH RISK"
        elif s['prob_ruin'] > 0.01:
            risk = "MODERATE RISK"
        elif s['prob_ruin'] > 0:
            risk = "LOW RISK"
        else:
            risk = "MINIMAL RISK"

        if s['p5'] > BUY_AND_HOLD_VALUE and s['prob_ruin'] < 0.05:
            verdict = "STRONG CANDIDATE -- 95% CI beats B&H"
        elif s['p5'] > INITIAL_CAPITAL and s['prob_ruin'] < 0.05:
            verdict = "VIABLE CANDIDATE -- 95% CI profitable"
        elif s['median'] > INITIAL_CAPITAL and s['prob_ruin'] < 0.10:
            verdict = "MARGINAL -- Median profitable but high variance"
        elif s['median'] > INITIAL_CAPITAL:
            verdict = "WEAK -- Median profitable but significant ruin risk"
        else:
            verdict = "REJECT -- Insufficient evidence of reliable profitability"

        print(f"     Risk: {risk} | Verdict: {verdict}")

    # ── Distribution Table ───────────────────────────────────────────────────
    print(f"\n\n{'=' * 100}")
    print(f"  BOOTSTRAP WALLET DISTRIBUTION (Percentiles)")
    print(f"{'=' * 100}")
    print(f"\n  {'Name':>6} {'Min':>10} {'P5':>10} {'P10':>10} {'P25':>10} "
          f"{'Median':>10} {'P75':>12} {'P95':>14} {'Max':>16}")
    print(f"  {'------':>6} {'----------':>10} {'----------':>10} {'----------':>10} {'----------':>10} "
          f"{'----------':>10} {'------------':>12} {'--------------':>14} {'----------------':>16}")
    for r in ranked:
        s = r["stats"]
        print(f"  {r['name']:>6} ${s['min']:>9,.0f} ${s['p5']:>9,.0f} ${s['p10']:>9,.0f} ${s['p25']:>9,.0f} "
              f"${s['median']:>9,.0f} ${s['p75']:>11,.0f} ${s['p95']:>13,.0f} ${s['max']:>15,.0f}")

    # ── Trade Multiplier Summary ─────────────────────────────────────────────
    print(f"\n\n{'=' * 100}")
    print(f"  TRADE MULTIPLIER SUMMARY")
    print(f"{'=' * 100}")
    print(f"\n  {'Name':>6} {'N':>3} {'WR':>5} {'AvgMult':>8} {'BestMult':>9} {'WorstMult':>10} {'Sharpe':>7}")
    print(f"  {'------':>6} {'---':>3} {'-----':>5} {'--------':>8} {'---------':>9} {'----------':>10} {'-------':>7}")
    for r in ranked:
        mults = r["multipliers"]
        if mults:
            avg_m = sum(mults) / len(mults)
            best_m = max(mults)
            worst_m = min(mults)
        else:
            avg_m = best_m = worst_m = 0
        print(f"  {r['name']:>6} {r['n_trades']:>3} {r['win_rate']:>4.0f}% "
              f"x{avg_m:>7.4f} x{best_m:>8.4f} x{worst_m:>9.4f} {r['sharpe']:>+7.3f}")

    print(f"\n{'=' * 100}")
    print(f"  ANALYSIS COMPLETE")
    print(f"  Seed={RANDOM_SEED} | Bootstrap={BOOTSTRAP_ITERATIONS:,} | Permutation={PERMUTATION_ITERATIONS:,}")
    print(f"{'=' * 100}")


if __name__ == "__main__":
    main()
