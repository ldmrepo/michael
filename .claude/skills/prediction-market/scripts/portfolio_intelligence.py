#!/usr/bin/env python3
"""
Portfolio Intelligence Engine

Aggregates multi-source research data (macro, sentiment, volume, momentum,
liquidity, news, on-chain) to compute Bayesian probability estimates and
Expected Value for every open prediction-market position.

Integrates with:
  - investment_research table (populated by collect_*.py scripts)
  - pm_positions / pm_prices / pm_markets tables (prediction-market skill)
  - Gamma API for live market data
  - Kelly criterion for optimal sizing

Usage:
  python portfolio_intelligence.py                    # Full report
  python portfolio_intelligence.py --json             # JSON output
  python portfolio_intelligence.py --market-id <id>   # Single market
  python portfolio_intelligence.py --include-binance   # Include Binance research
  python portfolio_intelligence.py --verbose           # Show signal breakdowns
"""

import argparse
import json
import math
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from output_format import success, error, report, table
from polymarket_client import create_client
from calculate_kelly import kelly_criterion, size_position
import db_utils
from config import DB_PATH, PROJECT_DATA_DIR


# ---------------------------------------------------------------------------
#  Constants & Configuration
# ---------------------------------------------------------------------------

SIGNAL_WEIGHTS: Dict[str, float] = {
    "macro": 0.15,
    "sentiment": 0.15,
    "volume": 0.10,
    "momentum": 0.20,
    "liquidity": 0.10,
    "news": 0.15,
    "onchain": 0.15,
}

# Mapping from investment_research categories to signal types
CATEGORY_TO_SIGNAL: Dict[str, str] = {
    "market": "sentiment",
    "derivatives": "volume",
    "macro": "macro",
    "sentiment": "sentiment",
    "etf": "macro",
    "news": "news",
    "onchain": "onchain",
}

# Keywords used to determine relevance of research to a market
CRYPTO_KEYWORDS = frozenset([
    "btc", "bitcoin", "eth", "ethereum", "crypto", "sol", "solana",
    "bnb", "xrp", "defi", "stablecoin", "altcoin", "token",
])

MACRO_KEYWORDS = frozenset([
    "fed", "fomc", "rate", "interest", "inflation", "cpi", "ppi",
    "gdp", "employment", "unemployment", "nonfarm", "payroll",
    "dxy", "dollar", "treasury", "yield", "m2", "monetary",
])

INTELLIGENCE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS pm_intelligence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    market_id TEXT NOT NULL,
    market_question TEXT,
    side TEXT,
    market_price REAL,
    estimated_prob REAL,
    edge_pct REAL,
    ev_per_dollar REAL,
    kelly_optimal_pct REAL,
    signal_breakdown TEXT,
    recommendation TEXT,
    confidence TEXT,
    created_at INTEGER DEFAULT (strftime('%s','now'))
);
"""


# ---------------------------------------------------------------------------
#  Database helpers
# ---------------------------------------------------------------------------

def ensure_intelligence_table(conn: sqlite3.Connection) -> None:
    """Create the pm_intelligence table if it does not exist."""
    conn.executescript(INTELLIGENCE_TABLE_SQL)


def get_latest_research_by_category(
    conn: sqlite3.Connection,
    category: str,
    hours: int = 48,
) -> List[Dict[str, Any]]:
    """Fetch the most recent research rows for *category* within *hours*."""
    cutoff = int(time.time()) - hours * 3600
    rows = conn.execute(
        "SELECT * FROM investment_research "
        "WHERE category = ? AND collected_at > ? "
        "ORDER BY collected_at DESC LIMIT 10",
        (category, cutoff),
    ).fetchall()
    return [dict(r) for r in rows]


def store_intelligence(
    conn: sqlite3.Connection,
    session_id: str,
    record: Dict[str, Any],
) -> None:
    """Insert one intelligence record."""
    conn.execute(
        "INSERT INTO pm_intelligence "
        "(session_id, market_id, market_question, side, market_price, "
        "estimated_prob, edge_pct, ev_per_dollar, kelly_optimal_pct, "
        "signal_breakdown, recommendation, confidence) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            session_id,
            record["market_id"],
            record.get("market_question", ""),
            record.get("side", ""),
            record.get("market_price", 0),
            record.get("estimated_prob", 0),
            record.get("edge_pct", 0),
            record.get("ev_per_dollar", 0),
            record.get("kelly_optimal_pct", 0),
            json.dumps(record.get("signal_breakdown", {}), ensure_ascii=False),
            record.get("recommendation", "HOLD"),
            record.get("confidence", "LOW"),
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
#  1. Multi-source Data Aggregation
# ---------------------------------------------------------------------------

def _is_crypto_related(question: str) -> bool:
    """Check whether a market question relates to crypto."""
    q_lower = question.lower()
    return any(kw in q_lower for kw in CRYPTO_KEYWORDS)


def _is_macro_related(question: str) -> bool:
    """Check whether a market question relates to macro economics."""
    q_lower = question.lower()
    return any(kw in q_lower for kw in MACRO_KEYWORDS)


def _parse_data_json(raw: str) -> Any:
    """Safely parse the data_json column."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _extract_fear_greed(data: Any) -> Optional[float]:
    """Extract Fear & Greed value from research data.

    Returns a normalised score in [-1, 1] where -1 = extreme fear, +1 = extreme greed.
    """
    if isinstance(data, list):
        # List of {value, classification, timestamp}
        if data and isinstance(data[0], dict) and "value" in data[0]:
            val = float(data[0]["value"])
            return (val - 50) / 50  # 0-100 -> -1..+1
    if isinstance(data, dict):
        # Could be nested under a key
        for key in ("fear_greed", "data", "value"):
            nested = data.get(key)
            if nested is not None:
                return _extract_fear_greed(nested)
    return None


