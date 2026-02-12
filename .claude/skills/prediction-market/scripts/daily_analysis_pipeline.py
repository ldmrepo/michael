#!/usr/bin/env python3
"""
Daily Analysis Pipeline for Polymarket Portfolio

Unified pipeline that orchestrates all analysis components:
sync positions, estimate probabilities, analyze portfolio,
run rebalancing, take snapshots, and generate unified reports.

Usage:
    python daily_analysis_pipeline.py                    # Full pipeline
    python daily_analysis_pipeline.py --telegram         # Telegram-formatted output
    python daily_analysis_pipeline.py --json             # JSON output
    python daily_analysis_pipeline.py --no-estimator     # Skip probability estimation
    python daily_analysis_pipeline.py --no-snapshot      # Skip snapshot
    python daily_analysis_pipeline.py --quick            # Analysis only, no rebalance
"""

import argparse
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import db_utils
from config import DB_PATH
from output_format import success, error, report
from polymarket_client import create_client

# Conditional imports for pipeline components
try:
    from estimate_true_probability import estimate_all_positions
    HAS_ESTIMATOR = True
except ImportError:
    HAS_ESTIMATOR = False

try:
    from analyze_portfolio import analyze_position, calc_portfolio_metrics
    HAS_ANALYZER = True
except ImportError:
    HAS_ANALYZER = False

try:
    from rebalance_engine import run_rebalance
    HAS_REBALANCER = True
except ImportError:
    HAS_REBALANCER = False

try:
    from track_performance import take_snapshot, compute_sharpe_like, compute_max_drawdown, ensure_snapshot_schema
    HAS_TRACKER = True
except ImportError:
    HAS_TRACKER = False


# === DB Schema for daily reports ===

