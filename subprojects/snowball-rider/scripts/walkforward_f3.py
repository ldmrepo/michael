#!/usr/bin/env python3
"""F3 Bollinger Band Regime Switch — Walk-Forward Validation.

Comprehensive validation of the F3 enhancement:
  When BB(20) width > 1.8x its 20-period average → tighten SL from -70% to -40%

Tests:
1. Walk-Forward (5 anchored windows) — F3 vs Baseline vs Current
2. Parameter Robustness — BB multiplier x tight SL grid per OOS window
3. Monte Carlo Bootstrap (1000 iterations) — shuffle trade returns
4. Half-Period Split — first half vs second half

Usage:
  cd snowball-rider && .venv/bin/python scripts/walkforward_f3.py
"""

from __future__ import annotations
import sys
import os
import json
import random
import math
import time
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
from itertools import product

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from snowball_rider.indicators import compute_ema, compute_rsi

# ── Constants ──────────────────────────────────────────────────────────────────
INITIAL_CAPITAL = 818.0
CRASH_THRESHOLD = 0.30
WARMUP_CANDLES = 200
RANDOM_SEED = 42

# ── Strategy parameters (consensus, fixed) ─────────────────────────────────────
EMA_FAST = 10
EMA_SLOW = 26
RSI_PERIOD = 21
RSI_LONG = 45
RSI_SHORT = 55
LEVERAGE = 2
TP_PCT = 20
TP_EMA_FAST = 7
TP_EMA_SLOW = 14
TP_CROSS_DAYS = 2
FEE_RATE = 0.0005
FUNDING_DAILY = 0.0003

# F3 defaults
BB_PERIOD = 20
BB_STD = 2.0
BB_MULT = 1.8
TIGHT_SL = -40.0
NORMAL_SL = -70.0


# ── Walk-Forward Windows ───────────────────────────────────────────────────────
WINDOWS = [
    {"name": "W1", "train_start": "2019-09-01", "train_end": "2021-03-31",
     "test_start": "2021-04-01", "test_end": "2022-03-31"},
    {"name": "W2", "train_start": "2019-09-01", "train_end": "2022-03-31",
     "test_start": "2022-04-01", "test_end": "2023-03-31"},
    {"name": "W3", "train_start": "2019-09-01", "train_end": "2023-03-31",
     "test_start": "2023-04-01", "test_end": "2024-03-31"},
    {"name": "W4", "train_start": "2019-09-01", "train_end": "2024-03-31",
     "test_start": "2024-04-01", "test_end": "2025-03-31"},
    {"name": "W5", "train_start": "2019-09-01", "train_end": "2025-03-31",
     "test_start": "2025-04-01", "test_end": "2026-03-23"},
]


# ── Data Loading ───────────────────────────────────────────────────────────────

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


def get_candles_with_warmup(all_candles: list[dict], target_start: str, target_end: str) -> list[dict]:
    """Get candles including warmup before target_start, up to target_end."""
    target_idx = None
    for i, c in enumerate(all_candles):
        if c["date"] >= target_start:
            target_idx = i
            break
    if target_idx is None:
        return []
    warmup_start = max(0, target_idx - WARMUP_CANDLES)
    end_idx = len(all_candles) - 1
    for i, c in enumerate(all_candles):
        if c["date"] > target_end:
            end_idx = i - 1
            break
    return all_candles[warmup_start:end_idx + 1]


# ── Bollinger Band Computation ─────────────────────────────────────────────────

def compute_bollinger_width(closes: list[float], period: int = 20, std_mult: float = 2.0) -> list[Optional[float]]:
    """Compute Bollinger Band width = (upper - lower) / middle for each bar.
    Returns None for bars with insufficient data.
    """
    results: list[Optional[float]] = []
    for i in range(len(closes)):
        if i + 1 < period:
            results.append(None)
            continue
        window = closes[i + 1 - period: i + 1]
        sma = sum(window) / period
        variance = sum((x - sma) ** 2 for x in window) / period
        std = math.sqrt(variance)
        upper = sma + std_mult * std
        lower = sma - std_mult * std
        width = (upper - lower) / sma if sma > 0 else 0.0
        results.append(width)
    return results


