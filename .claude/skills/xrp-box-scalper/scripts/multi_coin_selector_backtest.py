#!/usr/bin/env python3
"""
Dynamic top-k selector overlay for multi-coin scalping backtests.

The selector scores each symbol using only data available before each UTC day
opens, then allocates the full portfolio equally across the top-k symbols for
that day.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from typing import Any, Callable


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import multi_coin_scalper_backtest as multi
import xrp_edge_fade_backtest as edge
import xrp_micro_scalp_backtest as micro


@dataclass
class EngineAdapter:
    build_cfg: Callable[[str, int, float], Any]
    load_market_data: Callable[[Any], Any]
    run: Callable[[Any, Any | None], dict[str, Any]]
    score_daily: Callable[[Any, Any], dict[str, float]]


@dataclass
class SymbolRun:
    symbol: str
    quote_volume: float
    report: dict[str, Any]
    daily_returns: dict[str, float]
    selector_scores: dict[str, float]


ADAPTERS: dict[str, EngineAdapter] = {
    "edge-best-return": EngineAdapter(
        build_cfg=multi.build_edge_best_return,
        load_market_data=edge.load_market_data,
        run=edge.backtest,
        score_daily=lambda cfg, data: edge_selector_scores(cfg, data),
    ),
    "edge-aggressive": EngineAdapter(
        build_cfg=multi.build_edge_aggressive,
        load_market_data=edge.load_market_data,
        run=edge.backtest,
        score_daily=lambda cfg, data: edge_selector_scores(cfg, data),
    ),
    "micro-baseline": EngineAdapter(
        build_cfg=multi.build_micro_baseline,
        load_market_data=micro.load_market_data,
        run=micro.backtest,
        score_daily=lambda cfg, data: micro_selector_scores(cfg, data),
    ),
    "micro-aggressive": EngineAdapter(
        build_cfg=multi.build_micro_aggressive,
        load_market_data=micro.load_market_data,
        run=micro.backtest,
        score_daily=lambda cfg, data: micro_selector_scores(cfg, data),
    ),
}


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def utc_day_key(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def iter_future_days(first_ts_ms: int, last_ts_ms: int) -> list[tuple[str, int]]:
    start_day = datetime.fromtimestamp(first_ts_ms / 1000, tz=timezone.utc).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    end_day = datetime.fromtimestamp(last_ts_ms / 1000, tz=timezone.utc).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    out: list[tuple[str, int]] = []
    day = start_day + timedelta(days=1)
    while day <= end_day:
        out.append((day.strftime("%Y-%m-%d"), int(day.timestamp() * 1000) - 1))
        day += timedelta(days=1)
    return out


def build_daily_returns(report: dict[str, Any]) -> dict[str, float]:
    curve = report.get("equity_curve") or []
    if not curve:
        return {}
    last_equity_by_day: dict[str, float] = {}
    for ts_ms, equity in curve:
        last_equity_by_day[utc_day_key(int(ts_ms))] = float(equity)
    returns: dict[str, float] = {}
    prev_equity = float(report["starting_balance"])
    for day_key in sorted(last_equity_by_day):
        equity = last_equity_by_day[day_key]
        returns[day_key] = (equity / prev_equity) - 1.0 if prev_equity else 0.0
        prev_equity = equity
    return returns


def selector_summary(
    name: str,
    starting_balance: float,
    days: list[str],
    day_returns: dict[str, float],
    selection_counts: Counter[str],
) -> dict[str, Any]:
    balance = starting_balance
    peak = balance
    max_drawdown = 0.0
    for day_key in days:
        balance *= 1.0 + day_returns[day_key]
        peak = max(peak, balance)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - balance) / peak * 100.0)
    top_symbols = [
        {"symbol": symbol, "days_selected": count}
        for symbol, count in selection_counts.most_common(5)
    ]
    return {
        "name": name,
        "days": len(days),
        "starting_balance": round(starting_balance, 2),
        "ending_balance": round(balance, 2),
        "net_pnl_usd": round(balance - starting_balance, 2),
        "return_pct": round((balance / starting_balance - 1.0) * 100.0, 2) if starting_balance else 0.0,
        "max_drawdown_pct": round(max_drawdown, 2),
        "avg_daily_return_pct": round(sum(day_returns[day] for day in days) / len(days) * 100.0, 3) if days else 0.0,
        "selection_counts": top_symbols,
    }


def edge_selector_scores(cfg: edge.Config, data: edge.MarketData) -> dict[str, float]:
    candles_15m = data.candles_15m
    candles_1h = data.candles_1h
    candles_4h = data.candles_4h
    adx_1h = edge.compute_adx(candles_1h, cfg.adx_period)
    out: dict[str, float] = {}
    h1_idx = 0
    h4_idx = 0
    for day_key, eval_ts_ms in iter_future_days(candles_15m[0].open_time, candles_15m[-1].close_time):
        h1_idx = edge.align_latest_index(candles_1h, eval_ts_ms, h1_idx)
        h4_idx = edge.align_latest_index(candles_4h, eval_ts_ms, h4_idx)
        if h1_idx < max(cfg.adx_period * 2, cfg.breakout_confirm_bars - 1):
            continue
        if h4_idx < cfg.box_lookback_4h - 1:
            continue
        recent_15m_idx = edge.align_latest_index(candles_15m, eval_ts_ms, 0)
        price = candles_15m[recent_15m_idx].close
        adx = adx_1h[h1_idx]
        if adx is None:
            continue
        box_slice = candles_4h[h4_idx - cfg.box_lookback_4h + 1 : h4_idx + 1]
        box_low = min(c.low for c in box_slice)
        box_high = max(c.high for c in box_slice)
        box_height = box_high - box_low
        if box_height <= 0:
            continue
        box_mid = (box_low + box_high) / 2.0
        box_width_pct = box_height / box_mid if box_mid else 0.0
        breakout = edge.confirmed_breakout(
            candles_1h,
            h1_idx,
            box_low,
            box_high,
            cfg.breakout_confirm_bars,
            cfg.breakout_margin,
        )
        if breakout is not None or not (box_low <= price <= box_high):
            continue
        width_center = (cfg.box_min_width_pct + cfg.box_max_width_pct) / 2.0
        width_span = max((cfg.box_max_width_pct - cfg.box_min_width_pct) / 2.0, 1e-9)
        width_score = clamp01(1.0 - abs(box_width_pct - width_center) / width_span)
        adx_score = clamp01(1.0 - (adx / max(cfg.adx_max, 1e-9)))
        edge_distance = min(abs(price - box_low), abs(box_high - price))
        edge_proximity = clamp01(1.0 - (edge_distance / (box_height * 0.5)))
        center_penalty = 0.35 if edge.in_center_zone(price, box_low, box_high, cfg.mid_no_trade_fraction) else 1.0
        out[day_key] = round((0.45 * adx_score + 0.30 * width_score + 0.25 * edge_proximity) * center_penalty, 6)
    return out


def micro_selector_scores(cfg: micro.Config, data: micro.MarketData) -> dict[str, float]:
    candles_1m = data.candles_1m
    candles_15m = data.candles_15m
    adx_15m = edge.compute_adx(candles_15m, cfg.adx_period)
    atr_1m = edge.compute_atr(candles_1m, cfg.atr_period)
    vwap_1m = micro.rolling_vwap(candles_1m, cfg.vwap_window)
    out: dict[str, float] = {}
    m1_idx = 0
    m15_idx = 0
    for day_key, eval_ts_ms in iter_future_days(candles_1m[0].open_time, candles_1m[-1].close_time):
        m1_idx = edge.align_latest_index(candles_1m, eval_ts_ms, m1_idx)
        m15_idx = edge.align_latest_index(candles_15m, eval_ts_ms, m15_idx)
        if m1_idx < max(cfg.vwap_window, cfg.atr_period + 2):
            continue
        if m15_idx < max(cfg.box_lookback_15m - 1, cfg.adx_period * 2):
            continue
        adx = adx_15m[m15_idx]
        atr = atr_1m[m1_idx]
        vwap = vwap_1m[m1_idx]
        if adx is None or atr is None or vwap is None or atr <= 0:
            continue
        box_slice = candles_15m[m15_idx - cfg.box_lookback_15m + 1 : m15_idx + 1]
        box_low = min(c.low for c in box_slice)
        box_high = max(c.high for c in box_slice)
        box_height = box_high - box_low
        if box_height <= 0:
            continue
        price = candles_1m[m1_idx].close
        box_mid = (box_low + box_high) / 2.0
        box_width_pct = box_height / box_mid if box_mid else 0.0
        breakout = micro.confirmed_breakout(candles_15m, m15_idx, box_low, box_high, 2, 0.0008)
        if breakout is not None or not (box_low <= price <= box_high):
            continue
        width_center = (cfg.box_min_width_pct + cfg.box_max_width_pct) / 2.0
        width_span = max((cfg.box_max_width_pct - cfg.box_min_width_pct) / 2.0, 1e-9)
        width_score = clamp01(1.0 - abs(box_width_pct - width_center) / width_span)
        adx_score = clamp01(1.0 - (adx / max(cfg.adx_max, 1e-9)))
        edge_distance = min(abs(price - box_low), abs(box_high - price))
        edge_proximity = clamp01(1.0 - (edge_distance / (box_height * 0.5)))
        vwap_dev = abs(price - vwap) / atr
        vwap_score = clamp01(vwap_dev / max(cfg.min_vwap_dev_atr, 1e-9) / 2.0)
        center_penalty = 0.40 if edge.in_center_zone(price, box_low, box_high, cfg.mid_no_trade_fraction) else 1.0
        out[day_key] = round((0.35 * adx_score + 0.25 * width_score + 0.20 * edge_proximity + 0.20 * vwap_score) * center_penalty, 6)
    return out


def run_symbol(
    adapter: EngineAdapter,
    symbol: str,
    days: int,
    balance_per_symbol: float,
    quote_volume: float,
) -> SymbolRun:
    cfg = adapter.build_cfg(symbol, days, balance_per_symbol)
    market_data = adapter.load_market_data(cfg)
    report = adapter.run(cfg, market_data)
    daily_returns = build_daily_returns(report)
    selector_scores = adapter.score_daily(cfg, market_data)
    report["quote_volume_usd"] = quote_volume
    return SymbolRun(
        symbol=symbol,
        quote_volume=quote_volume,
        report=report,
        daily_returns=daily_returns,
        selector_scores=selector_scores,
    )


def simulate_selector(
    symbol_runs: list[SymbolRun],
    top_k: int,
    starting_balance: float,
) -> dict[str, Any]:
    common_days: set[str] | None = None
    for run in symbol_runs:
        available = set(run.daily_returns) & set(run.selector_scores)
        common_days = available if common_days is None else common_days & available
    ordered_days = sorted(common_days or [])
    if not ordered_days:
        raise RuntimeError("selector has no common days across symbols")

    baseline_day_returns: dict[str, float] = {}
    selector_day_returns: dict[str, float] = {}
    selection_counts: Counter[str] = Counter()
    picks_by_day: dict[str, list[str]] = {}

    for day_key in ordered_days:
        candidates = sorted(
            (
                (run.selector_scores[day_key], run.symbol, run.daily_returns[day_key])
                for run in symbol_runs
                if day_key in run.selector_scores and day_key in run.daily_returns
            ),
            reverse=True,
        )
        if not candidates:
            continue
        selected = candidates[:top_k]
        picks_by_day[day_key] = [symbol for _, symbol, _ in selected]
        selection_counts.update(picks_by_day[day_key])
        baseline_day_returns[day_key] = sum(ret for _, _, ret in candidates) / len(candidates)
        selector_day_returns[day_key] = sum(ret for _, _, ret in selected) / len(selected)

    baseline = selector_summary("equal_weight_all", starting_balance, ordered_days, baseline_day_returns, Counter())
    selected = selector_summary(f"top_{top_k}_selector", starting_balance, ordered_days, selector_day_returns, selection_counts)
    selected["sample_picks"] = [{"day": day_key, "symbols": picks_by_day[day_key]} for day_key in ordered_days[-5:]]
    selected["days_beating_baseline"] = sum(
        1 for day_key in ordered_days if selector_day_returns[day_key] > baseline_day_returns[day_key]
    )
    return {
        "baseline": baseline,
        "selected": selected,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Dynamic top-k selector for multi-coin scalp backtests")
    parser.add_argument("--engine", choices=sorted(ADAPTERS), default="edge-best-return")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--universe", choices=["majors", "all"], default="majors")
    parser.add_argument("--symbols", type=str, default="")
    parser.add_argument("--max-symbols", type=int, default=8)
    parser.add_argument("--min-quote-volume", type=float, default=50_000_000.0)
    parser.add_argument("--min-age-days", type=int, default=180)
    parser.add_argument("--balance-per-symbol", type=float, default=2000.0)
    parser.add_argument("--top-k", type=str, default="1,2")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()

    if args.symbols:
        symbol_meta = [
            multi.SymbolMeta(symbol=symbol.strip().upper(), quote_volume=float("nan"), onboard_date=0)
            for symbol in args.symbols.split(",")
            if symbol.strip()
        ]
    else:
        symbol_meta = multi.fetch_symbol_meta(
            universe=args.universe,
            max_symbols=args.max_symbols,
            min_quote_volume=args.min_quote_volume,
            min_age_days=args.min_age_days,
        )

    adapter = ADAPTERS[args.engine]
    symbol_runs: list[SymbolRun] = []
    failures: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, len(symbol_meta) or 1))) as executor:
        futures = {
            executor.submit(
                run_symbol,
                adapter,
                meta.symbol,
                args.days,
                args.balance_per_symbol,
                meta.quote_volume,
            ): meta.symbol
            for meta in symbol_meta
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                symbol_runs.append(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": str(exc)})

    if not symbol_runs:
        raise RuntimeError("no symbol runs completed successfully")

    symbol_runs.sort(key=lambda item: item.quote_volume, reverse=True)
    top_k_values = sorted({max(1, int(raw.strip())) for raw in args.top_k.split(",") if raw.strip()})
    total_starting_balance = len(symbol_runs) * args.balance_per_symbol
    comparisons = [
        simulate_selector(symbol_runs, top_k, total_starting_balance)
        for top_k in top_k_values
    ]

    output = {
        "engine": args.engine,
        "days": args.days,
        "universe": [run.symbol for run in symbol_runs],
        "universe_size": len(symbol_runs),
        "failures": failures,
        "per_symbol": [
            {
                "symbol": run.symbol,
                "quote_volume_usd": round(run.quote_volume, 2) if run.quote_volume == run.quote_volume else None,
                "return_pct": run.report["return_pct"],
                "net_pnl_usd": run.report["net_pnl_usd"],
                "trade_count": run.report["trade_count"],
                "max_drawdown_pct": run.report["max_drawdown_pct"],
            }
            for run in sorted(symbol_runs, key=lambda item: item.report["return_pct"], reverse=True)
        ],
        "comparisons": comparisons,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
