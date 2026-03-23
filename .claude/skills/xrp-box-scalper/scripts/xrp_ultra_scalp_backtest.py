#!/usr/bin/env python3
"""
Ultra-short XRP range scalp backtest.

Execution: 1m candles
Regime filter: 15m range condition
Holding time: minutes, not hours
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import xrp_edge_fade_backtest as common


@dataclass
class MarketData:
    candles_1m: list[common.Candle]
    candles_15m: list[common.Candle]


@dataclass
class Config:
    symbol: str = "XRPUSDT"
    days: int = 30
    leverage: float = 10.0
    fee_rate: float = 0.0004
    starting_balance: float = 2000.0
    risk_per_trade_pct: float = 0.50
    max_margin_fraction: float = 0.25
    rsi_period: int = 2
    rsi_long_max: float = 8.0
    rsi_short_min: float = 92.0
    atr_period: int = 14
    adx_period: int = 14
    adx_max: float = 18.0
    box_lookback_15m: int = 48
    box_min_width_pct: float = 0.008
    box_max_width_pct: float = 0.045
    entry_zone_fraction: float = 0.15
    mid_no_trade_fraction: float = 0.18
    stop_atr_mult: float = 0.75
    take_profit_rr: float = 1.35
    breakout_margin: float = 0.0008
    breakout_confirm_bars: int = 2
    max_hold_bars: int = 8
    cooldown_bars: int = 2
    daily_loss_limit_pct: float = 2.0
    loss_size_decay: float = 0.75
    loss_decay_after: int = 2


PRESETS: dict[str, dict[str, float | int]] = {
    "baseline": {},
    "aggressive": {
        "leverage": 12.0,
        "risk_per_trade_pct": 0.75,
        "max_margin_fraction": 0.35,
        "rsi_long_max": 10.0,
        "rsi_short_min": 90.0,
        "adx_max": 20.0,
        "entry_zone_fraction": 0.18,
        "max_hold_bars": 10,
        "daily_loss_limit_pct": 3.0,
    },
    "daytrade": {
        "leverage": 8.0,
        "risk_per_trade_pct": 0.25,
        "max_margin_fraction": 0.15,
        "rsi_long_max": 15.0,
        "rsi_short_min": 85.0,
        "adx_max": 24.0,
        "box_lookback_15m": 24,
        "entry_zone_fraction": 0.28,
        "mid_no_trade_fraction": 0.05,
        "box_max_width_pct": 0.06,
        "stop_atr_mult": 0.55,
        "take_profit_rr": 1.0,
        "max_hold_bars": 8,
        "cooldown_bars": 0,
        "daily_loss_limit_pct": 2.0,
    },
}


@dataclass
class Position:
    side: str
    entry_time_ms: int
    entry_price: float
    qty: float
    stop_price: float
    target_price: float
    bars_held: int = 0
    entry_fee_paid: float = 0.0


def confirmed_breakout(
    candles_15m: list[common.Candle],
    latest_idx: int,
    box_low: float,
    box_high: float,
    confirm_bars: int,
    margin: float,
) -> str | None:
    if latest_idx < confirm_bars - 1:
        return None
    recent = candles_15m[latest_idx - confirm_bars + 1 : latest_idx + 1]
    if all(c.close > box_high * (1.0 + margin) for c in recent):
        return "UP"
    if all(c.close < box_low * (1.0 - margin) for c in recent):
        return "DOWN"
    return None


def position_size(balance: float, cfg: Config, entry: float, stop: float, loss_streak: int) -> float:
    risk_amount = balance * (cfg.risk_per_trade_pct / 100.0)
    if loss_streak >= cfg.loss_decay_after:
        risk_amount *= cfg.loss_size_decay ** (loss_streak - cfg.loss_decay_after + 1)
    price_risk = abs(entry - stop)
    if price_risk <= 0:
        return 0.0
    qty = risk_amount / price_risk
    max_notional = balance * cfg.max_margin_fraction * cfg.leverage
    max_qty = max_notional / entry
    qty = min(qty, max_qty)
    return int(qty * 10) / 10.0


def make_config(profile: str, days: int) -> Config:
    cfg = Config(days=days, **PRESETS[profile])
    setattr(cfg, "_profile_name", profile)
    return cfg


def load_market_data(cfg: Config) -> MarketData:
    return MarketData(
        candles_1m=common.fetch_candles(cfg.symbol, "1m", cfg.days),
        candles_15m=common.fetch_candles(cfg.symbol, "15m", cfg.days + 3),
    )


def backtest(cfg: Config, market_data: MarketData | None = None) -> dict:
    data = market_data or load_market_data(cfg)
    candles_1m = data.candles_1m
    candles_15m = data.candles_15m

    rsi_1m = common.compute_rsi(common.closes(candles_1m), cfg.rsi_period)
    atr_1m = common.compute_atr(candles_1m, cfg.atr_period)
    adx_15m = common.compute_adx(candles_15m, cfg.adx_period)

    balance = cfg.starting_balance
    peak_equity = balance
    max_drawdown = 0.0
    trades: list[dict] = []
    pos: Position | None = None
    m15_idx = 0
    cooldown_until = -1
    loss_streak = 0
    daily_pnl: dict[str, float] = {}
    locked_days: set[str] = set()

    for i, candle in enumerate(candles_1m):
        if i < max(cfg.rsi_period + 2, cfg.atr_period + 2):
            continue
        m15_idx = common.align_latest_index(candles_15m, candle.open_time, m15_idx)
        if m15_idx < max(cfg.box_lookback_15m - 1, cfg.adx_period * 2):
            continue

        day_key = common.datetime.fromtimestamp(candle.open_time / 1000, tz=common.timezone.utc).strftime("%Y-%m-%d")
        if day_key not in daily_pnl:
            daily_pnl[day_key] = 0.0

        box_slice = candles_15m[m15_idx - cfg.box_lookback_15m + 1 : m15_idx + 1]
        box_low = min(c.low for c in box_slice)
        box_high = max(c.high for c in box_slice)
        box_height = box_high - box_low
        box_mid = (box_low + box_high) / 2.0
        box_width_pct = box_height / box_mid if box_mid else 0.0
        lower_zone_top = box_low + (box_height * cfg.entry_zone_fraction)
        upper_zone_bottom = box_high - (box_height * cfg.entry_zone_fraction)
        breakout = confirmed_breakout(
            candles_15m,
            m15_idx,
            box_low,
            box_high,
            cfg.breakout_confirm_bars,
            cfg.breakout_margin,
        )
        adx = adx_15m[m15_idx]
        atr = atr_1m[i]
        range_ok = (
            adx is not None
            and atr is not None
            and adx <= cfg.adx_max
            and cfg.box_min_width_pct <= box_width_pct <= cfg.box_max_width_pct
            and box_low <= candles_15m[m15_idx].close <= box_high
            and breakout is None
        )

        if pos is not None:
            pos.bars_held += 1
            if pos.side == "LONG":
                stop_hit = candle.low <= pos.stop_price
                target_hit = candle.high >= pos.target_price
            else:
                stop_hit = candle.high >= pos.stop_price
                target_hit = candle.low <= pos.target_price

            if stop_hit or target_hit or breakout or pos.bars_held >= cfg.max_hold_bars:
                if breakout:
                    exit_price = candle.close
                    reason = f"BREAKOUT_{breakout}"
                elif stop_hit:
                    exit_price = pos.stop_price
                    reason = "SL"
                elif target_hit:
                    exit_price = pos.target_price
                    reason = "TP"
                else:
                    exit_price = candle.close
                    reason = "TIME"

                if pos.side == "LONG":
                    gross = (exit_price - pos.entry_price) * pos.qty
                else:
                    gross = (pos.entry_price - exit_price) * pos.qty
                exit_fee = pos.qty * exit_price * cfg.fee_rate
                pnl = gross - pos.entry_fee_paid - exit_fee
                balance += pnl
                trades.append(
                    {
                        "side": pos.side,
                        "entry_time": common.fmt_ts(pos.entry_time_ms),
                        "exit_time": common.fmt_ts(candle.close_time),
                        "entry_price": round(pos.entry_price, 4),
                        "exit_price": round(exit_price, 4),
                        "qty": pos.qty,
                        "pnl_usd": round(pnl, 2),
                        "bars_held": pos.bars_held,
                        "reason": reason,
                    }
                )
                daily_pnl[day_key] += pnl
                loss_streak = loss_streak + 1 if pnl < 0 else 0
                cooldown_until = i + cfg.cooldown_bars
                pos = None

        if pos is None:
            if daily_pnl[day_key] <= -(cfg.starting_balance * (cfg.daily_loss_limit_pct / 100.0)):
                locked_days.add(day_key)
            if i < cooldown_until or day_key in locked_days or not range_ok:
                peak_equity = max(peak_equity, balance)
                max_drawdown = max(max_drawdown, (peak_equity - balance) / peak_equity * 100.0)
                continue
            if common.in_center_zone(candle.close, box_low, box_high, cfg.mid_no_trade_fraction):
                peak_equity = max(peak_equity, balance)
                max_drawdown = max(max_drawdown, (peak_equity - balance) / peak_equity * 100.0)
                continue

            rsi = rsi_1m[i]
            if rsi is None or atr is None:
                continue
            prev_close = candles_1m[i - 1].close
            bullish_reclaim = candle.close > prev_close and candle.close > candle.open
            bearish_reject = candle.close < prev_close and candle.close < candle.open
            long_signal = (
                rsi <= cfg.rsi_long_max
                and candle.low <= lower_zone_top
                and candle.close <= (box_low + box_height * 0.25)
                and bullish_reclaim
            )
            short_signal = (
                rsi >= cfg.rsi_short_min
                and candle.high >= upper_zone_bottom
                and candle.close >= (box_high - box_height * 0.25)
                and bearish_reject
            )

            if long_signal:
                entry = candle.close
                stop = entry - (cfg.stop_atr_mult * atr)
                target = entry + (entry - stop) * cfg.take_profit_rr
                qty = position_size(balance, cfg, entry, stop, loss_streak)
                if qty > 0:
                    pos = Position(
                        side="LONG",
                        entry_time_ms=candle.open_time,
                        entry_price=entry,
                        qty=qty,
                        stop_price=stop,
                        target_price=target,
                    )
                    pos.entry_fee_paid = qty * entry * cfg.fee_rate
            elif short_signal:
                entry = candle.close
                stop = entry + (cfg.stop_atr_mult * atr)
                target = entry - (stop - entry) * cfg.take_profit_rr
                qty = position_size(balance, cfg, entry, stop, loss_streak)
                if qty > 0:
                    pos = Position(
                        side="SHORT",
                        entry_time_ms=candle.open_time,
                        entry_price=entry,
                        qty=qty,
                        stop_price=stop,
                        target_price=target,
                    )
                    pos.entry_fee_paid = qty * entry * cfg.fee_rate

        mark_equity = balance
        if pos is not None:
            unrealized = (candle.close - pos.entry_price) * pos.qty if pos.side == "LONG" else (pos.entry_price - candle.close) * pos.qty
            mark_equity += unrealized - pos.entry_fee_paid
        peak_equity = max(peak_equity, mark_equity)
        max_drawdown = max(max_drawdown, (peak_equity - mark_equity) / peak_equity * 100.0)

    if pos is not None:
        last = candles_1m[-1]
        exit_price = last.close
        if pos.side == "LONG":
            gross = (exit_price - pos.entry_price) * pos.qty
        else:
            gross = (pos.entry_price - exit_price) * pos.qty
        exit_fee = pos.qty * exit_price * cfg.fee_rate
        pnl = gross - pos.entry_fee_paid - exit_fee
        balance += pnl
        trades.append(
            {
                "side": pos.side,
                "entry_time": common.fmt_ts(pos.entry_time_ms),
                "exit_time": common.fmt_ts(last.close_time),
                "entry_price": round(pos.entry_price, 4),
                "exit_price": round(exit_price, 4),
                "qty": pos.qty,
                "pnl_usd": round(pnl, 2),
                "bars_held": pos.bars_held,
                "reason": "EOD",
            }
        )

    wins = [t for t in trades if t["pnl_usd"] > 0]
    losses = [t for t in trades if t["pnl_usd"] <= 0]
    gross_profit = sum(t["pnl_usd"] for t in wins)
    gross_loss = abs(sum(t["pnl_usd"] for t in losses))
    return {
        "symbol": cfg.symbol,
        "days": cfg.days,
        "profile": getattr(cfg, "_profile_name", "custom"),
        "starting_balance": round(cfg.starting_balance, 2),
        "ending_balance": round(balance, 2),
        "net_pnl_usd": round(balance - cfg.starting_balance, 2),
        "return_pct": round((balance / cfg.starting_balance - 1.0) * 100.0, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "trade_count": len(trades),
        "win_rate_pct": round((len(wins) / len(trades) * 100.0), 2) if trades else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss else None,
        "avg_hold_minutes": round(sum(t["bars_held"] for t in trades) / len(trades), 2) if trades else 0.0,
        "long_trades": sum(1 for t in trades if t["side"] == "LONG"),
        "short_trades": sum(1 for t in trades if t["side"] == "SHORT"),
        "reason_counts": {k: sum(1 for t in trades if t["reason"] == k) for k in sorted({t["reason"] for t in trades})},
        "settings": {
            "leverage": cfg.leverage,
            "risk_per_trade_pct": cfg.risk_per_trade_pct,
            "max_margin_fraction": cfg.max_margin_fraction,
            "adx_max": cfg.adx_max,
            "rsi_long_max": cfg.rsi_long_max,
            "rsi_short_min": cfg.rsi_short_min,
            "box_lookback_15m": cfg.box_lookback_15m,
            "entry_zone_fraction": cfg.entry_zone_fraction,
            "stop_atr_mult": cfg.stop_atr_mult,
            "take_profit_rr": cfg.take_profit_rr,
            "max_hold_bars": cfg.max_hold_bars,
        },
        "sample_trades": trades[-10:],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="XRP ultra-short scalp backtest")
    parser.add_argument("--profile", choices=sorted(PRESETS), default="aggressive")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    cfg = make_config(args.profile, args.days)
    print(json.dumps(backtest(cfg), indent=2))


if __name__ == "__main__":
    main()