def compute_bb_width_avg(bb_widths: list[Optional[float]], period: int = 20) -> list[Optional[float]]:
    """Compute SMA of BB width values."""
    results: list[Optional[float]] = []
    for i in range(len(bb_widths)):
        if i + 1 < period:
            results.append(None)
            continue
        # Collect last `period` non-None values ending at i
        window = []
        for j in range(i + 1 - period, i + 1):
            if j >= 0 and bb_widths[j] is not None:
                window.append(bb_widths[j])
        if len(window) < period:
            results.append(None)
        else:
            results.append(sum(window) / len(window))
    return results


# ── Core Backtest with F3 Support ──────────────────────────────────────────────

@dataclass
class TradeRecord:
    entry_date: str
    exit_date: str
    side: str
    entry_price: float
    exit_price: float
    leveraged_pnl_pct: float
    wallet_before: float
    wallet_after: float
    exit_reason: str
    days_held: int
    sl_used: float  # the SL that was active for this trade


def run_backtest_f3(
    candles: list[dict],
    allocation: float = 1.0,
    sl_pct: float = -70.0,
    bb_mult: float = 0.0,      # 0 = disabled (no BB regime switch)
    tight_sl: float = -40.0,
    bb_period: int = BB_PERIOD,
    bb_std: float = BB_STD,
    bb_avg_period: int = 20,
    initial_capital: float = INITIAL_CAPITAL,
) -> dict:
    """Run backtest with optional F3 Bollinger Band regime switch.

    If bb_mult > 0: when BB width > bb_mult * avg(BB width, bb_avg_period),
    use tight_sl instead of sl_pct.
    """
    closes = [c["close"] for c in candles]
    lows = [c["low"] for c in candles]
    highs = [c["high"] for c in candles]
    dates = [c["date"] for c in candles]
    n = len(closes)

    # Indicators
    ema_f = compute_ema(closes, EMA_FAST)
    ema_s = compute_ema(closes, EMA_SLOW)
    rsi = compute_rsi(closes, RSI_PERIOD)
    ema_tf = compute_ema(closes, TP_EMA_FAST)
    ema_ts = compute_ema(closes, TP_EMA_SLOW)

    # Bollinger Band indicators (only if F3 enabled)
    use_f3 = bb_mult > 0
    bb_widths: list[Optional[float]] = []
    bb_width_avgs: list[Optional[float]] = []
    if use_f3:
        bb_widths = compute_bollinger_width(closes, bb_period, bb_std)
        bb_width_avgs = compute_bb_width_avg(bb_widths, bb_avg_period)

    wallet = initial_capital
    peak_wallet = wallet
    max_drawdown = 0.0
    trades: list[TradeRecord] = []
    sl_hits = 0

    in_position = False
    position_side = ""
    entry_price = 0.0
    entry_idx = 0
    allocated = 0.0
    tp_activated = False
    tp_cross_count = 0
    current_sl = sl_pct  # SL active for current trade
    liquidated = False

    warmup = max(EMA_SLOW, RSI_PERIOD, TP_EMA_SLOW) + 1

    for i in range(n):
        # Equity tracking
        if in_position:
            if position_side == "LONG":
                unrealized = ((closes[i] / entry_price) - 1) * 100 * LEVERAGE
            else:
                unrealized = ((entry_price / closes[i]) - 1) * 100 * LEVERAGE
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

        # Determine current SL regime for F3
        if use_f3 and i < len(bb_widths) and i < len(bb_width_avgs):
            bw = bb_widths[i]
            bwa = bb_width_avgs[i]
            if bw is not None and bwa is not None and bwa > 0:
                active_sl = tight_sl if (bw > bb_mult * bwa) else sl_pct
            else:
                active_sl = sl_pct
        else:
            active_sl = sl_pct

        # ── EXIT ──
        if in_position:
            # Update SL for current position based on regime
            current_sl = active_sl

            if position_side == "LONG":
                intraday_worst = ((lows[i] / entry_price) - 1) * 100 * LEVERAGE
                close_pnl = ((closes[i] / entry_price) - 1) * 100 * LEVERAGE
            else:
                intraday_worst = ((entry_price / highs[i]) - 1) * 100 * LEVERAGE
                close_pnl = ((entry_price / closes[i]) - 1) * 100 * LEVERAGE

            # Liquidation check
            if intraday_worst <= -100:
                old_wallet = wallet
                wallet = wallet - allocated
                if wallet < 0:
                    wallet = 0
                trades.append(TradeRecord(
                    entry_date=dates[entry_idx], exit_date=dates[i],
                    side=position_side, entry_price=entry_price, exit_price=closes[i],
                    leveraged_pnl_pct=-100.0, wallet_before=old_wallet, wallet_after=wallet,
                    exit_reason="LIQUIDATED", days_held=i - entry_idx, sl_used=current_sl))
                in_position = False
                tp_activated = False
                tp_cross_count = 0
                if wallet <= 10:
                    liquidated = True
                    break
                continue

            # SL check (uses current regime SL)
            if intraday_worst <= current_sl:
                fee_cost = FEE_RATE * LEVERAGE * 2 * 100
                net_pnl = current_sl - fee_cost
                old_wallet = wallet
                wallet = (old_wallet - allocated) + allocated * (1 + net_pnl / 100)
                if wallet < 0:
                    wallet = 0
                sl_hits += 1
                trades.append(TradeRecord(
                    entry_date=dates[entry_idx], exit_date=dates[i],
                    side=position_side, entry_price=entry_price, exit_price=closes[i],
                    leveraged_pnl_pct=net_pnl, wallet_before=old_wallet, wallet_after=wallet,
                    exit_reason="STOP_LOSS", days_held=i - entry_idx, sl_used=current_sl))
                in_position = False
                tp_activated = False
                tp_cross_count = 0
                if wallet <= 10:
                    liquidated = True
                    break
                continue

            # TP check
            if close_pnl >= TP_PCT:
                tp_activated = True

            if tp_activated:
                if position_side == "LONG" and ema_tf[i] < ema_ts[i]:
                    tp_cross_count += 1
                elif position_side == "SHORT" and ema_tf[i] > ema_ts[i]:
                    tp_cross_count += 1
                else:
                    tp_cross_count = 0

                if tp_cross_count >= TP_CROSS_DAYS:
                    fee_cost = FEE_RATE * LEVERAGE * 2 * 100
                    net_pnl = close_pnl - fee_cost
                    old_wallet = wallet
                    wallet = (old_wallet - allocated) + allocated * (1 + net_pnl / 100)
                    trades.append(TradeRecord(
                        entry_date=dates[entry_idx], exit_date=dates[i],
                        side=position_side, entry_price=entry_price, exit_price=closes[i],
                        leveraged_pnl_pct=net_pnl, wallet_before=old_wallet, wallet_after=wallet,
                        exit_reason="TP_EMA_CROSS", days_held=i - entry_idx, sl_used=current_sl))
                    in_position = False
                    tp_activated = False
                    tp_cross_count = 0
                    continue

            # Daily funding
            daily_funding = allocated * LEVERAGE * FUNDING_DAILY
            wallet -= daily_funding
            continue

        # ── ENTRY ──
        if wallet <= 10:
            break

        if ema_f[i] > ema_s[i] and rsi[i] > RSI_LONG:
            allocated = wallet * allocation
            entry_price = closes[i]
            entry_idx = i
            position_side = "LONG"
            in_position = True
            tp_activated = False
            tp_cross_count = 0
            current_sl = active_sl
            continue

        if ema_f[i] < ema_s[i] and rsi[i] < RSI_SHORT:
            allocated = wallet * allocation
            entry_price = closes[i]
            entry_idx = i
            position_side = "SHORT"
            in_position = True
            tp_activated = False
            tp_cross_count = 0
            current_sl = active_sl
            continue

    # Close open position at end
    if in_position and wallet > 0:
        if position_side == "LONG":
            close_pnl = ((closes[-1] / entry_price) - 1) * 100 * LEVERAGE
        else:
            close_pnl = ((entry_price / closes[-1]) - 1) * 100 * LEVERAGE
        fee_cost = FEE_RATE * LEVERAGE * 2 * 100
        net_pnl = close_pnl - fee_cost
        old_wallet = wallet
        wallet = (old_wallet - allocated) + allocated * (1 + net_pnl / 100)
        trades.append(TradeRecord(
            entry_date=dates[entry_idx], exit_date=dates[-1],
            side=position_side, entry_price=entry_price, exit_price=closes[-1],
            leveraged_pnl_pct=net_pnl, wallet_before=old_wallet, wallet_after=wallet,
            exit_reason="END_OF_DATA", days_held=len(closes) - 1 - entry_idx, sl_used=current_sl))

    # Stats
    total_return = (wallet / initial_capital - 1) * 100
    start_date = datetime.strptime(dates[warmup], "%Y-%m-%d")
    end_date = datetime.strptime(dates[-1], "%Y-%m-%d")
    years = (end_date - start_date).days / 365.25
    cagr = ((wallet / initial_capital) ** (1 / years) - 1) * 100 if years > 0 and wallet > 0 else 0
    win_count = sum(1 for t in trades if t.leveraged_pnl_pct > 0)
    loss_count = sum(1 for t in trades if t.leveraged_pnl_pct <= 0)
    win_rate = win_count / len(trades) * 100 if trades else 0

    return {
        "final_wallet": wallet,
        "total_return_pct": total_return,
        "cagr_pct": cagr,
        "max_drawdown_pct": max_drawdown,
        "trade_count": len(trades),
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": win_rate,
        "sl_hits": sl_hits,
        "liquidated": liquidated,
        "years": years,
        "trades": trades,
    }


