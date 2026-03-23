#!/usr/bin/env python3
"""
XRP Box-Range Scalping Strategy Optimizer
Fetches real Binance Futures data and finds optimal parameters.
"""

import json
import urllib.request
import numpy as np
from itertools import product
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

# ============================================================
# 1. FETCH REAL DATA
# ============================================================

def fetch_klines(symbol="XRPUSDT", interval="1h", limit=500):
    """Fetch klines from Binance Futures public API."""
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    # Parse: [open_time, open, high, low, close, volume, close_time, ...]
    candles = []
    for k in data:
        candles.append({
            "time": int(k[0]),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        })
    return candles


def compute_rsi(closes, period=14):
    """Compute RSI for a series of close prices."""
    rsi = np.full(len(closes), np.nan)
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    if avg_loss == 0:
        rsi[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100.0 - (100.0 / (1.0 + rs))
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i + 1] = 100.0 - (100.0 / (1.0 + rs))
    return rsi


# ============================================================
# 2. MARKET ANALYSIS
# ============================================================

def analyze_market(candles):
    """Compute box range, volatility, RSI distribution."""
    closes = np.array([c["close"] for c in candles])
    highs = np.array([c["high"] for c in candles])
    lows = np.array([c["low"] for c in candles])
    volumes = np.array([c["volume"] for c in candles])
    rsi = compute_rsi(closes)

    # Box range (using percentiles to exclude wicks)
    p5_low = np.percentile(lows, 5)
    p95_high = np.percentile(highs, 95)
    p25_low = np.percentile(lows, 25)
    p75_high = np.percentile(highs, 75)

    # Hourly returns
    returns = np.diff(closes) / closes[:-1]
    hourly_vol = np.std(returns)
    daily_vol = hourly_vol * np.sqrt(24)

    # ATR (14-period)
    tr = np.maximum(highs[1:] - lows[1:],
                    np.maximum(np.abs(highs[1:] - closes[:-1]),
                               np.abs(lows[1:] - closes[:-1])))
    atr14 = np.convolve(tr, np.ones(14)/14, mode='valid')[-1]

    valid_rsi = rsi[~np.isnan(rsi)]

    print("=" * 70)
    print("MARKET ANALYSIS — XRPUSDT Futures (1H candles)")
    print("=" * 70)
    print(f"Period: {len(candles)} candles (~{len(candles)//24} days)")
    print(f"Current price: ${closes[-1]:.4f}")
    print(f"Price range: ${np.min(lows):.4f} — ${np.max(highs):.4f}")
    print(f"Box range (P5-P95): ${p5_low:.4f} — ${p95_high:.4f}")
    print(f"Core range (P25-P75): ${p25_low:.4f} — ${p75_high:.4f}")
    print(f"Mean close: ${np.mean(closes):.4f}")
    print(f"Median close: ${np.median(closes):.4f}")
    print(f"Hourly volatility: {hourly_vol*100:.3f}%")
    print(f"Daily volatility (annualized from hourly): {daily_vol*100:.2f}%")
    print(f"ATR(14) 1H: ${atr14:.4f}")
    print(f"Avg volume (1H): {np.mean(volumes):,.0f} XRP")
    print()
    print("RSI Distribution:")
    print(f"  Mean: {np.mean(valid_rsi):.1f}")
    print(f"  RSI <= 30: {np.sum(valid_rsi <= 30)} candles ({np.sum(valid_rsi <= 30)/len(valid_rsi)*100:.1f}%)")
    print(f"  RSI <= 35: {np.sum(valid_rsi <= 35)} candles ({np.sum(valid_rsi <= 35)/len(valid_rsi)*100:.1f}%)")
    print(f"  RSI <= 40: {np.sum(valid_rsi <= 40)} candles ({np.sum(valid_rsi <= 40)/len(valid_rsi)*100:.1f}%)")
    print(f"  RSI 40-60: {np.sum((valid_rsi > 40) & (valid_rsi < 60))} candles")
    print(f"  RSI >= 60: {np.sum(valid_rsi >= 60)} candles")
    print()

    return closes, highs, lows, rsi, atr14


