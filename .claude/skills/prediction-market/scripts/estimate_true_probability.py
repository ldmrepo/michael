#!/usr/bin/env python3
"""
Multi-Source Probability Estimation Engine

Estimates "true" probabilities for prediction market positions by combining
multiple data signals: price momentum, news sentiment, macro environment,
temporal convergence, and volume/liquidity.

Usage:
  python estimate_true_probability.py              # Pretty report
  python estimate_true_probability.py --json       # JSON output
  python estimate_true_probability.py --verbose    # Detailed signal breakdown
  python estimate_true_probability.py --save       # Save estimates to DB
  python estimate_true_probability.py --market-id <id>  # Single market
"""

import argparse
import json
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from config import DB_PATH, PROJECT_DATA_DIR
from output_format import success, error, report, table
import db_utils


# === Constants ===

# Keyword maps for matching markets to investment research categories
CRYPTO_KEYWORDS = {
    "btc", "bitcoin", "eth", "ethereum", "sol", "solana",
    "crypto", "cryptocurrency", "xrp", "ripple", "doge", "bnb",
}
ECONOMICS_KEYWORDS = {
    "fed", "federal reserve", "rate", "interest", "cpi", "inflation",
    "gdp", "unemployment", "treasury", "yield", "fomc",
}
SPORTS_KEYWORDS = {
    "olympics", "gold medals", "hockey", "football", "soccer",
    "champions league", "world cup", "nba", "nfl", "medal",
}

# Sentiment keywords for news analysis
POSITIVE_KEYWORDS = [
    "surge", "rally", "bullish", "gain", "rise", "soar", "jump",
    "boost", "positive", "strong", "growth", "up", "high", "record",
    "breakthrough", "win", "victory", "succeed", "approve", "pass",
]
NEGATIVE_KEYWORDS = [
    "crash", "plunge", "bearish", "drop", "fall", "decline", "sink",
    "loss", "negative", "weak", "recession", "down", "low", "fail",
    "reject", "block", "defeat", "collapse", "concern", "risk",
]


# === Schema for estimates table ===

ESTIMATES_SCHEMA = """
CREATE TABLE IF NOT EXISTS pm_probability_estimates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL,
    estimated_prob REAL NOT NULL,
    market_price REAL NOT NULL,
    edge REAL NOT NULL,
    confidence REAL NOT NULL,
    signals_json TEXT,
    created_at INTEGER DEFAULT (strftime('%s','now'))
);
CREATE INDEX IF NOT EXISTS idx_pm_estimates_market
    ON pm_probability_estimates(market_id, created_at DESC);
"""


# === Helpers ===

def extract_keywords(question: str) -> List[str]:
    """Extract meaningful keywords from a market question."""
    # Lowercase and strip punctuation
    text = question.lower()
    text = re.sub(r"[^\w\s$]", " ", text)

    # Remove common stop words
    stop_words = {
        "will", "the", "be", "a", "an", "in", "on", "at", "to", "of",
        "by", "for", "is", "it", "this", "that", "with", "from", "or",
        "and", "not", "do", "does", "before", "after", "above", "below",
        "between", "than", "more", "most", "least", "over", "under",
        "end", "yes", "no", "any", "each", "during",
    }
    words = [w.strip("$") for w in text.split() if len(w) > 2 and w not in stop_words]

    # Also preserve dollar amounts like "$100k", "$50k"
    dollar_amounts = re.findall(r"\$[\d,]+[kmb]?", question.lower())
    words.extend(dollar_amounts)

    return list(set(words))


def classify_market(question: str) -> str:
    """Classify a market into a category based on its question."""
    q_lower = question.lower()
    if any(kw in q_lower for kw in CRYPTO_KEYWORDS):
        return "crypto"
    if any(kw in q_lower for kw in ECONOMICS_KEYWORDS):
        return "economics"
    if any(kw in q_lower for kw in SPORTS_KEYWORDS):
        return "sports"
    return "general"