def _extract_price_changes(data: Any) -> Dict[str, Optional[float]]:
    """Extract price change percentages from market research data."""
    result: Dict[str, Optional[float]] = {"1h": None, "24h": None, "7d": None}
    items = data if isinstance(data, list) else [data]
    for item in items:
        if not isinstance(item, dict):
            continue
        for src_key, dst_key in [
            ("change_1h", "1h"), ("change_24h", "24h"), ("change_7d", "7d"),
            ("price_change_percentage_1h_in_currency", "1h"),
            ("price_change_percentage_24h_in_currency", "24h"),
            ("price_change_percentage_7d_in_currency", "7d"),
        ]:
            val = item.get(src_key)
            if val is not None and result[dst_key] is None:
                try:
                    result[dst_key] = float(val)
                except (ValueError, TypeError):
                    pass
    return result


def _extract_macro_signal(data: Any) -> Optional[float]:
    """Extract a directional macro signal from FRED-like data.

    Returns a normalised score in [-1, 1].
    Positive means expansionary / supportive for risk assets.
    """
    if isinstance(data, dict):
        series_name = data.get("series", "")
        observations = data.get("data", [])
        if not observations or not isinstance(observations, list):
            return None

        # Use trend between most recent two observations
        values = []
        for obs in observations[:3]:
            v = obs.get("value")
            if v is not None:
                try:
                    values.append(float(v))
                except (ValueError, TypeError):
                    pass

        if len(values) < 2:
            return None

        delta = values[0] - values[1]

        # For rates / yields / DXY: rising is hawkish (negative for risk)
        hawkish_series = {"fed_funds", "dgs2", "dgs10", "dxy", "fedfunds", "t10y2y"}
        series_lower = series_name.lower().replace(" ", "_")
        if any(h in series_lower for h in hawkish_series):
            signal = -delta / max(abs(values[1]), 0.01)
        else:
            signal = delta / max(abs(values[1]), 0.01)

        return max(-1.0, min(1.0, signal))
    return None


def _extract_news_sentiment(data: Any) -> Optional[float]:
    """Derive a simple sentiment score from news articles.

    Returns [-1, 1]. Uses keyword-based heuristic (positive / negative words).
    """
    articles = data if isinstance(data, list) else []
    if not articles:
        return None

    positive_words = {"surge", "rally", "bullish", "gain", "rise", "up", "soar",
                      "breakout", "approve", "adoption", "inflow", "record"}
    negative_words = {"crash", "plunge", "bearish", "loss", "drop", "down", "fall",
                      "hack", "ban", "reject", "outflow", "fear", "sell-off", "selloff"}

    pos_count = 0
    neg_count = 0
    total = 0
    for art in articles[:20]:
        text = ""
        if isinstance(art, dict):
            text = (art.get("title", "") + " " + art.get("summary", "")).lower()
        elif isinstance(art, str):
            text = art.lower()
        if not text:
            continue
        total += 1
        words = set(text.split())
        pos_count += len(words & positive_words)
        neg_count += len(words & negative_words)

    if total == 0:
        return None

    raw = (pos_count - neg_count) / max(total, 1)
    return max(-1.0, min(1.0, raw / 3.0))  # normalise


def _extract_onchain_signal(data: Any) -> Optional[float]:
    """Extract on-chain signal from DeFi / DefiLlama data.

    Returns [-1, 1] based on TVL trend.
    """
    if isinstance(data, dict):
        protocols = data.get("protocols", [])
        if isinstance(protocols, list) and protocols:
            changes = []
            for p in protocols[:10]:
                if isinstance(p, dict):
                    c = p.get("change_1d")
                    if c is not None:
                        try:
                            changes.append(float(c))
                        except (ValueError, TypeError):
                            pass
            if changes:
                avg_change = sum(changes) / len(changes)
                return max(-1.0, min(1.0, avg_change / 10.0))
    return None