# ============================================================
# 3. BACKTESTER
# ============================================================

@dataclass
class TradeResult:
    entry_price: float
    exit_price: float
    pnl_pct: float  # without leverage
    is_win: bool
    exit_type: str  # 'tp', 'sl'


@dataclass
class BacktestResult:
    params: dict
    trades: List[TradeResult]
    n_trades: int = 0
    win_rate: float = 0.0
    total_pnl_pct: float = 0.0
    avg_return: float = 0.0
    std_return: float = 0.0
    sharpe: float = 0.0
    max_consec_losses: int = 0
    max_drawdown_pct: float = 0.0
    kelly: float = 0.0
    break_even_wr: float = 0.0
    daily_trades: float = 0.0
    daily_pnl_pct: float = 0.0


def backtest_single_tp(candles, closes, highs, lows, rsi_arr,
                       entry_price, tp_price, sl_offset, rsi_filter,
                       leverage=1.0):
    """
    Backtest box-range scalping with single TP.
    LONG only strategy: buy at entry, sell at TP or SL.
    Uses intra-candle high/low to check hits (conservative: SL checked first if both hit).
    """
    sl_price = entry_price - sl_offset
    trades = []
    in_trade = False
    n_candles = len(candles)
    total_hours = n_candles  # each candle = 1 hour

    for i in range(14, n_candles):  # skip first 14 for RSI warmup
        if not in_trade:
            # Entry condition: price touches entry level
            if lows[i] <= entry_price:
                # RSI filter
                if rsi_filter is not None and not np.isnan(rsi_arr[i]):
                    if rsi_arr[i] > rsi_filter:
                        continue
                in_trade = True
                actual_entry = entry_price
                continue

        if in_trade:
            # Check SL and TP within this candle
            sl_hit = lows[i] <= sl_price
            tp_hit = highs[i] >= tp_price

            if sl_hit and tp_hit:
                # Both hit in same candle — assume SL hit first (conservative)
                # Unless open is closer to TP
                if candles[i]["open"] >= tp_price:
                    # Opened above TP, TP hit first
                    pnl = (tp_price - actual_entry) / actual_entry
                    trades.append(TradeResult(actual_entry, tp_price, pnl, True, 'tp'))
                else:
                    pnl = (sl_price - actual_entry) / actual_entry
                    trades.append(TradeResult(actual_entry, sl_price, pnl, False, 'sl'))
                in_trade = False
            elif sl_hit:
                pnl = (sl_price - actual_entry) / actual_entry
                trades.append(TradeResult(actual_entry, sl_price, pnl, False, 'sl'))
                in_trade = False
            elif tp_hit:
                pnl = (tp_price - actual_entry) / actual_entry
                trades.append(TradeResult(actual_entry, tp_price, pnl, True, 'tp'))
                in_trade = False

    if not trades:
        return BacktestResult(params={}, trades=[], n_trades=0)

    returns = [t.pnl_pct for t in trades]
    wins = [t for t in trades if t.is_win]
    losses_list = [t for t in trades if not t.is_win]

    win_rate = len(wins) / len(trades) if trades else 0
    avg_win = np.mean([t.pnl_pct for t in wins]) if wins else 0
    avg_loss = abs(np.mean([t.pnl_pct for t in losses_list])) if losses_list else 0

    # Leveraged returns
    lev_returns = [r * leverage for r in returns]
    total_pnl = np.sum(lev_returns)

    # Compounded equity curve for drawdown
    equity = [1.0]
    for r in lev_returns:
        equity.append(equity[-1] * (1 + r))
    equity = np.array(equity)
    peak = np.maximum.accumulate(equity)
    drawdown = (peak - equity) / peak
    max_dd = np.max(drawdown) if len(drawdown) > 0 else 0

    # Max consecutive losses
    max_consec = 0
    current_consec = 0
    for t in trades:
        if not t.is_win:
            current_consec += 1
            max_consec = max(max_consec, current_consec)
        else:
            current_consec = 0

    avg_ret = np.mean(lev_returns)
    std_ret = np.std(lev_returns) if len(lev_returns) > 1 else 1e-9
    sharpe = avg_ret / std_ret if std_ret > 0 else 0

    # Kelly criterion: f* = (p * b - q) / b where b = avg_win/avg_loss
    if avg_loss > 0 and avg_win > 0:
        b = avg_win / avg_loss
        kelly = (win_rate * b - (1 - win_rate)) / b
    else:
        kelly = 0

    # Break-even win rate: WR * avg_win = (1-WR) * avg_loss
    # WR_be = avg_loss / (avg_win + avg_loss)
    if avg_win + avg_loss > 0:
        break_even = avg_loss / (avg_win + avg_loss)
    else:
        break_even = 0.5

    days = total_hours / 24
    daily_trades = len(trades) / days if days > 0 else 0
    daily_pnl = total_pnl / days if days > 0 else 0

    return BacktestResult(
        params={
            "entry": entry_price,
            "tp": tp_price,
            "sl_offset": sl_offset,
            "sl_price": sl_price,
            "rsi_filter": rsi_filter,
            "leverage": leverage,
        },
        trades=trades,
        n_trades=len(trades),
        win_rate=win_rate,
        total_pnl_pct=total_pnl * 100,
        avg_return=avg_ret * 100,
        std_return=std_ret * 100,
        sharpe=sharpe,
        max_consec_losses=max_consec,
        max_drawdown_pct=max_dd * 100,
        kelly=kelly,
        break_even_wr=break_even * 100,
        daily_trades=daily_trades,
        daily_pnl_pct=daily_pnl * 100,
    )