def parse_days_remaining(end_date_str: str) -> Optional[float]:
    """Parse end date and return days remaining."""
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
        return max(0, (end_date - now).total_seconds() / 86400)
    except (ValueError, TypeError):
        return None


# === Signal Functions ===

def calc_momentum_signal(
    price_history: List[Dict],
    current_yes_price: float,
) -> Tuple[float, str]:
    """
    Market Momentum Signal: -0.15 to +0.15 adjustment.
    Compare current price to 24h/72h moving average from pm_prices.
    """
    if not price_history or len(price_history) < 2:
        return 0.0, "insufficient price history"

    prices = [p["yes_price"] for p in price_history if p.get("yes_price")]
    if len(prices) < 2:
        return 0.0, "insufficient price data points"

    # Short-term MA (last ~5 snapshots ~ 24h if collected every 4-6h)
    short_window = min(5, len(prices))
    short_ma = sum(prices[:short_window]) / short_window

    # Long-term MA (last ~15 snapshots ~ 72h)
    long_window = min(15, len(prices))
    long_ma = sum(prices[:long_window]) / long_window

    # Deviation from short-term MA
    if short_ma > 0:
        short_deviation = (current_yes_price - short_ma) / short_ma
    else:
        short_deviation = 0

    # Deviation from long-term MA
    if long_ma > 0:
        long_deviation = (current_yes_price - long_ma) / long_ma
    else:
        long_deviation = 0

    # Combined momentum: weighted average
    momentum = short_deviation * 0.6 + long_deviation * 0.4

    # Scale to -0.15 to +0.15
    adjustment = max(-0.15, min(0.15, momentum * 1.5))

    # Detail string
    direction = "up" if adjustment > 0 else "down" if adjustment < 0 else "flat"
    pct = abs(adjustment) * 100
    detail = (
        f"{direction} {pct:.1f}% | "
        f"price={current_yes_price:.3f} "
        f"short_ma={short_ma:.3f} "
        f"long_ma={long_ma:.3f} "
        f"({len(prices)} snapshots)"
    )

    return round(adjustment, 4), detail


def calc_news_sentiment_signal(
    inv_conn: sqlite3.Connection,
    keywords: List[str],
    market_category: str,
) -> Tuple[float, str]:
    """
    News Sentiment Signal: -0.10 to +0.10 adjustment.
    Search investment_research for recent news matching market keywords.
    """
    # Get recent news (last 48 hours)
    cutoff = int(time.time()) - (48 * 3600)
    rows = inv_conn.execute(
        "SELECT data_json FROM investment_research WHERE category = 'news' AND collected_at > ? ORDER BY collected_at DESC LIMIT 5",
        (cutoff,),
    ).fetchall()

    if not rows:
        return 0.0, "no recent news data"

    # Parse all articles from the research entries
    all_articles = []
    for row in rows:
        try:
            data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            if isinstance(data, list):
                all_articles.extend(data)
            elif isinstance(data, dict) and "articles" in data:
                all_articles.extend(data["articles"])
        except (json.JSONDecodeError, TypeError):
            continue

    if not all_articles:
        return 0.0, "no parseable news articles"

    # Match articles to market keywords
    matched_articles = []
    for article in all_articles:
        title = (article.get("title", "") or "").lower()
        summary = (article.get("summary", "") or "").lower()
        text = title + " " + summary

        # Check if any keyword matches
        if any(kw in text for kw in keywords):
            matched_articles.append(article)

    if not matched_articles:
        return 0.0, f"0 matching articles (searched {len(all_articles)} total)"

    # Simple sentiment scoring
    positive_count = 0
    negative_count = 0
    for article in matched_articles:
        text = (
            (article.get("title", "") or "")
            + " "
            + (article.get("summary", "") or "")
        ).lower()
        pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in text)
        neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text)
        if pos > neg:
            positive_count += 1
        elif neg > pos:
            negative_count += 1

    total_matched = len(matched_articles)
    if total_matched == 0:
        return 0.0, "no matched articles"

    # Net sentiment ratio: -1.0 to +1.0
    sentiment_ratio = (positive_count - negative_count) / total_matched

    # Scale to -0.10 to +0.10
    adjustment = max(-0.10, min(0.10, sentiment_ratio * 0.10))

    detail = (
        f"{total_matched} matched articles | "
        f"positive={positive_count} negative={negative_count} | "
        f"sentiment={sentiment_ratio:+.2f}"
    )

    return round(adjustment, 4), detail


