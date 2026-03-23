#!/usr/bin/env python3
"""Speed-of-decline exit strategy backtest.

Tests sophisticated exit enhancements on the BTC 2x trend-following strategy:
  - Group E: Rate of Change (ROC) exits
  - Group F: Volatility Regime Switch
  - Group G: Time-Decay Stop
  - Group H: Chandelier Exit
  - Group I: Parabolic SAR-inspired
  - Group J: Best combinations

All with: EMA(10/26) + RSI(21, 45/55), 2x leverage, 100% allocation,
$818 initial, crash filtered, funding 0.03%/day, fee 0.05%.
TP: +20% latch + EMA(7/14) 2-day cross.
"""

from __future__ import annotations
import sys
import os
import json
import time
import math
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from snowball_rider.indicators import compute_ema, compute_rsi


# ── Constants ──
CRASH_THRESHOLD = 0.30
INITIAL_CAPITAL = 818.0
LEVERAGE = 2
ALLOCATION = 1.0
SL_PCT = -70.0
TP_ACTIVATION = 20.0
TP_EMA_FAST = 7
TP_EMA_SLOW = 14
TP_CROSS_DAYS = 2
FEE_RATE = 0.0005
FUNDING_RATE_DAILY = 0.0003
EMA_FAST = 10
EMA_SLOW = 26
RSI_PERIOD = 21
RSI_LONG = 45.0
RSI_SHORT = 55.0


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


def compute_atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[float | None]:
    """Average True Range."""
    results: list[float | None] = []
    for i in range(len(closes)):
        if i < 1 or i + 1 < period:
            results.append(None)
            continue
        trs = []
        for j in range(i + 1 - period, i + 1):
            if j < 1:
                trs.append(highs[j] - lows[j])
            else:
                tr = max(highs[j] - lows[j], abs(highs[j] - closes[j-1]), abs(lows[j] - closes[j-1]))
                trs.append(tr)
        results.append(sum(trs) / period)
    return results


def compute_bollinger_width(closes: list[float], period: int = 20) -> list[float | None]:
    """Bollinger Band width = (upper - lower) / middle = 4 * stddev / SMA."""
    results: list[float | None] = []
    for i in range(len(closes)):
        if i + 1 < period:
            results.append(None)
            continue
        window = closes[i + 1 - period: i + 1]
        sma = sum(window) / period
        variance = sum((x - sma) ** 2 for x in window) / period
        std = math.sqrt(variance)
        width = (4 * std) / sma if sma > 0 else 0
        results.append(width)
    return results


def compute_bollinger_width_avg(bb_widths: list[float | None], period: int = 20) -> list[float | None]:
    """Moving average of Bollinger Band width."""
    results: list[float | None] = []
    for i in range(len(bb_widths)):
        if bb_widths[i] is None or i + 1 < period:
            results.append(None)
            continue
        # Check all values in window are not None
        window = bb_widths[i + 1 - period: i + 1]
        if any(v is None for v in window):
            results.append(None)
            continue
        results.append(sum(window) / period)
    return results


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
class ExitStrategy:
    """Configurable exit strategy on top of the base SL/TP."""
    name: str
    label: str

    # Base SL (can be overridden dynamically)
    base_sl: float = SL_PCT

    # Group E: ROC exit
    roc_exit: bool = False
    roc_period: int = 3
    roc_threshold: float = -15.0  # leveraged %
    roc_require_rsi: bool = False
    roc_rsi_threshold: float = 30.0

    # Group F: Volatility regime switch
    vol_regime: bool = False
    vol_atr_period: int = 14
    vol_threshold: float = 0.05  # ATR/close ratio
    vol_tight_sl: float = -40.0
    vol_normal_sl: float = -70.0

    # Group F3: Bollinger Band width
    bb_regime: bool = False
    bb_period: int = 20
    bb_width_mult: float = 2.0  # BB width > mult * avg(BB width)
    bb_tight_sl: float = -40.0

    # Group G: Time-decay stop
    time_decay: bool = False
    time_decay_mode: str = "linear_week"  # linear_week | linear_day | step
    time_decay_start_sl: float = -70.0
    time_decay_end_sl: float = -40.0
    time_decay_rate_per_week: float = 1.0
    time_decay_days: int = 60
    time_decay_step_day: int = 30
    time_decay_step_sl: float = -50.0

    # Group H: Chandelier exit
    chandelier: bool = False
    chandelier_mult: float = 3.0
    chandelier_atr_period: int = 14

    # Group I: Parabolic SAR-inspired
    parabolic: bool = False
    parabolic_af_start: float = 0.02
    parabolic_af_step: float = 0.02
    parabolic_af_max: float = 0.20

    # Trailing stop (from previous study)
    trailing: bool = False
    trailing_activation: float = 10.0  # leveraged % to activate
    trailing_distance: float = 10.0    # trail distance in leveraged %