def _extract_volume_signal(data: Any) -> Optional[float]:
    """Extract volume / derivatives signal.

    Returns [-1, 1]. Rising volume / open interest is positive.
    """
    if isinstance(data, dict):
        for key in ("open_interest_change", "oi_change", "volume_change"):
            val = data.get(key)
            if val is not None:
                try:
                    return max(-1.0, min(1.0, float(val) / 20.0))
                except (ValueError, TypeError):
                    pass
    if isinstance(data, list):
        for item in data[:3]:
            result = _extract_volume_signal(item)
            if result is not None:
                return result
    return None


def aggregate_market_intelligence(
    conn: sqlite3.Connection,
    question: str,
    include_binance: bool = False,
) -> Dict[str, Optional[float]]:
    """Aggregate research signals relevant to a given market question.

    Returns a dict mapping signal name -> normalised score in [-1, 1] or None.
    """
    is_crypto = _is_crypto_related(question)
    is_macro = _is_macro_related(question)

    signals: Dict[str, Optional[float]] = {
        "macro": None,
        "sentiment": None,
        "volume": None,
        "momentum": None,
        "liquidity": None,
        "news": None,
        "onchain": None,
    }

    # --- Macro ---
    if is_crypto or is_macro:
        macro_rows = get_latest_research_by_category(conn, "macro")
        macro_scores: List[float] = []
        for row in macro_rows:
            parsed = _parse_data_json(row.get("data_json", ""))
            sig = _extract_macro_signal(parsed)
            if sig is not None:
                macro_scores.append(sig)
        if macro_scores:
            signals["macro"] = sum(macro_scores) / len(macro_scores)

    # --- Sentiment (Fear & Greed + smart money) ---
    if is_crypto:
        sent_rows = get_latest_research_by_category(conn, "sentiment")
        market_rows = get_latest_research_by_category(conn, "market")
        all_sentiment_rows = sent_rows + market_rows
        sent_scores: List[float] = []
        for row in all_sentiment_rows:
            parsed = _parse_data_json(row.get("data_json", ""))
            fg = _extract_fear_greed(parsed)
            if fg is not None:
                sent_scores.append(fg)
        if sent_scores:
            signals["sentiment"] = sum(sent_scores) / len(sent_scores)

    # --- Volume / Derivatives ---
    deriv_rows = get_latest_research_by_category(conn, "derivatives")
    vol_scores: List[float] = []
    for row in deriv_rows:
        parsed = _parse_data_json(row.get("data_json", ""))
        sig = _extract_volume_signal(parsed)
        if sig is not None:
            vol_scores.append(sig)
    if vol_scores:
        signals["volume"] = sum(vol_scores) / len(vol_scores)

    # --- Momentum (from market data price changes) ---
    if is_crypto:
        market_rows_m = get_latest_research_by_category(conn, "market")
        momentum_scores: List[float] = []
        for row in market_rows_m:
            parsed = _parse_data_json(row.get("data_json", ""))
            changes = _extract_price_changes(parsed)
            # Weight: 7d > 24h > 1h
            weighted: List[Tuple[float, float]] = []
            if changes["7d"] is not None:
                weighted.append((changes["7d"], 0.5))
            if changes["24h"] is not None:
                weighted.append((changes["24h"], 0.3))
            if changes["1h"] is not None:
                weighted.append((changes["1h"], 0.2))
            if weighted:
                total_w = sum(w for _, w in weighted)
                raw = sum(v * w for v, w in weighted) / total_w
                momentum_scores.append(max(-1.0, min(1.0, raw / 15.0)))
        if momentum_scores:
            signals["momentum"] = sum(momentum_scores) / len(momentum_scores)

    # --- News ---
    news_rows = get_latest_research_by_category(conn, "news")
    news_scores: List[float] = []
    for row in news_rows:
        parsed = _parse_data_json(row.get("data_json", ""))
        sig = _extract_news_sentiment(parsed)
        if sig is not None:
            news_scores.append(sig)
    if news_scores:
        signals["news"] = sum(news_scores) / len(news_scores)

    # --- On-chain ---
    if is_crypto:
        onchain_rows = get_latest_research_by_category(conn, "onchain")
        onchain_scores: List[float] = []
        for row in onchain_rows:
            parsed = _parse_data_json(row.get("data_json", ""))
            sig = _extract_onchain_signal(parsed)
            if sig is not None:
                onchain_scores.append(sig)
        if onchain_scores:
            signals["onchain"] = sum(onchain_scores) / len(onchain_scores)

    # --- ETF flows (mapped to macro) ---
    etf_rows = get_latest_research_by_category(conn, "etf")
    if etf_rows and signals["macro"] is None:
        for row in etf_rows:
            parsed = _parse_data_json(row.get("data_json", ""))
            if isinstance(parsed, dict):
                flow = parsed.get("net_flow") or parsed.get("total_flow")
                if flow is not None:
                    try:
                        normalised = max(-1.0, min(1.0, float(flow) / 500.0))
                        signals["macro"] = normalised
                    except (ValueError, TypeError):
                        pass

    return signals