def calc_macro_signal(
    inv_conn: sqlite3.Connection,
    market_category: str,
) -> Tuple[float, str]:
    """
    Macro Environment Signal: -0.05 to +0.05 adjustment.
    For crypto: check Fed rate expectations, DXY movement.
    For economics: check recent FRED data.
    """
    # Get recent macro data (last 48 hours)
    cutoff = int(time.time()) - (48 * 3600)
    rows = inv_conn.execute(
        "SELECT data_json FROM investment_research WHERE category = 'macro' AND collected_at > ? ORDER BY collected_at DESC LIMIT 10",
        (cutoff,),
    ).fetchall()

    if not rows:
        return 0.0, "no recent macro data"

    # Parse FRED series data
    fed_rate = None
    dxy = None
    cpi = None

    for row in rows:
        try:
            data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            if isinstance(data, dict):
                series_name = data.get("series", "")
                observations = data.get("data", [])
                if observations and isinstance(observations, list):
                    latest = observations[0]
                    value = latest.get("value")
                    if value is not None:
                        if "fed_funds" in series_name.lower() or "fedfunds" in series_name.lower():
                            fed_rate = value
                        elif "dxy" in series_name.lower() or "dollar" in series_name.lower():
                            dxy = value
                        elif "cpi" in series_name.lower():
                            cpi = value
        except (json.JSONDecodeError, TypeError):
            continue

    # Also check market/sentiment data
    sentiment_rows = inv_conn.execute(
        "SELECT data_json FROM investment_research WHERE category = 'sentiment' AND collected_at > ? ORDER BY collected_at DESC LIMIT 1",
        (cutoff,),
    ).fetchall()

    fear_greed = None
    if sentiment_rows:
        try:
            data = json.loads(sentiment_rows[0][0]) if isinstance(sentiment_rows[0][0], str) else sentiment_rows[0][0]
            if isinstance(data, list) and data:
                fear_greed = data[0].get("value")
        except (json.JSONDecodeError, TypeError):
            pass

    adjustment = 0.0
    details = []

    if market_category == "crypto":
        # High fear = contrarian buy signal, extreme greed = sell signal
        if fear_greed is not None:
            if fear_greed < 25:
                adjustment += 0.02  # Extreme fear → contrarian positive
                details.append(f"fear_greed={fear_greed} (extreme fear)")
            elif fear_greed > 75:
                adjustment -= 0.02  # Extreme greed → contrarian negative
                details.append(f"fear_greed={fear_greed} (extreme greed)")
            else:
                details.append(f"fear_greed={fear_greed} (neutral)")

        # Strong DXY = negative for crypto
        if dxy is not None:
            details.append(f"dxy={dxy}")

    elif market_category == "economics":
        # Fed rate data
        if fed_rate is not None:
            details.append(f"fed_rate={fed_rate}")
        if cpi is not None:
            details.append(f"cpi={cpi}")
    else:
        details.append("non-macro market, neutral")

    adjustment = max(-0.05, min(0.05, adjustment))
    detail_str = " | ".join(details) if details else "no relevant macro signals"

    return round(adjustment, 4), detail_str


