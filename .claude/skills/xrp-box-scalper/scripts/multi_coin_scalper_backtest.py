#!/usr/bin/env python3
"""
Multi-coin scalping portfolio backtest.

This script scans a liquid Binance Futures universe, runs a selected engine on
each symbol, and aggregates the results into an equal-weight sleeve portfolio.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any, Callable


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import xrp_edge_fade_backtest as edge
import xrp_micro_scalp_backtest as micro


MAJOR_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "BNBUSDT",
    "ADAUSDT",
    "SUIUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "LTCUSDT",
    "TRXUSDT",
]


@dataclass
class SymbolMeta:
    symbol: str
    quote_volume: float
    onboard_date: int


def fetch_symbol_meta(
    universe: str,
    max_symbols: int,
    min_quote_volume: float,
    min_age_days: int,
) -> list[SymbolMeta]:
    exchange_info = edge.request_json("/fapi/v1/exchangeInfo", {})
    tickers = edge.request_json("/fapi/v1/ticker/24hr", {})
    ticker_map = {row["symbol"]: row for row in tickers}
    allowed = set(MAJOR_SYMBOLS) if universe == "majors" else None
    min_age_ms = min_age_days * 24 * 60 * 60 * 1000
    now_ms = int(time.time() * 1000)

    out: list[SymbolMeta] = []
    for row in exchange_info["symbols"]:
        symbol = row["symbol"]
        if row["status"] != "TRADING":
            continue
        if row["contractType"] != "PERPETUAL":
            continue
        if row["quoteAsset"] != "USDT":
            continue
        if allowed is not None and symbol not in allowed:
            continue
        onboard_date = int(row.get("onboardDate", now_ms))
        if now_ms - onboard_date < min_age_ms:
            continue
        ticker = ticker_map.get(symbol)
        if ticker is None:
            continue
        quote_volume = float(ticker.get("quoteVolume", 0.0))
        if quote_volume < min_quote_volume:
            continue
        out.append(SymbolMeta(symbol=symbol, quote_volume=quote_volume, onboard_date=onboard_date))

    out.sort(key=lambda item: item.quote_volume, reverse=True)
    return out[:max_symbols]


def compute_max_drawdown(curve: list[tuple[int, float]]) -> float:
    peak = 0.0
    max_drawdown = 0.0
    for _, equity in curve:
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak * 100.0)
    return max_drawdown


def aggregate_equity_curve(reports: list[dict[str, Any]]) -> list[tuple[int, float]]:
    curve_maps: list[dict[int, float]] = []
    common_timestamps: set[int] | None = None
    for report in reports:
        curve = report.get("equity_curve")
        if not curve:
            return []
        curve_map = {int(ts): float(eq) for ts, eq in curve}
        curve_maps.append(curve_map)
        timestamps = set(curve_map)
        common_timestamps = timestamps if common_timestamps is None else common_timestamps & timestamps
    if not common_timestamps:
        return []
    portfolio_curve: list[tuple[int, float]] = []
    for ts in sorted(common_timestamps):
        portfolio_curve.append((ts, sum(curve_map[ts] for curve_map in curve_maps)))
    return portfolio_curve


def build_edge_best_return(symbol: str, days: int, balance: float) -> edge.Config:
    cfg = edge.Config(
        symbol=symbol,
        days=days,
        starting_balance=balance,
        leverage=10.0,
        risk_per_trade_pct=1.2,
        max_margin_fraction=0.4,
        max_hold_bars=28,
        daily_loss_limit_pct=3.0,
        stop_atr_mult=0.6,
        trail_atr_mult=1.0,
        include_equity_curve=True,
    )
    setattr(cfg, "_profile_name", "best_return")
    return cfg


def build_edge_aggressive(symbol: str, days: int, balance: float) -> edge.Config:
    cfg = edge.make_config("aggressive", days)
    cfg.symbol = symbol
    cfg.starting_balance = balance
    cfg.include_equity_curve = True
    return cfg


def build_micro_baseline(symbol: str, days: int, balance: float) -> micro.Config:
    cfg = micro.make_config("baseline", days)
    cfg.symbol = symbol
    cfg.starting_balance = balance
    cfg.include_equity_curve = True
    return cfg


def build_micro_aggressive(symbol: str, days: int, balance: float) -> micro.Config:
    cfg = micro.make_config("aggressive", days)
    cfg.symbol = symbol
    cfg.starting_balance = balance
    cfg.include_equity_curve = True
    return cfg


ENGINE_BUILDERS: dict[str, tuple[Callable[[str, int, float], Any], Callable[[Any], dict[str, Any]]]] = {
    "edge-best-return": (build_edge_best_return, edge.backtest),
    "edge-aggressive": (build_edge_aggressive, edge.backtest),
    "micro-baseline": (build_micro_baseline, micro.backtest),
    "micro-aggressive": (build_micro_aggressive, micro.backtest),
}


def run_symbol(engine_name: str, symbol: str, days: int, balance: float) -> dict[str, Any]:
    build_cfg, runner = ENGINE_BUILDERS[engine_name]
    cfg = build_cfg(symbol, days, balance)
    report = runner(cfg)
    report["quote_volume_usd"] = None
    return report


def aggregate_reports(
    engine_name: str,
    symbol_meta: list[SymbolMeta],
    reports: list[dict[str, Any]],
    failures: list[dict[str, str]],
) -> dict[str, Any]:
    report_by_symbol = {report["symbol"]: report for report in reports}
    ordered_reports = [report_by_symbol[item.symbol] for item in symbol_meta if item.symbol in report_by_symbol]
    for item in symbol_meta:
        if item.symbol in report_by_symbol:
            report_by_symbol[item.symbol]["quote_volume_usd"] = round(item.quote_volume, 2)

    starting_balance = sum(report["starting_balance"] for report in ordered_reports)
    ending_balance = sum(report["ending_balance"] for report in ordered_reports)
    trade_count = sum(report["trade_count"] for report in ordered_reports)
    long_trades = sum(report["long_trades"] for report in ordered_reports)
    short_trades = sum(report["short_trades"] for report in ordered_reports)
    weighted_win_rate = 0.0
    if trade_count > 0:
        weighted_win_rate = sum(report["win_rate_pct"] * report["trade_count"] for report in ordered_reports) / trade_count

    portfolio_curve = aggregate_equity_curve(ordered_reports)
    portfolio_max_drawdown = compute_max_drawdown(portfolio_curve) if portfolio_curve else None
    avg_symbol_drawdown = sum(report["max_drawdown_pct"] for report in ordered_reports) / len(ordered_reports)
    best_symbol = max(ordered_reports, key=lambda report: report["return_pct"])
    worst_symbol = min(ordered_reports, key=lambda report: report["return_pct"])

    per_symbol = [
        {
            "symbol": report["symbol"],
            "quote_volume_usd": round(report["quote_volume_usd"], 2) if report["quote_volume_usd"] is not None else None,
            "return_pct": report["return_pct"],
            "net_pnl_usd": report["net_pnl_usd"],
            "trade_count": report["trade_count"],
            "win_rate_pct": report["win_rate_pct"],
            "max_drawdown_pct": report["max_drawdown_pct"],
            "long_trades": report["long_trades"],
            "short_trades": report["short_trades"],
        }
        for report in sorted(ordered_reports, key=lambda item: item["return_pct"], reverse=True)
    ]

    return {
        "engine": engine_name,
        "days": ordered_reports[0]["days"] if ordered_reports else None,
        "universe": [item.symbol for item in symbol_meta],
        "universe_size": len(ordered_reports),
        "failures": failures,
        "portfolio": {
            "starting_balance": round(starting_balance, 2),
            "ending_balance": round(ending_balance, 2),
            "net_pnl_usd": round(ending_balance - starting_balance, 2),
            "return_pct": round((ending_balance / starting_balance - 1.0) * 100.0, 2) if starting_balance else 0.0,
            "trade_count": trade_count,
            "avg_trades_per_symbol": round(trade_count / len(ordered_reports), 2) if ordered_reports else 0.0,
            "weighted_win_rate_pct": round(weighted_win_rate, 2),
            "long_trades": long_trades,
            "short_trades": short_trades,
            "portfolio_max_drawdown_pct": round(portfolio_max_drawdown, 2) if portfolio_max_drawdown is not None else None,
            "avg_symbol_drawdown_pct": round(avg_symbol_drawdown, 2) if ordered_reports else 0.0,
        },
        "best_symbol": {
            "symbol": best_symbol["symbol"],
            "return_pct": best_symbol["return_pct"],
            "trade_count": best_symbol["trade_count"],
        },
        "worst_symbol": {
            "symbol": worst_symbol["symbol"],
            "return_pct": worst_symbol["return_pct"],
            "trade_count": worst_symbol["trade_count"],
        },
        "per_symbol": per_symbol,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-coin scalping portfolio backtest")
    parser.add_argument(
        "--engine",
        choices=sorted(ENGINE_BUILDERS),
        default="edge-best-return",
    )
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--universe", choices=["majors", "all"], default="majors")
    parser.add_argument("--symbols", type=str, default="")
    parser.add_argument("--max-symbols", type=int, default=8)
    parser.add_argument("--min-quote-volume", type=float, default=50_000_000.0)
    parser.add_argument("--min-age-days", type=int, default=180)
    parser.add_argument("--balance-per-symbol", type=float, default=2000.0)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    if args.symbols:
        symbols = [symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip()]
        symbol_meta = [SymbolMeta(symbol=symbol, quote_volume=math.nan, onboard_date=0) for symbol in symbols]
    else:
        symbol_meta = fetch_symbol_meta(
            universe=args.universe,
            max_symbols=args.max_symbols,
            min_quote_volume=args.min_quote_volume,
            min_age_days=args.min_age_days,
        )

    reports: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, len(symbol_meta) or 1))) as executor:
        futures = {
            executor.submit(run_symbol, args.engine, item.symbol, args.days, args.balance_per_symbol): item.symbol
            for item in symbol_meta
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                reports.append(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": str(exc)})

    if not reports:
        raise RuntimeError("no symbol backtests completed successfully")

    summary = aggregate_reports(args.engine, symbol_meta, reports, failures)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
