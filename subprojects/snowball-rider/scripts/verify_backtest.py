"""
Independent Backtest Verification — XRPUSDT Futures Snowball Rider
==================================================================
Re-implements the claimed strategy from scratch to verify:
  - $1,000 -> $241,435 (+24,043%) over 5.7 years
  - CAGR 163%, 3x leverage, 100% allocation

Strategy rules (as claimed):
  Entry LONG:  EMA(10) > EMA(30) + RSI(21) > 55
  Entry SHORT: EMA(10) < EMA(30) + RSI(21) < 45
  SL: -60% leveraged PnL
  TP activation: +15%, then exit when EMA(7) < EMA(14) for 2 consecutive days (LONG)
                                    or EMA(7) > EMA(14) for 2 consecutive days (SHORT)
"""

from __future__ import annotations
import sys
import os
import json
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

import requests

# Use the project's indicator functions
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from snowball_rider.indicators import compute_ema, compute_rsi


# ─────────────────────────────────────────────────────────────
# 1. DATA FETCHING  (paginated, no look-ahead)
# ─────────────────────────────────────────────────────────────

def fetch_all_klines(symbol: str = "XRPUSDT", interval: str = "1d") -> list[dict]:
    """Fetch ALL daily klines from Binance Futures, paginating backward."""
    url = "https://fapi.binance.com/fapi/v1/klines"
    all_klines = []
    end_time = None  # start from most recent

    while True:
        params = {"symbol": symbol, "interval": interval, "limit": 1500}
        if end_time is not None:
            params["endTime"] = end_time

        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if not data:
            break

        all_klines = data + all_klines  # prepend older data

        # Next page: go before the oldest candle we received
        oldest_open_time = data[0][0]
        end_time = oldest_open_time - 1

        print(f"  Fetched {len(data)} candles, total so far: {len(all_klines)}, "
              f"oldest: {datetime.fromtimestamp(oldest_open_time/1000, tz=timezone.utc).strftime('%Y-%m-%d')}")

        if len(data) < 1500:
            break  # no more data

        time.sleep(0.2)  # rate limit courtesy

    # Deduplicate by open_time
    seen = set()
    unique = []
    for k in all_klines:
        ot = k[0]
        if ot not in seen:
            seen.add(ot)
            unique.append(k)
    unique.sort(key=lambda x: x[0])

    # Parse into dicts
    candles = []
    for k in unique:
        candles.append({
            "open_time": int(k[0]),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "close_time": int(k[6]),
            "date": datetime.fromtimestamp(int(k[0])/1000, tz=timezone.utc).strftime('%Y-%m-%d'),
        })

    return candles


# ─────────────────────────────────────────────────────────────
# 2. BACKTEST ENGINE  (independent implementation)
# ─────────────────────────────────────────────────────────────

@dataclass
class Trade:
    entry_date: str
    exit_date: str
    side: str  # "LONG" or "SHORT"
    entry_price: float
    exit_price: float
    leveraged_pnl_pct: float
    wallet_before: float
    wallet_after: float
    exit_reason: str


@dataclass
class BacktestConfig:
    ema_fast: int = 10
    ema_slow: int = 30
    rsi_period: int = 21
    rsi_long_threshold: float = 55.0
    rsi_short_threshold: float = 45.0
    leverage: int = 3
    sl_pct: float = -60.0       # stop-loss in leveraged PnL %
    tp_activation_pct: float = 15.0  # TP activation threshold
    tp_ema_fast: int = 7
    tp_ema_slow: int = 14
    tp_cross_days: int = 2
    fee_rate: float = 0.0005    # 0.05% taker fee per side
    initial_capital: float = 1000.0
    include_fees: bool = True
    include_funding: bool = False
    funding_rate_daily: float = 0.0003  # ~0.01% per 8h = 0.03% per day
    sl_close_only: bool = False  # If True, only check SL on close price (unrealistic but may match claim)