DAILY_REPORTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS pm_daily_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date TEXT NOT NULL UNIQUE,
    report_text TEXT NOT NULL,
    report_json TEXT NOT NULL,
    created_at INTEGER DEFAULT (strftime('%s','now'))
);
"""


def ensure_daily_reports_schema(conn):
    """Create pm_daily_reports table if not exists"""
    conn.executescript(DAILY_REPORTS_SCHEMA)


# === Pipeline Steps ===

def step_sync_positions(conn, client) -> Dict:
    """Step 1: Sync positions from CLOB API and update current prices."""
    log("Step 1: Syncing positions...")

    positions = db_utils.get_positions(conn, status="open")

    if not positions:
        return {"status": "ok", "positions": 0, "message": "No open positions"}

    # Update current prices from Gamma API
    updated = 0
    for pos in positions:
        try:
            market = client.get_market(pos["market_id"])
            outcome_prices = market.get("outcomePrices", "[]")
            if isinstance(outcome_prices, str):
                outcome_prices = json.loads(outcome_prices)

            yes_price = float(outcome_prices[0]) if len(outcome_prices) > 0 else 0
            no_price = float(outcome_prices[1]) if len(outcome_prices) > 1 else 1.0 - yes_price

            current_price = yes_price if pos["side"] == "YES" else no_price

            conn.execute(
                "UPDATE pm_positions SET current_price = ? WHERE id = ?",
                (current_price, pos["id"])
            )
            updated += 1
            time.sleep(0.3)
        except Exception as e:
            log(f"  WARN: Failed to update price for {pos['market_id'][:20]}: {e}")

    conn.commit()
    log(f"  Synced {updated}/{len(positions)} positions")

    return {"status": "ok", "positions": len(positions), "updated": updated}


def step_estimate_probabilities(conn, client, save: bool = True) -> Dict:
    """Step 2: Estimate true probabilities using the estimator."""
    log("Step 2: Estimating true probabilities...")

    if not HAS_ESTIMATOR:
        log("  Estimator not available, skipping")
        return {"status": "skipped", "reason": "estimator not installed"}

    try:
        estimates = estimate_all_positions(conn, save=save)
        log(f"  Estimated {len(estimates)} positions")
        return {"status": "ok", "estimates": estimates}
    except Exception as e:
        log(f"  Estimation failed: {e}")
        return {"status": "error", "error": str(e)}


def step_analyze_portfolio(conn, client, estimates: Optional[Dict] = None) -> Dict:
    """Step 3: Run portfolio analysis with edge scoring."""
    log("Step 3: Analyzing portfolio...")

    if not HAS_ANALYZER:
        log("  Analyzer not available, skipping")
        return {"status": "skipped", "reason": "analyzer not installed"}

    positions = db_utils.get_positions(conn, status="open")
    if not positions:
        return {"status": "ok", "analyses": [], "portfolio": {"total_positions": 0}}

    # Build estimates lookup by market_id if available
    estimates_by_market = None
    if estimates and isinstance(estimates, dict) and estimates.get("status") == "ok":
        est_list = estimates.get("estimates", [])
        if isinstance(est_list, list):
            estimates_by_market = {}
            for est in est_list:
                mid = est.get("market_id", "")
                if mid:
                    estimates_by_market[mid] = est

    analyses = []
    for i, pos in enumerate(positions):
        try:
            analysis = analyze_position(pos, client, conn, estimates_by_market)
            if analysis:
                analyses.append(analysis)
        except Exception as e:
            log(f"  WARN: Analysis failed for {pos['market_id'][:20]}: {e}")
        if i < len(positions) - 1:
            time.sleep(0.3)

    # Get bankroll
    try:
        bankroll = client.get_balance_usdc()
        summary = db_utils.get_portfolio_summary(conn)
        bankroll += summary.get("total_invested", 0)
    except Exception:
        bankroll = 500

    portfolio = calc_portfolio_metrics(analyses, bankroll)

    log(f"  Analyzed {len(analyses)} positions")
    return {"status": "ok", "analyses": analyses, "portfolio": portfolio}


def step_run_rebalance(conn, client, use_estimator: bool = True) -> Dict:
    """Step 4: Run rebalancing engine."""
    log("Step 4: Running rebalancing engine...")

    if not HAS_REBALANCER:
        log("  Rebalancer not available, skipping")
        return {"status": "skipped", "reason": "rebalancer not installed"}

    try:
        result = run_rebalance(
            estimate_slippage_flag=False,
        )
        action_counts = {}
        for a in result.get("actions", []):
            act = a.get("action", "UNKNOWN")
            action_counts[act] = action_counts.get(act, 0) + 1

        log(f"  Rebalance complete: {action_counts}")
        return {"status": "ok", "result": result}
    except Exception as e:
        log(f"  Rebalance failed: {e}")
        return {"status": "error", "error": str(e)}


def step_take_snapshot(conn, client) -> Dict:
    """Step 5: Take daily portfolio snapshot."""
    log("Step 5: Taking daily snapshot...")

    if not HAS_TRACKER:
        log("  Tracker not available, skipping")
        return {"status": "skipped", "reason": "tracker not installed"}

    try:
        ensure_snapshot_schema(conn)

        # Replicate snapshot logic without calling sys.exit via output_format
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        open_positions = db_utils.get_positions(conn, status="open")
        closed_positions = db_utils.get_positions(conn, status="closed")

        # Fetch current market prices
        market_cache = {}
        if open_positions:
            from track_performance import get_current_prices_for_positions, position_cost, position_current_price, position_value, position_unrealized_pnl
            market_cache = get_current_prices_for_positions(client, open_positions)

            total_invested = sum(position_cost(p) for p in open_positions)
            total_value = 0.0
            unrealized_pnl = 0.0
            for pos in open_positions:
                info = market_cache.get(pos["market_id"], {})
                cp = position_current_price(pos, info)
                total_value += position_value(pos, cp)
                unrealized_pnl += position_unrealized_pnl(pos, cp)
        else:
            total_invested = 0.0
            total_value = 0.0
            unrealized_pnl = 0.0

        realized_pnl = sum(p.get("pnl", 0) or 0 for p in closed_positions)
        cash_balance = client.get_balance_usdc()
        position_count = len(open_positions)

        prev = conn.execute(
            "SELECT deposited_total FROM pm_snapshots ORDER BY snapshot_date DESC LIMIT 1"
        ).fetchone()
        deposited_total = prev["deposited_total"] if prev else (total_invested + cash_balance)

        conn.execute("""
            INSERT INTO pm_snapshots (snapshot_date, total_invested, total_value, cash_balance,
                unrealized_pnl, realized_pnl, position_count, deposited_total)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(snapshot_date) DO UPDATE SET
                total_invested = excluded.total_invested,
                total_value = excluded.total_value,
                cash_balance = excluded.cash_balance,
                unrealized_pnl = excluded.unrealized_pnl,
                realized_pnl = excluded.realized_pnl,
                position_count = excluded.position_count,
                deposited_total = excluded.deposited_total,
                created_at = strftime('%s','now')
        """, (today, round(total_invested, 2), round(total_value, 2),
              round(cash_balance, 2), round(unrealized_pnl, 2),
              round(realized_pnl, 2), position_count, round(deposited_total, 2)))
        conn.commit()

        nav = total_value + cash_balance

        # Previous snapshot for daily change
        prev_snap = conn.execute(
            "SELECT * FROM pm_snapshots WHERE snapshot_date < ? ORDER BY snapshot_date DESC LIMIT 1",
            (today,)
        ).fetchone()

        daily_change = 0.0
        daily_change_pct = 0.0
        if prev_snap:
            prev_nav = prev_snap["total_value"] + prev_snap["cash_balance"]
            daily_change = nav - prev_nav
            daily_change_pct = (daily_change / prev_nav * 100) if prev_nav > 0 else 0.0

        log(f"  Snapshot: NAV=${nav:.2f}, change={daily_change:+.2f} ({daily_change_pct:+.1f}%)")

        return {
            "status": "ok",
            "date": today,
            "nav": round(nav, 2),
            "total_invested": round(total_invested, 2),
            "total_value": round(total_value, 2),
            "cash_balance": round(cash_balance, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "realized_pnl": round(realized_pnl, 2),
            "position_count": position_count,
            "daily_change": round(daily_change, 2),
            "daily_change_pct": round(daily_change_pct, 2),
        }
    except Exception as e:
        log(f"  Snapshot failed: {e}")
        return {"status": "error", "error": str(e)}


# === Report Generation ===

def generate_unified_report(
    snapshot: Dict,
    analysis: Dict,
    rebalance: Dict,
    estimates: Dict,
    telegram_format: bool = False,
) -> str:
    """Generate unified daily report combining all pipeline results."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if telegram_format:
        return _format_telegram(today, snapshot, analysis, rebalance, estimates)
    else:
        return _format_text(today, snapshot, analysis, rebalance, estimates)