def run_backtest(candles: list[dict], strategy: ExitStrategy, allocation: float = ALLOCATION) -> dict:
    closes = [c["close"] for c in candles]
    lows = [c["low"] for c in candles]
    highs = [c["high"] for c in candles]
    dates = [c["date"] for c in candles]
    n = len(closes)

    # Indicators
    ema_fast = compute_ema(closes, EMA_FAST)
    ema_slow = compute_ema(closes, EMA_SLOW)
    rsi = compute_rsi(closes, RSI_PERIOD)
    ema_tp_fast = compute_ema(closes, TP_EMA_FAST)
    ema_tp_slow = compute_ema(closes, TP_EMA_SLOW)

    # Extra indicators (computed as needed)
    atr = None
    bb_width = None
    bb_width_avg = None

    if strategy.vol_regime or strategy.chandelier:
        atr_period = strategy.vol_atr_period if strategy.vol_regime else strategy.chandelier_atr_period
        atr = compute_atr(highs, lows, closes, atr_period)

    if strategy.chandelier and strategy.vol_regime:
        # Need both ATR periods if different
        if strategy.vol_atr_period != strategy.chandelier_atr_period:
            atr_vol = compute_atr(highs, lows, closes, strategy.vol_atr_period)
            atr_chand = compute_atr(highs, lows, closes, strategy.chandelier_atr_period)
        else:
            atr_vol = atr
            atr_chand = atr
    elif strategy.vol_regime:
        atr_vol = atr
        atr_chand = None
    elif strategy.chandelier:
        atr_chand = atr
        atr_vol = None
    else:
        atr_vol = None
        atr_chand = None

    if strategy.bb_regime:
        bb_width = compute_bollinger_width(closes, strategy.bb_period)
        bb_width_avg = compute_bollinger_width_avg(bb_width, strategy.bb_period)

    wallet = INITIAL_CAPITAL
    peak_wallet = wallet
    max_drawdown = 0.0
    trades: list[Trade] = []
    in_position = False
    position_side: str = ""
    entry_price = 0.0
    entry_date = ""
    entry_idx = 0
    allocated = 0.0
    tp_activated = False
    tp_cross_count = 0
    highest_since_entry = 0.0
    lowest_since_entry = float('inf')
    peak_leveraged_pnl = 0.0
    trailing_activated = False

    # Parabolic SAR state
    sar_value = 0.0
    sar_af = 0.0
    sar_ep = 0.0  # extreme point

    # Exit counters
    sl_hits = 0
    special_exit_hits = 0

    warmup = max(EMA_SLOW, RSI_PERIOD, TP_EMA_SLOW) + 1

    for i in range(n):
        # Equity tracking
        if in_position:
            if position_side == "LONG":
                unrealized_pct = ((closes[i] / entry_price) - 1) * 100 * LEVERAGE
            else:
                unrealized_pct = ((entry_price / closes[i]) - 1) * 100 * LEVERAGE
            unallocated = wallet - allocated
            current_equity = unallocated + allocated * (1 + unrealized_pct / 100)
        else:
            current_equity = wallet

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
            days_held = i - entry_idx

            # Track highs/lows since entry
            if highs[i] > highest_since_entry:
                highest_since_entry = highs[i]
            if lows[i] < lowest_since_entry:
                lowest_since_entry = lows[i]

            if position_side == "LONG":
                intraday_worst = ((lows[i] / entry_price) - 1) * 100 * LEVERAGE
                intraday_best = ((highs[i] / entry_price) - 1) * 100 * LEVERAGE
                close_pnl = ((closes[i] / entry_price) - 1) * 100 * LEVERAGE
            else:
                intraday_worst = ((entry_price / highs[i]) - 1) * 100 * LEVERAGE
                intraday_best = ((entry_price / lows[i]) - 1) * 100 * LEVERAGE
                close_pnl = ((entry_price / closes[i]) - 1) * 100 * LEVERAGE

            if intraday_best > peak_leveraged_pnl:
                peak_leveraged_pnl = intraday_best

            # Liquidation check
            if intraday_worst <= -100:
                wallet = wallet - allocated
                trades.append(Trade(entry_date=entry_date, exit_date=dates[i],
                    side=position_side, entry_price=entry_price, exit_price=closes[i],
                    leveraged_pnl_pct=-100.0, wallet_before=wallet+allocated, wallet_after=wallet,
                    exit_reason="LIQUIDATED", days_held=days_held))
                sl_hits += 1
                in_position = False
                tp_activated = False
                tp_cross_count = 0
                continue

            # ── Determine dynamic SL level ──
            current_sl = strategy.base_sl

            # Group F: Volatility regime switch
            if strategy.vol_regime and atr_vol is not None and atr_vol[i] is not None:
                atr_ratio = atr_vol[i] / closes[i]
                if atr_ratio > strategy.vol_threshold:
                    current_sl = strategy.vol_tight_sl
                else:
                    current_sl = strategy.vol_normal_sl

            # Group F3: Bollinger Band regime
            if strategy.bb_regime and bb_width is not None and bb_width_avg is not None:
                if bb_width[i] is not None and bb_width_avg[i] is not None and bb_width_avg[i] > 0:
                    if bb_width[i] > strategy.bb_width_mult * bb_width_avg[i]:
                        current_sl = strategy.bb_tight_sl

            # Group G: Time-decay stop
            if strategy.time_decay:
                if strategy.time_decay_mode == "linear_week":
                    weeks = days_held / 7
                    current_sl = max(
                        strategy.time_decay_end_sl,
                        strategy.time_decay_start_sl + weeks * strategy.time_decay_rate_per_week
                    )
                elif strategy.time_decay_mode == "linear_day":
                    progress = min(days_held / strategy.time_decay_days, 1.0)
                    current_sl = strategy.time_decay_start_sl + progress * (strategy.time_decay_end_sl - strategy.time_decay_start_sl)
                elif strategy.time_decay_mode == "step":
                    if days_held >= strategy.time_decay_step_day:
                        current_sl = strategy.time_decay_step_sl

            # SL check (with dynamic SL)
            if intraday_worst <= current_sl:
                fee_cost = FEE_RATE * LEVERAGE * 2 * 100
                net_pnl = current_sl - fee_cost
                old_wallet = wallet
                wallet = (old_wallet - allocated) + allocated * (1 + net_pnl / 100)
                if wallet < 0:
                    wallet = 0
                trades.append(Trade(entry_date=entry_date, exit_date=dates[i],
                    side=position_side, entry_price=entry_price, exit_price=closes[i],
                    leveraged_pnl_pct=net_pnl, wallet_before=old_wallet, wallet_after=wallet,
                    exit_reason="STOP_LOSS", days_held=days_held))
                sl_hits += 1
                in_position = False
                tp_activated = False
                tp_cross_count = 0
                continue

            # ── Special exits (checked on close) ──
            special_exit = False
            special_reason = ""

            # Group E: ROC exit
            if strategy.roc_exit and i >= strategy.roc_period:
                roc_price = (closes[i] / closes[i - strategy.roc_period] - 1) * 100 * LEVERAGE
                roc_trigger = roc_price < strategy.roc_threshold
                if strategy.roc_require_rsi:
                    roc_trigger = roc_trigger and rsi[i] is not None and rsi[i] < strategy.roc_rsi_threshold
                if position_side == "LONG" and roc_trigger:
                    special_exit = True
                    special_reason = f"ROC_EXIT({strategy.roc_period}d)"
                elif position_side == "SHORT":
                    # For SHORT, ROC going up is bad
                    roc_price_inv = -roc_price
                    roc_trigger_short = roc_price_inv < strategy.roc_threshold
                    if strategy.roc_require_rsi:
                        roc_trigger_short = roc_trigger_short and rsi[i] is not None and rsi[i] > (100 - strategy.roc_rsi_threshold)
                    if roc_trigger_short:
                        special_exit = True
                        special_reason = f"ROC_EXIT({strategy.roc_period}d)"

            # Group H: Chandelier exit
            if not special_exit and strategy.chandelier and atr_chand is not None and atr_chand[i] is not None:
                if position_side == "LONG":
                    chandelier_stop = highest_since_entry - strategy.chandelier_mult * atr_chand[i]
                    if closes[i] < chandelier_stop:
                        special_exit = True
                        special_reason = "CHANDELIER"
                else:  # SHORT
                    chandelier_stop = lowest_since_entry + strategy.chandelier_mult * atr_chand[i]
                    if closes[i] > chandelier_stop:
                        special_exit = True
                        special_reason = "CHANDELIER"

            # Group I: Parabolic SAR-inspired
            if not special_exit and strategy.parabolic:
                if position_side == "LONG":
                    # Update SAR
                    if highs[i] > sar_ep:
                        sar_ep = highs[i]
                        sar_af = min(sar_af + strategy.parabolic_af_step, strategy.parabolic_af_max)
                    sar_value = sar_value + sar_af * (sar_ep - sar_value)
                    # SAR should not be above the low of current or previous bar
                    if i >= 1:
                        sar_value = min(sar_value, lows[i], lows[i-1])
                    if closes[i] < sar_value:
                        special_exit = True
                        special_reason = "PARABOLIC_SAR"
                else:  # SHORT
                    if lows[i] < sar_ep:
                        sar_ep = lows[i]
                        sar_af = min(sar_af + strategy.parabolic_af_step, strategy.parabolic_af_max)
                    sar_value = sar_value - sar_af * (sar_value - sar_ep)
                    # SAR should not be below the high of current or previous bar
                    if i >= 1:
                        sar_value = max(sar_value, highs[i], highs[i-1])
                    if closes[i] > sar_value:
                        special_exit = True
                        special_reason = "PARABOLIC_SAR"

            # Trailing stop
            if not special_exit and strategy.trailing:
                if peak_leveraged_pnl >= strategy.trailing_activation:
                    trailing_activated = True
                if trailing_activated:
                    trail_sl = peak_leveraged_pnl - strategy.trailing_distance
                    if close_pnl <= trail_sl:
                        special_exit = True
                        special_reason = "TRAILING_STOP"

            if special_exit:
                fee_cost = FEE_RATE * LEVERAGE * 2 * 100
                net_pnl = close_pnl - fee_cost
                old_wallet = wallet
                wallet = (old_wallet - allocated) + allocated * (1 + net_pnl / 100)
                if wallet < 0:
                    wallet = 0
                trades.append(Trade(entry_date=entry_date, exit_date=dates[i],
                    side=position_side, entry_price=entry_price, exit_price=closes[i],
                    leveraged_pnl_pct=net_pnl, wallet_before=old_wallet, wallet_after=wallet,
                    exit_reason=special_reason, days_held=days_held))
                special_exit_hits += 1
                in_position = False
                tp_activated = False
                tp_cross_count = 0
                continue

            # TP check
            if close_pnl >= TP_ACTIVATION:
                tp_activated = True

            if tp_activated:
                if position_side == "LONG" and ema_tp_fast[i] < ema_tp_slow[i]:
                    tp_cross_count += 1
                elif position_side == "SHORT" and ema_tp_fast[i] > ema_tp_slow[i]:
                    tp_cross_count += 1
                else:
                    tp_cross_count = 0

                if tp_cross_count >= TP_CROSS_DAYS:
                    fee_cost = FEE_RATE * LEVERAGE * 2 * 100
                    net_pnl = close_pnl - fee_cost
                    old_wallet = wallet
                    wallet = (old_wallet - allocated) + allocated * (1 + net_pnl / 100)
                    trades.append(Trade(entry_date=entry_date, exit_date=dates[i],
                        side=position_side, entry_price=entry_price, exit_price=closes[i],
                        leveraged_pnl_pct=net_pnl, wallet_before=old_wallet, wallet_after=wallet,
                        exit_reason="TP_EMA_CROSS", days_held=days_held))
                    in_position = False
                    tp_activated = False
                    tp_cross_count = 0
                    continue

            # Daily funding on allocated portion
            daily_funding = allocated * LEVERAGE * FUNDING_RATE_DAILY
            wallet -= daily_funding
            continue

        # ── ENTRY ──
        if wallet <= 10:
            continue

        if ema_fast[i] > ema_slow[i] and rsi[i] > RSI_LONG:
            allocated = wallet * allocation
            entry_price = closes[i]
            entry_date = dates[i]
            entry_idx = i
            position_side = "LONG"
            in_position = True
            tp_activated = False
            tp_cross_count = 0
            highest_since_entry = highs[i]
            lowest_since_entry = lows[i]
            peak_leveraged_pnl = 0.0
            trailing_activated = False
            # Parabolic SAR init
            if strategy.parabolic:
                sar_value = lows[i]  # Start SAR at the low
                sar_af = strategy.parabolic_af_start
                sar_ep = highs[i]
            continue

        if ema_fast[i] < ema_slow[i] and rsi[i] < RSI_SHORT:
            allocated = wallet * allocation
            entry_price = closes[i]
            entry_date = dates[i]
            entry_idx = i
            position_side = "SHORT"
            in_position = True
            tp_activated = False
            tp_cross_count = 0
            highest_since_entry = highs[i]
            lowest_since_entry = lows[i]
            peak_leveraged_pnl = 0.0
            trailing_activated = False
            # Parabolic SAR init for SHORT
            if strategy.parabolic:
                sar_value = highs[i]  # Start SAR at the high
                sar_af = strategy.parabolic_af_start
                sar_ep = lows[i]
            continue

    # Close open position at end
    if in_position:
        if position_side == "LONG":
            close_pnl = ((closes[-1] / entry_price) - 1) * 100 * LEVERAGE
        else:
            close_pnl = ((entry_price / closes[-1]) - 1) * 100 * LEVERAGE
        fee_cost = FEE_RATE * LEVERAGE * 2 * 100
        net_pnl = close_pnl - fee_cost
        old_wallet = wallet
        wallet = (old_wallet - allocated) + allocated * (1 + net_pnl / 100)
        trades.append(Trade(entry_date=entry_date, exit_date=dates[-1],
            side=position_side, entry_price=entry_price, exit_price=closes[-1],
            leveraged_pnl_pct=net_pnl, wallet_before=old_wallet, wallet_after=wallet,
            exit_reason="END_OF_DATA", days_held=len(closes)-1-entry_idx))

    # Stats
    total_return = (wallet / INITIAL_CAPITAL - 1) * 100
    start_date = datetime.strptime(dates[warmup], "%Y-%m-%d")
    end_date = datetime.strptime(dates[-1], "%Y-%m-%d")
    years = (end_date - start_date).days / 365.25
    cagr = ((wallet / INITIAL_CAPITAL) ** (1 / years) - 1) * 100 if years > 0 and wallet > 0 else 0
    winning = [t for t in trades if t.leveraged_pnl_pct > 0]
    losing = [t for t in trades if t.leveraged_pnl_pct <= 0]

    return {
        "strategy": strategy.label,
        "final_wallet": wallet,
        "total_return_pct": total_return,
        "cagr_pct": cagr,
        "years": years,
        "max_drawdown_pct": max_drawdown,
        "total_trades": len(trades),
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "win_rate": len(winning) / len(trades) * 100 if trades else 0,
        "sl_hits": sl_hits,
        "special_exit_hits": special_exit_hits,
        "trades": trades,
    }