# ---------------------------------------------------------------------------
#  2. Bayesian Probability Estimation
# ---------------------------------------------------------------------------

def estimate_true_probability(
    market_price: float,
    side: str,
    signals: Dict[str, Optional[float]],
) -> Tuple[float, float]:
    """Estimate the true probability using market price as prior and intelligence signals.

    Args:
        market_price: Current YES price (implied probability) from the market.
        side: "YES" or "NO" — the direction we hold.
        signals: Dict of signal_name -> normalised score [-1, 1] or None.

    Returns:
        (estimated_prob, confidence_weight) where estimated_prob is in [0.01, 0.99]
        and confidence_weight is in [0, 1] indicating how many signals contributed.
    """
    prior = market_price  # Market price is the prior (YES probability)

    # Convert prior to log-odds for Bayesian updating
    prior = max(0.01, min(0.99, prior))
    log_odds = math.log(prior / (1.0 - prior))

    available_signals = 0
    total_weight = 0.0
    total_adjustment = 0.0

    for signal_name, weight in SIGNAL_WEIGHTS.items():
        score = signals.get(signal_name)
        if score is None:
            continue
        available_signals += 1
        total_weight += weight

        # Each signal nudges the log-odds.
        # For a YES position, a positive signal is bullish.
        # For a NO position, a positive overall market signal is actually bearish
        # for our position (we want the event NOT to happen).
        # But we estimate the TRUE probability regardless of our side.
        # The signal represents whether the underlying event is more or less likely.
        # For crypto positions: positive signal = bullish for crypto = higher YES prob.
        # For macro positions: similar logic.

        # Scale: a full +1.0 signal shifts log-odds by ~0.3 (moderate Bayesian update)
        nudge = score * weight * 2.0  # max shift per signal ~0.3
        total_adjustment += nudge

    # Apply the adjustment (rescaled if not all signals are present)
    if total_weight > 0:
        # Renormalise so that available signals contribute proportionally
        scale_factor = sum(SIGNAL_WEIGHTS.values()) / total_weight
        # But cap the total adjustment to avoid extreme swings
        adjusted_log_odds = log_odds + total_adjustment * min(scale_factor, 2.0)
    else:
        adjusted_log_odds = log_odds

    # Convert back to probability
    estimated_prob = 1.0 / (1.0 + math.exp(-adjusted_log_odds))
    estimated_prob = max(0.01, min(0.99, estimated_prob))

    # Confidence: fraction of signals that were available
    confidence_weight = available_signals / len(SIGNAL_WEIGHTS) if SIGNAL_WEIGHTS else 0
    return estimated_prob, confidence_weight


# ---------------------------------------------------------------------------
#  3. Expected Value Calculator
# ---------------------------------------------------------------------------

def calculate_position_ev(
    side: str,
    size: float,
    entry_price: float,
    market_price: float,
    estimated_prob: float,
    bankroll: float,
    kelly_fraction: float = 0.5,
) -> Dict[str, Any]:
    """Calculate EV, edge, and Kelly-optimal size for a single position.

    Args:
        side: "YES" or "NO"
        size: Number of contracts held
        entry_price: Price paid per contract
        market_price: Current YES market price
        estimated_prob: Our Bayesian estimate of YES probability
        bankroll: Total available capital
        kelly_fraction: Fraction of Kelly to use (default 0.5 = half Kelly)

    Returns:
        Dictionary with EV metrics, Kelly sizing, and risk metrics.
    """
    # Current market-implied probability (YES price)
    yes_price = market_price
    no_price = 1.0 - market_price

    if side == "YES":
        cost_per_contract = yes_price
        payout_if_win = 1.0 - yes_price  # profit per contract on YES win
        prob_win = estimated_prob
    else:
        cost_per_contract = no_price
        payout_if_win = yes_price  # profit per contract on NO win
        prob_win = 1.0 - estimated_prob

    # EV per dollar invested
    # Buying at cost_per_contract, winning payout_if_win with prob prob_win
    ev_per_dollar = (prob_win * payout_if_win - (1.0 - prob_win) * cost_per_contract) / cost_per_contract \
        if cost_per_contract > 0 else 0

    # Edge: difference between estimated probability and market probability
    if side == "YES":
        edge = estimated_prob - yes_price
    else:
        edge = (1.0 - estimated_prob) - no_price

    edge_pct = edge * 100

    # Kelly criterion
    kelly_result = kelly_criterion(estimated_prob, yes_price, kelly_fraction)
    sized = size_position(kelly_result, bankroll)

    kelly_optimal_pct = kelly_result.get("fractional_kelly_pct", 0)

    # Risk-adjusted return (Sharpe-like): EV / sqrt(variance)
    # Variance of binary bet: prob_win * (1-prob_win) * (payout + cost)^2
    variance = prob_win * (1.0 - prob_win) * (payout_if_win + cost_per_contract) ** 2
    risk_adjusted = ev_per_dollar / math.sqrt(variance) if variance > 0 else 0

    # Current position economics
    cost_basis = entry_price * size
    if side == "YES":
        current_value = yes_price * size
    else:
        current_value = no_price * size
    unrealised_pnl = current_value - cost_basis
    pnl_pct = (unrealised_pnl / cost_basis * 100) if cost_basis > 0 else 0

    return {
        "ev_per_dollar": round(ev_per_dollar, 4),
        "edge": round(edge, 4),
        "edge_pct": round(edge_pct, 2),
        "kelly_optimal_pct": round(kelly_optimal_pct, 2),
        "kelly_direction": kelly_result.get("direction", "NONE"),
        "kelly_position_usd": sized.get("position_size_usd", 0),
        "risk_adjusted_return": round(risk_adjusted, 4),
        "cost_basis": round(cost_basis, 2),
        "current_value": round(current_value, 2),
        "unrealised_pnl": round(unrealised_pnl, 2),
        "pnl_pct": round(pnl_pct, 1),
    }