def _format_text(today: str, snapshot: Dict, analysis: Dict, rebalance: Dict, estimates: Dict) -> str:
    """Format report as plain text."""
    lines = []
    lines.append(f"DAILY PORTFOLIO ANALYSIS ({today})")
    lines.append("=" * 60)
    lines.append("")

    # Portfolio Summary
    if snapshot.get("status") == "ok":
        nav = snapshot.get("nav", 0)
        change = snapshot.get("daily_change", 0)
        change_pct = snapshot.get("daily_change_pct", 0)
        sign = "+" if change >= 0 else ""

        lines.append("Portfolio Summary:")
        lines.append(f"  NAV: ${nav:.2f} ({sign}${change:.2f}, {sign}{change_pct:.1f}%)")
        lines.append(f"  Invested: ${snapshot.get('total_invested', 0):.2f} | Cash: ${snapshot.get('cash_balance', 0):.2f}")
        lines.append(f"  Positions: {snapshot.get('position_count', 0)} | Unrealized P&L: ${snapshot.get('unrealized_pnl', 0):+.2f}")
        lines.append("")

    # Top Movers (from analysis)
    if analysis.get("status") == "ok" and analysis.get("analyses"):
        analyses = analysis["analyses"]
        by_pnl = sorted(analyses, key=lambda a: a.get("pnl", 0), reverse=True)

        gainers = [a for a in by_pnl if a.get("pnl", 0) > 0][:3]
        losers = [a for a in by_pnl if a.get("pnl", 0) < 0][-3:][::-1]

        if gainers or losers:
            lines.append("Top Movers:")
            for a in gainers:
                lines.append(f"  + {a['question'][:50]}: ${a['pnl']:+.2f} ({a.get('pnl_pct', 0):+.1f}%)")
            for a in losers:
                lines.append(f"  - {a['question'][:50]}: ${a['pnl']:+.2f} ({a.get('pnl_pct', 0):+.1f}%)")
            lines.append("")

    # Edge Analysis
    if analysis.get("status") == "ok" and analysis.get("portfolio"):
        portfolio = analysis["portfolio"]
        lines.append("Edge Analysis:")
        lines.append(f"  Weighted Edge Score: {portfolio.get('weighted_edge_score', 0):+.1f}")
        lines.append(f"  Capital Efficiency: {portfolio.get('capital_efficiency_pct', 0):.0f}%")

        rec_dist = portfolio.get("recommendation_distribution", {})
        if rec_dist:
            parts = [f"{k}: {v}" for k, v in sorted(rec_dist.items())]
            lines.append(f"  Recommendations: {' | '.join(parts)}")
        lines.append("")

    # Estimator Quality
    if estimates.get("status") == "ok":
        est_list = estimates.get("estimates", [])
        if est_list:
            edges = [abs(e.get("edge", 0)) for e in est_list if isinstance(e, dict) and "edge" in e]
            confidences = [e.get("confidence", 0) for e in est_list if isinstance(e, dict) and "confidence" in e]

            if edges:
                lines.append("Estimator Quality:")
                lines.append(f"  Avg |Edge|: {sum(edges)/len(edges):.1f}%")
                if confidences:
                    lines.append(f"  Avg Confidence: {sum(confidences)/len(confidences):.2f}")
                strong_edge = sum(1 for e in edges if e > 5)
                lines.append(f"  Strong Edge (>5%): {strong_edge} positions")
                lines.append("")

    # Rebalancing Actions
    if rebalance.get("status") == "ok":
        result = rebalance.get("result", {})
        actions = result.get("actions", [])
        summary = result.get("summary", {})

        if actions:
            lines.append("Rebalancing Actions:")
            for action_type in ["EXIT", "REDUCE", "ADD", "HOLD"]:
                matching = [a for a in actions if a.get("action") == action_type]
                if matching and action_type != "HOLD":
                    names = ", ".join(a.get("question", "")[:30] for a in matching[:3])
                    lines.append(f"  {action_type} ({len(matching)}): {names}")
                elif action_type == "HOLD":
                    lines.append(f"  HOLD ({len(matching)}): Within parameters")
            lines.append("")

        # Risk Metrics
        if summary:
            lines.append("Risk Metrics:")
            hhi_before = summary.get("hhi_before", 0)
            hhi_after = summary.get("hhi_after", 0)
            lines.append(f"  HHI: {hhi_before:.0f} -> {hhi_after:.0f}" +
                         (" (improving)" if hhi_after < hhi_before else ""))
            lines.append(f"  Locked Capital: ${summary.get('locked_capital', 0):.2f}")
            lines.append("")

    # Snapshot risk metrics
    if snapshot.get("status") == "ok":
        try:
            conn = db_utils.get_connection()
            snapshots = [dict(r) for r in conn.execute(
                "SELECT * FROM pm_snapshots ORDER BY snapshot_date ASC"
            ).fetchall()]
            conn.close()

            if len(snapshots) >= 2:
                sharpe = compute_sharpe_like(snapshots)
                max_dd, current_dd = compute_max_drawdown(snapshots)
                lines.append("Historical Risk:")
                lines.append(f"  Sharpe-like: {sharpe:.2f}")
                lines.append(f"  Max Drawdown: {max_dd:.2f}%")
                lines.append(f"  Current Drawdown: {current_dd:.2f}%")
                lines.append("")
        except Exception:
            pass

    lines.append("=" * 60)
    return "\n".join(lines)


