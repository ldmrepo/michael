#!/usr/bin/env python3
"""
Research-based XRP range scalping backtest.

Strategy summary:
- Dynamic box from rolling 4h swing range
- Trade only when 1h regime looks range-bound
- Enter near box edges with RSI(2) confirmation
- No new entries near the box midpoint
- Scale out at midpoint, then trail/target the remainder
- Stop the trade on confirmed breakout or time stop
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


BASE_URL = "https://fapi.binance.com"
MS = {
    "1m": 60 * 1000,
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
}


@dataclass
class Candle:
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int


@dataclass
class FundingEvent:
    time_ms: int
    rate: float


@dataclass
class MarketData:
    candles_15m: list[Candle]
    candles_1h: list[Candle]
    candles_4h: list[Candle]
    funding: list[FundingEvent]


@dataclass
class Config:
    symbol: str = "XRPUSDT"
    days: int = 90
    leverage: float = 5.0
    fee_rate: float = 0.0004
    starting_balance: float = 2000.0
    risk_per_trade_pct: float = 0.35
    max_margin_fraction: float = 0.25
    adx_period: int = 14
    adx_max: float = 23.0
    rsi_period: int = 2
    rsi_long_max: float = 15.0
    rsi_short_min: float = 85.0
    atr_period: int = 14
    box_lookback_4h: int = 24
    box_min_width_pct: float = 0.045
    box_max_width_pct: float = 0.18
    entry_zone_fraction: float = 0.18
    mid_no_trade_fraction: float = 0.20
    stop_atr_mult: float = 0.60
    trail_atr_mult: float = 1.00
    tp2_fraction: float = 0.85
    breakout_margin: float = 0.001
    breakout_confirm_bars: int = 2
    max_hold_bars: int = 20
    cooldown_bars: int = 8
    daily_loss_limit_pct: float = 2.0
    loss_size_decay: float = 0.70
    loss_decay_after: int = 2
    include_equity_curve: bool = False


PRESETS: dict[str, dict[str, float | int]] = {
    "balanced": {},
    "aggressive": {
        "leverage": 8.0,
        "risk_per_trade_pct": 0.80,
        "max_margin_fraction": 0.40,
        "daily_loss_limit_pct": 3.0,
    },
    "conservative": {
        "leverage": 3.0,
        "risk_per_trade_pct": 0.25,
        "max_margin_fraction": 0.18,
        "adx_max": 20.0,
        "rsi_long_max": 12.0,
        "rsi_short_min": 88.0,
        "entry_zone_fraction": 0.16,
        "mid_no_trade_fraction": 0.24,
        "stop_atr_mult": 0.55,
        "trail_atr_mult": 0.90,
        "tp2_fraction": 0.80,
        "max_hold_bars": 16,
        "cooldown_bars": 12,
        "daily_loss_limit_pct": 1.5,
        "loss_size_decay": 0.60,
        "loss_decay_after": 2,
    },
}


@dataclass
class Position:
    side: str
    entry_time_ms: int
    entry_price: float
    qty: float
    stop_price: float
    tp1_price: float
    tp2_price: float
    box_low: float
    box_high: float
    atr: float
    bars_held: int = 0
    remaining_qty: float = 0.0
    realized_pnl: float = 0.0
    funding_paid: float = 0.0
    entry_fee_paid: float = 0.0
    exit_fees_paid: float = 0.0
    tp1_done: bool = False
    best_price: float = 0.0

    def __post_init__(self) -> None:
        self.remaining_qty = self.qty
        self.best_price = self.entry_price


def request_json(path: str, params: dict[str, Any]) -> Any:
    query = urllib.parse.urlencode(params)
    url = f"{BASE_URL}{path}?{query}"
    last_error: Exception | None = None
    for attempt in range(6):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 429:
                retry_after = exc.headers.get("Retry-After")
                wait_seconds = float(retry_after) if retry_after else min(2 ** attempt, 20)
                time.sleep(wait_seconds)
                continue
            raise
        except urllib.error.URLError as exc:
            last_error = exc
            time.sleep(min(2 ** attempt, 20))
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"request failed without response: {url}")


def fetch_candles(symbol: str, interval: str, days: int) -> list[Candle]:
    start_ms = int(time.time() * 1000) - days * 24 * 60 * 60 * 1000
    out: list[Candle] = []
    cursor = start_ms
    while True:
        batch = request_json(
            "/fapi/v1/klines",
            {
                "symbol": symbol,
                "interval": interval,
                "startTime": cursor,
                "limit": 1500,
            },
        )
        if not batch:
            break
        candles = [
            Candle(
                open_time=int(k[0]),
                open=float(k[1]),
                high=float(k[2]),
                low=float(k[3]),
                close=float(k[4]),
                volume=float(k[5]),
                close_time=int(k[6]),
            )
            for k in batch
        ]
        if out and candles[0].open_time <= out[-1].open_time:
            candles = [c for c in candles if c.open_time > out[-1].open_time]
        if not candles:
            break
        out.extend(candles)
        if len(batch) < 1500:
            break
        cursor = candles[-1].open_time + MS[interval]
        time.sleep(0.05)
    return out


def fetch_funding(symbol: str, days: int) -> list[FundingEvent]:
    start_ms = int(time.time() * 1000) - days * 24 * 60 * 60 * 1000
    out: list[FundingEvent] = []
    cursor = start_ms
    while True:
        batch = request_json(
            "/fapi/v1/fundingRate",
            {
                "symbol": symbol,
                "startTime": cursor,
                "limit": 1000,
            },
        )
        if not batch:
            break
        events = [
            FundingEvent(time_ms=int(row["fundingTime"]), rate=float(row["fundingRate"]))
            for row in batch
        ]
        if out and events and events[0].time_ms <= out[-1].time_ms:
            events = [e for e in events if e.time_ms > out[-1].time_ms]
        if not events:
            break
        out.extend(events)
        if len(batch) < 1000:
            break
        cursor = events[-1].time_ms + 1
        time.sleep(0.05)
    return out


def load_market_data(cfg: Config) -> MarketData:
    return MarketData(
        candles_15m=fetch_candles(cfg.symbol, "15m", cfg.days),
        candles_1h=fetch_candles(cfg.symbol, "1h", cfg.days + 10),
        candles_4h=fetch_candles(cfg.symbol, "4h", cfg.days + 20),
        funding=fetch_funding(cfg.symbol, cfg.days + 5),
    )


def closes(candles: list[Candle]) -> list[float]:
    return [c.close for c in candles]


def highs(candles: list[Candle]) -> list[float]:
    return [c.high for c in candles]


def lows(candles: list[Candle]) -> list[float]:
    return [c.low for c in candles]


def compute_rsi(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) < period + 1:
        return out
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, period + 1):
        delta = values[i] - values[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    out[period] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    for i in range(period + 1, len(values)):
        delta = values[i] - values[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(delta, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-delta, 0.0)) / period
        out[i] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return out


def compute_atr(candles: list[Candle], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(candles)
    if len(candles) < period + 1:
        return out
    trs: list[float] = []
    for i in range(1, len(candles)):
        cur = candles[i]
        prev = candles[i - 1]
        tr = max(cur.high - cur.low, abs(cur.high - prev.close), abs(cur.low - prev.close))
        trs.append(tr)
        if i == period:
            atr = sum(trs[:period]) / period
            out[i] = atr
        elif i > period:
            prev_atr = out[i - 1]
            assert prev_atr is not None
            out[i] = ((prev_atr * (period - 1)) + tr) / period
    return out


def compute_adx(candles: list[Candle], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(candles)
    if len(candles) < period * 2 + 1:
        return out

    tr_list: list[float] = []
    plus_dm_list: list[float] = []
    minus_dm_list: list[float] = []

    for i in range(1, len(candles)):
        cur = candles[i]
        prev = candles[i - 1]
        up_move = cur.high - prev.high
        down_move = prev.low - cur.low
        plus_dm = up_move if up_move > down_move and up_move > 0 else 0.0
        minus_dm = down_move if down_move > up_move and down_move > 0 else 0.0
        tr = max(cur.high - cur.low, abs(cur.high - prev.close), abs(cur.low - prev.close))
        tr_list.append(tr)
        plus_dm_list.append(plus_dm)
        minus_dm_list.append(minus_dm)

    tr14 = sum(tr_list[:period])
    plus14 = sum(plus_dm_list[:period])
    minus14 = sum(minus_dm_list[:period])

    dx_values: list[float] = []
    for i in range(period, len(tr_list)):
        if i > period:
            tr14 = tr14 - (tr14 / period) + tr_list[i]
            plus14 = plus14 - (plus14 / period) + plus_dm_list[i]
            minus14 = minus14 - (minus14 / period) + minus_dm_list[i]
        plus_di = 0.0 if tr14 == 0 else (plus14 / tr14) * 100.0
        minus_di = 0.0 if tr14 == 0 else (minus14 / tr14) * 100.0
        denom = plus_di + minus_di
        dx = 0.0 if denom == 0 else abs(plus_di - minus_di) / denom * 100.0
        dx_values.append(dx)
        if len(dx_values) == period:
            out[i + 1] = sum(dx_values) / period
        elif len(dx_values) > period:
            prev_adx = out[i]
            assert prev_adx is not None
            out[i + 1] = ((prev_adx * (period - 1)) + dx) / period
    return out


def fmt_ts(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def align_latest_index(candles: list[Candle], ts_ms: int, start_idx: int) -> int:
    idx = start_idx
    while idx + 1 < len(candles) and candles[idx + 1].close_time <= ts_ms:
        idx += 1
    return idx


def in_center_zone(price: float, box_low: float, box_high: float, center_fraction: float) -> bool:
    box_height = box_high - box_low
    mid = (box_low + box_high) / 2.0
    half_band = box_height * center_fraction / 2.0
    return (mid - half_band) <= price <= (mid + half_band)


def confirmed_breakout(
    h1_candles: list[Candle],
    latest_idx: int,
    box_low: float,
    box_high: float,
    confirm_bars: int,
    margin: float,
) -> str | None:
    if latest_idx < confirm_bars - 1:
        return None
    recent = h1_candles[latest_idx - confirm_bars + 1 : latest_idx + 1]
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
    return math.floor(qty * 10) / 10


def open_position(
    side: str,
    candle: Candle,
    box_low: float,
    box_high: float,
    atr: float,
    cfg: Config,
    balance: float,
    loss_streak: int,
) -> Position | None:
    box_height = box_high - box_low
    entry = candle.close
    if side == "LONG":
        raw_stop = box_low - (cfg.stop_atr_mult * atr)
        stop = min(raw_stop, entry - (atr * 0.5))
        tp1 = (box_low + box_high) / 2.0
        tp2 = box_low + (box_height * cfg.tp2_fraction)
    else:
        raw_stop = box_high + (cfg.stop_atr_mult * atr)
        stop = max(raw_stop, entry + (atr * 0.5))
        tp1 = (box_low + box_high) / 2.0
        tp2 = box_high - (box_height * cfg.tp2_fraction)
    if side == "LONG":
        if not (stop < entry < tp1 < tp2):
            return None
        reward_risk = (tp2 - entry) / max(entry - stop, 1e-9)
    else:
        if not (tp2 < tp1 < entry < stop):
            return None
        reward_risk = (entry - tp2) / max(stop - entry, 1e-9)
    if reward_risk < 1.20:
        return None
    qty = position_size(balance, cfg, entry, stop, loss_streak)
    if qty <= 0:
        return None
    pos = Position(
        side=side,
        entry_time_ms=candle.open_time,
        entry_price=entry,
        qty=qty,
        stop_price=stop,
        tp1_price=tp1,
        tp2_price=tp2,
        box_low=box_low,
        box_high=box_high,
        atr=atr,
    )
    pos.entry_fee_paid = qty * entry * cfg.fee_rate
    return pos


def realized_piece(position: Position, qty: float, price: float, cfg: Config) -> float:
    if position.side == "LONG":
        gross = (price - position.entry_price) * qty
    else:
        gross = (position.entry_price - price) * qty
    exit_fee = qty * price * cfg.fee_rate
    position.exit_fees_paid += exit_fee
    position.remaining_qty -= qty
    piece_pnl = gross - exit_fee
    position.realized_pnl += piece_pnl
    return piece_pnl


def backtest(cfg: Config, market_data: MarketData | None = None) -> dict[str, Any]:
    data = market_data or load_market_data(cfg)
    candles_15m = data.candles_15m
    candles_1h = data.candles_1h
    candles_4h = data.candles_4h
    funding = data.funding

    rsi2 = compute_rsi(closes(candles_15m), cfg.rsi_period)
    atr15 = compute_atr(candles_15m, cfg.atr_period)
    adx1h = compute_adx(candles_1h, cfg.adx_period)

    balance = cfg.starting_balance
    peak_equity = balance
    max_drawdown = 0.0
    equity_curve: list[tuple[int, float]] = []
    trades: list[dict[str, Any]] = []

    position: Position | None = None
    h1_idx = 0
    h4_idx = 0
    funding_idx = 0
    cooldown_until_bar = -1
    loss_streak = 0
    daily_pnl: dict[str, float] = {}
    locked_days: set[str] = set()

    for i, candle in enumerate(candles_15m):
        if i < max(cfg.rsi_period + 2, cfg.atr_period + 2):
            continue

        h1_idx = align_latest_index(candles_1h, candle.open_time, h1_idx)
        h4_idx = align_latest_index(candles_4h, candle.open_time, h4_idx)

        if h4_idx < cfg.box_lookback_4h - 1 or h1_idx < (cfg.adx_period * 2):
            continue

        box_slice = candles_4h[h4_idx - cfg.box_lookback_4h + 1 : h4_idx + 1]
        box_low = min(c.low for c in box_slice)
        box_high = max(c.high for c in box_slice)
        box_height = box_high - box_low
        box_mid = (box_low + box_high) / 2.0
        box_width_pct = box_height / box_mid if box_mid else 0.0
        lower_zone_top = box_low + (box_height * cfg.entry_zone_fraction)
        upper_zone_bottom = box_high - (box_height * cfg.entry_zone_fraction)

        day_key = datetime.fromtimestamp(candle.open_time / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        if day_key not in daily_pnl:
            daily_pnl[day_key] = 0.0

        adx = adx1h[h1_idx]
        atr = atr15[i]
        breakout = confirmed_breakout(
            candles_1h,
            h1_idx,
            box_low,
            box_high,
            cfg.breakout_confirm_bars,
            cfg.breakout_margin,
        )
        range_ok = (
            adx is not None
            and atr is not None
            and adx <= cfg.adx_max
            and cfg.box_min_width_pct <= box_width_pct <= cfg.box_max_width_pct
            and box_low <= candles_1h[h1_idx].close <= box_high
            and breakout is None
        )

        if position is not None:
            while funding_idx < len(funding) and funding[funding_idx].time_ms <= candle.close_time:
                event = funding[funding_idx]
                if event.time_ms >= position.entry_time_ms and position.remaining_qty > 0:
                    notional = position.remaining_qty * candle.close
                    if position.side == "LONG":
                        cash = notional * event.rate
                    else:
                        cash = -notional * event.rate
                    position.funding_paid += cash
                funding_idx += 1

            position.bars_held += 1
            if position.side == "LONG":
                position.best_price = max(position.best_price, candle.high)
            else:
                position.best_price = min(position.best_price, candle.low)

            if breakout:
                exit_price = candle.close
                realized_piece(position, position.remaining_qty, exit_price, cfg)
                total_pnl = position.realized_pnl - position.entry_fee_paid - position.funding_paid
                balance += total_pnl
                trades.append(
                    {
                        "side": position.side,
                        "entry_time": fmt_ts(position.entry_time_ms),
                        "exit_time": fmt_ts(candle.close_time),
                        "entry_price": round(position.entry_price, 4),
                        "exit_price": round(exit_price, 4),
                        "qty": position.qty,
                        "pnl_usd": round(total_pnl, 2),
                        "pnl_pct_on_balance": round(total_pnl / max(balance - total_pnl, 1e-9) * 100.0, 2),
                        "bars_held": position.bars_held,
                        "funding_usd": round(position.funding_paid, 4),
                        "reason": f"BREAKOUT_{breakout}",
                    }
                )
                daily_pnl[day_key] += total_pnl
                cooldown_until_bar = i + cfg.cooldown_bars
                loss_streak = loss_streak + 1 if total_pnl < 0 else 0
                position = None
                equity_curve.append((candle.close_time, balance))
                peak_equity = max(peak_equity, balance)
                max_drawdown = max(max_drawdown, (peak_equity - balance) / peak_equity * 100.0)
                continue

            if position.side == "LONG":
                if not position.tp1_done and candle.low <= position.stop_price:
                    exit_price = position.stop_price
                    realized_piece(position, position.remaining_qty, exit_price, cfg)
                    total_pnl = position.realized_pnl - position.entry_fee_paid - position.funding_paid
                    balance += total_pnl
                    trades.append(
                        {
                            "side": position.side,
                            "entry_time": fmt_ts(position.entry_time_ms),
                            "exit_time": fmt_ts(candle.close_time),
                            "entry_price": round(position.entry_price, 4),
                            "exit_price": round(exit_price, 4),
                            "qty": position.qty,
                            "pnl_usd": round(total_pnl, 2),
                            "pnl_pct_on_balance": round(total_pnl / max(balance - total_pnl, 1e-9) * 100.0, 2),
                            "bars_held": position.bars_held,
                            "funding_usd": round(position.funding_paid, 4),
                            "reason": "SL",
                        }
                    )
                    daily_pnl[day_key] += total_pnl
                    cooldown_until_bar = i + cfg.cooldown_bars
                    loss_streak += 1
                    position = None
                    equity_curve.append((candle.close_time, balance))
                    peak_equity = max(peak_equity, balance)
                    max_drawdown = max(max_drawdown, (peak_equity - balance) / peak_equity * 100.0)
                    continue

                if not position.tp1_done and candle.high >= position.tp1_price:
                    realized_piece(position, position.qty * 0.5, position.tp1_price, cfg)
                    position.tp1_done = True
                    position.stop_price = max(position.stop_price, position.entry_price)

                if position.tp1_done:
                    trail_stop = position.best_price - (cfg.trail_atr_mult * position.atr)
                    position.stop_price = max(position.stop_price, trail_stop)
                    if candle.low <= position.stop_price:
                        exit_price = position.stop_price
                        realized_piece(position, position.remaining_qty, exit_price, cfg)
                    elif candle.high >= position.tp2_price:
                        exit_price = position.tp2_price
                        realized_piece(position, position.remaining_qty, exit_price, cfg)
                    else:
                        exit_price = None
                    if exit_price is not None:
                        total_pnl = position.realized_pnl - position.entry_fee_paid - position.funding_paid
                        balance += total_pnl
                        reason = "TP2" if abs(exit_price - position.tp2_price) < 1e-9 else "TRAIL"
                        trades.append(
                            {
                                "side": position.side,
                                "entry_time": fmt_ts(position.entry_time_ms),
                                "exit_time": fmt_ts(candle.close_time),
                                "entry_price": round(position.entry_price, 4),
                                "exit_price": round(exit_price, 4),
                                "qty": position.qty,
                                "pnl_usd": round(total_pnl, 2),
                                "pnl_pct_on_balance": round(total_pnl / max(balance - total_pnl, 1e-9) * 100.0, 2),
                                "bars_held": position.bars_held,
                                "funding_usd": round(position.funding_paid, 4),
                                "reason": reason,
                            }
                        )
                        daily_pnl[day_key] += total_pnl
                        cooldown_until_bar = i + cfg.cooldown_bars
                        loss_streak = loss_streak + 1 if total_pnl < 0 else 0
                        position = None
                        equity_curve.append((candle.close_time, balance))
                        peak_equity = max(peak_equity, balance)
                        max_drawdown = max(max_drawdown, (peak_equity - balance) / peak_equity * 100.0)
                        continue

            else:
                if not position.tp1_done and candle.high >= position.stop_price:
                    exit_price = position.stop_price
                    realized_piece(position, position.remaining_qty, exit_price, cfg)
                    total_pnl = position.realized_pnl - position.entry_fee_paid - position.funding_paid
                    balance += total_pnl
                    trades.append(
                        {
                            "side": position.side,
                            "entry_time": fmt_ts(position.entry_time_ms),
                            "exit_time": fmt_ts(candle.close_time),
                            "entry_price": round(position.entry_price, 4),
                            "exit_price": round(exit_price, 4),
                            "qty": position.qty,
                            "pnl_usd": round(total_pnl, 2),
                            "pnl_pct_on_balance": round(total_pnl / max(balance - total_pnl, 1e-9) * 100.0, 2),
                            "bars_held": position.bars_held,
                            "funding_usd": round(position.funding_paid, 4),
                            "reason": "SL",
                        }
                    )
                    daily_pnl[day_key] += total_pnl
                    cooldown_until_bar = i + cfg.cooldown_bars
                    loss_streak += 1
                    position = None
                    equity_curve.append((candle.close_time, balance))
                    peak_equity = max(peak_equity, balance)
                    max_drawdown = max(max_drawdown, (peak_equity - balance) / peak_equity * 100.0)
                    continue

                if not position.tp1_done and candle.low <= position.tp1_price:
                    realized_piece(position, position.qty * 0.5, position.tp1_price, cfg)
                    position.tp1_done = True
                    position.stop_price = min(position.stop_price, position.entry_price)

                if position.tp1_done:
                    trail_stop = position.best_price + (cfg.trail_atr_mult * position.atr)
                    position.stop_price = min(position.stop_price, trail_stop)
                    if candle.high >= position.stop_price:
                        exit_price = position.stop_price
                        realized_piece(position, position.remaining_qty, exit_price, cfg)
                    elif candle.low <= position.tp2_price:
                        exit_price = position.tp2_price
                        realized_piece(position, position.remaining_qty, exit_price, cfg)
                    else:
                        exit_price = None
                    if exit_price is not None:
                        total_pnl = position.realized_pnl - position.entry_fee_paid - position.funding_paid
                        balance += total_pnl
                        reason = "TP2" if abs(exit_price - position.tp2_price) < 1e-9 else "TRAIL"
                        trades.append(
                            {
                                "side": position.side,
                                "entry_time": fmt_ts(position.entry_time_ms),
                                "exit_time": fmt_ts(candle.close_time),
                                "entry_price": round(position.entry_price, 4),
                                "exit_price": round(exit_price, 4),
                                "qty": position.qty,
                                "pnl_usd": round(total_pnl, 2),
                                "pnl_pct_on_balance": round(total_pnl / max(balance - total_pnl, 1e-9) * 100.0, 2),
                                "bars_held": position.bars_held,
                                "funding_usd": round(position.funding_paid, 4),
                                "reason": reason,
                            }
                        )
                        daily_pnl[day_key] += total_pnl
                        cooldown_until_bar = i + cfg.cooldown_bars
                        loss_streak = loss_streak + 1 if total_pnl < 0 else 0
                        position = None
                        equity_curve.append((candle.close_time, balance))
                        peak_equity = max(peak_equity, balance)
                        max_drawdown = max(max_drawdown, (peak_equity - balance) / peak_equity * 100.0)
                        continue

            if position is not None and position.bars_held >= cfg.max_hold_bars:
                exit_price = candle.close
                realized_piece(position, position.remaining_qty, exit_price, cfg)
                total_pnl = position.realized_pnl - position.entry_fee_paid - position.funding_paid
                balance += total_pnl
                trades.append(
                    {
                        "side": position.side,
                        "entry_time": fmt_ts(position.entry_time_ms),
                        "exit_time": fmt_ts(candle.close_time),
                        "entry_price": round(position.entry_price, 4),
                        "exit_price": round(exit_price, 4),
                        "qty": position.qty,
                        "pnl_usd": round(total_pnl, 2),
                        "pnl_pct_on_balance": round(total_pnl / max(balance - total_pnl, 1e-9) * 100.0, 2),
                        "bars_held": position.bars_held,
                        "funding_usd": round(position.funding_paid, 4),
                        "reason": "TIME",
                    }
                )
                daily_pnl[day_key] += total_pnl
                cooldown_until_bar = i + cfg.cooldown_bars
                loss_streak = loss_streak + 1 if total_pnl < 0 else 0
                position = None
                equity_curve.append((candle.close_time, balance))
                peak_equity = max(peak_equity, balance)
                max_drawdown = max(max_drawdown, (peak_equity - balance) / peak_equity * 100.0)
                continue

        if position is None:
            if i < cooldown_until_bar:
                equity_curve.append((candle.close_time, balance))
                peak_equity = max(peak_equity, balance)
                max_drawdown = max(max_drawdown, (peak_equity - balance) / peak_equity * 100.0)
                continue
            if daily_pnl[day_key] <= -(cfg.starting_balance * (cfg.daily_loss_limit_pct / 100.0)):
                locked_days.add(day_key)
            if day_key in locked_days:
                equity_curve.append((candle.close_time, balance))
                peak_equity = max(peak_equity, balance)
                max_drawdown = max(max_drawdown, (peak_equity - balance) / peak_equity * 100.0)
                continue
            if not range_ok or atr is None:
                equity_curve.append((candle.close_time, balance))
                peak_equity = max(peak_equity, balance)
                max_drawdown = max(max_drawdown, (peak_equity - balance) / peak_equity * 100.0)
                continue
            if in_center_zone(candle.close, box_low, box_high, cfg.mid_no_trade_fraction):
                equity_curve.append((candle.close_time, balance))
                peak_equity = max(peak_equity, balance)
                max_drawdown = max(max_drawdown, (peak_equity - balance) / peak_equity * 100.0)
                continue

            rv = rsi2[i]
            bullish_reclaim = candle.close > candle.open and candle.close >= candles_15m[i - 1].close
            bearish_reject = candle.close < candle.open and candle.close <= candles_15m[i - 1].close

            long_signal = (
                rv is not None
                and rv <= cfg.rsi_long_max
                and candle.low <= lower_zone_top
                and candle.close <= (box_low + box_height * 0.30)
                and bullish_reclaim
            )
            short_signal = (
                rv is not None
                and rv >= cfg.rsi_short_min
                and candle.high >= upper_zone_bottom
                and candle.close >= (box_high - box_height * 0.30)
                and bearish_reject
            )

            if long_signal:
                position = open_position("LONG", candle, box_low, box_high, atr, cfg, balance, loss_streak)
            elif short_signal:
                position = open_position("SHORT", candle, box_low, box_high, atr, cfg, balance, loss_streak)

        mark_equity = balance
        if position is not None:
            if position.side == "LONG":
                unrealized = (candle.close - position.entry_price) * position.remaining_qty
            else:
                unrealized = (position.entry_price - candle.close) * position.remaining_qty
            mark_equity += position.realized_pnl - position.entry_fee_paid - position.funding_paid + unrealized
        equity_curve.append((candle.close_time, mark_equity))
        peak_equity = max(peak_equity, mark_equity)
        if peak_equity > 0:
            max_drawdown = max(max_drawdown, (peak_equity - mark_equity) / peak_equity * 100.0)

    if position is not None:
        last_candle = candles_15m[-1]
        realized_piece(position, position.remaining_qty, last_candle.close, cfg)
        total_pnl = position.realized_pnl - position.entry_fee_paid - position.funding_paid
        balance += total_pnl
        trades.append(
            {
                "side": position.side,
                "entry_time": fmt_ts(position.entry_time_ms),
                "exit_time": fmt_ts(last_candle.close_time),
                "entry_price": round(position.entry_price, 4),
                "exit_price": round(last_candle.close, 4),
                "qty": position.qty,
                "pnl_usd": round(total_pnl, 2),
                "pnl_pct_on_balance": round(total_pnl / max(balance - total_pnl, 1e-9) * 100.0, 2),
                "bars_held": position.bars_held,
                "funding_usd": round(position.funding_paid, 4),
                "reason": "EOD",
            }
        )

    wins = [t for t in trades if t["pnl_usd"] > 0]
    losses = [t for t in trades if t["pnl_usd"] <= 0]
    gross_profit = sum(t["pnl_usd"] for t in wins)
    gross_loss = abs(sum(t["pnl_usd"] for t in losses))
    avg_hold = statistics.mean(t["bars_held"] for t in trades) * 15 / 60 if trades else 0.0
    long_trades = [t for t in trades if t["side"] == "LONG"]
    short_trades = [t for t in trades if t["side"] == "SHORT"]

    recent_box = {
        "low": round(min(c.low for c in candles_4h[-cfg.box_lookback_4h:]), 4),
        "high": round(max(c.high for c in candles_4h[-cfg.box_lookback_4h:]), 4),
    }
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
        "avg_hold_hours": round(avg_hold, 2),
        "long_trades": len(long_trades),
        "short_trades": len(short_trades),
        "reason_counts": {
            key: sum(1 for t in trades if t["reason"] == key)
            for key in sorted({t["reason"] for t in trades})
        },
        "settings": {
            "leverage": cfg.leverage,
            "risk_per_trade_pct": cfg.risk_per_trade_pct,
            "max_margin_fraction": cfg.max_margin_fraction,
            "adx_max": cfg.adx_max,
            "rsi_long_max": cfg.rsi_long_max,
            "rsi_short_min": cfg.rsi_short_min,
            "entry_zone_fraction": cfg.entry_zone_fraction,
            "mid_no_trade_fraction": cfg.mid_no_trade_fraction,
            "max_hold_bars": cfg.max_hold_bars,
            "daily_loss_limit_pct": cfg.daily_loss_limit_pct,
        },
        "recent_box": recent_box,
        "latest_price": candles_15m[-1].close,
        "sample_trades": trades[-5:],
    }
    if cfg.include_equity_curve:
        report["equity_curve"] = equity_curve
    return report


def make_config(profile: str, days: int) -> Config:
    if profile not in PRESETS:
        raise ValueError(f"unknown profile: {profile}")
    cfg = Config(days=days, **PRESETS[profile])
    setattr(cfg, "_profile_name", profile)
    return cfg


def main() -> None:
    parser = argparse.ArgumentParser(description="XRP edge-fade range scalping backtest")
    parser.add_argument("--profile", choices=sorted(PRESETS), default="aggressive")
    parser.add_argument("--days", type=int, default=90)
    args = parser.parse_args()
    cfg = make_config(args.profile, args.days)
    report = backtest(cfg)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