# ---------------------------------------------------------------------------
#  4. Recommendation Engine
# ---------------------------------------------------------------------------

def _determine_recommendation(
    edge_pct: float,
    ev_per_dollar: float,
    confidence: float,
    kelly_optimal_pct: float,
    pnl_pct: float,
) -> Tuple[str, str]:
    """Determine recommendation and confidence level.

    Returns:
        (recommendation, confidence_level) where recommendation is one of
        STRONG_BUY, BUY, HOLD, REDUCE, EXIT and confidence_level is
        HIGH, MEDIUM, or LOW.
    """
    # Confidence level based on signal availability
    if confidence >= 0.6:
        conf_label = "HIGH"
    elif confidence >= 0.3:
        conf_label = "MEDIUM"
    else:
        conf_label = "LOW"

    # Recommendation logic
    if edge_pct > 10 and ev_per_dollar > 0.10 and kelly_optimal_pct > 15:
        rec = "STRONG_BUY"
    elif edge_pct > 5 and ev_per_dollar > 0.05:
        rec = "BUY"
    elif edge_pct > -3 and ev_per_dollar > -0.05:
        rec = "HOLD"
    elif edge_pct > -8 or (pnl_pct < -20 and ev_per_dollar < -0.05):
        rec = "REDUCE"
    else:
        rec = "EXIT"

    # If confidence is LOW, downgrade aggressive recommendations
    if conf_label == "LOW":
        if rec == "STRONG_BUY":
            rec = "BUY"
        elif rec == "EXIT":
            rec = "REDUCE"

    return rec, conf_label


# ---------------------------------------------------------------------------
#  5. Portfolio-Level Metrics
# ---------------------------------------------------------------------------

def _hhi(weights: List[float]) -> float:
    """Herfindahl-Hirschman Index for concentration.

    Returns value in [0, 10000]. Lower = more diversified.
    """
    total = sum(weights)
    if total <= 0:
        return 0
    shares = [(w / total) * 100 for w in weights]
    return sum(s * s for s in shares)


def calculate_portfolio_metrics(
    analyses: List[Dict[str, Any]],
    bankroll: float,
) -> Dict[str, Any]:
    """Calculate aggregate portfolio-level intelligence metrics."""
    if not analyses:
        return {
            "total_positions": 0,
            "total_invested": 0,
            "total_current_value": 0,
            "unrealised_pnl": 0,
            "unrealised_pnl_pct": 0,
            "weighted_avg_ev": 0,
            "capital_efficiency_score": 0,
            "diversification_score": 0,
            "hhi": 0,
            "risk_adjusted_expectation": 0,
            "bankroll": bankroll,
            "recommendation_distribution": {},
        }

    total_invested = sum(a["ev_metrics"]["cost_basis"] for a in analyses)
    total_current_value = sum(a["ev_metrics"]["current_value"] for a in analyses)
    unrealised_pnl = total_current_value - total_invested

    # Weighted average EV (by capital deployed)
    if total_invested > 0:
        weighted_ev = sum(
            a["ev_metrics"]["ev_per_dollar"] * a["ev_metrics"]["cost_basis"] / total_invested
            for a in analyses
        )
    else:
        weighted_ev = 0

    # HHI concentration (by position size)
    position_sizes = [a["ev_metrics"]["cost_basis"] for a in analyses]
    hhi_value = _hhi(position_sizes)
    # Diversification score: 100 = perfectly diversified, 0 = single position
    max_hhi = 10000  # single position
    min_hhi = 10000 / max(len(analyses), 1)  # equally weighted
    if max_hhi > min_hhi:
        div_score = max(0, (1 - (hhi_value - min_hhi) / (max_hhi - min_hhi))) * 100
    else:
        div_score = 100

    # Capital efficiency: fraction of capital in positive-EV positions
    pos_ev_capital = sum(
        a["ev_metrics"]["cost_basis"]
        for a in analyses
        if a["ev_metrics"]["ev_per_dollar"] > 0
    )
    cap_efficiency = (pos_ev_capital / total_invested * 100) if total_invested > 0 else 0

    # Risk-adjusted return expectation
    ra_scores = [a["ev_metrics"]["risk_adjusted_return"] for a in analyses]
    avg_ra = sum(ra_scores) / len(ra_scores) if ra_scores else 0

    # Recommendation distribution
    rec_counts: Dict[str, int] = {}
    for a in analyses:
        rec = a["recommendation"]
        rec_counts[rec] = rec_counts.get(rec, 0) + 1

    return {
        "total_positions": len(analyses),
        "total_invested": round(total_invested, 2),
        "total_current_value": round(total_current_value, 2),
        "unrealised_pnl": round(unrealised_pnl, 2),
        "unrealised_pnl_pct": round(
            unrealised_pnl / total_invested * 100, 2
        ) if total_invested > 0 else 0,
        "weighted_avg_ev": round(weighted_ev, 4),
        "capital_efficiency_score": round(cap_efficiency, 1),
        "diversification_score": round(div_score, 1),
        "hhi": round(hhi_value, 1),
        "risk_adjusted_expectation": round(avg_ra, 4),
        "bankroll": round(bankroll, 2),
        "recommendation_distribution": rec_counts,
    }


