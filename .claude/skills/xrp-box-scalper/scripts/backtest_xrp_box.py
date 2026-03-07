#!/usr/bin/env python3
"""
XRP Box Scalper Backtest Engine
===============================
Fetches real Binance Futures data and backtests a box-range scalping strategy.

Strategy: Buy XRP when price dips into the box bottom with RSI confirmation,
          take profit at box top, stop-loss below box bottom.

Two backtests:
  1. High-resolution: 5m candles (~5 days)
  2. Extended: 1h candles (~21 days)

Three parameter sets compared:
  A (baseline):     Entry=$1.34,  TP=$1.40,  SL=$1.325, Lev=12x
  B (optimized):    Entry=$1.335, TP=$1.42,  SL=$1.305, Lev=12x
  C (conservative): Entry=$1.335, TP=$1.42,  SL=$1.305, Lev=7x
"""

import json
import math
import sys
import urllib.request
from datetime import datetime, timezone
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_klines(symbol: str, interval: str, limit: int) -> list[dict]:
    """Fetch kline/candlestick data from Binance Futures public API."""
    url = (
        f"https://fapi.binance.com/fapi/v1/klines"
        f"?symbol={symbol}&interval={interval}&limit={limit}"
    )
    print(f"  Fetching {symbol} {interval} x{limit} ... ", end="", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = json.loads(resp.read().decode())
    candles = []
    for k in raw:
        candles.append({
            "open_time": k[0],
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "close_time": k[6],
        })
    t0 = datetime.fromtimestamp(candles[0]["open_time"] / 1000, tz=timezone.utc)
    t1 = datetime.fromtimestamp(candles[-1]["open_time"] / 1000, tz=timezone.utc)
    print(f"OK  ({len(candles)} candles, {t0:%Y-%m-%d %H:%M} -> {t1:%Y-%m-%d %H:%M} UTC)")
    return candles


# ---------------------------------------------------------------------------
# RSI calculation (Wilder's smoothing)
# ---------------------------------------------------------------------------

def compute_rsi(closes: list[float], period: int = 14) -> list[float | None]:
    """Return RSI series aligned with closes. First `period` values are None."""
    rsi = [None] * len(closes)
    if len(closes) < period + 1:
        return rsi

    gains = []
    losses = []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    if avg_loss == 0:
        rsi[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100.0 - 100.0 / (1.0 + rs)

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i + 1] = 100.0 - 100.0 / (1.0 + rs)

    return rsi


# ---------------------------------------------------------------------------
# Trade record
# ---------------------------------------------------------------------------

class Trade(NamedTuple):
    entry_time: int
    exit_time: int
    entry_price: float
    exit_price: float
    side: str  # "LONG"
    pnl_pct: float  # % return on margin
    pnl_usd: float
    fee_usd: float
    funding_usd: float
    holding_candles: int
    result: str  # "TP" or "SL"


# ---------------------------------------------------------------------------
# Backtest engine
# ---------------------------------------------------------------------------

class ParamSet(NamedTuple):
    name: str
    entry_price: float
    tp_price: float
    sl_price: float
    leverage: int
    initial_margin: float
    rsi_threshold: float
    rsi_period: int
    fee_rate: float
    funding_rate_8h: float


def run_backtest(candles: list[dict], params: ParamSet, interval_minutes: int) -> list[Trade]:
    """Run backtest on candle data with given parameters. Returns list of trades."""
    closes = [c["close"] for c in candles]
    rsi_series = compute_rsi(closes, params.rsi_period)

    trades: list[Trade] = []
    in_position = False
    entry_candle_idx = 0
    cooldown_until = 0
    consecutive_sl = 0
    daily_pnl: dict[str, float] = {}
    balance = params.initial_margin

    # Cooldown settings based on interval
    if interval_minutes <= 5:
        cooldown_3sl = 24   # 2 hours
        cooldown_5sl = 144  # 12 hours
    else:
        cooldown_3sl = 2    # 2 hours
        cooldown_5sl = 12   # 12 hours

    position_size = params.initial_margin * params.leverage

    for i, candle in enumerate(candles):
        if i < params.rsi_period + 1:
            continue

        candle_day = datetime.fromtimestamp(
            candle["open_time"] / 1000, tz=timezone.utc
        ).strftime("%Y-%m-%d")

        # Check daily loss limit
        day_pnl = daily_pnl.get(candle_day, 0.0)
        day_loss_pct = day_pnl / params.initial_margin * 100
        if day_loss_pct <= -3.0:
            continue

        if in_position:
            # Check exit conditions
            hit_tp = candle["high"] >= params.tp_price
            hit_sl = candle["low"] <= params.sl_price

            if hit_sl and hit_tp:
                # Conservative: assume SL hit first
                exit_price = params.sl_price
                result = "SL"
            elif hit_sl:
                exit_price = params.sl_price
                result = "SL"
            elif hit_tp:
                exit_price = params.tp_price
                result = "TP"
            else:
                continue

            holding_candles = i - entry_candle_idx
            holding_hours = holding_candles * interval_minutes / 60.0

            # P/L calculation
            price_change_pct = (exit_price - params.entry_price) / params.entry_price
            pnl_pct = price_change_pct * params.leverage * 100  # % on margin

            # Fees: entry + exit
            fee_usd = position_size * params.fee_rate * 2

            # Funding: proportional to holding time
            funding_periods = holding_hours / 8.0
            funding_usd = position_size * params.funding_rate_8h * funding_periods

            pnl_usd = position_size * price_change_pct - fee_usd - funding_usd

            trade = Trade(
                entry_time=candles[entry_candle_idx]["open_time"],
                exit_time=candle["open_time"],
                entry_price=params.entry_price,
                exit_price=exit_price,
                side="LONG",
                pnl_pct=pnl_pct,
                pnl_usd=pnl_usd,
                fee_usd=fee_usd,
                funding_usd=funding_usd,
                holding_candles=holding_candles,
                result=result,
            )
            trades.append(trade)
            balance += pnl_usd
            daily_pnl[candle_day] = daily_pnl.get(candle_day, 0.0) + pnl_usd

            in_position = False

            # Consecutive SL tracking
            if result == "SL":
                consecutive_sl += 1
                if consecutive_sl >= 5:
                    cooldown_until = i + cooldown_5sl
                    consecutive_sl = 0
                elif consecutive_sl >= 3:
                    cooldown_until = i + cooldown_3sl
            else:
                consecutive_sl = 0

        else:
            # Check entry conditions
            if i < cooldown_until:
                continue

            rsi_val = rsi_series[i]
            if rsi_val is None:
                continue

            cond_price = candle["close"] <= params.entry_price
            cond_rsi = rsi_val <= params.rsi_threshold
            cond_bullish = candle["close"] > candle["open"]

            if cond_price and cond_rsi and cond_bullish:
                in_position = True
                entry_candle_idx = i

    return trades


# ---------------------------------------------------------------------------
# Metrics calculation
# ---------------------------------------------------------------------------

def calc_metrics(trades: list[Trade], params: ParamSet, candles: list[dict],
                 interval_minutes: int) -> dict:
    """Calculate comprehensive backtest metrics."""
    if not trades:
        return {"total_trades": 0, "note": "No trades executed"}

    wins = [t for t in trades if t.result == "TP"]
    losses = [t for t in trades if t.result == "SL"]

    total_pnl = sum(t.pnl_usd for t in trades)
    total_fees = sum(t.fee_usd for t in trades)
    total_funding = sum(t.funding_usd for t in trades)
    gross_profit = sum(t.pnl_usd for t in wins) if wins else 0
    gross_loss = abs(sum(t.pnl_usd for t in losses)) if losses else 0

    win_rate = len(wins) / len(trades) * 100
    avg_win = (sum(t.pnl_usd for t in wins) / len(wins)) if wins else 0
    avg_loss = (sum(t.pnl_usd for t in losses) / len(losses)) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Consecutive wins/losses
    max_consec_wins = max_consec_losses = 0
    cur_consec = 0
    cur_type = None
    for t in trades:
        if t.result == cur_type:
            cur_consec += 1
        else:
            cur_type = t.result
            cur_consec = 1
        if cur_type == "TP":
            max_consec_wins = max(max_consec_wins, cur_consec)
        else:
            max_consec_losses = max(max_consec_losses, cur_consec)

    # Max drawdown
    equity = params.initial_margin
    peak = equity
    max_dd = 0
    max_dd_pct = 0
    for t in trades:
        equity += t.pnl_usd
        peak = max(peak, equity)
        dd = peak - equity
        dd_pct = dd / peak * 100 if peak > 0 else 0
        max_dd = max(max_dd, dd)
        max_dd_pct = max(max_dd_pct, dd_pct)

    # Average holding time
    avg_holding_candles = sum(t.holding_candles for t in trades) / len(trades)
    avg_holding_hours = avg_holding_candles * interval_minutes / 60.0

    # Daily P/L for Sharpe
    daily_pnl: dict[str, float] = {}
    for t in trades:
        day = datetime.fromtimestamp(t.exit_time / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        daily_pnl[day] = daily_pnl.get(day, 0.0) + t.pnl_usd

    daily_returns = list(daily_pnl.values())
    if len(daily_returns) > 1:
        mean_ret = sum(daily_returns) / len(daily_returns)
        var_ret = sum((r - mean_ret) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
        std_ret = math.sqrt(var_ret) if var_ret > 0 else 0.001
        sharpe = (mean_ret / std_ret) * math.sqrt(365) if std_ret > 0 else 0
    else:
        sharpe = 0
        mean_ret = daily_returns[0] if daily_returns else 0

    # Time span
    t0 = candles[0]["open_time"]
    t1 = candles[-1]["open_time"]
    days_span = max((t1 - t0) / (1000 * 86400), 1)

    # Annualized return
    total_return_pct = total_pnl / params.initial_margin * 100
    annual_return_pct = total_return_pct * (365 / days_span)

    # Calmar ratio
    calmar = annual_return_pct / max_dd_pct if max_dd_pct > 0 else float("inf")

    # R:R ratio achieved
    rr_achieved = abs(avg_win / avg_loss) if avg_loss != 0 else float("inf")

    # Kelly criterion
    p = len(wins) / len(trades)
    if avg_loss != 0 and avg_win != 0:
        b = abs(avg_win / avg_loss)
        kelly = p - (1 - p) / b if b > 0 else 0
    else:
        kelly = 0

    # Break-even win rate
    tp_dist = params.tp_price - params.entry_price
    sl_dist = params.entry_price - params.sl_price
    rr_ratio = tp_dist / sl_dist if sl_dist > 0 else 1
    break_even_wr = 1 / (1 + rr_ratio) * 100

    return {
        "total_trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "total_pnl_usd": total_pnl,
        "total_pnl_pct": total_return_pct,
        "total_fees": total_fees,
        "total_funding": total_funding,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "max_consec_wins": max_consec_wins,
        "max_consec_losses": max_consec_losses,
        "max_drawdown_usd": max_dd,
        "max_drawdown_pct": max_dd_pct,
        "sharpe_ratio": sharpe,
        "calmar_ratio": calmar,
        "avg_holding_hours": avg_holding_hours,
        "rr_achieved": rr_achieved,
        "kelly_criterion": kelly,
        "break_even_wr": break_even_wr,
        "rr_ratio_theoretical": rr_ratio,
        "annual_return_pct": annual_return_pct,
        "days_span": days_span,
        "daily_pnl": daily_pnl,
        "final_balance": params.initial_margin + total_pnl,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(metrics: dict, params: ParamSet, interval_label: str):
    """Print formatted backtest report."""
    print(f"\n{'='*72}")
    print(f"  {params.name} | {interval_label}")
    print(f"  Entry=${params.entry_price} | TP=${params.tp_price} | SL=${params.sl_price} | "
          f"Lev={params.leverage}x | Margin=${params.initial_margin}")
    print(f"{'='*72}")

    if metrics["total_trades"] == 0:
        print("  ** No trades executed in this period **")
        print(f"  Note: {metrics.get('note', 'N/A')}")
        return

    m = metrics
    print(f"  Period: {m['days_span']:.1f} days")
    print(f"")
    print(f"  {'Metric':<30} {'Value':>15}")
    print(f"  {'-'*30} {'-'*15}")
    print(f"  {'Total Trades':<30} {m['total_trades']:>15}")
    print(f"  {'Wins / Losses':<30} {str(m['wins'])+' / '+str(m['losses']):>15}")
    print(f"  {'Win Rate':<30} {m['win_rate']:>14.1f}%")
    print(f"  {'Total P/L ($)':<30} {m['total_pnl_usd']:>14.2f}$")
    print(f"  {'Total P/L (%)':<30} {m['total_pnl_pct']:>14.2f}%")
    print(f"  {'Total Fees':<30} {m['total_fees']:>14.2f}$")
    print(f"  {'Total Funding':<30} {m['total_funding']:>14.2f}$")
    print(f"  {'Avg Win':<30} {m['avg_win']:>14.2f}$")
    print(f"  {'Avg Loss':<30} {m['avg_loss']:>14.2f}$")
    pf = f"{m['profit_factor']:.2f}" if m['profit_factor'] != float('inf') else "INF"
    print(f"  {'Profit Factor':<30} {pf:>15}")
    print(f"  {'Max Consec Wins':<30} {m['max_consec_wins']:>15}")
    print(f"  {'Max Consec Losses':<30} {m['max_consec_losses']:>15}")
    print(f"  {'Max Drawdown ($)':<30} {m['max_drawdown_usd']:>14.2f}$")
    print(f"  {'Max Drawdown (%)':<30} {m['max_drawdown_pct']:>14.2f}%")
    print(f"  {'Sharpe Ratio (ann.)':<30} {m['sharpe_ratio']:>14.2f}")
    cal = f"{m['calmar_ratio']:.2f}" if m['calmar_ratio'] != float('inf') else "INF"
    print(f"  {'Calmar Ratio':<30} {cal:>15}")
    print(f"  {'Avg Holding Time':<30} {m['avg_holding_hours']:>13.1f}h")
    rr = f"{m['rr_achieved']:.2f}" if m['rr_achieved'] != float('inf') else "INF"
    print(f"  {'R:R Achieved':<30} {rr:>15}")
    print(f"  {'R:R Theoretical':<30} {m['rr_ratio_theoretical']:>14.2f}")
    print(f"  {'Kelly Criterion':<30} {m['kelly_criterion']:>14.3f}")
    print(f"  {'Break-Even Win Rate':<30} {m['break_even_wr']:>14.1f}%")
    print(f"  {'Annual Return (%)':<30} {m['annual_return_pct']:>14.1f}%")
    print(f"  {'Final Balance':<30} {m['final_balance']:>14.2f}$")

    # Daily breakdown
    if m["daily_pnl"]:
        print(f"\n  --- Daily P/L Breakdown ---")
        print(f"  {'Date':<14} {'P/L ($)':>12} {'Cumulative':>12}")
        cum = 0
        for day in sorted(m["daily_pnl"].keys()):
            pnl = m["daily_pnl"][day]
            cum += pnl
            marker = "  " if pnl >= 0 else " *"
            print(f"  {day:<14} {pnl:>11.2f}$ {cum:>11.2f}${marker}")


def print_comparison(all_results: list[tuple[ParamSet, dict]], interval_label: str):
    """Print side-by-side comparison table."""
    print(f"\n{'='*72}")
    print(f"  COMPARISON TABLE | {interval_label}")
    print(f"{'='*72}")

    header = f"  {'Metric':<25}"
    for params, _ in all_results:
        header += f" {params.name:>14}"
    print(header)
    print(f"  {'-'*25}" + f" {'-'*14}" * len(all_results))

    rows = [
        ("Total Trades", "total_trades", "d"),
        ("Win Rate (%)", "win_rate", ".1f"),
        ("Total P/L ($)", "total_pnl_usd", ".2f"),
        ("Total P/L (%)", "total_pnl_pct", ".2f"),
        ("Profit Factor", "profit_factor", ".2f"),
        ("Max DD (%)", "max_drawdown_pct", ".2f"),
        ("Sharpe Ratio", "sharpe_ratio", ".2f"),
        ("Avg Holding (h)", "avg_holding_hours", ".1f"),
        ("Kelly", "kelly_criterion", ".3f"),
        ("Final Balance", "final_balance", ".2f"),
    ]

    for label, key, fmt in rows:
        row = f"  {label:<25}"
        for _, m in all_results:
            if m["total_trades"] == 0:
                row += f" {'N/A':>14}"
            else:
                val = m[key]
                if val == float("inf"):
                    row += f" {'INF':>14}"
                else:
                    row += f" {val:>{14}{fmt}}"
        print(row)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 72)
    print("  XRP Box Scalper Backtest Engine")
    print("  Real Binance Futures Data")
    print("=" * 72)

    # Define parameter sets
    param_sets = [
        ParamSet("Set A (base)", 1.34, 1.40, 1.325, 12, 1353, 35, 14, 0.0002, 0.0001),
        ParamSet("Set B (opt)", 1.335, 1.42, 1.305, 12, 1353, 35, 14, 0.0002, 0.0001),
        ParamSet("Set C (cons)", 1.335, 1.42, 1.305, 7, 1353, 35, 14, 0.0002, 0.0001),
    ]

    # Fetch data
    print("\n[1/2] Fetching 5-minute candles...")
    candles_5m = fetch_klines("XRPUSDT", "5m", 1500)
    print("[2/2] Fetching 1-hour candles...")
    candles_1h = fetch_klines("XRPUSDT", "1h", 500)

    # Price range summary
    print(f"\n--- Data Summary ---")
    for label, candles in [("5m", candles_5m), ("1h", candles_1h)]:
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        closes = [c["close"] for c in candles]
        t0 = datetime.fromtimestamp(candles[0]["open_time"] / 1000, tz=timezone.utc)
        t1 = datetime.fromtimestamp(candles[-1]["open_time"] / 1000, tz=timezone.utc)
        print(f"  {label}: {t0:%Y-%m-%d} to {t1:%Y-%m-%d} | "
              f"H={max(highs):.4f} L={min(lows):.4f} Last={closes[-1]:.4f}")

    # Check if entry zone was even touched
    entry_zone = 1.335
    touches_5m = sum(1 for c in candles_5m if c["low"] <= entry_zone)
    touches_1h = sum(1 for c in candles_1h if c["low"] <= entry_zone)
    print(f"  5m candles touching <=${entry_zone}: {touches_5m}/{len(candles_5m)}")
    print(f"  1h candles touching <=${entry_zone}: {touches_1h}/{len(candles_1h)}")

    # Run backtests
    output_lines = []

    for interval_label, candles, interval_min in [
        ("5m candles (~5 days)", candles_5m, 5),
        ("1h candles (~21 days)", candles_1h, 60),
    ]:
        print(f"\n{'#'*72}")
        print(f"  BACKTEST: {interval_label}")
        print(f"{'#'*72}")

        results = []
        for params in param_sets:
            trades = run_backtest(candles, params, interval_min)
            metrics = calc_metrics(trades, params, candles, interval_min)
            print_report(metrics, params, interval_label)
            results.append((params, metrics))

        print_comparison(results, interval_label)

    # Additional analysis: RSI distribution in entry zone
    print(f"\n{'='*72}")
    print(f"  RSI ANALYSIS IN ENTRY ZONE")
    print(f"{'='*72}")
    for label, candles in [("5m", candles_5m), ("1h", candles_1h)]:
        closes = [c["close"] for c in candles]
        rsi = compute_rsi(closes, 14)
        entry_rsi = []
        for i, c in enumerate(candles):
            if c["close"] <= 1.335 and rsi[i] is not None:
                entry_rsi.append(rsi[i])
        if entry_rsi:
            below_35 = sum(1 for r in entry_rsi if r <= 35)
            print(f"  {label}: {len(entry_rsi)} candles close<=$1.335, "
                  f"{below_35} with RSI<=35 ({below_35/len(entry_rsi)*100:.0f}%)")
            print(f"       RSI range: {min(entry_rsi):.1f} - {max(entry_rsi):.1f}, "
                  f"avg={sum(entry_rsi)/len(entry_rsi):.1f}")
        else:
            print(f"  {label}: No candles with close <= $1.335")

    # Relaxed RSI analysis
    print(f"\n  --- What if RSI threshold was relaxed? ---")
    for rsi_thresh in [40, 45, 50, 60]:
        for label, candles, interval_min in [("5m", candles_5m, 5), ("1h", candles_1h, 60)]:
            p = ParamSet(f"RSI<={rsi_thresh}", 1.335, 1.42, 1.305, 12, 1353,
                         rsi_thresh, 14, 0.0002, 0.0001)
            trades = run_backtest(candles, p, interval_min)
            metrics = calc_metrics(trades, p, candles, interval_min)
            if metrics["total_trades"] > 0:
                print(f"  {label} RSI<={rsi_thresh}: {metrics['total_trades']} trades, "
                      f"WR={metrics['win_rate']:.0f}%, "
                      f"P/L=${metrics['total_pnl_usd']:.2f} ({metrics['total_pnl_pct']:.1f}%)")
            else:
                print(f"  {label} RSI<={rsi_thresh}: 0 trades")

    # No-RSI filter analysis
    print(f"\n  --- What if NO RSI filter? (price + bullish only) ---")
    for label, candles, interval_min in [("5m", candles_5m, 5), ("1h", candles_1h, 60)]:
        p = ParamSet("No RSI", 1.335, 1.42, 1.305, 12, 1353, 100, 14, 0.0002, 0.0001)
        trades = run_backtest(candles, p, interval_min)
        metrics = calc_metrics(trades, p, candles, interval_min)
        if metrics["total_trades"] > 0:
            print(f"  {label} No RSI: {metrics['total_trades']} trades, "
                  f"WR={metrics['win_rate']:.0f}%, "
                  f"P/L=${metrics['total_pnl_usd']:.2f} ({metrics['total_pnl_pct']:.1f}%), "
                  f"MaxDD={metrics['max_drawdown_pct']:.1f}%")
        else:
            print(f"  {label} No RSI: 0 trades")

    # Save results
    save_path = "/tmp/xrp_backtest_results.txt"
    print(f"\n  Saving results to {save_path}...")

    import io
    import contextlib

    # Re-run with captured output
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        # Summary output for file
        print("XRP Box Scalper Backtest Results")
        print(f"Generated: {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S UTC}")
        print(f"Data: XRPUSDT Binance Futures")
        print(f"5m candles: {len(candles_5m)}, 1h candles: {len(candles_1h)}")
        print()

        for interval_label, candles, interval_min in [
            ("5m (~5d)", candles_5m, 5),
            ("1h (~21d)", candles_1h, 60),
        ]:
            for params in param_sets:
                trades = run_backtest(candles, params, interval_min)
                metrics = calc_metrics(trades, params, candles, interval_min)
                print(f"{params.name} | {interval_label}: "
                      f"trades={metrics['total_trades']}, "
                      f"WR={metrics.get('win_rate', 0):.1f}%, "
                      f"P/L=${metrics.get('total_pnl_usd', 0):.2f}, "
                      f"MaxDD={metrics.get('max_drawdown_pct', 0):.2f}%, "
                      f"Sharpe={metrics.get('sharpe_ratio', 0):.2f}")

    with open(save_path, "w") as f:
        f.write(buf.getvalue())

    print(f"  Done! Results saved to {save_path}")
    print(f"\n{'='*72}")
    print(f"  BACKTEST COMPLETE")
    print(f"{'='*72}")


if __name__ == "__main__":
    main()