# ── Section 1: Walk-Forward Test ───────────────────────────────────────────────

def run_walkforward(all_candles: list[dict]):
    """Run 5-window walk-forward comparing F3 vs Baseline vs Current."""
    print()
    print("=" * 100)
    print("  SECTION 1: WALK-FORWARD TEST (5 Anchored Windows)")
    print("  Strategies: (a) Baseline 100% SL-70  (b) F3 100% BB>1.8x→SL-40  (c) Current 80% SL-70")
    print("=" * 100)

    results_table = []

    for w in WINDOWS:
        print(f"\n{'─' * 100}")
        print(f"  {w['name']}: Train {w['train_start']}→{w['train_end']} | Test {w['test_start']}→{w['test_end']}")
        print(f"{'─' * 100}")

        # Get OOS candles (with warmup for indicators)
        oos_candles = get_candles_with_warmup(all_candles, w['test_start'], w['test_end'])
        print(f"  OOS candles: {len(oos_candles)} (incl. warmup)")

        # (a) Baseline: 100% allocation, SL -70%, no BB
        r_baseline = run_backtest_f3(oos_candles, allocation=1.0, sl_pct=NORMAL_SL,
                                      bb_mult=0, initial_capital=INITIAL_CAPITAL)

        # (b) F3: 100% allocation, BB>1.8x → SL -40%, else SL -70%
        r_f3 = run_backtest_f3(oos_candles, allocation=1.0, sl_pct=NORMAL_SL,
                                bb_mult=BB_MULT, tight_sl=TIGHT_SL,
                                initial_capital=INITIAL_CAPITAL)

        # (c) Current: 80% allocation, SL -70%, no BB
        # Note: the user said "current" uses 80% allocation — using 0.6 as per CLAUDE.md consensus (60%)
        # Actually user explicitly says "80% allocation" for current
        r_current = run_backtest_f3(oos_candles, allocation=0.8, sl_pct=NORMAL_SL,
                                     bb_mult=0, initial_capital=INITIAL_CAPITAL)

        row = {
            "window": w["name"],
            "baseline": r_baseline,
            "f3": r_f3,
            "current": r_current,
        }
        results_table.append(row)

        print(f"\n  {'Strategy':<25} {'Final$':>10} {'Return%':>10} {'MaxDD%':>8} {'Trades':>7} {'SL Hits':>8} {'WR%':>6}")
        print(f"  {'─'*25} {'─'*10} {'─'*10} {'─'*8} {'─'*7} {'─'*8} {'─'*6}")
        for label, r in [("(a) Baseline 100% SL-70", r_baseline),
                          ("(b) F3 100% BB→SL-40", r_f3),
                          ("(c) Current 80% SL-70", r_current)]:
            print(f"  {label:<25} ${r['final_wallet']:>9,.2f} {r['total_return_pct']:>+9.1f}% {r['max_drawdown_pct']:>7.1f}% {r['trade_count']:>7} {r['sl_hits']:>8} {r['win_rate']:>5.0f}%")

        # Check if F3 beats baseline
        f3_better = r_f3['total_return_pct'] > r_baseline['total_return_pct']
        f3_positive = r_f3['total_return_pct'] > 0
        print(f"\n  F3 positive: {'YES' if f3_positive else 'NO'} | F3 > Baseline: {'YES' if f3_better else 'NO'}")

    # Summary table
    print(f"\n\n{'=' * 100}")
    print(f"  WALK-FORWARD SUMMARY")
    print(f"{'=' * 100}")
    print(f"\n  {'Window':<8} {'Baseline Return':>16} {'F3 Return':>16} {'Current Return':>16} {'F3>Base':>9} {'F3>0':>6}")
    print(f"  {'─'*8} {'─'*16} {'─'*16} {'─'*16} {'─'*9} {'─'*6}")

    f3_positive_count = 0
    f3_beats_baseline_count = 0
    for row in results_table:
        b_ret = row["baseline"]["total_return_pct"]
        f_ret = row["f3"]["total_return_pct"]
        c_ret = row["current"]["total_return_pct"]
        f3_pos = f_ret > 0
        f3_beat = f_ret > b_ret
        if f3_pos:
            f3_positive_count += 1
        if f3_beat:
            f3_beats_baseline_count += 1
        beat_str = "YES" if f3_beat else "NO"
        pos_str = "YES" if f3_pos else "NO"
        print(f"  {row['window']:<8} {b_ret:>+15.1f}% {f_ret:>+15.1f}% {c_ret:>+15.1f}% {beat_str:>9} {pos_str:>6}")

    print(f"\n  F3 positive OOS: {f3_positive_count}/5")
    print(f"  F3 beats baseline: {f3_beats_baseline_count}/5")

    return results_table, f3_positive_count, f3_beats_baseline_count