# ---------------------------------------------------------------------------
#  6. Main Intelligence Report
# ---------------------------------------------------------------------------

def analyze_single_position(
    position: Dict[str, Any],
    client: Any,
    conn: sqlite3.Connection,
    bankroll: float,
    include_binance: bool = False,
    verbose: bool = False,
) -> Optional[Dict[str, Any]]:
    """Run full intelligence analysis on a single position."""
    market_id = position["market_id"]
    side = position["side"]
    size = position["size"]
    entry_price = position["entry_price"]

    # Fetch live market data from Gamma API
    try:
        market = client.get_market(market_id)
    except Exception as e:
        return {
            "market_id": market_id,
            "error": f"Failed to fetch market: {e}",
            "question": "Unknown",
            "side": side,
            "recommendation": "HOLD",
            "confidence": "LOW",
            "ev_metrics": {
                "ev_per_dollar": 0, "edge": 0, "edge_pct": 0,
                "kelly_optimal_pct": 0, "kelly_direction": "NONE",
                "kelly_position_usd": 0, "risk_adjusted_return": 0,
                "cost_basis": round(entry_price * size, 2),
                "current_value": 0, "unrealised_pnl": 0, "pnl_pct": 0,
            },
            "signal_breakdown": {},
        }

    question = market.get("question", "Unknown")[:100]
    end_date = market.get("endDate", "")
    volume = float(market.get("volume", 0) or 0)
    liquidity_val = float(market.get("liquidity", 0) or 0)

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
    if yes_price <= 0 or yes_price >= 1:
        return None  # invalid price, skip

    market_price = yes_price  # YES price = implied probability

    # Parse tags
    tags_raw = market.get("tags", [])
    if isinstance(tags_raw, str):
        try:
            tags_raw = json.loads(tags_raw)
        except (json.JSONDecodeError, TypeError):
            tags_raw = []

    # --- Step 1: Aggregate intelligence ---
    signals = aggregate_market_intelligence(conn, question, include_binance)

    # Supplement with position-specific data

    # Momentum from local price history
    price_history = db_utils.get_price_history(conn, market_id, limit=20)
    if price_history and len(price_history) >= 2:
        recent = [p.get("yes_price", 0) for p in price_history[:10] if p.get("yes_price")]
        if len(recent) >= 2:
            price_momentum = (recent[0] - recent[-1]) / max(recent[-1], 0.01)
            local_momentum = max(-1.0, min(1.0, price_momentum * 5))
            # Blend with existing momentum signal
            if signals["momentum"] is not None:
                signals["momentum"] = signals["momentum"] * 0.5 + local_momentum * 0.5
            else:
                signals["momentum"] = local_momentum

    # Liquidity signal from market depth
    liq_total = volume + liquidity_val
    if liq_total > 2_000_000:
        liq_signal = -0.3  # very efficient market
    elif liq_total > 500_000:
        liq_signal = -0.1
    elif liq_total > 100_000:
        liq_signal = 0.0
    elif liq_total > 10_000:
        liq_signal = 0.3  # thin market, mispricing possible
    else:
        liq_signal = 0.5
    signals["liquidity"] = liq_signal

    # --- Step 2: Bayesian probability estimation ---
    estimated_prob, confidence_weight = estimate_true_probability(
        market_price, side, signals,
    )

    # --- Step 3: EV calculation ---
    ev_metrics = calculate_position_ev(
        side=side,
        size=size,
        entry_price=entry_price,
        market_price=market_price,
        estimated_prob=estimated_prob,
        bankroll=bankroll,
    )

    # --- Step 4: Recommendation ---
    recommendation, confidence = _determine_recommendation(
        edge_pct=ev_metrics["edge_pct"],
        ev_per_dollar=ev_metrics["ev_per_dollar"],
        confidence=confidence_weight,
        kelly_optimal_pct=ev_metrics["kelly_optimal_pct"],
        pnl_pct=ev_metrics["pnl_pct"],
    )

    # Days remaining
    days_left = None
    if end_date:
        try:
            if end_date.endswith("Z"):
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            else:
                end_dt = datetime.fromisoformat(end_date)
                if end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=timezone.utc)
            days_left = round((end_dt - datetime.now(timezone.utc)).total_seconds() / 86400, 1)
        except (ValueError, TypeError):
            pass

    return {
        "market_id": market_id,
        "question": question,
        "side": side,
        "size": size,
        "entry_price": round(entry_price, 4),
        "market_price": round(market_price, 4),
        "estimated_prob": round(estimated_prob, 4),
        "signal_breakdown": {k: round(v, 4) if v is not None else None for k, v in signals.items()},
        "ev_metrics": ev_metrics,
        "recommendation": recommendation,
        "confidence": confidence,
        "volume": round(volume, 0),
        "liquidity": round(liquidity_val, 0),
        "days_remaining": days_left,
        "end_date": end_date,
        "tags": tags_raw if isinstance(tags_raw, list) else [],
    }


