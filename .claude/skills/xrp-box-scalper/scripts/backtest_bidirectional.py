#!/usr/bin/env python3
"""
XRP/USDT Bidirectional Box-Range Scalping Backtest
===================================================
Tests LONG + SHORT simultaneously (Binance Hedge mode).
Fetches real kline data from Binance Futures public API.
"""

import json
import urllib.request
import datetime
import sys
from collections import defaultdict

# ─── Data Fetching ───────────────────────────────────────────────────────────

def fetch_klines(symbol, interval, limit):
    """Fetch klines from Binance Futures (no auth needed)."""
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    print(f"  Fetching {interval} data ({limit} candles)...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    candles = []
    for k in data:
        candles.append({
            "open_time": int(k[0]),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "close_time": int(k[6]),
        })
    t0 = datetime.datetime.utcfromtimestamp(candles[0]["open_time"] / 1000)
    t1 = datetime.datetime.utcfromtimestamp(candles[-1]["open_time"] / 1000)
    print(f"  Got {len(candles)} candles: {t0} -> {t1} UTC")
    return candles


# ─── RSI (Wilder's smoothing) ───────────────────────────────────────────────

def compute_rsi(candles, period=14):
    """Compute RSI using Wilder's smoothing. Returns list aligned with candles."""
    rsi = [50.0] * len(candles)
    if len(candles) < period + 1:
        return rsi
    gains, losses = [], []
    for i in range(1, period + 1):
        delta = candles[i]["close"] - candles[i - 1]["close"]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    for i in range(period, len(candles)):
        if i > period:
            delta = candles[i]["close"] - candles[i - 1]["close"]
            avg_gain = (avg_gain * (period - 1) + max(delta, 0)) / period
            avg_loss = (avg_loss * (period - 1) + max(-delta, 0)) / period
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        rsi[i] = 100 - 100 / (1 + rs)
    return rsi


# ─── Backtest Engine ────────────────────────────────────────────────────────

class Position:
    def __init__(self, side, entry_price, entry_time, margin, leverage):
        self.side = side  # "LONG" or "SHORT"
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.margin = margin
        self.leverage = leverage
        self.size_usd = margin * leverage
        self.qty = self.size_usd / entry_price
        self.funding_paid = 0.0
        self.bars_held = 0

    def pnl(self, exit_price):
        if self.side == "LONG":
            raw = (exit_price - self.entry_price) / self.entry_price
        else:
            raw = (self.entry_price - exit_price) / self.entry_price
        return raw * self.size_usd

    def pnl_pct(self, exit_price):
        return self.pnl(exit_price) / self.margin * 100


def run_backtest(candles, interval, config, initial_margin=1353.0, fee_rate=0.0004):
    """
    Run bidirectional backtest.
    config: (label, long_entry, long_tp, long_sl, short_entry, short_tp, short_sl, leverage)
    """
    label, long_entry, long_tp, long_sl, short_entry, short_tp, short_sl, leverage = config
    box_low, box_high = 1.33, 1.47  # Only trade within box range

    long_enabled = long_entry is not None
    short_enabled = short_entry is not None

    # Cooldown settings
    if interval == "1h":
        cooldown_bars = 2
        funding_interval_bars = 8  # every 8 hours
    elif interval == "4h":
        cooldown_bars = 1
        funding_interval_bars = 2  # every 8 hours = 2 x 4h bars
    else:  # 5m
        cooldown_bars = 24
        funding_interval_bars = 96  # 8h * 12 (5m bars)

    funding_rate = 0.0001  # 0.01% per 8h

    # State
    margin_per_side = initial_margin / (2 if (long_enabled and short_enabled) else 1)
    long_pos = None
    short_pos = None
    long_cooldown = 0
    short_cooldown = 0
    long_consec_sl = 0
    short_consec_sl = 0

    # Tracking
    trades = []
    equity_curve = [initial_margin]
    total_equity = initial_margin
    peak_equity = initial_margin
    max_drawdown = 0.0
    daily_pnl = defaultdict(float)
    daily_loss_today = 0.0
    current_day = None
    stopped_for_day = False

    rsi = compute_rsi(candles)

    for i in range(1, len(candles)):
        c = candles[i]
        ts = datetime.datetime.utcfromtimestamp(c["open_time"] / 1000)
        day_key = ts.strftime("%Y-%m-%d")

        # Reset daily loss tracking
        if day_key != current_day:
            current_day = day_key
            daily_loss_today = 0.0
            stopped_for_day = False

        if stopped_for_day:
            # Still track funding
            if long_pos:
                long_pos.bars_held += 1
            if short_pos:
                short_pos.bars_held += 1
            equity_curve.append(total_equity)
            continue

        is_bullish = c["close"] > c["open"]
        is_bearish = c["close"] < c["open"]

        # Decrement cooldowns
        if long_cooldown > 0:
            long_cooldown -= 1
        if short_cooldown > 0:
            short_cooldown -= 1

        # ── Check exits for existing positions ──

        # LONG exit
        if long_pos:
            long_pos.bars_held += 1
            # Funding: LONG pays every funding_interval_bars
            if long_pos.bars_held % funding_interval_bars == 0:
                fund = long_pos.size_usd * funding_rate
                long_pos.funding_paid += fund

            exited = False
            # Conservative: check SL first if both possible
            if c["low"] <= long_sl:
                # SL hit
                pnl = long_pos.pnl(long_sl) - (long_pos.size_usd * fee_rate * 2) - long_pos.funding_paid
                pnl_pct = pnl / long_pos.margin * 100
                trades.append({
                    "side": "LONG", "entry": long_pos.entry_price, "exit": long_sl,
                    "pnl": pnl, "pnl_pct": pnl_pct, "result": "SL",
                    "entry_time": long_pos.entry_time, "exit_time": ts,
                    "bars_held": long_pos.bars_held, "funding": long_pos.funding_paid,
                })
                daily_pnl[day_key] += pnl
                total_equity += pnl
                daily_loss_today += pnl
                long_consec_sl += 1
                if long_consec_sl >= 3:
                    long_cooldown = cooldown_bars
                    long_consec_sl = 0
                long_pos = None
                exited = True
            elif c["high"] >= long_tp:
                # TP hit
                pnl = long_pos.pnl(long_tp) - (long_pos.size_usd * fee_rate * 2) - long_pos.funding_paid
                pnl_pct = pnl / long_pos.margin * 100
                trades.append({
                    "side": "LONG", "entry": long_pos.entry_price, "exit": long_tp,
                    "pnl": pnl, "pnl_pct": pnl_pct, "result": "TP",
                    "entry_time": long_pos.entry_time, "exit_time": ts,
                    "bars_held": long_pos.bars_held, "funding": long_pos.funding_paid,
                })
                daily_pnl[day_key] += pnl
                total_equity += pnl
                long_consec_sl = 0
                long_pos = None
                exited = True

        # SHORT exit
        if short_pos:
            short_pos.bars_held += 1
            # Funding: SHORT earns
            if short_pos.bars_held % funding_interval_bars == 0:
                fund = short_pos.size_usd * funding_rate
                short_pos.funding_paid -= fund  # negative = earning

            exited_short = False
            if c["high"] >= short_sl:
                # SL hit
                pnl = short_pos.pnl(short_sl) - (short_pos.size_usd * fee_rate * 2) - short_pos.funding_paid
                pnl_pct = pnl / short_pos.margin * 100
                trades.append({
                    "side": "SHORT", "entry": short_pos.entry_price, "exit": short_sl,
                    "pnl": pnl, "pnl_pct": pnl_pct, "result": "SL",
                    "entry_time": short_pos.entry_time, "exit_time": ts,
                    "bars_held": short_pos.bars_held, "funding": short_pos.funding_paid,
                })
                daily_pnl[day_key] += pnl
                total_equity += pnl
                daily_loss_today += pnl
                short_consec_sl += 1
                if short_consec_sl >= 3:
                    short_cooldown = cooldown_bars
                    short_consec_sl = 0
                short_pos = None
                exited_short = True
            elif c["low"] <= short_tp:
                # TP hit
                pnl = short_pos.pnl(short_tp) - (short_pos.size_usd * fee_rate * 2) - short_pos.funding_paid
                pnl_pct = pnl / short_pos.margin * 100
                trades.append({
                    "side": "SHORT", "entry": short_pos.entry_price, "exit": short_tp,
                    "pnl": pnl, "pnl_pct": pnl_pct, "result": "TP",
                    "entry_time": short_pos.entry_time, "exit_time": ts,
                    "bars_held": short_pos.bars_held, "funding": short_pos.funding_paid,
                })
                daily_pnl[day_key] += pnl
                total_equity += pnl
                short_consec_sl = 0
                short_pos = None
                exited_short = True

        # Daily loss limit check
        if daily_loss_today <= -(initial_margin * 0.05):
            stopped_for_day = True
            equity_curve.append(total_equity)
            continue

        # ── Check entries (only within box range) ──
        in_box = box_low <= c["close"] <= box_high

        # LONG entry
        if (long_enabled and long_pos is None and long_cooldown == 0
                and in_box and is_bullish and c["close"] <= long_entry):
            long_pos = Position("LONG", c["close"], ts, margin_per_side, leverage)

        # SHORT entry
        if (short_enabled and short_pos is None and short_cooldown == 0
                and in_box and is_bearish and c["close"] >= short_entry):
            short_pos = Position("SHORT", c["close"], ts, margin_per_side, leverage)

        # Track equity
        unrealized = 0
        if long_pos:
            unrealized += long_pos.pnl(c["close"])
        if short_pos:
            unrealized += short_pos.pnl(c["close"])
        current_equity = total_equity + unrealized
        equity_curve.append(current_equity)
        if current_equity > peak_equity:
            peak_equity = current_equity
        dd = (peak_equity - current_equity) / peak_equity * 100
        if dd > max_drawdown:
            max_drawdown = dd

    # ── Compute Metrics ──
    long_trades = [t for t in trades if t["side"] == "LONG"]
    short_trades = [t for t in trades if t["side"] == "SHORT"]

    def side_metrics(side_trades, side_label):
        if not side_trades:
            return {
                "label": side_label, "count": 0, "wins": 0, "losses": 0,
                "win_rate": 0, "total_pnl": 0, "avg_win": 0, "avg_loss": 0,
                "profit_factor": 0, "max_consec_loss": 0, "avg_hold_bars": 0,
                "total_funding": 0, "rr_achieved": 0,
            }
        wins = [t for t in side_trades if t["pnl"] > 0]
        losses = [t for t in side_trades if t["pnl"] <= 0]
        gross_profit = sum(t["pnl"] for t in wins) if wins else 0
        gross_loss = abs(sum(t["pnl"] for t in losses)) if losses else 0
        avg_win = gross_profit / len(wins) if wins else 0
        avg_loss = gross_loss / len(losses) if losses else 0

        # Max consecutive losses
        max_cl = 0
        cl = 0
        for t in side_trades:
            if t["pnl"] <= 0:
                cl += 1
                max_cl = max(max_cl, cl)
            else:
                cl = 0

        return {
            "label": side_label,
            "count": len(side_trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(side_trades) * 100 if side_trades else 0,
            "total_pnl": sum(t["pnl"] for t in side_trades),
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": gross_profit / gross_loss if gross_loss > 0 else float("inf"),
            "max_consec_loss": max_cl,
            "avg_hold_bars": sum(t["bars_held"] for t in side_trades) / len(side_trades),
            "total_funding": sum(t["funding"] for t in side_trades),
            "rr_achieved": avg_win / avg_loss if avg_loss > 0 else float("inf"),
        }

    long_m = side_metrics(long_trades, "LONG")
    short_m = side_metrics(short_trades, "SHORT")

    # Combined
    total_count = len(trades)
    total_wins = long_m["wins"] + short_m["wins"]
    total_pnl = sum(t["pnl"] for t in trades)
    gross_profit = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] <= 0))

    # Trades per day
    if candles:
        span_ms = candles[-1]["open_time"] - candles[0]["open_time"]
        span_days = max(span_ms / (1000 * 86400), 1)
    else:
        span_days = 1

    return {
        "label": label,
        "interval": interval,
        "total_trades": total_count,
        "total_wins": total_wins,
        "win_rate": total_wins / total_count * 100 if total_count > 0 else 0,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl / initial_margin * 100,
        "profit_factor": gross_profit / gross_loss if gross_loss > 0 else float("inf"),
        "max_drawdown": max_drawdown,
        "trades_per_day": total_count / span_days,
        "total_funding": sum(t["funding"] for t in trades),
        "long": long_m,
        "short": short_m,
        "daily_pnl": dict(daily_pnl),
        "trades": trades,
        "span_days": span_days,
        "final_equity": total_equity,
    }