def calc_temporal_signal(
    days_remaining: Optional[float],
) -> Tuple[float, str]:
    """
    Temporal Convergence Signal: -0.05 to +0.05.
    As expiry approaches, market prices converge to true value,
    so reduce our confidence in any divergence from market price.
    """
    if days_remaining is None:
        return 0.0, "no expiry date"

    if days_remaining <= 0:
        return -0.05, "expired, market price is definitive"

    # Confidence factor: full confidence when >30 days, decreasing linearly
    confidence_factor = min(1.0, days_remaining / 30)

    # Near expiry → push our estimate toward market price (negative adjustment to edge)
    # This is expressed as a dampening factor, not an absolute adjustment
    # We return a negative adjustment that will reduce the magnitude of our total edge
    dampening = -0.05 * (1 - confidence_factor)

    detail = f"{days_remaining:.1f}d remaining | confidence_factor={confidence_factor:.2f}"

    return round(dampening, 4), detail


def calc_liquidity_signal(
    volume: float,
    liquidity: float,
    price_history: List[Dict],
) -> Tuple[float, str]:
    """
    Volume/Liquidity Signal: -0.05 to +0.05.
    Low liquidity = more likely mispriced (positive edge opportunity).
    High volume + stable price = efficient (less edge).
    """
    total_depth = volume + liquidity

    # Base adjustment from liquidity level
    if total_depth > 2_000_000:
        base = -0.03  # Very high liquidity, very efficient
    elif total_depth > 500_000:
        base = -0.01  # High liquidity
    elif total_depth > 100_000:
        base = 0.0    # Medium liquidity
    elif total_depth > 10_000:
        base = 0.02   # Low liquidity, mispricing potential
    else:
        base = 0.04   # Very low liquidity

    # Price stability from recent history (high stability + high volume = efficient)
    stability_adj = 0.0
    if len(price_history) >= 3:
        prices = [p["yes_price"] for p in price_history[:10] if p.get("yes_price")]
        if len(prices) >= 3:
            avg = sum(prices) / len(prices)
            if avg > 0:
                volatility = sum(abs(p - avg) for p in prices) / len(prices) / avg
                if volatility < 0.02 and total_depth > 500_000:
                    stability_adj = -0.02  # Very stable + liquid = efficient
                elif volatility > 0.10:
                    stability_adj = 0.02   # Volatile = potential mispricing

    adjustment = max(-0.05, min(0.05, base + stability_adj))

    detail = (
        f"vol=${volume:,.0f} liq=${liquidity:,.0f} | "
        f"depth_class={'high' if total_depth > 500_000 else 'medium' if total_depth > 100_000 else 'low'}"
    )

    return round(adjustment, 4), detail


# === Core Estimation ===