# ============================================================
# 4. MULTI-TP BACKTESTER
# ============================================================

def backtest_multi_tp(candles, closes, highs, lows, rsi_arr,
                      entry_price, tp_levels, tp_weights, sl_offset,
                      rsi_filter, leverage=1.0):
    """
    Multi-TP strategy. tp_levels = list of TP prices, tp_weights = allocation fractions.
    E.g., tp_levels=[1.38, 1.42], tp_weights=[0.5, 0.5]
    """
    sl_price = entry_price - sl_offset
    all_returns = []
    n_candles = len(candles)
    in_trade = False
    remaining_weight = 0
    active_tps = []

    for i in range(14, n_candles):
        if not in_trade:
            if lows[i] <= entry_price:
                if rsi_filter is not None and not np.isnan(rsi_arr[i]):
                    if rsi_arr[i] > rsi_filter:
                        continue
                in_trade = True
                actual_entry = entry_price
                remaining_weight = 1.0
                active_tps = list(zip(tp_levels, tp_weights))
                continue

        if in_trade:
            sl_hit = lows[i] <= sl_price
            trade_pnl = 0.0

            if sl_hit:
                # All remaining position stopped out
                pnl = (sl_price - actual_entry) / actual_entry
                trade_pnl += pnl * remaining_weight
                in_trade = False
                all_returns.append(trade_pnl)
                continue

            # Check TPs from lowest to highest
            new_active = []
            for tp, weight in active_tps:
                if highs[i] >= tp:
                    pnl = (tp - actual_entry) / actual_entry
                    trade_pnl += pnl * weight
                    remaining_weight -= weight
                else:
                    new_active.append((tp, weight))
            active_tps = new_active

            if trade_pnl > 0:
                all_returns.append(trade_pnl)

            if remaining_weight <= 0.001:
                in_trade = False

    if not all_returns:
        return None

    lev_returns = [r * leverage for r in all_returns]
    total_pnl = np.sum(lev_returns)

    equity = [1.0]
    for r in lev_returns:
        equity.append(equity[-1] * (1 + r))
    equity = np.array(equity)
    peak = np.maximum.accumulate(equity)
    drawdown = (peak - equity) / peak
    max_dd = np.max(drawdown)

    avg_ret = np.mean(lev_returns)
    std_ret = np.std(lev_returns) if len(lev_returns) > 1 else 1e-9
    sharpe = avg_ret / std_ret if std_ret > 0 else 0

    wins = sum(1 for r in lev_returns if r > 0)
    win_rate = wins / len(lev_returns)

    days = n_candles / 24
    daily_pnl = total_pnl / days

    return {
        "n_trades": len(all_returns),
        "win_rate": win_rate,
        "total_pnl_pct": total_pnl * 100,
        "sharpe": sharpe,
        "max_dd_pct": max_dd * 100,
        "daily_pnl_pct": daily_pnl * 100,
        "avg_return_pct": avg_ret * 100,
    }