def _format_telegram(today: str, snapshot: Dict, analysis: Dict, rebalance: Dict, estimates: Dict) -> str:
    """Format report for Telegram (markdown-compatible, mobile-friendly)."""
    lines = []
    lines.append(f"*DAILY PORTFOLIO ANALYSIS ({today})*")
    lines.append("")

    # Portfolio Summary
    if snapshot.get("status") == "ok":
        nav = snapshot.get("nav", 0)
        change = snapshot.get("daily_change", 0)
        change_pct = snapshot.get("daily_change_pct", 0)
        sign = "+" if change >= 0 else ""
        arrow = "^" if change >= 0 else "v"

        lines.append(f"*Portfolio*: ${nav:.2f} ({sign}${change:.2f}, {sign}{change_pct:.1f}%)")
        lines.append(f"Invested: ${snapshot.get('total_invested', 0):.2f} | Cash: ${snapshot.get('cash_balance', 0):.2f}")
        lines.append(f"Positions: {snapshot.get('position_count', 0)}")
        lines.append("")

    # Top Movers
    if analysis.get("status") == "ok" and analysis.get("analyses"):
        analyses = analysis["analyses"]
        by_pnl = sorted(analyses, key=lambda a: a.get("pnl", 0), reverse=True)
        gainers = [a for a in by_pnl if a.get("pnl", 0) > 0][:2]
        losers = [a for a in by_pnl if a.get("pnl", 0) < 0][-2:][::-1]

        if gainers or losers:
            lines.append("*Movers*:")
            for a in gainers:
                lines.append(f"  {a['question'][:40]}: ${a['pnl']:+.2f}")
            for a in losers:
                lines.append(f"  {a['question'][:40]}: ${a['pnl']:+.2f}")
            lines.append("")

    # Rebalancing Actions (non-HOLD only)
    if rebalance.get("status") == "ok":
        actions = rebalance.get("result", {}).get("actions", [])
        non_hold = [a for a in actions if a.get("action") != "HOLD"]
        if non_hold:
            lines.append("*Actions*:")
            for a in non_hold[:5]:
                lines.append(f"  {a['action']}: {a.get('question', '')[:35]}")
            lines.append("")

    # Edge summary
    if analysis.get("status") == "ok" and analysis.get("portfolio"):
        portfolio = analysis["portfolio"]
        lines.append(f"*Edge*: {portfolio.get('weighted_edge_score', 0):+.1f} | Efficiency: {portfolio.get('capital_efficiency_pct', 0):.0f}%")

    return "\n".join(lines)