def define_strategies() -> list[ExitStrategy]:
    """Define all test strategies."""
    strategies = []

    # ── Baseline: current strategy (SL -70%, TP +20% latch) ──
    strategies.append(ExitStrategy(name="baseline", label="Baseline (SL-70% TP+20%)", base_sl=-70.0))

    # ── 80% allocation baseline ──
    # (handled separately in main with allocation param)

    # ── Previous best: Trailing Stop 10% at +10% activation ──
    strategies.append(ExitStrategy(
        name="trailing_best", label="Trailing 10%@+10%",
        base_sl=-70.0, trailing=True, trailing_activation=10.0, trailing_distance=10.0
    ))

    # ── Group E: Rate of Change (ROC) Exit ──
    strategies.append(ExitStrategy(
        name="E1", label="E1: ROC 3d<-15%",
        base_sl=-70.0, roc_exit=True, roc_period=3, roc_threshold=-15.0
    ))
    strategies.append(ExitStrategy(
        name="E2", label="E2: ROC 5d<-20%",
        base_sl=-70.0, roc_exit=True, roc_period=5, roc_threshold=-20.0
    ))
    strategies.append(ExitStrategy(
        name="E3", label="E3: ROC 3d<-10%+RSI<30",
        base_sl=-70.0, roc_exit=True, roc_period=3, roc_threshold=-10.0,
        roc_require_rsi=True, roc_rsi_threshold=30.0
    ))

    # ── Group F: Volatility Regime Switch ──
    strategies.append(ExitStrategy(
        name="F1", label="F1: ATR/C>5% SL-40%",
        base_sl=-70.0, vol_regime=True, vol_threshold=0.05, vol_tight_sl=-40.0, vol_normal_sl=-70.0
    ))
    strategies.append(ExitStrategy(
        name="F2", label="F2: ATR/C>4% SL-50%",
        base_sl=-70.0, vol_regime=True, vol_threshold=0.04, vol_tight_sl=-50.0, vol_normal_sl=-70.0
    ))
    strategies.append(ExitStrategy(
        name="F3", label="F3: BB width>2x avg SL-40%",
        base_sl=-70.0, bb_regime=True, bb_width_mult=2.0, bb_tight_sl=-40.0
    ))

    # ── Group G: Time-Decay Stop ──
    strategies.append(ExitStrategy(
        name="G1", label="G1: SL tighten 1%/wk",
        base_sl=-70.0, time_decay=True, time_decay_mode="linear_week",
        time_decay_start_sl=-70.0, time_decay_end_sl=-50.0, time_decay_rate_per_week=1.0
    ))
    strategies.append(ExitStrategy(
        name="G2", label="G2: SL -70->-40 60d",
        base_sl=-70.0, time_decay=True, time_decay_mode="linear_day",
        time_decay_start_sl=-70.0, time_decay_end_sl=-40.0, time_decay_days=60
    ))
    strategies.append(ExitStrategy(
        name="G3", label="G3: SL -70->-50 @30d",
        base_sl=-70.0, time_decay=True, time_decay_mode="step",
        time_decay_start_sl=-70.0, time_decay_step_day=30, time_decay_step_sl=-50.0
    ))

    # ── Group H: Chandelier Exit ──
    strategies.append(ExitStrategy(
        name="H1", label="H1: Chand 3.0x ATR14",
        base_sl=-70.0, chandelier=True, chandelier_mult=3.0, chandelier_atr_period=14
    ))
    strategies.append(ExitStrategy(
        name="H2", label="H2: Chand 2.5x ATR14",
        base_sl=-70.0, chandelier=True, chandelier_mult=2.5, chandelier_atr_period=14
    ))
    strategies.append(ExitStrategy(
        name="H3", label="H3: Chand 3.5x ATR14",
        base_sl=-70.0, chandelier=True, chandelier_mult=3.5, chandelier_atr_period=14
    ))

    # ── Group I: Parabolic SAR-inspired ──
    strategies.append(ExitStrategy(
        name="I1", label="I1: SAR af0.01 max0.10",
        base_sl=-70.0, parabolic=True,
        parabolic_af_start=0.01, parabolic_af_step=0.01, parabolic_af_max=0.10
    ))
    strategies.append(ExitStrategy(
        name="I2", label="I2: SAR af0.02 max0.20",
        base_sl=-70.0, parabolic=True,
        parabolic_af_start=0.02, parabolic_af_step=0.02, parabolic_af_max=0.20
    ))
    strategies.append(ExitStrategy(
        name="I3", label="I3: SAR af0.01 max0.05",
        base_sl=-70.0, parabolic=True,
        parabolic_af_start=0.01, parabolic_af_step=0.01, parabolic_af_max=0.05
    ))

    return strategies


