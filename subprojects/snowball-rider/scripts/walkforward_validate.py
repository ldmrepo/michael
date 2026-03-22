#!/usr/bin/env python3
"""Walk-forward validation for Strategy B (3x 40% allocation).

Runs 4 sequential OOS windows to test strategy robustness across different
market regimes. Each window trains on expanding history and tests on held-out
future data.

Strategy B config:
  leverage=3, allocation=0.4, sl_pct=-60, tp_activation_pct=10
  ema_fast=12, ema_slow=26, rsi_period=21
  rsi_long_threshold=50, rsi_short_threshold=50
  tp_ema_fast=7, tp_ema_slow=14, tp_cross_days=2
  initial_capital=818, include_funding=True
"""

from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.dirname(__file__))

from backtest_btc_2x import (
    fetch_all_klines, filter_crashes, run_backtest, print_trades, Config, Trade
)


# ── Walk-forward windows ──
WINDOWS = [
    {
        "name": "Window 1 (Bear 2022)",
        "train_start": "2019-09",
        "train_end": "2021-12",
        "test_start": "2022-01",
        "test_end": "2022-12",
    },
    {
        "name": "Window 2 (Recovery 2023)",
        "train_start": "2019-09",
        "train_end": "2022-12",
        "test_start": "2023-01",
        "test_end": "2023-12",
    },
    {
        "name": "Window 3 (Bull 2024)",
        "train_start": "2019-09",
        "train_end": "2023-12",
        "test_start": "2024-01",
        "test_end": "2024-12",
    },
    {
        "name": "Window 4 (Recent 2025-2026)",
        "train_start": "2019-09",
        "train_end": "2024-12",
        "test_start": "2025-01",
        "test_end": "2026-03",
    },
]


def make_config() -> Config:
    """Strategy B configuration."""
    return Config(
        leverage=3,
        allocation=0.4,
        sl_pct=-60,
        tp_activation_pct=10,
        ema_fast=12,
        ema_slow=26,
        rsi_period=21,
        rsi_long_threshold=50.0,
        rsi_short_threshold=50.0,
        tp_ema_fast=7,
        tp_ema_slow=14,
        tp_cross_days=2,
        initial_capital=818.0,
        include_funding=True,
        fee_rate=0.0005,
        funding_rate_daily=0.0003,
    )


def date_in_range(date_str: str, start_month: str, end_month: str) -> bool:
    """Check if date YYYY-MM-DD falls within [start_month, end_month] inclusive.
    start_month/end_month are YYYY-MM format.
    """
    ym = date_str[:7]  # YYYY-MM
    return start_month <= ym <= end_month


def run_window_backtest(
    all_candles: list[dict],
    train_start: str,
    train_end: str,
    test_start: str,
    test_end: str,
    config: Config,
) -> dict:
    """Run backtest on test period with indicator warmup from training data.

    We feed the backtest engine ALL candles from train_start through test_end,
    but only count trades that ENTER during the test period.
    """
    # Filter candles: train_start through test_end
    warmup_and_test = [
        c for c in all_candles
        if date_in_range(c["date"], train_start, test_end)
    ]

    if not warmup_and_test:
        return {"total_trades": 0, "trades": [], "final_wallet": config.initial_capital,
                "total_return_pct": 0, "max_drawdown_pct": 0, "win_rate": 0,
                "winning_trades": 0, "losing_trades": 0, "cagr_pct": 0,
                "avg_win_pct": 0, "avg_loss_pct": 0, "avg_days_held": 0,
                "data_start": "", "data_end": "", "trade_start": "",
                "buy_and_hold_pct": 0, "best_trade_pct": 0, "worst_trade_pct": 0,
                "years": 0}

    # Run full backtest on the combined data
    full_result = run_backtest(warmup_and_test, config)

    # Filter: only keep trades that ENTERED during the test period
    test_trades = [
        t for t in full_result["trades"]
        if date_in_range(t.entry_date, test_start, test_end)
    ]

    # Recompute stats for test-period trades only
    winning = [t for t in test_trades if t.leveraged_pnl_pct > 0]
    losing = [t for t in test_trades if t.leveraged_pnl_pct <= 0]

    # Compute test-period return: chain the wallet changes from test trades
    # Start from the wallet value just before the first test trade
    if test_trades:
        test_start_wallet = test_trades[0].wallet_before
        test_end_wallet = test_trades[-1].wallet_after
        test_return = (test_end_wallet / test_start_wallet - 1) * 100 if test_start_wallet > 0 else 0
    else:
        test_start_wallet = config.initial_capital
        test_end_wallet = config.initial_capital
        test_return = 0

    # MaxDD only during test period
    # We need to re-derive this from the equity curve approach
    # For simplicity, compute max drawdown from the test trades' wallet series
    peak = test_start_wallet
    max_dd = 0.0
    for t in test_trades:
        if t.wallet_before > peak:
            peak = t.wallet_before
        # Check drawdown at worst point (wallet_after if loss)
        for w in [t.wallet_before, t.wallet_after]:
            if w > peak:
                peak = w
            dd = (peak - w) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

    return {
        "total_trades": len(test_trades),
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "win_rate": len(winning) / len(test_trades) * 100 if test_trades else 0,
        "test_start_wallet": test_start_wallet,
        "final_wallet": test_end_wallet,
        "total_return_pct": test_return,
        "max_drawdown_pct": max_dd,
        "avg_win_pct": sum(t.leveraged_pnl_pct for t in winning) / len(winning) if winning else 0,
        "avg_loss_pct": sum(t.leveraged_pnl_pct for t in losing) / len(losing) if losing else 0,
        "avg_days_held": sum(t.days_held for t in test_trades) / len(test_trades) if test_trades else 0,
        "best_trade_pct": max((t.leveraged_pnl_pct for t in test_trades), default=0),
        "worst_trade_pct": min((t.leveraged_pnl_pct for t in test_trades), default=0),
        "trades": test_trades,
        "test_start": test_start,
        "test_end": test_end,
    }