# ── Section 2: Parameter Robustness ────────────────────────────────────────────

def run_param_robustness(all_candles: list[dict]):
    """Test BB multiplier x tight SL grid on each OOS window."""
    print(f"\n\n{'=' * 100}")
    print(f"  SECTION 2: PARAMETER ROBUSTNESS IN OOS")
    print(f"  BB multipliers: [1.5, 1.8, 2.0, 2.2] x tight SL: [-35, -40, -45]")
    print(f"{'=' * 100}")

    bb_mults = [1.5, 1.8, 2.0, 2.2]
    tight_sls = [-35, -40, -45]

    for w in WINDOWS:
        print(f"\n{'─' * 100}")
        print(f"  {w['name']}: OOS {w['test_start']}→{w['test_end']}")
        print(f"{'─' * 100}")

        oos_candles = get_candles_with_warmup(all_candles, w['test_start'], w['test_end'])

        # Also run baseline for comparison
        r_base = run_backtest_f3(oos_candles, allocation=1.0, sl_pct=NORMAL_SL, bb_mult=0)

        print(f"\n  Baseline (no BB): return={r_base['total_return_pct']:+.1f}%, MaxDD={r_base['max_drawdown_pct']:.1f}%")
        print(f"\n  {'BB Mult':>8} {'Tight SL':>9} {'Return%':>10} {'MaxDD%':>8} {'Trades':>7} {'SL Hits':>8} {'vs Base':>8}")
        print(f"  {'─'*8} {'─'*9} {'─'*10} {'─'*8} {'─'*7} {'─'*8} {'─'*8}")

        best_return = -999
        best_params = ""
        for bm, tsl in product(bb_mults, tight_sls):
            r = run_backtest_f3(oos_candles, allocation=1.0, sl_pct=NORMAL_SL,
                                 bb_mult=bm, tight_sl=tsl)
            diff = r['total_return_pct'] - r_base['total_return_pct']
            marker = "  <<<" if bm == BB_MULT and tsl == TIGHT_SL else ""
            print(f"  {bm:>8.1f} {tsl:>9.0f}% {r['total_return_pct']:>+9.1f}% {r['max_drawdown_pct']:>7.1f}% {r['trade_count']:>7} {r['sl_hits']:>8} {diff:>+7.1f}%{marker}")
            if r['total_return_pct'] > best_return:
                best_return = r['total_return_pct']
                best_params = f"BB={bm}, SL={tsl}%"

        print(f"\n  Best in {w['name']}: {best_params} → {best_return:+.1f}%")