def run_intelligence_report(
    conn: sqlite3.Connection,
    client: Any,
    positions: List[Dict[str, Any]],
    bankroll: float,
    include_binance: bool = False,
    verbose: bool = False,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Run the full intelligence report across all positions.

    Returns:
        (analyses, portfolio_metrics)
    """
    session_id = str(uuid.uuid4())[:8]
    ensure_intelligence_table(conn)

    analyses: List[Dict[str, Any]] = []
    for i, pos in enumerate(positions):
        result = analyze_single_position(
            pos, client, conn, bankroll, include_binance, verbose,
        )
        if result is None:
            continue

        analyses.append(result)

        # Store to DB
        store_intelligence(conn, session_id, {
            "market_id": result["market_id"],
            "market_question": result["question"],
            "side": result["side"],
            "market_price": result["market_price"],
            "estimated_prob": result["estimated_prob"],
            "edge_pct": result["ev_metrics"]["edge_pct"],
            "ev_per_dollar": result["ev_metrics"]["ev_per_dollar"],
            "kelly_optimal_pct": result["ev_metrics"]["kelly_optimal_pct"],
            "signal_breakdown": result["signal_breakdown"],
            "recommendation": result["recommendation"],
            "confidence": result["confidence"],
        })

        # Rate limit between API calls
        if i < len(positions) - 1:
            time.sleep(0.3)

    portfolio = calculate_portfolio_metrics(analyses, bankroll)
    return analyses, portfolio


# ---------------------------------------------------------------------------
#  7. Pretty-Print Formatter
# ---------------------------------------------------------------------------

def format_pretty_report(
    analyses: List[Dict[str, Any]],
    portfolio: Dict[str, Any],
    verbose: bool = False,
) -> str:
    """Format a human-readable intelligence report."""
    lines: List[str] = []

    lines.append("")
    lines.append("=" * 76)
    lines.append("  PORTFOLIO INTELLIGENCE REPORT")
    lines.append("=" * 76)

    # Portfolio summary
    lines.append("")
    lines.append(
        f"  Positions: {portfolio['total_positions']}  |  "
        f"Invested: ${portfolio['total_invested']:,.2f}  |  "
        f"Value: ${portfolio['total_current_value']:,.2f}  |  "
        f"PnL: ${portfolio['unrealised_pnl']:+,.2f} "
        f"({portfolio['unrealised_pnl_pct']:+.1f}%)"
    )
    lines.append(
        f"  Weighted EV: {portfolio['weighted_avg_ev']:+.4f}  |  "
        f"Capital Efficiency: {portfolio['capital_efficiency_score']:.0f}%  |  "
        f"Diversification: {portfolio['diversification_score']:.0f}%  |  "
        f"Bankroll: ${portfolio['bankroll']:,.2f}"
    )

    rec_dist = portfolio.get("recommendation_distribution", {})
    if rec_dist:
        parts = [f"{k}: {v}" for k, v in sorted(rec_dist.items())]
        lines.append(f"  Recommendations: {' | '.join(parts)}")

    lines.append("")
    lines.append("-" * 76)

    # Sort by EV descending
    sorted_analyses = sorted(
        analyses,
        key=lambda a: a["ev_metrics"]["ev_per_dollar"],
        reverse=True,
    )

    rec_markers = {
        "STRONG_BUY": "[++]",
        "BUY": "[ +]",
        "HOLD": "[ =]",
        "REDUCE": "[ -]",
        "EXIT": "[--]",
    }

    for a in sorted_analyses:
        ev = a["ev_metrics"]
        rec = a["recommendation"]
        conf = a["confidence"]
        marker = rec_markers.get(rec, "[  ]")

        lines.append(f"  {marker} {a['question']}")
        lines.append(
            f"       {a['side']} x{a['size']:.0f} @ ${a['entry_price']:.2f} -> "
            f"mkt ${a['market_price']:.2f}  |  "
            f"PnL: ${ev['unrealised_pnl']:+.2f} ({ev['pnl_pct']:+.1f}%)"
        )
        lines.append(
            f"       Est.Prob: {a['estimated_prob']:.1%}  "
            f"Edge: {ev['edge_pct']:+.1f}%  "
            f"EV/$: {ev['ev_per_dollar']:+.4f}  "
            f"Kelly: {ev['kelly_optimal_pct']:.1f}%  "
            f"-> {rec} ({conf})"
        )

        if verbose:
            sb = a.get("signal_breakdown", {})
            signal_parts: List[str] = []
            for sig_name in SIGNAL_WEIGHTS:
                val = sb.get(sig_name)
                if val is not None:
                    signal_parts.append(f"{sig_name}:{val:+.2f}")
                else:
                    signal_parts.append(f"{sig_name}:n/a")
            lines.append(f"       Signals: {' | '.join(signal_parts)}")

        days = a.get("days_remaining")
        days_str = f"{days:.0f}d left" if days is not None else "no expiry"
        lines.append(
            f"       Vol: ${a['volume']:,.0f}  Liq: ${a['liquidity']:,.0f}  {days_str}"
        )
        lines.append("")

    lines.append("=" * 76)

    # Action items
    strong_buys = [a for a in analyses if a["recommendation"] == "STRONG_BUY"]
    buys = [a for a in analyses if a["recommendation"] == "BUY"]
    exits = [a for a in analyses if a["recommendation"] == "EXIT"]
    reduces = [a for a in analyses if a["recommendation"] == "REDUCE"]

    if strong_buys or buys or exits or reduces:
        lines.append("  ACTION ITEMS:")
        for a in strong_buys:
            lines.append(
                f"    STRONG BUY: {a['question']} "
                f"(edge: {a['ev_metrics']['edge_pct']:+.1f}%, "
                f"kelly: {a['ev_metrics']['kelly_optimal_pct']:.1f}%)"
            )
        for a in buys:
            lines.append(
                f"    BUY MORE: {a['question']} "
                f"(edge: {a['ev_metrics']['edge_pct']:+.1f}%)"
            )
        for a in reduces:
            lines.append(
                f"    REDUCE: {a['question']} "
                f"(edge: {a['ev_metrics']['edge_pct']:+.1f}%)"
            )
        for a in exits:
            lines.append(
                f"    EXIT: {a['question']} "
                f"(edge: {a['ev_metrics']['edge_pct']:+.1f}%)"
            )
        lines.append("=" * 76)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
#  8. CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Portfolio Intelligence Engine")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--market-id", type=str, default="",
                        help="Analyze a single market by ID")
    parser.add_argument("--include-binance", action="store_true",
                        help="Include Binance research data")
    parser.add_argument("--verbose", action="store_true",
                        help="Show signal breakdowns")
    parser.add_argument("--bankroll", type=float, default=0,
                        help="Override bankroll for Kelly sizing")
    parser.add_argument("--kelly-fraction", type=float, default=0.5,
                        help="Kelly fraction (default 0.5 = half Kelly)")
    args = parser.parse_args()

    # Database connection
    try:
        conn = db_utils.get_connection()
    except Exception as e:
        error(f"Database connection failed: {e}", code="DB_ERROR")
        return

    # Polymarket client
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
            error(
                f"No open position found for market: {args.market_id}",
                code="NOT_FOUND",
            )
            return
    else:
        positions = db_utils.get_positions(conn)

    if not positions:
        if args.json:
            success(
                data={"positions": [], "portfolio": {"total_positions": 0}},
                message="No open positions",
            )
        else:
            print("\nNo open positions found.")
        return

    # Determine bankroll
    bankroll = args.bankroll
    if bankroll <= 0:
        try:
            bankroll = client.get_balance_usdc()
            summary = db_utils.get_portfolio_summary(conn)
            bankroll += summary.get("total_invested", 0)
        except Exception:
            bankroll = 500  # Fallback default

    # Run intelligence report
    analyses, portfolio = run_intelligence_report(
        conn=conn,
        client=client,
        positions=positions,
        bankroll=bankroll,
        include_binance=args.include_binance,
        verbose=args.verbose,
    )

    # Output
    if args.json:
        success(
            data={"positions": analyses, "portfolio": portfolio},
            message=f"Intelligence report: {len(analyses)} positions analyzed",
        )
    else:
        report_text = format_pretty_report(analyses, portfolio, args.verbose)
        report(report_text, data={"positions": analyses, "portfolio": portfolio})


if __name__ == "__main__":
    main()