def save_report_to_db(conn, report_text: str, report_json: Dict):
    """Save daily report to pm_daily_reports table."""
    ensure_daily_reports_schema(conn)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    conn.execute("""
        INSERT INTO pm_daily_reports (report_date, report_text, report_json)
        VALUES (?, ?, ?)
        ON CONFLICT(report_date) DO UPDATE SET
            report_text = excluded.report_text,
            report_json = excluded.report_json,
            created_at = strftime('%s','now')
    """, (today, report_text, json.dumps(report_json, ensure_ascii=False)))
    conn.commit()


# === Logging ===

_verbose = True

def log(msg: str):
    """Print pipeline progress to stderr."""
    if _verbose:
        print(f"  {msg}", file=sys.stderr)


# === Main Pipeline ===

def run_pipeline(
    use_estimator: bool = True,
    take_snapshot_flag: bool = True,
    run_analysis: bool = True,
    run_rebalance_flag: bool = True,
    generate_report_flag: bool = True,
    save_estimates: bool = True,
    telegram_format: bool = False,
) -> Dict:
    """Run the full daily analysis pipeline.

    Each step handles its own errors gracefully.
    Returns a dict with results from all pipeline steps.
    """
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "steps": {},
    }

    conn = db_utils.get_connection()
    client = create_client()

    # Step 1: Sync positions
    try:
        results["steps"]["sync"] = step_sync_positions(conn, client)
    except Exception as e:
        results["steps"]["sync"] = {"status": "error", "error": str(e)}
        log(f"  Sync failed: {e}")

    # Step 2: Estimate probabilities
    estimates_result = {"status": "skipped"}
    if use_estimator and HAS_ESTIMATOR:
        try:
            estimates_result = step_estimate_probabilities(conn, client, save=save_estimates)
        except Exception as e:
            estimates_result = {"status": "error", "error": str(e)}
            log(f"  Estimation failed: {e}")
    results["steps"]["estimates"] = estimates_result

    # Step 3: Portfolio analysis
    analysis_result = {"status": "skipped"}
    if run_analysis:
        try:
            analysis_result = step_analyze_portfolio(conn, client, estimates_result)
        except Exception as e:
            analysis_result = {"status": "error", "error": str(e)}
            log(f"  Analysis failed: {e}")
    results["steps"]["analysis"] = analysis_result

    # Step 4: Rebalancing
    rebalance_result = {"status": "skipped"}
    if run_rebalance_flag:
        try:
            rebalance_result = step_run_rebalance(conn, client, use_estimator=use_estimator)
        except Exception as e:
            rebalance_result = {"status": "error", "error": str(e)}
            log(f"  Rebalance failed: {e}")
    results["steps"]["rebalance"] = rebalance_result

    # Step 5: Daily snapshot
    snapshot_result = {"status": "skipped"}
    if take_snapshot_flag:
        try:
            snapshot_result = step_take_snapshot(conn, client)
        except Exception as e:
            snapshot_result = {"status": "error", "error": str(e)}
            log(f"  Snapshot failed: {e}")
    results["steps"]["snapshot"] = snapshot_result

    # Step 6: Generate unified report
    if generate_report_flag:
        try:
            report_text = generate_unified_report(
                snapshot=snapshot_result,
                analysis=analysis_result,
                rebalance=rebalance_result,
                estimates=estimates_result,
                telegram_format=telegram_format,
            )
            results["report"] = report_text
        except Exception as e:
            results["report"] = f"Report generation failed: {e}"
            log(f"  Report generation failed: {e}")

    # Step 7: Save report to DB
    if generate_report_flag and "report" in results:
        try:
            save_report_to_db(conn, results["report"], results)
            log("Step 7: Report saved to DB")
        except Exception as e:
            log(f"  Report save failed: {e}")

    conn.close()
    return results