# ============================================================
# 5. LEVERAGE OPTIMIZATION
# ============================================================

def find_optimal_leverage(candles, closes, highs, lows, rsi_arr,
                          entry, tp, sl_offset, rsi_filter):
    """Test leverages from 1x to 50x, find where EV turns negative."""
    results = []
    for lev in [1, 2, 3, 5, 7, 10, 12, 15, 20, 25, 30, 40, 50]:
        # Check if liquidation is possible
        # For LONG: liq price ≈ entry * (1 - 1/lev) (simplified, ignoring fees/maintenance)
        liq_price = entry * (1 - 0.9 / lev)  # 90% of margin = liquidation
        sl_price = entry - sl_offset

        # If SL is below liquidation, we get liquidated before SL
        liquidation_risk = sl_price < liq_price

        r = backtest_single_tp(candles, closes, highs, lows, rsi_arr,
                               entry, tp, sl_offset, rsi_filter, leverage=lev)
        results.append({
            "leverage": lev,
            "total_pnl": r.total_pnl_pct,
            "daily_pnl": r.daily_pnl_pct,
            "max_dd": r.max_drawdown_pct,
            "sharpe": r.sharpe,
            "liq_price": liq_price,
            "liq_risk": liquidation_risk,
            "n_trades": r.n_trades,
        })
    return results


# ============================================================
# MAIN
# ============================================================