def estimate_market_probability(
    position: Dict,
    market_data: Dict,
    price_history: List[Dict],
    inv_conn: sqlite3.Connection,
    verbose: bool = False,
) -> Dict:
    """
    Estimate true probability for a single market position.
    Combines all signal sources into a weighted estimate.
    """
    market_id = position["market_id"]
    side = position["side"]
    question = market_data.get("question", "Unknown")

    # Parse current YES price
    prices_raw = market_data.get("outcomePrices", "")
    if isinstance(prices_raw, str):
        try:
            prices = json.loads(prices_raw)
        except (json.JSONDecodeError, TypeError):
            prices = []
    else:
        prices = prices_raw or []

    yes_price = float(prices[0]) if prices else 0
    market_price = yes_price  # Market's implied YES probability

    # Market metadata
    volume = float(market_data.get("volume", 0) or 0)
    liquidity = float(market_data.get("liquidity", 0) or 0)
    end_date = market_data.get("endDate", "")
    days_remaining = parse_days_remaining(end_date)

    # Classify market and extract keywords
    category = classify_market(question)
    keywords = extract_keywords(question)

    # === Calculate each signal ===
    momentum_adj, momentum_detail = calc_momentum_signal(price_history, yes_price)
    news_adj, news_detail = calc_news_sentiment_signal(inv_conn, keywords, category)
    macro_adj, macro_detail = calc_macro_signal(inv_conn, category)
    temporal_adj, temporal_detail = calc_temporal_signal(days_remaining)
    liquidity_adj, liquidity_detail = calc_liquidity_signal(volume, liquidity, price_history)

    # === Combine signals ===
    # Start from market price, apply adjustments
    raw_estimate = market_price + momentum_adj + news_adj + macro_adj + liquidity_adj

    # Apply temporal dampening: as expiry approaches, pull estimate toward market
    if days_remaining is not None:
        confidence_factor = min(1.0, days_remaining / 30)
        # Blend our estimate with market price based on temporal confidence
        raw_estimate = market_price + (raw_estimate - market_price) * confidence_factor

    # Clamp to valid probability range
    estimated_prob = max(0.01, min(0.99, raw_estimate))

    # Edge = our estimate minus market price
    edge = estimated_prob - market_price

    # For NO positions, the effective edge is inverted:
    # If YES is overpriced (edge < 0), that's good for NO holders
    if side == "NO":
        effective_edge = -edge
    else:
        effective_edge = edge

    # Confidence: how much we trust our own estimate (0 to 1)
    # Base confidence from data availability
    data_sources = 0
    if price_history and len(price_history) >= 2:
        data_sources += 1
    if news_adj != 0:
        data_sources += 1
    if macro_adj != 0:
        data_sources += 1

    # More data sources = higher base confidence
    base_confidence = min(0.8, 0.3 + data_sources * 0.15)

    # Temporal factor reduces confidence near expiry
    temporal_factor = min(1.0, (days_remaining or 30) / 30)
    confidence = round(base_confidence * temporal_factor, 2)

    # EV per dollar for the position's side
    if side == "YES":
        position_price = yes_price
        win_prob = estimated_prob
    else:
        position_price = 1 - yes_price
        win_prob = 1 - estimated_prob

    if position_price > 0:
        # EV = (win_prob * payout) - cost = win_prob * (1/position_price) - 1
        ev_per_dollar = (win_prob / position_price) - 1
    else:
        ev_per_dollar = 0

    signals = {
        "momentum": {"adjustment": momentum_adj, "detail": momentum_detail},
        "news_sentiment": {"adjustment": news_adj, "detail": news_detail},
        "macro": {"adjustment": macro_adj, "detail": macro_detail},
        "temporal": {"adjustment": temporal_adj, "detail": temporal_detail},
        "liquidity": {"adjustment": liquidity_adj, "detail": liquidity_detail},
    }

    return {
        "market_id": market_id,
        "question": question[:100],
        "side": side,
        "category": category,
        "keywords": keywords[:8],
        "market_price": round(market_price, 4),
        "estimated_true_prob": round(estimated_prob, 4),
        "edge": round(edge, 4),
        "effective_edge": round(effective_edge, 4),
        "edge_pct": round(edge * 100, 2),
        "confidence": confidence,
        "signals": signals,
        "ev_per_dollar": round(ev_per_dollar, 4),
        "days_remaining": round(days_remaining, 1) if days_remaining is not None else None,
        "volume": round(volume, 0),
        "liquidity": round(liquidity, 0),
    }


# === Output Formatting ===