# ─── Display ────────────────────────────────────────────────────────────────

def print_comparison(results):
    """Print comparison table of all configs."""
    print("\n" + "=" * 120)
    print("PARAMETER SET COMPARISON")
    print("=" * 120)
    header = f"{'Config':<22} {'TF':>3} {'Trades':>6} {'W/L':>7} {'WR%':>6} {'P/L $':>9} {'P/L %':>8} {'PF':>6} {'MaxDD%':>7} {'T/day':>6} {'Fund$':>7}"
    print(header)
    print("-" * 120)
    for r in results:
        long_str = f"{r['long']['wins']}W" if r['long']['count'] > 0 else "-"
        short_str = f"{r['short']['wins']}W" if r['short']['count'] > 0 else "-"
        wl = f"{r['total_wins']}/{r['total_trades'] - r['total_wins']}"
        print(
            f"{r['label']:<22} {r['interval']:>3} "
            f"{r['total_trades']:>6} {wl:>7} {r['win_rate']:>5.1f}% "
            f"{r['total_pnl']:>+9.2f} {r['total_pnl_pct']:>+7.2f}% "
            f"{r['profit_factor']:>6.2f} {r['max_drawdown']:>6.2f}% "
            f"{r['trades_per_day']:>6.2f} {r['total_funding']:>+7.2f}"
        )


