#!/usr/bin/env python3
"""
Portfolio EV Analyzer

Calculates Expected Value and edge scores for each position in the portfolio.
Provides actionable recommendations: HOLD, ADD, REDUCE, EXIT, REVIEW.

Usage:
  python analyze_portfolio.py              # Full analysis with pretty print
  python analyze_portfolio.py --json       # JSON output
  python analyze_portfolio.py --market-id <id>  # Analyze single market
  python analyze_portfolio.py --bankroll 500    # Override bankroll for Kelly sizing
  python analyze_portfolio.py --use-estimator  # Use multi-source probability estimator
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from output_format import success, error, report, table
from polymarket_client import create_client
from calculate_kelly import kelly_criterion, size_position
import db_utils

# Try to import the true probability estimator
try:
    from estimate_true_probability import estimate_all_positions
    HAS_ESTIMATOR = True
except ImportError:
    HAS_ESTIMATOR = False


# === Edge Score Calculation ===

def calc_trend_score(position: Dict, current_price: float, price_history: List[Dict]) -> float:
    """
    Trend score (-30 to +30): Is price moving toward or away from our position?
    Compares current price to entry price and recent price history.
    """
    side = position["side"]
    entry_price = position["entry_price"]

    # Basic: current vs entry
    if side == "YES":
        price_delta = current_price - entry_price
    else:
        # For NO positions, price falling = good for us
        price_delta = entry_price - current_price

    # Normalize: a 10-cent move is significant
    basic_trend = max(-30, min(30, price_delta * 150))

    # If we have price history, check recent direction (last few snapshots)
    if len(price_history) >= 2:
        recent_prices = [p.get("yes_price", 0) for p in price_history[:5] if p.get("yes_price")]
        if len(recent_prices) >= 2:
            # recent_prices[0] is most recent, recent_prices[-1] is oldest
            recent_delta = recent_prices[0] - recent_prices[-1]
            if side == "NO":
                recent_delta = -recent_delta
            momentum = max(-15, min(15, recent_delta * 100))
            basic_trend = max(-30, min(30, basic_trend * 0.6 + momentum * 0.4))

    return round(basic_trend, 1)


def calc_liquidity_score(volume: float, liquidity: float) -> float:
    """
    Liquidity score (-20 to +20): Higher liquidity = more efficient = harder to have edge.
    """
    total = volume + liquidity

    if total > 2_000_000:
        return -15  # Very high liquidity, market is very efficient
    elif total > 500_000:
        return -5   # High liquidity
    elif total > 100_000:
        return 0    # Medium liquidity
    elif total > 10_000:
        return 10   # Low liquidity, potential for mispricing
    else:
        return 15   # Very low liquidity, high mispricing potential (but also risky)


def calc_time_score(end_date_str: str) -> float:
    """
    Time score (-20 to +20): Days to expiry impact.
    """
    if not end_date_str:
        return 0  # Unknown expiry

    try:
        # Gamma API endDate has Z suffix (UTC)
        if end_date_str.endswith("Z"):
            end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        else:
            end_date = datetime.fromisoformat(end_date_str)
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        days_remaining = (end_date - now).total_seconds() / 86400

        if days_remaining < 0:
            return -20  # Already expired
        elif days_remaining < 1:
            return -20  # Less than 1 day, almost settled
        elif days_remaining < 7:
            return -10  # Less than a week
        elif days_remaining <= 30:
            return 0    # 1-4 weeks
        else:
            return 10   # More than a month, more uncertainty
    except (ValueError, TypeError):
        return 0


def calc_profit_score(position: Dict, current_price: float) -> float:
    """
    Profit score (-30 to +30): Current P&L performance.
    """
    side = position["side"]
    entry_price = position["entry_price"]
    size = position["size"]

    if side == "YES":
        pnl_per_contract = current_price - entry_price
    else:
        pnl_per_contract = (1 - current_price) - (1 - entry_price)
        # Simplifies to: entry_price - current_price... but for NO position value

    pnl_pct = pnl_per_contract / entry_price if entry_price > 0 else 0

    # Scale: 10% profit = +10, 20%+ = +20, losses mirror
    score = pnl_pct * 100  # 1% PnL = 1 point
    return round(max(-30, min(30, score)), 1)


def calc_edge_score(
    position: Dict,
    current_price: float,
    volume: float,
    liquidity: float,
    end_date: str,
    price_history: List[Dict],
) -> Dict:
    """Calculate composite edge score and component breakdown."""
    trend = calc_trend_score(position, current_price, price_history)
    liq = calc_liquidity_score(volume, liquidity)
    time_s = calc_time_score(end_date)
    profit = calc_profit_score(position, current_price)

    total = round(trend + liq + time_s + profit, 1)

    return {
        "total": total,
        "trend_score": trend,
        "liquidity_score": liq,
        "time_score": time_s,
        "profit_score": profit,
    }


def get_recommendation(edge_score: float) -> str:
    """Map edge score to recommendation."""
    if edge_score > 30:
        return "ADD"
    elif edge_score > 10:
        return "HOLD"
    elif edge_score >= -10:
        return "REVIEW"
    elif edge_score >= -30:
        return "REDUCE"
    else:
        return "EXIT"


def days_until(end_date_str: str) -> Optional[float]:
    """Calculate days until end date."""
    if not end_date_str:
        return None
    try:
        if end_date_str.endswith("Z"):
            end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        else:
            end_date = datetime.fromisoformat(end_date_str)
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return round((end_date - now).total_seconds() / 86400, 1)
    except (ValueError, TypeError):
        return None


# === Portfolio-Level Metrics ===

def calc_portfolio_metrics(analyses: List[Dict], bankroll: float) -> Dict:
    """Calculate portfolio-level aggregate metrics."""
    if not analyses:
        return {
            "total_positions": 0,
            "total_invested": 0,
            "weighted_edge_score": 0,
            "capital_in_low_edge": 0,
            "capital_efficiency_pct": 0,
        }

    total_invested = sum(a["cost_basis"] for a in analyses)
    # Weighted edge score by position size
    if total_invested > 0:
        weighted_edge = sum(
            a["edge"]["total"] * a["cost_basis"] / total_invested
            for a in analyses
        )
    else:
        weighted_edge = 0

    # Capital in low-edge positions (edge_score between -10 and 10)
    low_edge_capital = sum(
        a["cost_basis"] for a in analyses
        if -10 <= a["edge"]["total"] <= 10
    )
    negative_edge_capital = sum(
        a["cost_basis"] for a in analyses
        if a["edge"]["total"] < -10
    )

    # Category/tag concentration
    tag_counts: Dict[str, int] = {}
    for a in analyses:
        for tag in a.get("tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    # Recommendations distribution
    rec_counts: Dict[str, int] = {}
    for a in analyses:
        rec = a["recommendation"]
        rec_counts[rec] = rec_counts.get(rec, 0) + 1

    # Unrealized PnL
    total_current_value = sum(a["current_value"] for a in analyses)
    unrealized_pnl = total_current_value - total_invested

    return {
        "total_positions": len(analyses),
        "total_invested": round(total_invested, 2),
        "total_current_value": round(total_current_value, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "unrealized_pnl_pct": round(unrealized_pnl / total_invested * 100, 2) if total_invested > 0 else 0,
        "weighted_edge_score": round(weighted_edge, 1),
        "capital_in_low_edge": round(low_edge_capital, 2),
        "capital_in_negative_edge": round(negative_edge_capital, 2),
        "capital_efficiency_pct": round(
            (1 - (low_edge_capital + negative_edge_capital) / total_invested) * 100, 1
        ) if total_invested > 0 else 0,
        "bankroll": bankroll,
        "tag_concentration": tag_counts,
        "recommendation_distribution": rec_counts,
    }


# === Main Analysis ===

def analyze_position(
    position: Dict,
    client: Any,
    conn: Any,
    estimates_by_market: Optional[Dict] = None,
) -> Optional[Dict]:
    """Analyze a single position. Returns analysis dict or None on failure."""
    market_id = position["market_id"]

    # Fetch live market data from Gamma API
    try:
        market = client.get_market(market_id)
    except Exception as e:
        return {
            "market_id": market_id,
            "error": f"Failed to fetch market: {e}",
            "question": "Unknown",
            "recommendation": "REVIEW",
            "edge": {"total": 0, "trend_score": 0, "liquidity_score": 0, "time_score": 0, "profit_score": 0},
        }

    # Parse market data
    question = market.get("question", "Unknown")[:80]
    end_date = market.get("endDate", "")
    volume = float(market.get("volume", 0) or 0)
    liquidity = float(market.get("liquidity", 0) or 0)
    tags_raw = market.get("tags", [])
    if isinstance(tags_raw, str):
        try:
            tags_raw = json.loads(tags_raw)
        except (json.JSONDecodeError, TypeError):
            tags_raw = []

    # Parse current prices
    prices_raw = market.get("outcomePrices", "")
    if isinstance(prices_raw, str):
        try:
            prices = json.loads(prices_raw)
        except (json.JSONDecodeError, TypeError):
            prices = []
    else:
        prices = prices_raw or []

    yes_price = float(prices[0]) if len(prices) > 0 else 0
    no_price = float(prices[1]) if len(prices) > 1 else (1 - yes_price if yes_price > 0 else 0)

    if position["side"] == "YES":
        current_price = yes_price
    else:
        current_price = no_price

    # Market implied probability (always YES price)
    market_implied_prob = yes_price

    # Get price history from local DB
    price_history = db_utils.get_price_history(conn, market_id, limit=10)

    # Calculate heuristic edge score (always computed as baseline)
    edge = calc_edge_score(
        position=position,
        current_price=yes_price,  # Always use YES price for consistency
        volume=volume,
        liquidity=liquidity,
        end_date=end_date,
        price_history=price_history,
    )

    # Check if estimator data is available for this market
    estimator_data = None
    if estimates_by_market and market_id in estimates_by_market:
        est = estimates_by_market[market_id]
        estimator_data = {
            "estimated_true_prob": est.get("estimated_true_prob"),
            "confidence": est.get("confidence"),
            "edge": est.get("edge"),
            "edge_pct": est.get("edge_pct"),
            "signal_breakdown": est.get("signal_breakdown", {}),
            "data_sources": est.get("data_sources", []),
        }
        # Override edge total with estimator's edge_pct for recommendation
        if estimator_data["edge_pct"] is not None:
            # Map estimator edge_pct to our edge score scale
            # estimator edge_pct is in percentage points (e.g., +5.0 means 5% edge)
            # Our heuristic edge scale is roughly -100 to +100
            edge["total"] = estimator_data["edge_pct"] * 10  # 5% edge -> 50 edge score

    recommendation = get_recommendation(edge["total"])

    # Position economics
    side = position["side"]
    entry_price = position["entry_price"]
    size = position["size"]
    cost_basis = entry_price * size

    if side == "YES":
        current_value = yes_price * size
        pnl = (yes_price - entry_price) * size
    else:
        current_value = no_price * size
        pnl = (no_price - (1 - entry_price)) * size
        # More accurately for NO: we paid (1-entry_YES_price) per contract,
        # current value is (1-current_YES_price) per contract
        # But entry_price in DB is the NO price we paid
        current_value = (1 - yes_price) * size
        pnl = ((1 - yes_price) - entry_price) * size

    pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0

    # Kelly calculation
    if estimator_data and estimator_data["estimated_true_prob"] is not None:
        # Use estimator's true probability directly
        estimated_prob = max(0.01, min(0.99, estimator_data["estimated_true_prob"]))
    else:
        # Fallback: heuristic shift from edge score
        estimated_shift = edge["total"] / 200  # +-50 edge = +-25% shift
        if side == "YES":
            estimated_prob = max(0.01, min(0.99, market_implied_prob + estimated_shift))
        else:
            estimated_prob = max(0.01, min(0.99, market_implied_prob - estimated_shift))

    kelly_result = kelly_criterion(estimated_prob, market_implied_prob)
    ev_per_dollar = kelly_result.get("expected_value_per_dollar", 0)

    # Days remaining
    days_left = days_until(end_date)

    result = {
        "market_id": market_id,
        "question": question,
        "side": side,
        "size": size,
        "entry_price": round(entry_price, 4),
        "current_price": round(current_price, 4),
        "market_implied_prob": round(market_implied_prob, 4),
        "cost_basis": round(cost_basis, 2),
        "current_value": round(current_value, 2),
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 1),
        "edge": edge,
        "ev_per_dollar": round(ev_per_dollar, 4),
        "recommendation": recommendation,
        "kelly": {
            "direction": kelly_result.get("direction", "NONE"),
            "fractional_kelly_pct": kelly_result.get("fractional_kelly_pct", 0),
            "edge_pct": kelly_result.get("edge_pct", 0),
        },
        "volume": round(volume, 0),
        "liquidity": round(liquidity, 0),
        "days_remaining": days_left,
        "end_date": end_date,
        "tags": tags_raw if isinstance(tags_raw, list) else [],
    }

    # Add estimator fields when available
    if estimator_data:
        result["estimated_true_prob"] = estimator_data["estimated_true_prob"]
        result["estimator_confidence"] = estimator_data["confidence"]
        result["signal_breakdown"] = estimator_data["signal_breakdown"]
        result["ev_per_dollar_estimated"] = round(ev_per_dollar, 4)
        result["data_sources"] = estimator_data["data_sources"]

    return result


def format_pretty_report(analyses: List[Dict], portfolio: Dict) -> str:
    """Format a pretty-printed text report."""
    lines = []
    lines.append("")
    lines.append("=" * 72)
    lines.append("  PORTFOLIO EV ANALYSIS")
    lines.append("=" * 72)

    # Portfolio summary
    lines.append("")
    lines.append(f"  Positions: {portfolio['total_positions']}  |  "
                 f"Invested: ${portfolio['total_invested']:,.2f}  |  "
                 f"Value: ${portfolio['total_current_value']:,.2f}  |  "
                 f"PnL: ${portfolio['unrealized_pnl']:+,.2f} ({portfolio['unrealized_pnl_pct']:+.1f}%)")
    lines.append(f"  Weighted Edge: {portfolio['weighted_edge_score']:+.1f}  |  "
                 f"Capital Efficiency: {portfolio['capital_efficiency_pct']:.0f}%  |  "
                 f"Bankroll: ${portfolio['bankroll']:,.2f}")

    # Recommendation distribution
    rec_dist = portfolio.get("recommendation_distribution", {})
    if rec_dist:
        rec_parts = [f"{k}: {v}" for k, v in sorted(rec_dist.items())]
        lines.append(f"  Recommendations: {' | '.join(rec_parts)}")

    lines.append("")
    lines.append("-" * 72)

    # Sort by edge score descending
    sorted_analyses = sorted(analyses, key=lambda a: a["edge"]["total"], reverse=True)

    for a in sorted_analyses:
        edge_total = a["edge"]["total"]
        rec = a["recommendation"]

        # Recommendation marker
        rec_marker = {
            "ADD": "[++]",
            "HOLD": "[ +]",
            "REVIEW": "[ ?]",
            "REDUCE": "[ -]",
            "EXIT": "[--]",
        }.get(rec, "[  ]")

        lines.append(f"  {rec_marker} {a['question']}")
        lines.append(f"       {a['side']} x{a['size']:.0f} @ ${a['entry_price']:.2f} -> ${a['current_price']:.2f}  "
                     f"PnL: ${a['pnl']:+.2f} ({a['pnl_pct']:+.1f}%)")

        # Show estimator-enhanced edge or heuristic edge
        if "estimated_true_prob" in a and a["estimated_true_prob"] is not None:
            est_prob = a["estimated_true_prob"]
            confidence = a.get("estimator_confidence", 0)
            lines.append(f"       Edge: {edge_total:+.1f} "
                         f"(est_prob:{est_prob:.2f} vs market:{a['market_implied_prob']:.2f}) "
                         f"confidence:{confidence:.1f}")
            # Signal breakdown
            signals = a.get("signal_breakdown", {})
            if signals:
                sig_parts = [f"{k}:{v:+.3f}" for k, v in signals.items()]
                lines.append(f"       Signals: {' '.join(sig_parts)}")
            lines.append(f"       EV/$ {a['ev_per_dollar']:+.4f}  "
                         f"-> {rec}")
        else:
            lines.append(f"       Edge: {edge_total:+.1f} "
                         f"(trend:{a['edge']['trend_score']:+.0f} "
                         f"liq:{a['edge']['liquidity_score']:+.0f} "
                         f"time:{a['edge']['time_score']:+.0f} "
                         f"profit:{a['edge']['profit_score']:+.0f})  "
                         f"EV/$ {a['ev_per_dollar']:+.4f}  "
                         f"-> {rec}")

        days = a.get("days_remaining")
        days_str = f"{days:.0f}d left" if days is not None else "no expiry"
        lines.append(f"       Vol: ${a['volume']:,.0f}  Liq: ${a['liquidity']:,.0f}  {days_str}")
        lines.append("")

    lines.append("=" * 72)

    # Action items
    exits = [a for a in analyses if a["recommendation"] == "EXIT"]
    reduces = [a for a in analyses if a["recommendation"] == "REDUCE"]
    adds = [a for a in analyses if a["recommendation"] == "ADD"]

    if exits or reduces or adds:
        lines.append("  ACTION ITEMS:")
        for a in exits:
            lines.append(f"    EXIT: {a['question']} (edge: {a['edge']['total']:+.1f})")
        for a in reduces:
            lines.append(f"    REDUCE: {a['question']} (edge: {a['edge']['total']:+.1f})")
        for a in adds:
            lines.append(f"    ADD: {a['question']} (edge: {a['edge']['total']:+.1f})")
        lines.append("=" * 72)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Portfolio EV Analyzer")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--market-id", type=str, default="",
                        help="Analyze a single market by ID")
    parser.add_argument("--bankroll", type=float, default=0,
                        help="Override bankroll for Kelly sizing (default: auto from balance)")
    parser.add_argument("--use-estimator", action="store_true",
                        help="Use multi-source true probability estimator for edge calculation")
    args = parser.parse_args()

    # Initialize
    try:
        conn = db_utils.get_connection()
    except Exception as e:
        error(f"Database connection failed: {e}", code="DB_ERROR")
        return

    try:
        client = create_client()
    except Exception as e:
        error(f"Client initialization failed: {e}", code="CLIENT_ERROR")
        return

    # Get positions
    if args.market_id:
        positions = [
            p for p in db_utils.get_positions(conn) if p["market_id"] == args.market_id
        ]
        if not positions:
            error(f"No open position found for market: {args.market_id}", code="NOT_FOUND")
            return
    else:
        positions = db_utils.get_positions(conn)

    if not positions:
        if args.json:
            success(data={"positions": [], "portfolio": {"total_positions": 0}},
                    message="No open positions")
        else:
            print("\nNo open positions found.")
        return

    # Load estimator data if requested
    estimates_by_market = None
    if args.use_estimator:
        if not HAS_ESTIMATOR:
            print("  [WARN] --use-estimator requested but estimate_true_probability module not found. "
                  "Falling back to heuristic.", file=sys.stderr)
        else:
            try:
                estimates = estimate_all_positions(conn)
                estimates_by_market = {
                    e["market_id"]: e for e in estimates.get("estimates", [])
                }
                print(f"  Loaded estimator data for {len(estimates_by_market)} markets", file=sys.stderr)
            except Exception as e:
                print(f"  [WARN] Estimator failed: {e}. Falling back to heuristic.", file=sys.stderr)

    # Determine bankroll
    bankroll = args.bankroll
    if bankroll <= 0:
        try:
            bankroll = client.get_balance_usdc()
            # Add invested capital for total bankroll
            summary = db_utils.get_portfolio_summary(conn)
            bankroll += summary.get("total_invested", 0)
        except Exception:
            bankroll = 500  # Fallback default

    # Analyze each position
    analyses = []
    for i, pos in enumerate(positions):
        analysis = analyze_position(pos, client, conn, estimates_by_market)
        if analysis:
            analyses.append(analysis)
        # Rate limiting between API calls
        if i < len(positions) - 1:
            time.sleep(0.3)

    # Portfolio metrics
    portfolio = calc_portfolio_metrics(analyses, bankroll)

    # Add estimator metadata to portfolio if used
    if estimates_by_market:
        portfolio["estimator_used"] = True
        # Calculate average confidence across positions that have estimator data
        confidences = [
            a["estimator_confidence"] for a in analyses
            if "estimator_confidence" in a and a["estimator_confidence"] is not None
        ]
        portfolio["avg_confidence"] = round(sum(confidences) / len(confidences), 2) if confidences else 0
        # Collect unique data sources
        all_sources = set()
        for a in analyses:
            for src in a.get("data_sources", []):
                all_sources.add(src)
        portfolio["data_sources"] = sorted(all_sources)
    else:
        portfolio["estimator_used"] = False

    # Output
    if args.json:
        success(data={
            "positions": analyses,
            "portfolio": portfolio,
        }, message=f"Analyzed {len(analyses)} positions")
    else:
        report_text = format_pretty_report(analyses, portfolio)
        report(report_text, data={
            "positions": analyses,
            "portfolio": portfolio,
        })


if __name__ == "__main__":
    main()