def format_verbose_report(estimates: List[Dict], meta: Dict) -> str:
    """Format a detailed verbose report with signal breakdowns."""
    lines = []
    lines.append("")
    lines.append("=" * 76)
    lines.append("  PROBABILITY ESTIMATION ENGINE — DETAILED REPORT")
    lines.append("=" * 76)
    lines.append(f"  Positions analyzed: {meta['positions_analyzed']}  |  "
                 f"Avg confidence: {meta['avg_confidence']:.2f}  |  "
                 f"Data sources: {', '.join(meta['data_sources_used'])}")
    lines.append("")

    # Sort by absolute edge descending (biggest mispricings first)
    sorted_est = sorted(estimates, key=lambda e: abs(e["effective_edge"]), reverse=True)

    for est in sorted_est:
        edge_marker = ">>>" if est["effective_edge"] > 0.03 else "<<<" if est["effective_edge"] < -0.03 else "---"
        lines.append(f"  {edge_marker} {est['question']}")
        lines.append(f"      Side: {est['side']}  |  Category: {est['category']}  |  "
                     f"Keywords: {', '.join(est['keywords'][:5])}")
        lines.append(f"      Market price (YES): {est['market_price']:.4f}  |  "
                     f"Our estimate: {est['estimated_true_prob']:.4f}")
        lines.append(f"      Edge: {est['edge']:+.4f} ({est['edge_pct']:+.2f}%)  |  "
                     f"Effective edge: {est['effective_edge']:+.4f}  |  "
                     f"Confidence: {est['confidence']:.2f}")
        lines.append(f"      EV/dollar: {est['ev_per_dollar']:+.4f}  |  "
                     f"Days left: {est['days_remaining']:.0f}d" if est["days_remaining"] is not None else
                     f"      EV/dollar: {est['ev_per_dollar']:+.4f}  |  Days left: N/A")
        lines.append("")

        # Signal breakdown
        for signal_name, signal_data in est["signals"].items():
            adj = signal_data["adjustment"]
            adj_str = f"{adj:+.4f}" if adj != 0 else " 0.0000"
            lines.append(f"      [{adj_str}] {signal_name}: {signal_data['detail']}")
        lines.append("")
        lines.append("  " + "-" * 72)
        lines.append("")

    # Summary: opportunities
    opportunities = [e for e in estimates if e["effective_edge"] > 0.02]
    warnings = [e for e in estimates if e["effective_edge"] < -0.03]

    if opportunities:
        lines.append("  OPPORTUNITIES (positive effective edge > 2%):")
        for e in sorted(opportunities, key=lambda x: x["effective_edge"], reverse=True):
            lines.append(f"    + {e['question'][:60]}  edge={e['effective_edge']:+.4f}")
    if warnings:
        lines.append("  WARNINGS (negative effective edge > 3%):")
        for e in sorted(warnings, key=lambda x: x["effective_edge"]):
            lines.append(f"    - {e['question'][:60]}  edge={e['effective_edge']:+.4f}")

    lines.append("")
    lines.append("=" * 76)
    return "\n".join(lines)


def format_summary_report(estimates: List[Dict], meta: Dict) -> str:
    """Format a concise summary report."""
    lines = []
    lines.append("")
    lines.append("=" * 72)
    lines.append("  PROBABILITY ESTIMATES")
    lines.append("=" * 72)

    # Table
    headers = ["Market", "Side", "Mkt", "Est", "Edge", "Conf", "EV/$"]
    rows = []
    sorted_est = sorted(estimates, key=lambda e: abs(e["effective_edge"]), reverse=True)
    for est in sorted_est:
        rows.append([
            est["question"][:40],
            est["side"],
            f"{est['market_price']:.2f}",
            f"{est['estimated_true_prob']:.2f}",
            f"{est['effective_edge']:+.3f}",
            f"{est['confidence']:.2f}",
            f"{est['ev_per_dollar']:+.3f}",
        ])

    lines.append(table(headers, rows))
    lines.append("")
    lines.append(f"  Analyzed: {meta['positions_analyzed']}  |  "
                 f"Avg confidence: {meta['avg_confidence']:.2f}")
    lines.append("=" * 72)

    return "\n".join(lines)


# === Save to DB ===

def save_estimates(conn: sqlite3.Connection, estimates: List[Dict]) -> int:
    """Save estimates to pm_probability_estimates table."""
    conn.executescript(ESTIMATES_SCHEMA)
    saved = 0
    for est in estimates:
        conn.execute(
            "INSERT INTO pm_probability_estimates (market_id, estimated_prob, market_price, edge, confidence, signals_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                est["market_id"],
                est["estimated_true_prob"],
                est["market_price"],
                est["edge"],
                est["confidence"],
                json.dumps(est["signals"], ensure_ascii=False),
            ),
        )
        saved += 1
    conn.commit()
    return saved