def run_backtest(candles: list[dict], config: BacktestConfig) -> dict:
    """Run backtest on daily candles. Returns results dict."""

    closes = [c["close"] for c in candles]
    lows = [c["low"] for c in candles]
    highs = [c["high"] for c in candles]
    dates = [c["date"] for c in candles]
    n = len(closes)

    # Compute indicators on FULL series
    ema_fast = compute_ema(closes, config.ema_fast)
    ema_slow = compute_ema(closes, config.ema_slow)
    rsi = compute_rsi(closes, config.rsi_period)
    ema_tp_fast = compute_ema(closes, config.tp_ema_fast)
    ema_tp_slow = compute_ema(closes, config.tp_ema_slow)

    # State
    wallet = config.initial_capital
    peak_wallet = wallet
    max_drawdown = 0.0
    trades: list[Trade] = []

    in_position = False
    position_side: Optional[str] = None
    entry_price = 0.0
    entry_date = ""
    tp_activated = False
    tp_cross_count = 0

    equity_curve = []

    # Warmup: need at least max(ema_slow, rsi_period) bars
    warmup = max(config.ema_slow, config.rsi_period, config.tp_ema_slow) + 1

    for i in range(n):
        # Record equity
        if in_position:
            if position_side == "LONG":
                unrealized_pnl_pct = ((closes[i] / entry_price) - 1) * 100 * config.leverage
            else:
                unrealized_pnl_pct = ((entry_price / closes[i]) - 1) * 100 * config.leverage
            current_equity = wallet * (1 + unrealized_pnl_pct / 100)
        else:
            current_equity = wallet

        equity_curve.append({"date": dates[i], "equity": current_equity})

        # Track drawdown on equity curve
        if current_equity > peak_wallet:
            peak_wallet = current_equity
        dd = (peak_wallet - current_equity) / peak_wallet * 100 if peak_wallet > 0 else 0
        if dd > max_drawdown:
            max_drawdown = dd

        # Skip warmup period
        if i < warmup:
            continue

        # Check indicators are valid
        if any(v is None for v in [ema_fast[i], ema_slow[i], rsi[i], ema_tp_fast[i], ema_tp_slow[i]]):
            continue

        # ── EXIT LOGIC ──
        if in_position:
            # Check stop-loss
            if position_side == "LONG":
                worst_price = lows[i]
                worst_pnl_pct = ((worst_price / entry_price) - 1) * 100 * config.leverage
                close_pnl_pct = ((closes[i] / entry_price) - 1) * 100 * config.leverage
            else:  # SHORT
                worst_price = highs[i]
                worst_pnl_pct = ((entry_price / worst_price) - 1) * 100 * config.leverage
                close_pnl_pct = ((entry_price / closes[i]) - 1) * 100 * config.leverage

            # SL check: use intraday extreme (realistic) or close-only (unrealistic)
            sl_check_pnl = close_pnl_pct if config.sl_close_only else worst_pnl_pct
            if sl_check_pnl <= config.sl_pct:
                # If using close-only SL, exit at close price (optimistic)
                # If using realistic SL, exit at worst price (may gap past SL)
                if config.sl_close_only:
                    exit_pnl_pct = close_pnl_pct
                else:
                    exit_pnl_pct = worst_pnl_pct  # realistic: slippage through SL

                # Apply fees
                fee_cost = 0.0
                if config.include_fees:
                    # Fee on entry + exit (both as % of notional)
                    fee_cost = config.fee_rate * config.leverage * 2 * 100  # as pct of wallet

                net_pnl = exit_pnl_pct - fee_cost
                wallet_after = wallet * (1 + net_pnl / 100)
                if wallet_after < 0:
                    wallet_after = 0

                trades.append(Trade(
                    entry_date=entry_date, exit_date=dates[i],
                    side=position_side, entry_price=entry_price,
                    exit_price=worst_price, leveraged_pnl_pct=net_pnl,
                    wallet_before=wallet, wallet_after=wallet_after,
                    exit_reason="STOP_LOSS"
                ))
                wallet = wallet_after
                in_position = False
                tp_activated = False
                tp_cross_count = 0
                continue

            # TP activation check
            if close_pnl_pct >= config.tp_activation_pct:
                tp_activated = True

            # TP exit: EMA cross for N consecutive days
            if tp_activated:
                if position_side == "LONG" and ema_tp_fast[i] < ema_tp_slow[i]:
                    tp_cross_count += 1
                elif position_side == "SHORT" and ema_tp_fast[i] > ema_tp_slow[i]:
                    tp_cross_count += 1
                else:
                    tp_cross_count = 0

                if tp_cross_count >= config.tp_cross_days:
                    # Apply fees
                    fee_cost = 0.0
                    if config.include_fees:
                        fee_cost = config.fee_rate * config.leverage * 2 * 100

                    # Apply funding cost
                    funding_cost = 0.0
                    if config.include_funding:
                        # Count days in position
                        entry_idx = dates.index(entry_date)
                        days_held = i - entry_idx
                        funding_cost = config.funding_rate_daily * config.leverage * days_held * 100

                    net_pnl = close_pnl_pct - fee_cost - funding_cost
                    wallet_after = wallet * (1 + net_pnl / 100)

                    trades.append(Trade(
                        entry_date=entry_date, exit_date=dates[i],
                        side=position_side, entry_price=entry_price,
                        exit_price=closes[i], leveraged_pnl_pct=net_pnl,
                        wallet_before=wallet, wallet_after=wallet_after,
                        exit_reason="TP_EMA_CROSS"
                    ))
                    wallet = wallet_after
                    in_position = False
                    tp_activated = False
                    tp_cross_count = 0
                    continue

            # Funding rate cost accrual (daily)
            if config.include_funding:
                daily_funding = wallet * config.leverage * config.funding_rate_daily
                wallet -= daily_funding

            continue  # Hold position, don't check entry

        # ── ENTRY LOGIC ──
        # LONG: ema_fast > ema_slow AND rsi > threshold
        if ema_fast[i] > ema_slow[i] and rsi[i] > config.rsi_long_threshold:
            if wallet <= 0:
                continue
            entry_price = closes[i]
            entry_date = dates[i]
            position_side = "LONG"
            in_position = True
            tp_activated = False
            tp_cross_count = 0

            # Deduct entry fee from wallet conceptually (already in pnl calc)
            continue

        # SHORT: ema_fast < ema_slow AND rsi < threshold
        if ema_fast[i] < ema_slow[i] and rsi[i] < config.rsi_short_threshold:
            if wallet <= 0:
                continue
            entry_price = closes[i]
            entry_date = dates[i]
            position_side = "SHORT"
            in_position = True
            tp_activated = False
            tp_cross_count = 0
            continue

    # Close any open position at end
    if in_position:
        if position_side == "LONG":
            close_pnl_pct = ((closes[-1] / entry_price) - 1) * 100 * config.leverage
        else:
            close_pnl_pct = ((entry_price / closes[-1]) - 1) * 100 * config.leverage

        fee_cost = config.fee_rate * config.leverage * 2 * 100 if config.include_fees else 0
        net_pnl = close_pnl_pct - fee_cost
        wallet_after = wallet * (1 + net_pnl / 100)

        trades.append(Trade(
            entry_date=entry_date, exit_date=dates[-1],
            side=position_side, entry_price=entry_price,
            exit_price=closes[-1], leveraged_pnl_pct=net_pnl,
            wallet_before=wallet, wallet_after=wallet_after,
            exit_reason="END_OF_DATA"
        ))
        wallet = wallet_after

    # Compute stats
    total_return = (wallet / config.initial_capital - 1) * 100

    start_date = datetime.strptime(dates[warmup], "%Y-%m-%d")
    end_date = datetime.strptime(dates[-1], "%Y-%m-%d")
    years = (end_date - start_date).days / 365.25
    cagr = ((wallet / config.initial_capital) ** (1 / years) - 1) * 100 if years > 0 and wallet > 0 else 0

    winning = [t for t in trades if t.leveraged_pnl_pct > 0]
    losing = [t for t in trades if t.leveraged_pnl_pct <= 0]

    return {
        "config": {
            "ema_fast": config.ema_fast,
            "ema_slow": config.ema_slow,
            "rsi_period": config.rsi_period,
            "rsi_long": config.rsi_long_threshold,
            "rsi_short": config.rsi_short_threshold,
            "leverage": config.leverage,
            "sl_pct": config.sl_pct,
            "tp_activation": config.tp_activation_pct,
            "fees": config.include_fees,
            "funding": config.include_funding,
        },
        "initial_capital": config.initial_capital,
        "final_wallet": wallet,
        "total_return_pct": total_return,
        "cagr_pct": cagr,
        "years": years,
        "max_drawdown_pct": max_drawdown,
        "total_trades": len(trades),
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "win_rate": len(winning) / len(trades) * 100 if trades else 0,
        "avg_win_pct": sum(t.leveraged_pnl_pct for t in winning) / len(winning) if winning else 0,
        "avg_loss_pct": sum(t.leveraged_pnl_pct for t in losing) / len(losing) if losing else 0,
        "best_trade_pct": max((t.leveraged_pnl_pct for t in trades), default=0),
        "worst_trade_pct": min((t.leveraged_pnl_pct for t in trades), default=0),
        "data_start": dates[0],
        "data_end": dates[-1],
        "trade_start": dates[warmup],
        "trades": trades,
        "equity_curve": equity_curve,
    }


