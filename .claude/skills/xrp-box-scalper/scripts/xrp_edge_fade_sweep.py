#!/usr/bin/env python3
"""
Parameter sweep for the XRP edge-fade range scalper.

Loads Binance Futures data once, then evaluates a compact search space to find
higher-return candidates and risk-adjusted alternatives.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import xrp_edge_fade_backtest as bt


SEARCH_SPACE: dict[str, list[float | int]] = {
    "leverage": [8.0, 10.0, 12.0],
    "risk_per_trade_pct": [0.8, 1.0, 1.2],
    "max_margin_fraction": [0.35, 0.40, 0.50],
    "max_hold_bars": [20, 24, 28],
    "daily_loss_limit_pct": [3.0, 4.0],
    "stop_atr_mult": [0.60, 0.75],
    "trail_atr_mult": [1.00, 1.15],
}


def build_candidates(limit: int | None = None) -> list[dict[str, float | int]]:
    keys = list(SEARCH_SPACE)
    candidates: list[dict[str, float | int]] = []
    for values in itertools.product(*(SEARCH_SPACE[k] for k in keys)):
        candidate = dict(zip(keys, values))
        # Skip obviously unstable combos.
        if candidate["risk_per_trade_pct"] >= 1.2 and candidate["max_margin_fraction"] >= 0.50:
            continue
        if candidate["leverage"] >= 12.0 and candidate["risk_per_trade_pct"] >= 1.2:
            continue
        if candidate["stop_atr_mult"] > candidate["trail_atr_mult"]:
            continue
        candidates.append(candidate)
        if limit and len(candidates) >= limit:
            break
    return candidates


def score(report: dict) -> float:
    ret = report["return_pct"]
    mdd = report["max_drawdown_pct"]
    pf = report["profit_factor"] or 0.0
    trades = report["trade_count"]
    return ret - (mdd * 0.75) + min(pf, 5.0) * 0.25 + min(trades, 20) * 0.03


def run(days: int, top_n: int, candidate_limit: int | None) -> dict:
    base_cfg = bt.make_config("aggressive", days)
    market_data = bt.load_market_data(base_cfg)
    candidates = build_candidates(candidate_limit)

    results: list[dict] = []
    for idx, overrides in enumerate(candidates, start=1):
        cfg_kwargs = {field: getattr(base_cfg, field) for field in base_cfg.__dataclass_fields__}
        cfg_kwargs.update(overrides)
        cfg = bt.Config(**cfg_kwargs)
        setattr(cfg, "_profile_name", f"sweep-{idx}")
        report = bt.backtest(cfg, market_data=market_data)
        report["candidate"] = overrides
        report["score"] = round(score(report), 2)
        results.append(report)

    by_return = sorted(results, key=lambda r: (r["return_pct"], -r["max_drawdown_pct"]), reverse=True)
    by_score = sorted(results, key=lambda r: (r["score"], r["return_pct"]), reverse=True)

    return {
        "days": days,
        "candidates_tested": len(results),
        "top_by_return": by_return[:top_n],
        "top_by_score": by_score[:top_n],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep XRP edge-fade backtest parameters")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--top", type=int, default=8)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    print(json.dumps(run(args.days, args.top, args.limit), indent=2))


if __name__ == "__main__":
    main()