def print_side_breakdown(result):
    """Print LONG vs SHORT breakdown for a single result."""
    print(f"\n{'─' * 80}")
    print(f"  SIDE BREAKDOWN: {result['label']} ({result['interval']})")
    print(f"{'─' * 80}")
    for m in [result["long"], result["short"]]:
        if m["count"] == 0:
            print(f"  {m['label']}: No trades")
            continue
        print(f"  {m['label']}:")
        print(f"    Trades: {m['count']}  |  Wins: {m['wins']}  |  Losses: {m['losses']}  |  Win Rate: {m['win_rate']:.1f}%")
        print(f"    Total P/L: ${m['total_pnl']:+.2f}  |  Avg Win: ${m['avg_win']:.2f}  |  Avg Loss: ${m['avg_loss']:.2f}")
        print(f"    Profit Factor: {m['profit_factor']:.2f}  |  R:R Achieved: {m['rr_achieved']:.2f}")
        print(f"    Max Consec Loss: {m['max_consec_loss']}  |  Avg Hold: {m['avg_hold_bars']:.1f} bars")
        print(f"    Net Funding: ${m['total_funding']:+.2f}")


def print_daily_pnl(result):
    """Print day-by-day P/L."""
    if not result["daily_pnl"]:
        return
    print(f"\n{'─' * 60}")
    print(f"  DAILY P/L: {result['label']} ({result['interval']})")
    print(f"{'─' * 60}")
    cumulative = 0
    for day in sorted(result["daily_pnl"].keys()):
        pnl = result["daily_pnl"][day]
        cumulative += pnl
        bar_len = int(abs(pnl) / 5)
        bar = ("+" * bar_len) if pnl >= 0 else ("-" * bar_len)
        print(f"  {day}: {pnl:>+8.2f}  cum: {cumulative:>+9.2f}  {bar}")