# === CLI ===

def main():
    global _verbose

    parser = argparse.ArgumentParser(description="Daily Analysis Pipeline")
    parser.add_argument("--telegram", action="store_true", help="Telegram-formatted output")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--no-estimator", action="store_true", help="Skip probability estimation")
    parser.add_argument("--no-snapshot", action="store_true", help="Skip daily snapshot")
    parser.add_argument("--no-rebalance", action="store_true", help="Skip rebalancing")
    parser.add_argument("--quick", action="store_true", help="Analysis only, no rebalance or snapshot")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")
    args = parser.parse_args()

    if args.quiet:
        _verbose = False

    try:
        result = run_pipeline(
            use_estimator=not args.no_estimator,
            take_snapshot_flag=not args.no_snapshot and not args.quick,
            run_analysis=True,
            run_rebalance_flag=not args.no_rebalance and not args.quick,
            generate_report_flag=True,
            save_estimates=not args.no_estimator,
            telegram_format=args.telegram,
        )
    except Exception as e:
        error(f"Pipeline failed: {e}", code="PIPELINE_ERROR")
        return

    if args.json:
        # Strip non-serializable data for JSON output
        clean_result = {
            "timestamp": result.get("timestamp"),
            "report": result.get("report", ""),
            "steps": {},
        }
        for step_name, step_data in result.get("steps", {}).items():
            clean_result["steps"][step_name] = {
                "status": step_data.get("status", "unknown"),
            }
            # Include key metrics
            if step_name == "snapshot" and step_data.get("status") == "ok":
                for key in ["nav", "daily_change", "daily_change_pct", "position_count", "cash_balance"]:
                    if key in step_data:
                        clean_result["steps"][step_name][key] = step_data[key]
            elif step_name == "analysis" and step_data.get("status") == "ok":
                portfolio = step_data.get("portfolio", {})
                clean_result["steps"][step_name]["portfolio"] = {
                    "total_positions": portfolio.get("total_positions", 0),
                    "total_invested": portfolio.get("total_invested", 0),
                    "unrealized_pnl": portfolio.get("unrealized_pnl", 0),
                    "weighted_edge_score": portfolio.get("weighted_edge_score", 0),
                }
            elif step_name == "rebalance" and step_data.get("status") == "ok":
                rb_result = step_data.get("result", {})
                summary = rb_result.get("summary", {})
                clean_result["steps"][step_name]["actions_exit"] = summary.get("actions_exit", 0)
                clean_result["steps"][step_name]["actions_reduce"] = summary.get("actions_reduce", 0)
                clean_result["steps"][step_name]["actions_hold"] = summary.get("actions_hold", 0)
                clean_result["steps"][step_name]["actions_add"] = summary.get("actions_add", 0)

        success(clean_result, "pipeline_complete")
    else:
        report_text = result.get("report", "No report generated")
        report(report_text, data={
            "timestamp": result.get("timestamp"),
            "steps": {k: v.get("status", "unknown") for k, v in result.get("steps", {}).items()},
        })


if __name__ == "__main__":
    main()