def main():
    print("Fetching XRPUSDT 1H klines from Binance Futures...")
    candles = fetch_klines("XRPUSDT", "1h", 500)
    print(f"Fetched {len(candles)} candles.\n")

    closes = np.array([c["close"] for c in candles])
    highs = np.array([c["high"] for c in candles])
    lows = np.array([c["low"] for c in candles])
    rsi_arr = compute_rsi(closes)

    # --- Market Analysis ---
    analyze_market(candles)

    # ============================================================
    # PARAMETER GRID SEARCH
    # ============================================================
    print("=" * 70)
    print("PARAMETER OPTIMIZATION — Grid Search")
    print("=" * 70)

    entry_prices = np.arange(1.33, 1.365, 0.005)
    exit_prices = np.arange(1.38, 1.47, 0.01)
    sl_offsets = np.arange(0.01, 0.035, 0.005)
    rsi_filters = [None, 40, 35, 30]

    all_results = []
    tested = 0

    for entry, tp, sl_off, rsi_f in product(entry_prices, exit_prices, sl_offsets, rsi_filters):
        entry = round(entry, 4)
        tp = round(tp, 4)
        sl_off = round(sl_off, 4)

        # Skip invalid combos
        if tp <= entry:
            continue

        # Test at baseline leverage 12x
        r = backtest_single_tp(candles, closes, highs, lows, rsi_arr,
                               entry, tp, sl_off, rsi_f, leverage=12.0)
        if r.n_trades >= 3:  # minimum trades for statistical relevance
            all_results.append(r)
        tested += 1

    print(f"Tested {tested} combinations, {len(all_results)} with >= 3 trades.\n")

    # Rank by risk-adjusted return (Sharpe)
    all_results.sort(key=lambda x: x.sharpe, reverse=True)

    print("-" * 70)
    print("TOP 10 PARAMETER SETS (by Sharpe ratio, 12x leverage)")
    print("-" * 70)
    print(f"{'#':>2} | {'Entry':>7} | {'TP':>7} | {'SL':>7} | {'RSI':>4} | {'Trades':>6} | {'WR%':>5} | {'PnL%':>8} | {'Sharpe':>6} | {'MaxDD%':>6} | {'Kelly':>6} | {'BE_WR%':>6} | {'Daily%':>7}")
    print("-" * 140)

    for i, r in enumerate(all_results[:10]):
        p = r.params
        rsi_str = f"{p['rsi_filter']}" if p['rsi_filter'] else "None"
        print(f"{i+1:>2} | ${p['entry']:.3f} | ${p['tp']:.2f} | ${p['sl_price']:.3f} | {rsi_str:>4} | {r.n_trades:>6} | {r.win_rate*100:>5.1f} | {r.total_pnl_pct:>+8.1f} | {r.sharpe:>6.2f} | {r.max_drawdown_pct:>6.1f} | {r.kelly:>6.2f} | {r.break_even_wr:>6.1f} | {r.daily_pnl_pct:>+7.2f}")

    # Also show top 5 by total PnL
    pnl_sorted = sorted(all_results, key=lambda x: x.total_pnl_pct, reverse=True)
    print("\n" + "-" * 70)
    print("TOP 5 BY TOTAL P/L (12x leverage)")
    print("-" * 70)
    for i, r in enumerate(pnl_sorted[:5]):
        p = r.params
        rsi_str = f"{p['rsi_filter']}" if p['rsi_filter'] else "None"
        print(f"{i+1:>2} | ${p['entry']:.3f} | ${p['tp']:.2f} | ${p['sl_price']:.3f} | {rsi_str:>4} | {r.n_trades:>6} | {r.win_rate*100:>5.1f} | {r.total_pnl_pct:>+8.1f} | {r.sharpe:>6.2f} | {r.max_drawdown_pct:>6.1f} | {r.daily_pnl_pct:>+7.2f}")

    # ============================================================
    # MULTI-TP COMPARISON
    # ============================================================
    print("\n" + "=" * 70)
    print("MULTI-TP OPTIMIZATION")
    print("=" * 70)

    # Use the best Sharpe params as base
    best = all_results[0].params
    base_entry = best["entry"]
    base_sl = best["sl_offset"]
    base_rsi = best["rsi_filter"]
    base_tp = best["tp"]

    # Define TP levels relative to entry
    tp_spread = base_tp - base_entry
    tp1 = base_entry + tp_spread * 0.6   # conservative first TP
    tp2 = base_tp                         # original TP
    tp3 = base_entry + tp_spread * 1.5    # extended TP

    strategies = {
        "A: Single TP (100%)": ([base_tp], [1.0]),
        "B: 2-stage (50/50)": ([tp1, tp2], [0.5, 0.5]),
        "C: 3-stage (50/30/20)": ([tp1, tp2, tp3], [0.5, 0.3, 0.2]),
        "D: 2-stage (70/30 wide)": ([round(base_entry + tp_spread * 0.5, 4), round(base_entry + tp_spread * 1.3, 4)], [0.7, 0.3]),
    }

    print(f"\nBase: Entry=${base_entry:.3f}, SL_off=${base_sl:.3f}, RSI={base_rsi}, Leverage=12x")
    print(f"TP spread: ${tp_spread:.4f}")
    print()

    for name, (levels, weights) in strategies.items():
        levels_r = [round(l, 4) for l in levels]
        result = backtest_multi_tp(candles, closes, highs, lows, rsi_arr,
                                   base_entry, levels_r, weights, base_sl,
                                   base_rsi, leverage=12.0)
        if result:
            tp_str = " / ".join([f"${l:.4f}({int(w*100)}%)" for l, w in zip(levels_r, weights)])
            print(f"  {name}")
            print(f"    TPs: {tp_str}")
            print(f"    Trades: {result['n_trades']}, WR: {result['win_rate']*100:.1f}%, PnL: {result['total_pnl_pct']:+.1f}%")
            print(f"    Sharpe: {result['sharpe']:.2f}, MaxDD: {result['max_dd_pct']:.1f}%, Daily: {result['daily_pnl_pct']:+.2f}%")
            print()
        else:
            print(f"  {name}: No trades triggered.\n")

    # ============================================================
    # LEVERAGE OPTIMIZATION
    # ============================================================
    print("=" * 70)
    print("LEVERAGE OPTIMIZATION")
    print("=" * 70)
    print(f"Using best params: Entry=${base_entry:.3f}, TP=${base_tp:.2f}, SL_off=${base_sl:.3f}, RSI={base_rsi}")
    print()

    lev_results = find_optimal_leverage(candles, closes, highs, lows, rsi_arr,
                                        base_entry, base_tp, base_sl, base_rsi)

    print(f"{'Lev':>4} | {'TotalPnL%':>10} | {'DailyPnL%':>10} | {'MaxDD%':>8} | {'Sharpe':>7} | {'LiqPrice':>9} | {'LiqRisk':>8}")
    print("-" * 75)
    for lr in lev_results:
        print(f"{lr['leverage']:>3}x | {lr['total_pnl']:>+10.1f} | {lr['daily_pnl']:>+10.2f} | {lr['max_dd']:>8.1f} | {lr['sharpe']:>7.2f} | ${lr['liq_price']:>8.4f} | {'YES' if lr['liq_risk'] else 'no':>8}")

    # Find where EV turns negative
    ev_negative_lev = None
    for lr in lev_results:
        if lr['total_pnl'] < 0 and ev_negative_lev is None:
            ev_negative_lev = lr['leverage']

    # Kelly optimal leverage
    best_result = all_results[0]
    kelly_f = best_result.kelly
    # Kelly suggests fraction of bankroll; with base leverage already in params
    # Optimal leverage ≈ kelly * (1/base_risk_per_trade)
    base_risk = best_result.params["sl_offset"] / best_result.params["entry"]
    kelly_lev = kelly_f / base_risk if base_risk > 0 else 0

    print(f"\nKelly criterion fraction: {kelly_f:.3f}")
    print(f"Base risk per trade: {base_risk*100:.2f}%")
    print(f"Kelly optimal leverage: {kelly_lev:.1f}x")
    if ev_negative_lev:
        print(f"EV turns negative at: {ev_negative_lev}x leverage")
    else:
        print("EV remains positive across all tested leverages (but MaxDD grows!)")

    # Find leverage for 10% daily target
    print("\nFor 10% daily target on $1,353 margin:")
    for lr in lev_results:
        if lr['daily_pnl'] >= 10:
            print(f"  -> {lr['leverage']}x achieves {lr['daily_pnl']:+.2f}% daily (but MaxDD = {lr['max_dd']:.1f}%)")
            break
    else:
        print(f"  -> 10% daily NOT achievable with these params in this market regime")
        best_daily = max(lev_results, key=lambda x: x['daily_pnl'])
        print(f"  -> Best achievable: {best_daily['daily_pnl']:+.2f}% daily at {best_daily['leverage']}x (MaxDD = {best_daily['max_dd']:.1f}%)")

    # ============================================================
    # FINAL RECOMMENDATIONS
    # ============================================================
    print("\n" + "=" * 70)
    print("FINAL RECOMMENDATIONS")
    print("=" * 70)

    margin = 1353.0  # USD

    print(f"\nAccount margin: ${margin:.0f}")
    print()

    # Top 5 with dollar amounts
    print("TOP 5 PARAMETER SETS (Ranked by Risk-Adjusted Return)")
    print("-" * 100)
    for i, r in enumerate(all_results[:5]):
        p = r.params
        rsi_str = f"RSI<={p['rsi_filter']}" if p['rsi_filter'] else "No RSI filter"
        daily_dollar = r.daily_pnl_pct / 100 * margin
        max_dd_dollar = r.max_drawdown_pct / 100 * margin
        print(f"\n  #{i+1}: Entry=${p['entry']:.3f} → TP=${p['tp']:.2f} | SL=${p['sl_price']:.3f} | {rsi_str}")
        print(f"      Trades: {r.n_trades} | WR: {r.win_rate*100:.1f}% | Total PnL: {r.total_pnl_pct:+.1f}%")
        print(f"      Sharpe: {r.sharpe:.2f} | Kelly: {r.kelly:.2f} | Break-even WR: {r.break_even_wr:.1f}%")
        print(f"      Daily P/L: {r.daily_pnl_pct:+.2f}% (${daily_dollar:+.2f}/day)")
        print(f"      Max Drawdown: {r.max_drawdown_pct:.1f}% (${max_dd_dollar:.0f})")
        print(f"      Max Consecutive Losses: {r.max_consec_losses}")

    # Compare with baseline
    print("\n" + "-" * 70)
    print("BASELINE COMPARISON")
    print("-" * 70)
    baseline = backtest_single_tp(candles, closes, highs, lows, rsi_arr,
                                  1.34, 1.40, 0.015, None, leverage=12.0)
    if baseline.n_trades > 0:
        best_r = all_results[0]
        print(f"\n  Baseline (Entry=$1.340, TP=$1.40, SL=$1.325, 12x):")
        print(f"    Trades: {baseline.n_trades}, WR: {baseline.win_rate*100:.1f}%, PnL: {baseline.total_pnl_pct:+.1f}%")
        print(f"    Sharpe: {baseline.sharpe:.2f}, MaxDD: {baseline.max_drawdown_pct:.1f}%")
        print(f"    Daily: {baseline.daily_pnl_pct:+.2f}% (${baseline.daily_pnl_pct/100*margin:+.2f}/day)")
        print(f"\n  Optimized #{1} (Entry=${best_r.params['entry']:.3f}, TP=${best_r.params['tp']:.2f}, SL=${best_r.params['sl_price']:.3f}):")
        print(f"    Trades: {best_r.n_trades}, WR: {best_r.win_rate*100:.1f}%, PnL: {best_r.total_pnl_pct:+.1f}%")
        print(f"    Sharpe: {best_r.sharpe:.2f}, MaxDD: {best_r.max_drawdown_pct:.1f}%")
        print(f"    Daily: {best_r.daily_pnl_pct:+.2f}% (${best_r.daily_pnl_pct/100*margin:+.2f}/day)")
        if best_r.sharpe > baseline.sharpe:
            improvement = (best_r.sharpe - baseline.sharpe) / abs(baseline.sharpe) * 100 if baseline.sharpe != 0 else float('inf')
            print(f"\n  => Sharpe improvement: {improvement:+.0f}%")
    else:
        print("  Baseline: No trades triggered in this period.")
        print("  This suggests the current price range has shifted away from $1.34-$1.40.")
        print("  The optimizer above has found parameters matching the ACTUAL current range.")

    # Worst-case scenario
    print("\n" + "-" * 70)
    print("WORST-CASE SCENARIO ANALYSIS")
    print("-" * 70)
    best_p = all_results[0].params if all_results else {"sl_offset": 0.015, "entry": 1.34}
    risk_per_trade = best_p["sl_offset"] / best_p["entry"] * 12  # leveraged
    max_consec = all_results[0].max_consec_losses if all_results else 5
    print(f"  Risk per trade (12x): {risk_per_trade*100:.1f}%")
    print(f"  Max consecutive losses observed: {max_consec}")
    print(f"  Worst case ({max_consec} consec losses):")
    remaining = margin
    for j in range(max_consec):
        loss = remaining * risk_per_trade
        remaining -= loss
        print(f"    Loss #{j+1}: -${loss:.0f} → ${remaining:.0f} remaining")
    print(f"  Total worst-case drawdown: ${margin - remaining:.0f} ({(1 - remaining/margin)*100:.1f}%)")


if __name__ == "__main__":
    main()