# ── Section 3: Monte Carlo Bootstrap ──────────────────────────────────────────

def run_monte_carlo(all_candles: list[dict]):
    """Shuffle trade returns from F3 full-period, compute distribution."""
    print(f"\n\n{'=' * 100}")
    print(f"  SECTION 3: MONTE CARLO BOOTSTRAP (1000 iterations)")
    print(f"{'=' * 100}")

    # Run F3 on full data
    r_f3_full = run_backtest_f3(all_candles, allocation=1.0, sl_pct=NORMAL_SL,
                                 bb_mult=BB_MULT, tight_sl=TIGHT_SL)
    r_base_full = run_backtest_f3(all_candles, allocation=1.0, sl_pct=NORMAL_SL, bb_mult=0)

    f3_trades = r_f3_full["trades"]
    if not f3_trades:
        print("  No trades from F3 full-period. Cannot run Monte Carlo.")
        return 0.0

    # Extract trade multipliers (wallet_after / wallet_before)
    multipliers = []
    for t in f3_trades:
        if t.wallet_before > 0:
            multipliers.append(t.wallet_after / t.wallet_before)
        else:
            multipliers.append(0.0)

    print(f"\n  F3 Full-Period: ${r_f3_full['final_wallet']:,.2f} ({r_f3_full['total_return_pct']:+.1f}%)")
    print(f"  Baseline Full-Period: ${r_base_full['final_wallet']:,.2f} ({r_base_full['total_return_pct']:+.1f}%)")
    print(f"  Trade count: {len(multipliers)}")
    print(f"  Trade multipliers: min={min(multipliers):.4f}, max={max(multipliers):.4f}, "
          f"median={sorted(multipliers)[len(multipliers)//2]:.4f}")

    random.seed(RANDOM_SEED)
    n_iter = 1000
    mc_finals = []
    n_trades = len(multipliers)

    for _ in range(n_iter):
        # Bootstrap: sample WITH REPLACEMENT from trade multipliers
        sampled = [random.choice(multipliers) for _ in range(n_trades)]
        wallet = INITIAL_CAPITAL
        for m in sampled:
            wallet *= m
        mc_finals.append(wallet)

    mc_finals.sort()
    mc_returns = [(w / INITIAL_CAPITAL - 1) * 100 for w in mc_finals]

    positive_count = sum(1 for r in mc_returns if r > 0)
    beats_baseline_count = sum(1 for w in mc_finals if w > r_base_full['final_wallet'])
    p_positive = positive_count / n_iter * 100
    p_beats_baseline = beats_baseline_count / n_iter * 100

    p5 = mc_returns[int(n_iter * 0.05)]
    p25 = mc_returns[int(n_iter * 0.25)]
    p50 = mc_returns[int(n_iter * 0.50)]
    p75 = mc_returns[int(n_iter * 0.75)]
    p95 = mc_returns[int(n_iter * 0.95)]

    print(f"\n  Monte Carlo Results ({n_iter} iterations):")
    print(f"  {'─' * 50}")
    print(f"  P(return > 0):          {p_positive:.1f}%")
    print(f"  P(return > baseline):   {p_beats_baseline:.1f}%")
    print(f"  5th percentile return:  {p5:+.1f}%")
    print(f"  25th percentile return: {p25:+.1f}%")
    print(f"  Median return:          {p50:+.1f}%")
    print(f"  75th percentile return: {p75:+.1f}%")
    print(f"  95th percentile return: {p95:+.1f}%")
    print(f"  {'─' * 50}")

    # Also show wallet values
    print(f"\n  Wallet Distribution:")
    print(f"  5th pct:  ${mc_finals[int(n_iter*0.05)]:,.2f}")
    print(f"  Median:   ${mc_finals[int(n_iter*0.50)]:,.2f}")
    print(f"  95th pct: ${mc_finals[int(n_iter*0.95)]:,.2f}")

    return p_positive


