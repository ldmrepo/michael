#!/usr/bin/env python3
"""
Microstructure-inspired XRP scalp backtest.

This engine tries to improve on the naive ultra-short scalper by adding:
- maker-style entry limits
- rolling VWAP mean reversion exits
- session/time filters
- microstructure proxies from 1m candles (CLV, wick imbalance, relative volume)

It does not use true historical order book data. Order-book imbalance is
approximated from candle microstructure.
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
    leverage: float = 8.0
    maker_fee_rate: float = 0.0002
    taker_fee_rate: float = 0.0004
    starting_balance: float = 2000.0
    risk_per_trade_pct: float = 0.30
    max_margin_fraction: float = 0.18
    rsi_period: int = 2
    rsi_long_max: float = 14.0
    rsi_short_min: float = 86.0
    atr_period: int = 14
    adx_period: int = 14
    adx_max: float = 22.0
    box_lookback_15m: int = 24
    box_min_width_pct: float = 0.010
    box_max_width_pct: float = 0.060
    entry_zone_fraction: float = 0.22
    mid_no_trade_fraction: float = 0.08
    vwap_window: int = 20
    min_vwap_dev_atr: float = 0.18
    rel_vol_window: int = 20
    rel_vol_min: float = 0.95
    clv_long_min: float = 0.30
    clv_short_max: float = -0.30
    maker_offset_atr: float = 0.08
    entry_expire_bars: int = 3
    stop_atr_mult: float = 0.55
    take_profit_rr: float = 0.90
    max_hold_bars: int = 6
    cooldown_bars: int = 1
    daily_loss_limit_pct: float = 1.5
    loss_size_decay: float = 0.75
    loss_decay_after: int = 2
    use_time_filter: bool = True
    include_equity_curve: bool = False


PRESETS: dict[str, dict[str, float | int | bool]] = {
    "baseline": {},
    "aggressive": {
        "leverage": 10.0,
        "risk_per_trade_pct": 0.45,
        "max_margin_fraction": 0.22,
        "rsi_long_max": 16.0,
        "rsi_short_min": 84.0,
        "adx_max": 24.0,
        "entry_zone_fraction": 0.25,
        "mid_no_trade_fraction": 0.05,
        "min_vwap_dev_atr": 0.14,
        "rel_vol_min": 0.85,
        "max_hold_bars": 8,
        "daily_loss_limit_pct": 2.0,
    },
}


@dataclass
class PendingEntry:
    side: str
    price: float
    created_idx: int
    expires_idx: int
    atr: float
    box_low: float
    box_high: float


@dataclass
class Position:
    side: str
    entry_idx: int
    entry_time_ms: int
    entry_price: float
    qty: float
    stop_price: float
    target_price: float
    bars_held: int = 0
    entry_fee_paid: float = 0.0


def make_config(profile: str, days: int) -> Config:
    cfg = Config(days=days, **PRESETS[profile])
    setattr(cfg, "_profile_name", profile)
    return cfg


def load_market_data(cfg: Config) -> MarketData:
    return MarketData(
        candles_1m=common.fetch_candles(cfg.symbol, "1m", cfg.days),
        candles_15m=common.fetch_candles(cfg.symbol, "15m", cfg.days + 3),
    )


def rolling_vwap(candles: list[common.Candle], window: int) -> list[float | None]:
    out: list[float | None] = [None] * len(candles)
    num = 0.0
    den = 0.0
    vals: list[tuple[float, float]] = []
    for i, c in enumerate(candles):
        tp = (c.high + c.low + c.close) / 3.0
        pv = tp * c.volume
        vals.append((pv, c.volume))
        num += pv
        den += c.volume
        if i >= window:
            old_pv, old_v = vals[i - window]
            num -= old_pv
            den -= old_v
        if i >= window - 1 and den > 0:
            out[i] = num / den
    return out


def rolling_mean(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= window:
            s -= values[i - window]
        if i >= window - 1:
            out[i] = s / window
    return out


def candle_clv(c: common.Candle) -> float:
    rng = c.high - c.low
    if rng <= 0:
        return 0.0
    return ((c.close - c.low) - (c.high - c.close)) / rng


def session_ok(candle: common.Candle, use_time_filter: bool) -> bool:
    if not use_time_filter:
        return True
    hour = common.datetime.fromtimestamp(candle.open_time / 1000, tz=common.timezone.utc).hour
    return (0 <= hour <= 4) or (12 <= hour <= 17)


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


def backtest(cfg: Config, market_data: MarketData | None = None) -> dict:
    data = market_data or load_market_data(cfg)
    candles_1m = data.candles_1m
    candles_15m = data.candles_15m

    rsi_1m = common.compute_rsi(common.closes(candles_1m), cfg.rsi_period)
    atr_1m = common.compute_atr(candles_1m, cfg.atr_period)
    adx_15m = common.compute_adx(candles_15m, cfg.adx_period)
    vwap_1m = rolling_vwap(candles_1m, cfg.vwap_window)
    rel_vol_avg = rolling_mean([c.volume for c in candles_1m], cfg.rel_vol_window)

    balance = cfg.starting_balance
    peak_equity = balance
    max_drawdown = 0.0
    equity_curve: list[tuple[int, float]] = []
    trades: list[dict] = []
    pos: Position | None = None
    pending: PendingEntry | None = None
    m15_idx = 0
    cooldown_until = -1
    loss_streak = 0
    daily_pnl: dict[str, float] = {}
    locked_days: set[str] = set()

    for i, candle in enumerate(candles_1m):
        if i < max(cfg.rsi_period + 2, cfg.atr_period + 2, cfg.vwap_window):
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
            2,
            0.0008,
        )
        adx = adx_15m[m15_idx]
        atr = atr_1m[i]
        cur_vwap = vwap_1m[i]
        vol_avg = rel_vol_avg[i]
        range_ok = (
            adx is not None
            and atr is not None
            and cur_vwap is not None
            and vol_avg is not None
            and adx <= cfg.adx_max
            and cfg.box_min_width_pct <= box_width_pct <= cfg.box_max_width_pct
            and box_low <= candles_15m[m15_idx].close <= box_high
            and breakout is None
            and session_ok(candle, cfg.use_time_filter)
        )

        if pos is not None:
            pos.bars_held += 1
            cur_vwap = vwap_1m[i] or pos.entry_price
            if pos.side == "LONG":
                stop_hit = candle.low <= pos.stop_price
                vwap_hit = cur_vwap > pos.entry_price and candle.high >= cur_vwap
                target_hit = candle.high >= pos.target_price
            else:
                stop_hit = candle.high >= pos.stop_price
                vwap_hit = cur_vwap < pos.entry_price and candle.low <= cur_vwap
                target_hit = candle.low <= pos.target_price

            exit_price = None
            reason = None
            exit_fee_rate = cfg.maker_fee_rate
            if breakout:
                exit_price = candle.close
                reason = f"BREAKOUT_{breakout}"
                exit_fee_rate = cfg.taker_fee_rate
            elif stop_hit:
                exit_price = pos.stop_price
                reason = "SL"
                exit_fee_rate = cfg.taker_fee_rate
            elif vwap_hit:
                exit_price = cur_vwap
                reason = "VWAP"
            elif target_hit:
                exit_price = pos.target_price
                reason = "TP"
            elif pos.bars_held >= cfg.max_hold_bars:
                exit_price = candle.close
                reason = "TIME"
                exit_fee_rate = cfg.taker_fee_rate

            if exit_price is not None:
                if pos.side == "LONG":
                    gross = (exit_price - pos.entry_price) * pos.qty
                else:
                    gross = (pos.entry_price - exit_price) * pos.qty
                exit_fee = pos.qty * exit_price * exit_fee_rate
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

        if pending is not None and pos is None:
            if i > pending.expires_idx:
                pending = None
            else:
                if pending.side == "LONG" and candle.low <= pending.price:
                    stop = pending.price - (cfg.stop_atr_mult * pending.atr)
                    target = pending.price + (pending.price - stop) * cfg.take_profit_rr
                    qty = position_size(balance, cfg, pending.price, stop, loss_streak)
                    if qty > 0:
                        pos = Position(
                            side="LONG",
                            entry_idx=i,
                            entry_time_ms=candle.open_time,
                            entry_price=pending.price,
                            qty=qty,
                            stop_price=stop,
                            target_price=target,
                        )
                        pos.entry_fee_paid = qty * pending.price * cfg.maker_fee_rate
                    pending = None
                elif pending.side == "SHORT" and candle.high >= pending.price:
                    stop = pending.price + (cfg.stop_atr_mult * pending.atr)
                    target = pending.price - (stop - pending.price) * cfg.take_profit_rr
                    qty = position_size(balance, cfg, pending.price, stop, loss_streak)
                    if qty > 0:
                        pos = Position(
                            side="SHORT",
                            entry_idx=i,
                            entry_time_ms=candle.open_time,
                            entry_price=pending.price,
                            qty=qty,
                            stop_price=stop,
                            target_price=target,
                        )
                        pos.entry_fee_paid = qty * pending.price * cfg.maker_fee_rate
                    pending = None

        if pos is None and pending is None:
            if daily_pnl[day_key] <= -(cfg.starting_balance * (cfg.daily_loss_limit_pct / 100.0)):
                locked_days.add(day_key)
            if i < cooldown_until or day_key in locked_days or not range_ok:
                equity_curve.append((candle.close_time, balance))
                peak_equity = max(peak_equity, balance)
                max_drawdown = max(max_drawdown, (peak_equity - balance) / peak_equity * 100.0)
                continue
            if common.in_center_zone(candle.close, box_low, box_high, cfg.mid_no_trade_fraction):
                equity_curve.append((candle.close_time, balance))
                peak_equity = max(peak_equity, balance)
                max_drawdown = max(max_drawdown, (peak_equity - balance) / peak_equity * 100.0)
                continue

            rsi = rsi_1m[i]
            if rsi is None or atr is None or cur_vwap is None or vol_avg is None or vol_avg <= 0:
                continue

            clv = candle_clv(candle)
            rel_vol = candle.volume / vol_avg
            prev_close = candles_1m[i - 1].close
            bullish_reclaim = candle.close > prev_close and candle.close > candle.open
            bearish_reject = candle.close < prev_close and candle.close < candle.open

            long_signal = (
                rsi <= cfg.rsi_long_max
                and candle.low <= lower_zone_top
                and candle.close < cur_vwap - (cfg.min_vwap_dev_atr * atr)
                and clv >= cfg.clv_long_min
                and rel_vol >= cfg.rel_vol_min
                and bullish_reclaim
            )
            short_signal = (
                rsi >= cfg.rsi_short_min
                and candle.high >= upper_zone_bottom
                and candle.close > cur_vwap + (cfg.min_vwap_dev_atr * atr)
                and clv <= cfg.clv_short_max
                and rel_vol >= cfg.rel_vol_min
                and bearish_reject
            )

            if long_signal:
                limit_price = candle.close - (cfg.maker_offset_atr * atr)
                pending = PendingEntry(
                    side="LONG",
                    price=limit_price,
                    created_idx=i,
                    expires_idx=i + cfg.entry_expire_bars,
                    atr=atr,
                    box_low=box_low,
                    box_high=box_high,
                )
            elif short_signal:
                limit_price = candle.close + (cfg.maker_offset_atr * atr)
                pending = PendingEntry(
                    side="SHORT",
                    price=limit_price,
                    created_idx=i,
                    expires_idx=i + cfg.entry_expire_bars,
                    atr=atr,
                    box_low=box_low,
                    box_high=box_high,
                )

        mark_equity = balance
        if pos is not None:
            unrealized = (candle.close - pos.entry_price) * pos.qty if pos.side == "LONG" else (pos.entry_price - candle.close) * pos.qty
            mark_equity += unrealized - pos.entry_fee_paid
        equity_curve.append((candle.close_time, mark_equity))
        peak_equity = max(peak_equity, mark_equity)
        max_drawdown = max(max_drawdown, (peak_equity - mark_equity) / peak_equity * 100.0)

    wins = [t for t in trades if t["pnl_usd"] > 0]
    losses = [t for t in trades if t["pnl_usd"] <= 0]
    gross_profit = sum(t["pnl_usd"] for t in wins)
    gross_loss = abs(sum(t["pnl_usd"] for t in losses))
    report = {
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
            "entry_zone_fraction": cfg.entry_zone_fraction,
            "min_vwap_dev_atr": cfg.min_vwap_dev_atr,
            "rel_vol_min": cfg.rel_vol_min,
            "maker_offset_atr": cfg.maker_offset_atr,
            "max_hold_bars": cfg.max_hold_bars,
            "use_time_filter": cfg.use_time_filter,
        },
        "sample_trades": trades[-10:],
    }
    if cfg.include_equity_curve:
        report["equity_curve"] = equity_curve
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="XRP microstructure-inspired scalp backtest")
    parser.add_argument("--profile", choices=sorted(PRESETS), default="aggressive")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    cfg = make_config(args.profile, args.days)
    print(json.dumps(backtest(cfg), indent=2))


if __name__ == "__main__":
    main()