def main():
    print("=" * 80)
    print("  WALK-FORWARD VALIDATION — Strategy B")
    print("  3x Leverage | 40% Allocation | SL -60% | TP 10% EMA7/14 cross")
    print("  EMA 12/26 | RSI 21 (>50 long, <50 short)")
    print("  Initial: $818 | Crash excluded | Funding included")
    print("=" * 80)

    # Fetch & filter data
    candles = fetch_all_klines("BTCUSDT")
    filtered = filter_crashes(candles)
    print(f"  Total data: {len(filtered)} candles (crash days removed)")
    print(f"  Range: {filtered[0]['date']} to {filtered[-1]['date']}")

    config = make_config()
    window_results = []

    # ── Per-window OOS tests ──
    for w in WINDOWS:
        print(f"\n\n{'='*80}")
        print(f"  {w['name']}")
        print(f"  Train: {w['train_start']} to {w['train_end']}")
        print(f"  Test:  {w['test_start']} to {w['test_end']} (OOS)")
        print(f"{'='*80}")

        r = run_window_backtest(
            filtered,
            w["train_start"], w["train_end"],
            w["test_start"], w["test_end"],
            config,
        )
        window_results.append((w["name"], r))

        if r["total_trades"] == 0:
            print("  No trades in test period.")
            continue

        print(f"  Start Wallet: ${r['test_start_wallet']:,.2f}")
        print(f"  Final Wallet: ${r['final_wallet']:,.2f}")
        print(f"  Return:       {r['total_return_pct']:+.1f}%")
        print(f"  MaxDD:        {r['max_drawdown_pct']:.1f}%")
        print(f"  Trades:       {r['total_trades']} (W:{r['winning_trades']} L:{r['losing_trades']} WR:{r['win_rate']:.0f}%)")
        print(f"  Avg Win:      {r['avg_win_pct']:+.1f}%  Avg Loss: {r['avg_loss_pct']:+.1f}%")
        print(f"  Avg Hold:     {r['avg_days_held']:.0f} days")
        print(f"  Best Trade:   {r['best_trade_pct']:+.1f}%  Worst: {r['worst_trade_pct']:+.1f}%")

        # Trade list
        print(f"\n  {'#':>3} {'Entry':>10} {'Exit':>10} {'Side':>5} {'Entry$':>10} {'Exit$':>10} {'PnL%':>8} {'Days':>5} {'Wallet':>12} {'Reason'}")
        print(f"  {'---':>3} {'----------':>10} {'----------':>10} {'-----':>5} {'----------':>10} {'----------':>10} {'--------':>8} {'-----':>5} {'------------':>12} {'------'}")
        for idx, t in enumerate(r["trades"], 1):
            print(f"  {idx:3d} {t.entry_date:>10} {t.exit_date:>10} {t.side:>5} "
                  f"{t.entry_price:10.2f} {t.exit_price:10.2f} {t.leveraged_pnl_pct:+8.1f}% "
                  f"{t.days_held:5d} ${t.wallet_after:11,.2f} {t.exit_reason}")

    # ── FULL PERIOD BASELINE ──
    print(f"\n\n{'='*80}")
    print(f"  FULL PERIOD BASELINE (for comparison)")
    print(f"  Data: {filtered[0]['date']} to {filtered[-1]['date']}")
    print(f"{'='*80}")

    full_result = run_backtest(filtered, config)
    print(f"  Final:  ${full_result['final_wallet']:,.2f}  ({full_result['total_return_pct']:+,.1f}%)")
    print(f"  CAGR:   {full_result['cagr_pct']:+.1f}%")
    print(f"  MaxDD:  {full_result['max_drawdown_pct']:.1f}%")
    print(f"  Trades: {full_result['total_trades']} (W:{full_result['winning_trades']} L:{full_result['losing_trades']} WR:{full_result['win_rate']:.0f}%)")
    print(f"  Avg Win: {full_result['avg_win_pct']:+.1f}%  Avg Loss: {full_result['avg_loss_pct']:+.1f}%")
    print(f"  Avg Hold: {full_result['avg_days_held']:.0f} days")
    print(f"  B&H:    {full_result['buy_and_hold_pct']:+,.1f}%")
    print_trades(full_result)

    # ── SUMMARY TABLE ──
    print(f"\n\n{'='*80}")
    print(f"  WALK-FORWARD SUMMARY — Strategy B (3x 40%)")
    print(f"{'='*80}")
    print(f"  {'Window':<30} {'Trades':>7} {'WR':>6} {'Return':>10} {'MaxDD':>8} {'AvgWin':>8} {'AvgLoss':>8}")
    print(f"  {'-'*30} {'-'*7} {'-'*6} {'-'*10} {'-'*8} {'-'*8} {'-'*8}")

    total_trades_all = 0
    total_wins_all = 0
    positive_windows = 0

    for name, r in window_results:
        total_trades_all += r["total_trades"]
        total_wins_all += r["winning_trades"]
        if r["total_return_pct"] > 0:
            positive_windows += 1
        print(f"  {name:<30} {r['total_trades']:>7} {r['win_rate']:>5.0f}% {r['total_return_pct']:>+9.1f}% "
              f"{r['max_drawdown_pct']:>7.1f}% {r['avg_win_pct']:>+7.1f}% {r['avg_loss_pct']:>+7.1f}%")

    overall_wr = total_wins_all / total_trades_all * 100 if total_trades_all > 0 else 0
    print(f"\n  Overall OOS trades: {total_trades_all}")
    print(f"  Overall OOS win rate: {overall_wr:.0f}%")
    print(f"  Positive windows: {positive_windows}/{len(WINDOWS)}")
    print(f"\n  Full period baseline: {full_result['total_trades']} trades, "
          f"{full_result['win_rate']:.0f}% WR, {full_result['total_return_pct']:+,.1f}% return, "
          f"{full_result['max_drawdown_pct']:.1f}% MaxDD")

    # ── STABILITY CHECK ──
    print(f"\n\n{'='*80}")
    print(f"  STABILITY ASSESSMENT")
    print(f"{'='*80}")
    oos_returns = [r["total_return_pct"] for _, r in window_results]
    oos_wrs = [r["win_rate"] for _, r in window_results if r["total_trades"] > 0]

    if oos_returns:
        avg_return = sum(oos_returns) / len(oos_returns)
        min_return = min(oos_returns)
        max_return = max(oos_returns)
        print(f"  OOS Return range: {min_return:+.1f}% to {max_return:+.1f}%")
        print(f"  OOS Avg return:   {avg_return:+.1f}%")

    if oos_wrs:
        avg_wr = sum(oos_wrs) / len(oos_wrs)
        min_wr = min(oos_wrs)
        max_wr = max(oos_wrs)
        print(f"  OOS WR range:     {min_wr:.0f}% to {max_wr:.0f}%")
        print(f"  OOS Avg WR:       {avg_wr:.0f}%")

    # Pass/fail criteria
    degradation_threshold = 0.7  # OOS WR should be at least 70% of full-period WR
    full_wr = full_result["win_rate"]
    if full_wr > 0 and avg_wr >= full_wr * degradation_threshold:
        print(f"\n  PASS: OOS WR ({avg_wr:.0f}%) >= {degradation_threshold*100:.0f}% of full-period WR ({full_wr:.0f}%)")
    else:
        print(f"\n  WARN: OOS WR ({avg_wr:.0f}%) < {degradation_threshold*100:.0f}% of full-period WR ({full_wr:.0f}%)")

    if positive_windows >= 3:
        print(f"  PASS: {positive_windows}/4 windows profitable")
    else:
        print(f"  WARN: Only {positive_windows}/4 windows profitable")

    max_dd_all = max(r["max_drawdown_pct"] for _, r in window_results)
    if max_dd_all <= 40:
        print(f"  PASS: Max OOS drawdown ({max_dd_all:.1f}%) <= 40%")
    else:
        print(f"  WARN: Max OOS drawdown ({max_dd_all:.1f}%) > 40%")


if __name__ == "__main__":
    main()