# ── Section 4: Half-Period Split ───────────────────────────────────────────────

def run_half_period(all_candles: list[dict]):
    """Compare F3 vs baseline vs current on first half and second half."""
    print(f"\n\n{'=' * 100}")
    print(f"  SECTION 4: HALF-PERIOD SPLIT")
    print(f"  First Half:  2019-09 → 2022-09")
    print(f"  Second Half: 2022-09 → 2026-03")
    print(f"{'=' * 100}")

    halves = [
        ("First Half  (2019.09-2022.09)", "2019-09-01", "2022-09-30"),
        ("Second Half (2022.09-2026.03)", "2022-09-01", "2026-03-23"),
    ]

    half_results = []

    for label, start, end in halves:
        candles = get_candles_with_warmup(all_candles, start, end)
        print(f"\n{'─' * 100}")
        print(f"  {label}: {len(candles)} candles (incl. warmup)")
        print(f"{'─' * 100}")

        r_baseline = run_backtest_f3(candles, allocation=1.0, sl_pct=NORMAL_SL, bb_mult=0)
        r_f3 = run_backtest_f3(candles, allocation=1.0, sl_pct=NORMAL_SL,
                                bb_mult=BB_MULT, tight_sl=TIGHT_SL)
        r_current = run_backtest_f3(candles, allocation=0.8, sl_pct=NORMAL_SL, bb_mult=0)

        print(f"\n  {'Strategy':<25} {'Final$':>10} {'Return%':>10} {'MaxDD%':>8} {'Trades':>7} {'SL Hits':>8}")
        print(f"  {'─'*25} {'─'*10} {'─'*10} {'─'*8} {'─'*7} {'─'*8}")
        for slabel, r in [("Baseline 100% SL-70", r_baseline),
                           ("F3 100% BB→SL-40", r_f3),
                           ("Current 80% SL-70", r_current)]:
            print(f"  {slabel:<25} ${r['final_wallet']:>9,.2f} {r['total_return_pct']:>+9.1f}% {r['max_drawdown_pct']:>7.1f}% {r['trade_count']:>7} {r['sl_hits']:>8}")

        half_results.append({
            "label": label,
            "baseline": r_baseline,
            "f3": r_f3,
            "current": r_current,
        })

    # Check if both halves are positive for F3
    both_positive = all(hr["f3"]["total_return_pct"] > 0 for hr in half_results)
    print(f"\n  F3 positive in first half:  {'YES' if half_results[0]['f3']['total_return_pct'] > 0 else 'NO'} ({half_results[0]['f3']['total_return_pct']:+.1f}%)")
    print(f"  F3 positive in second half: {'YES' if half_results[1]['f3']['total_return_pct'] > 0 else 'NO'} ({half_results[1]['f3']['total_return_pct']:+.1f}%)")
    print(f"  Both halves positive: {'YES' if both_positive else 'NO'}")

    return both_positive, half_results


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    print("=" * 100)
    print("  F3 BOLLINGER BAND REGIME SWITCH — WALK-FORWARD VALIDATION")
    print(f"  Strategy: EMA {EMA_FAST}/{EMA_SLOW}, RSI {RSI_PERIOD} (>{RSI_LONG}/<{RSI_SHORT}), {LEVERAGE}x leverage")
    print(f"  F3: BB({BB_PERIOD}) width > {BB_MULT}x avg → SL {TIGHT_SL}% (else {NORMAL_SL}%)")
    print(f"  TP: +{TP_PCT}% latch → EMA({TP_EMA_FAST}) vs EMA({TP_EMA_SLOW}) cross {TP_CROSS_DAYS} days")
    print(f"  Initial Capital: ${INITIAL_CAPITAL}")
    print("=" * 100)

    # Load data
    all_candles = load_candles()
    all_candles = filter_crashes(all_candles)
    print(f"  Data: {len(all_candles)} candles ({all_candles[0]['date']} to {all_candles[-1]['date']})")

    # Full-period sanity check
    print(f"\n  Full-Period Sanity Check:")
    r_full_base = run_backtest_f3(all_candles, allocation=1.0, sl_pct=NORMAL_SL, bb_mult=0)
    r_full_f3 = run_backtest_f3(all_candles, allocation=1.0, sl_pct=NORMAL_SL,
                                 bb_mult=BB_MULT, tight_sl=TIGHT_SL)
    r_full_curr = run_backtest_f3(all_candles, allocation=0.8, sl_pct=NORMAL_SL, bb_mult=0)
    print(f"  Baseline: ${r_full_base['final_wallet']:,.2f} ({r_full_base['total_return_pct']:+.1f}%, MaxDD {r_full_base['max_drawdown_pct']:.1f}%)")
    print(f"  F3:       ${r_full_f3['final_wallet']:,.2f} ({r_full_f3['total_return_pct']:+.1f}%, MaxDD {r_full_f3['max_drawdown_pct']:.1f}%)")
    print(f"  Current:  ${r_full_curr['final_wallet']:,.2f} ({r_full_curr['total_return_pct']:+.1f}%, MaxDD {r_full_curr['max_drawdown_pct']:.1f}%)")

    # Section 1: Walk-Forward
    wf_results, f3_pos_count, f3_beats_count = run_walkforward(all_candles)

    # Section 2: Parameter Robustness
    run_param_robustness(all_candles)

    # Section 3: Monte Carlo
    p_positive = run_monte_carlo(all_candles)

    # Section 4: Half-Period Split
    both_halves_positive, half_results = run_half_period(all_candles)

    # ── FINAL VERDICT ──────────────────────────────────────────────────────────
    elapsed = time.time() - t0
    print(f"\n\n{'=' * 100}")
    print(f"  FINAL VERDICT")
    print(f"{'=' * 100}")

    criteria = [
        (f"F3 positive in >= 3/5 OOS windows", f3_pos_count >= 3, f"{f3_pos_count}/5"),
        (f"F3 beats baseline in >= 3/5 OOS windows", f3_beats_count >= 3, f"{f3_beats_count}/5"),
        (f"Monte Carlo P(return > 0) > 90%", p_positive > 90, f"{p_positive:.1f}%"),
        (f"Both halves show positive returns", both_halves_positive,
         f"H1={half_results[0]['f3']['total_return_pct']:+.1f}%, H2={half_results[1]['f3']['total_return_pct']:+.1f}%"),
    ]

    all_pass = True
    print(f"\n  {'#':>3} {'Criterion':<50} {'Result':>8} {'Detail':<30}")
    print(f"  {'─'*3} {'─'*50} {'─'*8} {'─'*30}")
    for i, (desc, passed, detail) in enumerate(criteria, 1):
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  {i:3d} {desc:<50} {status:>8} {detail}")

    print(f"\n  {'=' * 60}")
    if all_pass:
        print(f"  OVERALL VERDICT: PASS — F3 is validated for live deployment")
    else:
        print(f"  OVERALL VERDICT: FAIL — F3 does NOT pass all criteria")
        fails = [desc for desc, passed, _ in criteria if not passed]
        for f in fails:
            print(f"    - FAILED: {f}")
    print(f"  {'=' * 60}")

    print(f"\n  Total runtime: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print("=" * 100)


if __name__ == "__main__":
    main()