def print_results(label: str, results: dict) -> None:
    """Pretty-print backtest results."""
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    cfg = results["config"]
    print(f"  Params: EMA({cfg['ema_fast']}/{cfg['ema_slow']}), RSI({cfg['rsi_period']}), "
          f"RSI thresholds({cfg['rsi_long']}/{cfg['rsi_short']})")
    print(f"  Leverage: {cfg['leverage']}x, SL: {cfg['sl_pct']}%, TP: +{cfg['tp_activation']}% then EMA exit")
    print(f"  Fees: {'YES (0.05% taker)' if cfg['fees'] else 'NO'}")
    print(f"  Funding: {'YES' if cfg['funding'] else 'NO'}")
    print(f"  Data: {results['data_start']} to {results['data_end']} ({results['years']:.1f} years)")
    print(f"  ---")
    print(f"  Initial:      ${results['initial_capital']:,.0f}")
    print(f"  Final:        ${results['final_wallet']:,.2f}")
    print(f"  Total Return: {results['total_return_pct']:+,.1f}%")
    print(f"  CAGR:         {results['cagr_pct']:+,.1f}%")
    print(f"  Max Drawdown: {results['max_drawdown_pct']:.1f}%")
    print(f"  ---")
    print(f"  Total Trades: {results['total_trades']}")
    print(f"  Wins/Losses:  {results['winning_trades']}/{results['losing_trades']}")
    print(f"  Win Rate:     {results['win_rate']:.1f}%")
    print(f"  Avg Win:      {results['avg_win_pct']:+.1f}%")
    print(f"  Avg Loss:     {results['avg_loss_pct']:+.1f}%")
    print(f"  Best Trade:   {results['best_trade_pct']:+.1f}%")
    print(f"  Worst Trade:  {results['worst_trade_pct']:+.1f}%")
    print()

    # Print individual trades
    print(f"  {'#':>3} {'Entry':>10} {'Exit':>10} {'Side':>5} {'Entry$':>8} {'Exit$':>8} {'PnL%':>8} {'Wallet':>12} {'Reason'}")
    print(f"  {'---':>3} {'----------':>10} {'----------':>10} {'-----':>5} {'--------':>8} {'--------':>8} {'--------':>8} {'------------':>12} {'------'}")
    for idx, t in enumerate(results["trades"], 1):
        print(f"  {idx:3d} {t.entry_date:>10} {t.exit_date:>10} {t.side:>5} "
              f"{t.entry_price:8.4f} {t.exit_price:8.4f} {t.leveraged_pnl_pct:+8.1f}% "
              f"${t.wallet_after:11,.2f} {t.exit_reason}")