def print_trade_log(result, max_trades=30):
    """Print individual trades."""
    trades = result["trades"]
    if not trades:
        return
    print(f"\n{'─' * 100}")
    print(f"  TRADE LOG: {result['label']} ({result['interval']}) — showing last {min(len(trades), max_trades)} trades")
    print(f"{'─' * 100}")
    print(f"  {'#':>3} {'Side':<6} {'Entry$':>8} {'Exit$':>8} {'Result':>6} {'P/L$':>9} {'P/L%':>8} {'Bars':>5} {'Fund$':>7} {'Time'}")
    for idx, t in enumerate(trades[-max_trades:], 1):
        print(
            f"  {idx:>3} {t['side']:<6} {t['entry']:>8.4f} {t['exit']:>8.4f} "
            f"{t['result']:>6} {t['pnl']:>+9.2f} {t['pnl_pct']:>+7.2f}% "
            f"{t['bars_held']:>5} {t['funding']:>+7.3f} {t['entry_time']}"
        )


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 80)
    print("  XRP/USDT BIDIRECTIONAL BOX-RANGE SCALPING BACKTEST")
    print("  Binance Futures Hedge Mode | LONG + SHORT Simultaneous")
    print("=" * 80)

    configs = [
        # (label, long_entry, long_tp, long_sl, short_entry, short_tp, short_sl, leverage)
        ("Balanced 12x",    1.36, 1.42, 1.33, 1.44, 1.38, 1.47, 12),
        ("Tight 12x",       1.36, 1.42, 1.33, 1.43, 1.38, 1.46, 12),
        ("Wide 12x",        1.35, 1.42, 1.32, 1.44, 1.38, 1.48, 12),
        ("Aggressive 12x",  1.37, 1.42, 1.34, 1.43, 1.38, 1.46, 12),
        ("Conservative 7x", 1.36, 1.42, 1.33, 1.44, 1.38, 1.47, 7),
        ("LONG only 12x",   1.36, 1.42, 1.33, None, None, None, 12),
    ]

    all_results = []

    for interval, limit in [("1h", 500), ("4h", 1000), ("5m", 1500)]:
        print(f"\n{'=' * 80}")
        print(f"  TIMEFRAME: {interval} ({limit} candles)")
        print(f"{'=' * 80}")

        candles = fetch_klines("XRPUSDT", interval, limit)

        # Price range info
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        closes = [c["close"] for c in candles]
        print(f"  Price range: ${min(lows):.4f} - ${max(highs):.4f}")
        print(f"  Current: ${closes[-1]:.4f}")
        print(f"  Avg volume: {sum(c['volume'] for c in candles) / len(candles):,.0f}")

        interval_results = []
        for cfg in configs:
            r = run_backtest(candles, interval, cfg)
            interval_results.append(r)
            all_results.append(r)

        print_comparison(interval_results)

        # Find best by total P/L
        best = max(interval_results, key=lambda r: r["total_pnl"])
        print(f"\n  >>> BEST for {interval}: {best['label']} "
              f"(P/L: ${best['total_pnl']:+.2f}, {best['total_pnl_pct']:+.2f}%, "
              f"WR: {best['win_rate']:.1f}%, PF: {best['profit_factor']:.2f})")

        # Detailed breakdown for best
        print_side_breakdown(best)
        print_daily_pnl(best)
        print_trade_log(best)

        # Also show LONG-only for comparison
        long_only = [r for r in interval_results if "LONG only" in r["label"]]
        if long_only:
            lo = long_only[0]
            print(f"\n  --- LONG-only baseline: P/L ${lo['total_pnl']:+.2f} ({lo['total_pnl_pct']:+.2f}%) ---")

    # ── Final Summary ──
    print("\n" + "=" * 120)
    print("  FINAL SUMMARY — ALL RESULTS")
    print("=" * 120)
    print_comparison(all_results)

    # Best overall
    best_overall = max(all_results, key=lambda r: r["total_pnl"])
    print(f"\n{'*' * 80}")
    print(f"  RECOMMENDATION: {best_overall['label']} on {best_overall['interval']}")
    print(f"  Total P/L: ${best_overall['total_pnl']:+.2f} ({best_overall['total_pnl_pct']:+.2f}%)")
    print(f"  Win Rate: {best_overall['win_rate']:.1f}% | Profit Factor: {best_overall['profit_factor']:.2f}")
    print(f"  Max Drawdown: {best_overall['max_drawdown']:.2f}%")
    print(f"  Trades/day: {best_overall['trades_per_day']:.2f} over {best_overall['span_days']:.1f} days")
    print(f"  Net Funding Impact: ${best_overall['total_funding']:+.2f}")
    print(f"{'*' * 80}")

    # Bidirectional advantage
    print("\n  BIDIRECTIONAL ADVANTAGE ANALYSIS:")
    for interval in ["1h", "5m"]:
        bi_results = [r for r in all_results if r["interval"] == interval and "LONG only" not in r["label"]]
        lo_results = [r for r in all_results if r["interval"] == interval and "LONG only" in r["label"]]
        if bi_results and lo_results:
            best_bi = max(bi_results, key=lambda r: r["total_pnl"])
            lo = lo_results[0]
            diff = best_bi["total_pnl"] - lo["total_pnl"]
            print(f"  {interval}: Best bidirectional ({best_bi['label']}): ${best_bi['total_pnl']:+.2f} "
                  f"vs LONG-only: ${lo['total_pnl']:+.2f} => "
                  f"Advantage: ${diff:+.2f} ({'BETTER' if diff > 0 else 'WORSE'})")

    # Save to file
    output_path = "/tmp/xrp_backtest_bidirectional.txt"
    with open(output_path, "w") as f:
        import io
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()

        # Re-run summary
        print("XRP/USDT Bidirectional Box Scalping Backtest Results")
        print(f"Generated: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"Best config: {best_overall['label']} ({best_overall['interval']})")
        print(f"P/L: ${best_overall['total_pnl']:+.2f} ({best_overall['total_pnl_pct']:+.2f}%)")
        print(f"Win Rate: {best_overall['win_rate']:.1f}%")
        print(f"Profit Factor: {best_overall['profit_factor']:.2f}")
        print(f"Max Drawdown: {best_overall['max_drawdown']:.2f}%")
        print(f"Trades: {best_overall['total_trades']} ({best_overall['trades_per_day']:.2f}/day)")
        print(f"Net Funding: ${best_overall['total_funding']:+.2f}")
        print()
        for r in all_results:
            print(f"{r['label']:22s} {r['interval']:3s}: P/L ${r['total_pnl']:+9.2f} ({r['total_pnl_pct']:+7.2f}%) "
                  f"WR {r['win_rate']:5.1f}% PF {r['profit_factor']:6.2f} "
                  f"Trades {r['total_trades']:3d} DD {r['max_drawdown']:5.2f}%")

        sys.stdout = old_stdout
        f.write(buffer.getvalue())

    print(f"\n  Results saved to: {output_path}")
    print("\n  BACKTEST COMPLETE.")


if __name__ == "__main__":
    main()