def main():
    print("=" * 90)
    print("  BTC Speed-of-Decline Exit Strategy Backtest")
    print("  EMA(10/26) RSI(21, 45/55) | 2x Leverage | $818 | Crash filtered | Funding 0.03%/day")
    print("  TP: +20% latch + EMA(7/14) 2-day cross | Base SL: -70%")
    print("=" * 90)

    candles = fetch_all_klines("BTCUSDT")
    filtered = filter_crashes(candles)
    print(f"  Data: {len(filtered)} candles (crash days removed)")
    print(f"  Period: {filtered[0]['date']} ~ {filtered[-1]['date']}")

    strategies = define_strategies()
    results = []

    # Run all strategies with 100% allocation
    for strat in strategies:
        r = run_backtest(filtered, strat, allocation=1.0)
        results.append(r)
        print(f"  {strat.label:<30} -> ${r['final_wallet']:>12,.2f}  CAGR {r['cagr_pct']:>+7.1f}%  MDD {r['max_drawdown_pct']:>5.1f}%  "
              f"Trades {r['total_trades']:>2}  WR {r['win_rate']:>4.0f}%  SL {r['sl_hits']:>2}  Special {r['special_exit_hits']:>2}")

    # 80% allocation baseline
    baseline_80 = ExitStrategy(name="baseline_80", label="Baseline 80% alloc", base_sl=-70.0)
    r80 = run_backtest(filtered, baseline_80, allocation=0.8)
    results.append(r80)
    print(f"  {baseline_80.label:<30} -> ${r80['final_wallet']:>12,.2f}  CAGR {r80['cagr_pct']:>+7.1f}%  MDD {r80['max_drawdown_pct']:>5.1f}%  "
          f"Trades {r80['total_trades']:>2}  WR {r80['win_rate']:>4.0f}%  SL {r80['sl_hits']:>2}  Special {r80['special_exit_hits']:>2}")

    # ── Find top 2 from Groups E-I for combination ──
    print(f"\n{'='*90}")
    print("  FINDING TOP 2 FROM E-I FOR COMBINATION (Group J)")
    print(f"{'='*90}")

    # Score: prioritize CAGR/MDD ratio (higher is better)
    ei_results = [(r, s) for r, s in zip(results, strategies) if s.name.startswith(('E', 'F', 'G', 'H', 'I'))]
    ei_scored = []
    for r, s in ei_results:
        ratio = r['cagr_pct'] / r['max_drawdown_pct'] if r['max_drawdown_pct'] > 0 else 0
        ei_scored.append((ratio, r, s))
        print(f"  {s.label:<30} CAGR/MDD = {ratio:.3f}  (CAGR {r['cagr_pct']:+.1f}%, MDD {r['max_drawdown_pct']:.1f}%)")
    ei_scored.sort(key=lambda x: x[0], reverse=True)

    top2 = ei_scored[:2]
    print(f"\n  Top 2 for combination:")
    for ratio, r, s in top2:
        print(f"    {s.label} (CAGR/MDD = {ratio:.3f})")

    # ── Group J: Combinations with trailing stop ──
    print(f"\n{'='*90}")
    print("  GROUP J: BEST COMBINATIONS WITH TRAILING STOP")
    print(f"{'='*90}")

    j_strategies = []
    for idx, (ratio, r, s) in enumerate(top2, 1):
        # Combine the strategy with trailing stop 10% @ +10%
        j_strat = ExitStrategy(
            name=f"J{idx}",
            label=f"J{idx}: {s.name}+Trail10%",
            base_sl=s.base_sl,
            roc_exit=s.roc_exit, roc_period=s.roc_period, roc_threshold=s.roc_threshold,
            roc_require_rsi=s.roc_require_rsi, roc_rsi_threshold=s.roc_rsi_threshold,
            vol_regime=s.vol_regime, vol_atr_period=s.vol_atr_period, vol_threshold=s.vol_threshold,
            vol_tight_sl=s.vol_tight_sl, vol_normal_sl=s.vol_normal_sl,
            bb_regime=s.bb_regime, bb_period=s.bb_period, bb_width_mult=s.bb_width_mult,
            bb_tight_sl=s.bb_tight_sl,
            time_decay=s.time_decay, time_decay_mode=s.time_decay_mode,
            time_decay_start_sl=s.time_decay_start_sl, time_decay_end_sl=s.time_decay_end_sl,
            time_decay_rate_per_week=s.time_decay_rate_per_week, time_decay_days=s.time_decay_days,
            time_decay_step_day=s.time_decay_step_day, time_decay_step_sl=s.time_decay_step_sl,
            chandelier=s.chandelier, chandelier_mult=s.chandelier_mult, chandelier_atr_period=s.chandelier_atr_period,
            parabolic=s.parabolic, parabolic_af_start=s.parabolic_af_start,
            parabolic_af_step=s.parabolic_af_step, parabolic_af_max=s.parabolic_af_max,
            trailing=True, trailing_activation=10.0, trailing_distance=10.0,
        )
        j_strategies.append(j_strat)

    for j_strat in j_strategies:
        rj = run_backtest(filtered, j_strat, allocation=1.0)
        results.append(rj)
        print(f"  {j_strat.label:<30} -> ${rj['final_wallet']:>12,.2f}  CAGR {rj['cagr_pct']:>+7.1f}%  MDD {rj['max_drawdown_pct']:>5.1f}%  "
              f"Trades {rj['total_trades']:>2}  WR {rj['win_rate']:>4.0f}%  SL {rj['sl_hits']:>2}  Special {rj['special_exit_hits']:>2}")

    # ── F3 ROBUSTNESS SWEEP ──
    print(f"\n{'='*90}")
    print("  F3 ROBUSTNESS SWEEP — BB Width Multiplier x Tight SL Level")
    print(f"{'='*90}")
    print(f"  {'Mult':>5} {'TightSL':>8} {'Final$':>12} {'CAGR%':>8} {'MaxDD%':>8} {'Trades':>7} {'WR%':>5} {'SL':>4} {'CAGR/MDD':>9}")
    print(f"  {'-'*5} {'-'*8} {'-'*12} {'-'*8} {'-'*8} {'-'*7} {'-'*5} {'-'*4} {'-'*9}")

    f3_sweep_results = []
    for mult in [1.5, 1.8, 2.0, 2.2, 2.5, 3.0]:
        for tight_sl in [-30, -35, -40, -45, -50, -55]:
            s = ExitStrategy(
                name=f"F3_m{mult}_sl{tight_sl}",
                label=f"F3 BB>{mult}x SL{tight_sl}%",
                base_sl=-70.0, bb_regime=True, bb_width_mult=mult, bb_tight_sl=float(tight_sl)
            )
            r = run_backtest(filtered, s, allocation=1.0)
            ratio = r['cagr_pct'] / r['max_drawdown_pct'] if r['max_drawdown_pct'] > 0 else 0
            f3_sweep_results.append((mult, tight_sl, r, ratio))
            print(f"  {mult:>5.1f} {tight_sl:>7}% ${r['final_wallet']:>11,.0f} {r['cagr_pct']:>+7.1f}% {r['max_drawdown_pct']:>7.1f}% "
                  f"{r['total_trades']:>7} {r['win_rate']:>4.0f}% {r['sl_hits']:>4} {ratio:>9.3f}")

    # Find best F3 variant
    best_f3 = max(f3_sweep_results, key=lambda x: x[3])
    print(f"\n  Best F3 variant: BB>{best_f3[0]}x SL{best_f3[1]}%  "
          f"(CAGR/MDD = {best_f3[3]:.3f}, CAGR {best_f3[2]['cagr_pct']:+.1f}%, MDD {best_f3[2]['max_drawdown_pct']:.1f}%)")
    results.append(best_f3[2])

    # ── F3 + 80% allocation ──
    print(f"\n{'='*90}")
    print("  F3 BEST + ALLOCATION SWEEP")
    print(f"{'='*90}")
    best_mult, best_tsl = best_f3[0], best_f3[1]
    print(f"  Using F3 BB>{best_mult}x SL{best_tsl}%")
    print(f"  {'Alloc':>6} {'Final$':>12} {'CAGR%':>8} {'MaxDD%':>8} {'CAGR/MDD':>9}")
    print(f"  {'-'*6} {'-'*12} {'-'*8} {'-'*8} {'-'*9}")
    for alloc in [0.6, 0.7, 0.8, 0.9, 1.0]:
        s = ExitStrategy(
            name=f"F3_best_a{int(alloc*100)}",
            label=f"F3 best @{int(alloc*100)}% alloc",
            base_sl=-70.0, bb_regime=True, bb_width_mult=best_mult, bb_tight_sl=float(best_tsl)
        )
        r = run_backtest(filtered, s, allocation=alloc)
        ratio = r['cagr_pct'] / r['max_drawdown_pct'] if r['max_drawdown_pct'] > 0 else 0
        print(f"  {alloc*100:>5.0f}% ${r['final_wallet']:>11,.0f} {r['cagr_pct']:>+7.1f}% {r['max_drawdown_pct']:>7.1f}% {ratio:>9.3f}")

    # ── FINAL COMPARISON TABLE ──
    print(f"\n\n{'='*130}")
    print(f"  FINAL COMPARISON TABLE — Speed-of-Decline Exit Strategies")
    print(f"  Initial: $818 | 2x Leverage | EMA(10/26) RSI(21,45/55) | Crash filtered | Funding 0.03%/day | Fee 0.05%")
    print(f"{'='*130}")
    print(f"  {'Strategy':<30} {'Final$':>12} {'CAGR%':>8} {'MaxDD%':>8} {'Trades':>7} {'WinR%':>6} {'SL':>4} {'Special':>8} {'CAGR/MDD':>9}")
    print(f"  {'-'*30} {'-'*12} {'-'*8} {'-'*8} {'-'*7} {'-'*6} {'-'*4} {'-'*8} {'-'*9}")

    for r in results:
        ratio = r['cagr_pct'] / r['max_drawdown_pct'] if r['max_drawdown_pct'] > 0 else 0
        marker = ""
        # Mark the best CAGR/MDD ratio
        print(f"  {r['strategy']:<30} ${r['final_wallet']:>11,.0f} {r['cagr_pct']:>+7.1f}% {r['max_drawdown_pct']:>7.1f}% "
              f"{r['total_trades']:>7} {r['win_rate']:>5.0f}% {r['sl_hits']:>4} {r['special_exit_hits']:>8} {ratio:>9.3f}")

    # Find best by different criteria
    print(f"\n  {'─'*90}")
    best_cagr = max(results, key=lambda r: r['cagr_pct'])
    best_mdd = min(results, key=lambda r: r['max_drawdown_pct'])
    best_ratio = max(results, key=lambda r: r['cagr_pct'] / r['max_drawdown_pct'] if r['max_drawdown_pct'] > 0 else 0)
    best_final = max(results, key=lambda r: r['final_wallet'])

    print(f"  Best CAGR:      {best_cagr['strategy']} ({best_cagr['cagr_pct']:+.1f}%)")
    print(f"  Best MaxDD:     {best_mdd['strategy']} ({best_mdd['max_drawdown_pct']:.1f}%)")
    print(f"  Best CAGR/MDD:  {best_ratio['strategy']} ({best_ratio['cagr_pct']/best_ratio['max_drawdown_pct']:.3f})")
    print(f"  Best Final$:    {best_final['strategy']} (${best_final['final_wallet']:,.0f})")

    # ── Trade detail for top 3 by CAGR/MDD ──
    print(f"\n\n{'='*130}")
    print(f"  TRADE DETAILS — Top 3 by CAGR/MDD Ratio")
    print(f"{'='*130}")

    scored_all = sorted(results, key=lambda r: r['cagr_pct'] / r['max_drawdown_pct'] if r['max_drawdown_pct'] > 0 else 0, reverse=True)
    for r in scored_all[:3]:
        ratio = r['cagr_pct'] / r['max_drawdown_pct'] if r['max_drawdown_pct'] > 0 else 0
        print(f"\n  {r['strategy']}  (CAGR/MDD = {ratio:.3f})")
        print(f"  {'#':>3} {'Entry':>10} {'Exit':>10} {'Side':>5} {'Entry$':>10} {'Exit$':>10} {'PnL%':>8} {'Days':>5} {'Wallet':>12} {'Reason'}")
        print(f"  {'---':>3} {'----------':>10} {'----------':>10} {'-----':>5} {'----------':>10} {'----------':>10} {'--------':>8} {'-----':>5} {'------------':>12} {'------'}")
        for idx, t in enumerate(r['trades'], 1):
            print(f"  {idx:3d} {t.entry_date:>10} {t.exit_date:>10} {t.side:>5} "
                  f"{t.entry_price:10.2f} {t.exit_price:10.2f} {t.leveraged_pnl_pct:+8.1f}% "
                  f"{t.days_held:5d} ${t.wallet_after:11,.2f} {t.exit_reason}")

    # ── Improvement vs baseline ──
    print(f"\n\n{'='*130}")
    print(f"  IMPROVEMENT VS BASELINE")
    print(f"{'='*130}")
    baseline = results[0]
    baseline_ratio = baseline['cagr_pct'] / baseline['max_drawdown_pct'] if baseline['max_drawdown_pct'] > 0 else 0
    print(f"  {'Strategy':<30} {'dCAGR':>8} {'dMDD':>8} {'dCAGR/MDD':>10} {'Verdict':<12}")
    print(f"  {'-'*30} {'-'*8} {'-'*8} {'-'*10} {'-'*12}")
    for r in results[1:]:
        dcagr = r['cagr_pct'] - baseline['cagr_pct']
        dmdd = r['max_drawdown_pct'] - baseline['max_drawdown_pct']
        ratio = r['cagr_pct'] / r['max_drawdown_pct'] if r['max_drawdown_pct'] > 0 else 0
        dratio = ratio - baseline_ratio
        if dmdd < -2 and dcagr > -5:
            verdict = "IMPROVED"
        elif dmdd < -5 and dcagr < -10:
            verdict = "MIXED"
        elif dcagr > 5 and dmdd <= 0:
            verdict = "STRONG"
        elif dcagr < -20:
            verdict = "WORSE"
        elif abs(dcagr) < 5 and abs(dmdd) < 3:
            verdict = "NEUTRAL"
        else:
            verdict = "REVIEW"
        print(f"  {r['strategy']:<30} {dcagr:>+7.1f}% {dmdd:>+7.1f}% {dratio:>+9.3f} {verdict:<12}")


if __name__ == "__main__":
    main()