# ─────────────────────────────────────────────────────────────
# 3. MAIN — Run all tests
# ─────────────────────────────────────────────────────────────

def run_backtest_strict_sl(candles: list[dict], config: BacktestConfig) -> dict:
    """Same as run_backtest but SL loss is CAPPED at exactly sl_pct (perfect execution assumption)."""
    closes = [c["close"] for c in candles]
    lows = [c["low"] for c in candles]
    highs = [c["high"] for c in candles]
    dates = [c["date"] for c in candles]
    n = len(closes)

    ema_fast = compute_ema(closes, config.ema_fast)
    ema_slow = compute_ema(closes, config.ema_slow)
    rsi = compute_rsi(closes, config.rsi_period)
    ema_tp_fast = compute_ema(closes, config.tp_ema_fast)
    ema_tp_slow = compute_ema(closes, config.tp_ema_slow)

    wallet = config.initial_capital
    peak_wallet = wallet
    max_drawdown = 0.0
    trades: list[Trade] = []
    in_position = False
    position_side: Optional[str] = None
    entry_price = 0.0
    entry_date = ""
    tp_activated = False
    tp_cross_count = 0
    equity_curve = []
    warmup = max(config.ema_slow, config.rsi_period, config.tp_ema_slow) + 1

    for i in range(n):
        if in_position:
            if position_side == "LONG":
                unrealized = ((closes[i] / entry_price) - 1) * 100 * config.leverage
            else:
                unrealized = ((entry_price / closes[i]) - 1) * 100 * config.leverage
            current_equity = wallet * (1 + unrealized / 100)
        else:
            current_equity = wallet
        equity_curve.append({"date": dates[i], "equity": current_equity})
        if current_equity > peak_wallet:
            peak_wallet = current_equity
        dd = (peak_wallet - current_equity) / peak_wallet * 100 if peak_wallet > 0 else 0
        if dd > max_drawdown:
            max_drawdown = dd

        if i < warmup:
            continue
        if any(v is None for v in [ema_fast[i], ema_slow[i], rsi[i], ema_tp_fast[i], ema_tp_slow[i]]):
            continue

        if in_position:
            if position_side == "LONG":
                close_pnl_pct = ((closes[i] / entry_price) - 1) * 100 * config.leverage
                intraday_worst = ((lows[i] / entry_price) - 1) * 100 * config.leverage
            else:
                close_pnl_pct = ((entry_price / closes[i]) - 1) * 100 * config.leverage
                intraday_worst = ((entry_price / highs[i]) - 1) * 100 * config.leverage

            # STRICT SL: if intraday touched SL, exit at EXACTLY SL level (perfect execution)
            if intraday_worst <= config.sl_pct:
                exit_pnl_pct = config.sl_pct  # capped at exactly -60%
                fee_cost = config.fee_rate * config.leverage * 2 * 100 if config.include_fees else 0
                net_pnl = exit_pnl_pct - fee_cost
                wallet_after = wallet * (1 + net_pnl / 100)
                if wallet_after < 0:
                    wallet_after = 0
                trades.append(Trade(entry_date=entry_date, exit_date=dates[i],
                    side=position_side, entry_price=entry_price, exit_price=closes[i],
                    leveraged_pnl_pct=net_pnl, wallet_before=wallet, wallet_after=wallet_after,
                    exit_reason="STOP_LOSS_STRICT"))
                wallet = wallet_after
                in_position = False
                tp_activated = False
                tp_cross_count = 0
                continue

            if close_pnl_pct >= config.tp_activation_pct:
                tp_activated = True
            if tp_activated:
                if position_side == "LONG" and ema_tp_fast[i] < ema_tp_slow[i]:
                    tp_cross_count += 1
                elif position_side == "SHORT" and ema_tp_fast[i] > ema_tp_slow[i]:
                    tp_cross_count += 1
                else:
                    tp_cross_count = 0
                if tp_cross_count >= config.tp_cross_days:
                    fee_cost = config.fee_rate * config.leverage * 2 * 100 if config.include_fees else 0
                    net_pnl = close_pnl_pct - fee_cost
                    wallet_after = wallet * (1 + net_pnl / 100)
                    trades.append(Trade(entry_date=entry_date, exit_date=dates[i],
                        side=position_side, entry_price=entry_price, exit_price=closes[i],
                        leveraged_pnl_pct=net_pnl, wallet_before=wallet, wallet_after=wallet_after,
                        exit_reason="TP_EMA_CROSS"))
                    wallet = wallet_after
                    in_position = False
                    tp_activated = False
                    tp_cross_count = 0
                    continue
            continue

        # Entry
        if ema_fast[i] > ema_slow[i] and rsi[i] > config.rsi_long_threshold:
            if wallet <= 0:
                continue
            entry_price = closes[i]
            entry_date = dates[i]
            position_side = "LONG"
            in_position = True
            tp_activated = False
            tp_cross_count = 0
            continue
        if ema_fast[i] < ema_slow[i] and rsi[i] < config.rsi_short_threshold:
            if wallet <= 0:
                continue
            entry_price = closes[i]
            entry_date = dates[i]
            position_side = "SHORT"
            in_position = True
            tp_activated = False
            tp_cross_count = 0
            continue

    if in_position:
        if position_side == "LONG":
            close_pnl_pct = ((closes[-1] / entry_price) - 1) * 100 * config.leverage
        else:
            close_pnl_pct = ((entry_price / closes[-1]) - 1) * 100 * config.leverage
        fee_cost = config.fee_rate * config.leverage * 2 * 100 if config.include_fees else 0
        net_pnl = close_pnl_pct - fee_cost
        wallet_after = wallet * (1 + net_pnl / 100)
        trades.append(Trade(entry_date=entry_date, exit_date=dates[-1],
            side=position_side, entry_price=entry_price, exit_price=closes[-1],
            leveraged_pnl_pct=net_pnl, wallet_before=wallet, wallet_after=wallet_after,
            exit_reason="END_OF_DATA"))
        wallet = wallet_after

    total_return = (wallet / config.initial_capital - 1) * 100
    start_date = datetime.strptime(dates[warmup], "%Y-%m-%d")
    end_date = datetime.strptime(dates[-1], "%Y-%m-%d")
    years = (end_date - start_date).days / 365.25
    cagr = ((wallet / config.initial_capital) ** (1 / years) - 1) * 100 if years > 0 and wallet > 0 else 0
    winning = [t for t in trades if t.leveraged_pnl_pct > 0]
    losing = [t for t in trades if t.leveraged_pnl_pct <= 0]

    return {
        "config": {
            "ema_fast": config.ema_fast, "ema_slow": config.ema_slow,
            "rsi_period": config.rsi_period, "rsi_long": config.rsi_long_threshold,
            "rsi_short": config.rsi_short_threshold, "leverage": config.leverage,
            "sl_pct": config.sl_pct, "tp_activation": config.tp_activation_pct,
            "fees": config.include_fees, "funding": config.include_funding,
        },
        "initial_capital": config.initial_capital,
        "final_wallet": wallet,
        "total_return_pct": total_return,
        "cagr_pct": cagr,
        "years": years,
        "max_drawdown_pct": max_drawdown,
        "total_trades": len(trades),
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "win_rate": len(winning) / len(trades) * 100 if trades else 0,
        "avg_win_pct": sum(t.leveraged_pnl_pct for t in winning) / len(winning) if winning else 0,
        "avg_loss_pct": sum(t.leveraged_pnl_pct for t in losing) / len(losing) if losing else 0,
        "best_trade_pct": max((t.leveraged_pnl_pct for t in trades), default=0),
        "worst_trade_pct": min((t.leveraged_pnl_pct for t in trades), default=0),
        "data_start": dates[0],
        "data_end": dates[-1],
        "trade_start": dates[warmup],
        "trades": trades,
        "equity_curve": equity_curve,
    }