# === Main ===

def main():
    parser = argparse.ArgumentParser(description="Multi-Source Probability Estimation Engine")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--verbose", action="store_true", help="Detailed signal breakdown")
    parser.add_argument("--save", action="store_true", help="Save estimates to DB")
    parser.add_argument("--market-id", type=str, default="", help="Analyze single market by ID")
    args = parser.parse_args()

    # Connect to prediction market DB
    try:
        conn = db_utils.get_connection()
    except Exception as e:
        error(f"Database connection failed: {e}", code="DB_ERROR")
        return

    # Connect to investment research DB (same memory.db)
    try:
        inv_conn = sqlite3.connect(str(DB_PATH))
        inv_conn.row_factory = sqlite3.Row
    except Exception as e:
        error(f"Investment DB connection failed: {e}", code="DB_ERROR")
        return

    # Initialize Gamma API client (read-only, no trading creds needed)
    try:
        from polymarket_client import create_client
        client = create_client()
    except Exception as e:
        error(f"Client initialization failed: {e}", code="CLIENT_ERROR")
        return

    # Get positions
    if args.market_id:
        positions = [p for p in db_utils.get_positions(conn) if p["market_id"] == args.market_id]
        if not positions:
            error(f"No open position found for market: {args.market_id}", code="NOT_FOUND")
            return
    else:
        positions = db_utils.get_positions(conn)

    if not positions:
        if args.json:
            success(data={"estimates": [], "meta": {"positions_analyzed": 0}},
                    message="No open positions")
        else:
            print("\nNo open positions found.")
        return

    # Analyze each position
    estimates = []
    data_sources_used = set(["pm_prices"])

    for i, pos in enumerate(positions):
        market_id = pos["market_id"]

        # Fetch live market data from Gamma API
        try:
            market_data = client.get_market(market_id)
        except Exception as e:
            estimates.append({
                "market_id": market_id,
                "question": "Failed to fetch",
                "side": pos["side"],
                "category": "unknown",
                "keywords": [],
                "market_price": 0,
                "estimated_true_prob": 0,
                "edge": 0,
                "effective_edge": 0,
                "edge_pct": 0,
                "confidence": 0,
                "signals": {},
                "ev_per_dollar": 0,
                "days_remaining": None,
                "volume": 0,
                "liquidity": 0,
                "error": str(e),
            })
            continue

        # Get price history from local DB
        price_history = db_utils.get_price_history(conn, market_id, limit=20)

        # Run estimation
        est = estimate_market_probability(
            position=pos,
            market_data=market_data,
            price_history=price_history,
            inv_conn=inv_conn,
            verbose=args.verbose,
        )
        estimates.append(est)

        # Track data sources
        if price_history:
            data_sources_used.add("pm_prices")
        # Check if investment research was used
        data_sources_used.add("investment_research")

        # Rate limiting between Gamma API calls
        if i < len(positions) - 1:
            time.sleep(0.3)

    # Build metadata
    confidences = [e["confidence"] for e in estimates if e.get("confidence", 0) > 0]
    meta = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "positions_analyzed": len(estimates),
        "data_sources_used": sorted(data_sources_used),
        "avg_confidence": round(sum(confidences) / len(confidences), 2) if confidences else 0,
    }

    # Save to DB if requested
    if args.save:
        valid_estimates = [e for e in estimates if e.get("market_price", 0) > 0]
        saved = save_estimates(conn, valid_estimates)
        meta["saved_to_db"] = saved

    # Close connections
    inv_conn.close()
    conn.close()

    # Output
    result_data = {"estimates": estimates, "meta": meta}

    if args.json:
        success(data=result_data, message=f"Estimated {len(estimates)} positions")
    elif args.verbose:
        report_text = format_verbose_report(estimates, meta)
        report(report_text, data=result_data)
    else:
        report_text = format_summary_report(estimates, meta)
        report(report_text, data=result_data)


if __name__ == "__main__":
    main()