def main():
    print("=" * 70)
    print("  INDEPENDENT BACKTEST VERIFICATION")
    print("  XRPUSDT Futures — Snowball Rider Strategy")
    print("=" * 70)

    # Fetch data
    print("\n[1] Fetching XRPUSDT daily klines from Binance Futures...")
    candles = fetch_all_klines("XRPUSDT", "1d")
    print(f"  Total candles: {len(candles)}")
    print(f"  Date range: {candles[0]['date']} to {candles[-1]['date']}")

    # Cache data locally
    cache_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'xrpusdt_1d_klines.json')
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, 'w') as f:
        json.dump(candles, f)
    print(f"  Cached to {cache_path}")

    # ── TEST A: Exact claimed parameters, NO fees ──
    print("\n[2] Running backtests...")

    config_no_fees = BacktestConfig(
        ema_fast=10, ema_slow=30, rsi_period=21,
        rsi_long_threshold=55, rsi_short_threshold=45,
        leverage=3, sl_pct=-60, tp_activation_pct=15,
        tp_ema_fast=7, tp_ema_slow=14, tp_cross_days=2,
        include_fees=False, include_funding=False,
    )
    results_no_fees = run_backtest(candles, config_no_fees)
    print_results("TEST A: Claimed Parameters — NO FEES (reproducing claim)", results_no_fees)

    # ── TEST B: Same parameters, WITH fees ──
    config_fees = BacktestConfig(
        ema_fast=10, ema_slow=30, rsi_period=21,
        rsi_long_threshold=55, rsi_short_threshold=45,
        leverage=3, sl_pct=-60, tp_activation_pct=15,
        tp_ema_fast=7, tp_ema_slow=14, tp_cross_days=2,
        include_fees=True, include_funding=False,
    )
    results_fees = run_backtest(candles, config_fees)
    print_results("TEST B: Claimed Parameters — WITH 0.05% Taker Fees", results_fees)

    # ── TEST C: With fees AND funding rate ──
    config_full = BacktestConfig(
        ema_fast=10, ema_slow=30, rsi_period=21,
        rsi_long_threshold=55, rsi_short_threshold=45,
        leverage=3, sl_pct=-60, tp_activation_pct=15,
        tp_ema_fast=7, tp_ema_slow=14, tp_cross_days=2,
        include_fees=True, include_funding=True,
    )
    results_full = run_backtest(candles, config_full)
    print_results("TEST C: Claimed Parameters — WITH Fees + Funding Rate", results_full)

    # ── TEST D: Close-only SL (unrealistic but may match claim) ──
    config_close_sl = BacktestConfig(
        ema_fast=10, ema_slow=30, rsi_period=21,
        rsi_long_threshold=55, rsi_short_threshold=45,
        leverage=3, sl_pct=-60, tp_activation_pct=15,
        tp_ema_fast=7, tp_ema_slow=14, tp_cross_days=2,
        include_fees=False, include_funding=False,
        sl_close_only=True,
    )
    results_close_sl = run_backtest(candles, config_close_sl)
    print_results("TEST D: Close-Only SL — NO FEES (may match original claim)", results_close_sl)

    # ── TEST D2: Close-only SL with fees ──
    config_close_sl_fees = BacktestConfig(
        ema_fast=10, ema_slow=30, rsi_period=21,
        rsi_long_threshold=55, rsi_short_threshold=45,
        leverage=3, sl_pct=-60, tp_activation_pct=15,
        tp_ema_fast=7, tp_ema_slow=14, tp_cross_days=2,
        include_fees=True, include_funding=False,
        sl_close_only=True,
    )
    results_close_sl_fees = run_backtest(candles, config_close_sl_fees)
    print_results("TEST D2: Close-Only SL — WITH FEES", results_close_sl_fees)

    # ── TEST D3: No SL at all ──
    config_no_sl = BacktestConfig(
        ema_fast=10, ema_slow=30, rsi_period=21,
        rsi_long_threshold=55, rsi_short_threshold=45,
        leverage=3, sl_pct=-999, tp_activation_pct=15,  # effectively no SL
        tp_ema_fast=7, tp_ema_slow=14, tp_cross_days=2,
        include_fees=False, include_funding=False,
        sl_close_only=True,
    )
    results_no_sl = run_backtest(candles, config_no_sl)
    print_results("TEST D3: NO SL, NO FEES (pure trend following)", results_no_sl)

    # ── TEST D4: What if SL = -20% unleveraged (same as -60% leveraged) but enforced strictly ──
    # This means: if close drops 20% from entry, exit at exactly the SL level
    config_strict_sl = BacktestConfig(
        ema_fast=10, ema_slow=30, rsi_period=21,
        rsi_long_threshold=55, rsi_short_threshold=45,
        leverage=3, sl_pct=-60, tp_activation_pct=15,
        tp_ema_fast=7, tp_ema_slow=14, tp_cross_days=2,
        include_fees=False, include_funding=False,
        sl_close_only=True,
    )
    # Manually patch: cap the SL loss at exactly -60%
    results_strict_sl = run_backtest_strict_sl(candles, config_strict_sl)
    print_results("TEST D4: Strict SL — Capped at -60% (assumes perfect SL execution)", results_strict_sl)

    # ── TEST E: Robustness — Parameter Sensitivity (with close-only SL to give best chance) ──
    print("\n" + "=" * 70)
    print("  ROBUSTNESS CHECK — Parameter Sensitivity")
    print("=" * 70)

    param_variants = [
        ("Baseline (10/30, RSI 55/45)", 10, 30, 21, 55, 45),
        ("EMA 9/29", 9, 29, 21, 55, 45),
        ("EMA 11/31", 11, 31, 21, 55, 45),
        ("EMA 8/32", 8, 32, 21, 55, 45),
        ("EMA 12/28", 12, 28, 21, 55, 45),
        ("RSI 53/47", 10, 30, 21, 53, 47),
        ("RSI 57/43", 10, 30, 21, 57, 43),
        ("RSI 50/50", 10, 30, 21, 50, 50),
        ("RSI 60/40", 10, 30, 21, 60, 40),
        ("RSI period 14", 10, 30, 14, 55, 45),
        ("RSI period 28", 10, 30, 28, 55, 45),
        ("Live params: EMA 20/50 RSI 14", 20, 50, 14, 55, 45),
    ]

    print(f"\n  {'Variant':<35} {'Final$':>12} {'Return%':>10} {'CAGR%':>8} {'MaxDD%':>8} {'Trades':>7} {'WinRate':>8}")
    print(f"  {'-'*35} {'-'*12} {'-'*10} {'-'*8} {'-'*8} {'-'*7} {'-'*8}")

    robustness_results = []
    for label, ef, es, rp, rl, rs in param_variants:
        cfg = BacktestConfig(
            ema_fast=ef, ema_slow=es, rsi_period=rp,
            rsi_long_threshold=rl, rsi_short_threshold=rs,
            leverage=3, sl_pct=-60, tp_activation_pct=15,
            tp_ema_fast=7, tp_ema_slow=14, tp_cross_days=2,
            include_fees=True, include_funding=False,
            sl_close_only=True,  # Give best chance, still with fees
        )
        r = run_backtest(candles, cfg)
        robustness_results.append((label, r))
        print(f"  {label:<35} ${r['final_wallet']:>11,.0f} {r['total_return_pct']:>+9,.0f}% "
              f"{r['cagr_pct']:>+7,.0f}% {r['max_drawdown_pct']:>7.1f}% {r['total_trades']:>7} "
              f"{r['win_rate']:>7.1f}%")

    # ── TEST E: Alternative assets (survivorship bias check) ──
    print("\n" + "=" * 70)
    print("  SURVIVORSHIP BIAS CHECK — Same Strategy on Other Assets")
    print("=" * 70)

    alt_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "ADAUSDT"]

    print(f"\n  {'Symbol':<12} {'Final$':>12} {'Return%':>10} {'CAGR%':>8} {'MaxDD%':>8} {'Trades':>7} {'WinRate':>8}")
    print(f"  {'-'*12} {'-'*12} {'-'*10} {'-'*8} {'-'*8} {'-'*7} {'-'*8}")

    # First, XRPUSDT baseline (close-only SL + fees)
    print(f"  {'XRPUSDT':<12} ${results_close_sl_fees['final_wallet']:>11,.0f} {results_close_sl_fees['total_return_pct']:>+9,.0f}% "
          f"{results_close_sl_fees['cagr_pct']:>+7,.0f}% {results_close_sl_fees['max_drawdown_pct']:>7.1f}% "
          f"{results_close_sl_fees['total_trades']:>7} {results_close_sl_fees['win_rate']:>7.1f}%")

    for sym in alt_symbols:
        try:
            print(f"  Fetching {sym}...", end="", flush=True)
            alt_candles = fetch_all_klines(sym, "1d")
            cfg = BacktestConfig(
                ema_fast=10, ema_slow=30, rsi_period=21,
                rsi_long_threshold=55, rsi_short_threshold=45,
                leverage=3, sl_pct=-60, tp_activation_pct=15,
                tp_ema_fast=7, tp_ema_slow=14, tp_cross_days=2,
                include_fees=True, include_funding=False,
                sl_close_only=True,  # Give best chance
            )
            r = run_backtest(alt_candles, cfg)
            print(f"\r  {sym:<12} ${r['final_wallet']:>11,.0f} {r['total_return_pct']:>+9,.0f}% "
                  f"{r['cagr_pct']:>+7,.0f}% {r['max_drawdown_pct']:>7.1f}% {r['total_trades']:>7} "
                  f"{r['win_rate']:>7.1f}%")
        except Exception as e:
            print(f"\r  {sym:<12} FAILED: {e}")

    # ── ANALYSIS ──
    print("\n" + "=" * 70)
    print("  CRITICAL ANALYSIS")
    print("=" * 70)

    print(f"""
  1. CLAIM vs REALITY (no fees):
     Claimed: $1,000 -> $241,435 (+24,043%), CAGR 163%
     Our result: $1,000 -> ${results_no_fees['final_wallet']:,.2f} ({results_no_fees['total_return_pct']:+,.1f}%), CAGR {results_no_fees['cagr_pct']:+,.1f}%

  2. IMPACT OF FEES:
     Without fees: ${results_no_fees['final_wallet']:,.2f}
     With fees:    ${results_fees['final_wallet']:,.2f}
     Fee drag:     {'N/A (both zero)' if results_no_fees['final_wallet'] == 0 else f"{(1 - results_fees['final_wallet']/results_no_fees['final_wallet'])*100:.1f}% reduction"}

  3. IMPACT OF FUNDING RATE:
     With fees only:     ${results_fees['final_wallet']:,.2f}
     With fees+funding:  ${results_full['final_wallet']:,.2f}
     Funding drag:       {'N/A (both zero)' if results_fees['final_wallet'] == 0 else f"{(1 - results_full['final_wallet']/results_fees['final_wallet'])*100:.1f}% reduction"}

  4. MAX DRAWDOWN:
     No fees:         {results_no_fees['max_drawdown_pct']:.1f}%
     With fees:       {results_fees['max_drawdown_pct']:.1f}%
     With everything: {results_full['max_drawdown_pct']:.1f}%

  5. PARAMETER SENSITIVITY:
     If small changes cause big swings -> OVERFITTED
""")

    # Check parameter sensitivity
    baseline_return = robustness_results[0][1]['total_return_pct']
    returns = [r[1]['total_return_pct'] for r in robustness_results[1:]]
    if baseline_return != 0:
        max_deviation = max(abs(r - baseline_return) / abs(baseline_return) * 100 for r in returns)
    else:
        max_deviation = float('inf')

    print(f"  Baseline return: {baseline_return:+,.0f}%")
    print(f"  Max deviation from baseline: {max_deviation:.0f}%")
    if max_deviation > 50:
        print(f"  ** OVERFITTING DETECTED: {max_deviation:.0f}% max deviation with small param changes **")
    else:
        print(f"  Parameter sensitivity appears reasonable (<50% deviation)")

    print(f"""
  6. ADDITIONAL RED FLAGS:
     - The LIVE strategy uses EMA(20/50) + RSI(14), NOT the backtest EMA(10/30) + RSI(21)
       This is CLASSIC data snooping: testing many params, picking the best
     - 60% stop-loss on 3x leverage = 20% underlying price move
       XRP daily moves >20% are rare but devastating when they happen
     - 100% allocation at 3x leverage means a single bad trade can lose 60% of capital
     - On daily candles, the SL may not trigger at exactly -60% (gap risk)
     - Funding rates on altcoin futures can be significant during volatile periods
     - Liquidity: 100% wallet at 3x on XRPUSDT may face slippage for large accounts
""")

    print("=" * 70)
    print("  VERIFICATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
