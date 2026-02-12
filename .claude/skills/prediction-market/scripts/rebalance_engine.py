#!/usr/bin/env python3
"""
Portfolio Rebalancing Engine (Phase 2)

Analyzes current portfolio positions and generates specific rebalancing actions
based on concentration limits, edge scores, Kelly criterion, and risk rules.

Usage:
  python rebalance_engine.py               # Full rebalancing plan (dry-run)
  python rebalance_engine.py --execute     # Analyze AND execute (with confirmation)
  python rebalance_engine.py --execute --force  # Execute without confirmation
  python rebalance_engine.py --execute --action EXIT  # Only execute EXIT actions
  python rebalance_engine.py --json        # JSON output
  python rebalance_engine.py --max-position-pct 15
  python rebalance_engine.py --max-category-pct 40
  python rebalance_engine.py --kelly-fraction 0.5
  python rebalance_engine.py --bankroll 500
  python rebalance_engine.py --use-estimator  # Use multi-source probability estimator
  python rebalance_engine.py --telegram    # Telegram-formatted summary
"""

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import db_utils
from calculate_kelly import kelly_criterion, size_position
from config import DB_PATH, PROJECT_DATA_DIR
from output_format import error, report, success, table
from polymarket_client import create_client

# Try to import the true probability estimator
try:
    from estimate_true_probability import estimate_all_positions
    HAS_ESTIMATOR = True
except ImportError:
    HAS_ESTIMATOR = False


# === Schema for rebalancing history ===

REBALANCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS pm_rebalances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    market_id TEXT NOT NULL,
    action TEXT NOT NULL,
    reason TEXT,
    current_size REAL,
    suggested_change REAL,
    executed INTEGER DEFAULT 0,
    executed_at INTEGER,
    created_at INTEGER DEFAULT (strftime('%s','now'))
);
CREATE INDEX IF NOT EXISTS idx_pm_rebalances_session ON pm_rebalances(session_id, created_at DESC);
"""


def ensure_rebalance_schema(conn):
    """Create pm_rebalances table if not exists"""
    conn.executescript(REBALANCE_SCHEMA)


# === Market data fetching ===

def fetch_live_market_data(client, market_ids: List[str], slug_map: Dict[str, str] = None) -> Dict[str, Dict]:
    """Fetch current market data from Gamma API for all positions.

    Args:
        slug_map: Optional dict mapping market_id (condition_id) to slug for reliable lookups.
    """
    if slug_map is None:
        slug_map = {}
    data = {}
    for mid in market_ids:
        try:
            slug = slug_map.get(mid)
            if slug:
                result = client._gamma_get("/markets", {"slug": slug})
            else:
                result = client._gamma_get("/markets", {"condition_id": mid})
            if result and isinstance(result, list) and len(result) > 0:
                market = result[0]
                prices_raw = market.get("outcomePrices", "")
                if isinstance(prices_raw, str):
                    try:
                        prices = json.loads(prices_raw)
                    except (json.JSONDecodeError, TypeError):
                        prices = []
                else:
                    prices = prices_raw or []

                yes_price = float(prices[0]) if len(prices) > 0 else 0
                no_price = float(prices[1]) if len(prices) > 1 else 0

                # Parse tags
                tags_raw = market.get("tags", [])
                if isinstance(tags_raw, str):
                    try:
                        tags_raw = json.loads(tags_raw)
                    except (json.JSONDecodeError, TypeError):
                        tags_raw = []

                # Parse end date
                end_date_str = market.get("endDate", "")
                days_to_expiry = None
                if end_date_str:
                    try:
                        end_dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                        days_to_expiry = max((end_dt - datetime.now(timezone.utc)).total_seconds() / 86400, 0)
                    except Exception:
                        pass

                # Get clob token IDs for order book queries
                clob_token_ids = market.get("clobTokenIds", [])

                # Event grouping
                event_slug = market.get("groupItemTitle", "") or market.get("slug", "")
                condition_id = market.get("conditionId", "")

                data[mid] = {
                    "question": market.get("question", ""),
                    "yes_price": yes_price,
                    "no_price": no_price,
                    "active": market.get("active", False),
                    "closed": market.get("closed", False),
                    "end_date": end_date_str,
                    "days_to_expiry": days_to_expiry,
                    "volume_24h": float(market.get("volume24hr", 0) or 0),
                    "liquidity": float(market.get("liquidity", 0) or 0),
                    "tags": tags_raw,
                    "clob_token_ids": clob_token_ids,
                    "event_slug": event_slug,
                    "condition_id": condition_id,
                }
            time.sleep(0.3)
        except Exception as e:
            print(f"  [WARN] Failed to fetch {mid}: {e}", file=sys.stderr)
    return data


# === Portfolio risk calculations ===

def calculate_concentration(positions: List[Dict], total_value: float) -> List[Dict]:
    """Calculate position-level concentration (% of portfolio)"""
    for pos in positions:
        invested = pos["entry_price"] * pos["size"]
        pos["invested"] = invested
        pos["pct_of_portfolio"] = (invested / total_value * 100) if total_value > 0 else 0
    return positions


def calculate_category_concentration(
    positions: List[Dict], market_data: Dict[str, Dict]
) -> Dict[str, Dict]:
    """Calculate category-level concentration"""
    categories: Dict[str, Dict] = {}

    for pos in positions:
        mid = pos["market_id"]
        mdata = market_data.get(mid, {})
        tags = mdata.get("tags", [])

        # Infer category from tags or question
        category = _infer_category(tags, mdata.get("question", ""))
        invested = pos.get("invested", pos["entry_price"] * pos["size"])

        if category not in categories:
            categories[category] = {"invested": 0, "count": 0, "market_ids": []}
        categories[category]["invested"] += invested
        categories[category]["count"] += 1
        categories[category]["market_ids"].append(mid)

    return categories


def _infer_category(tags: List[str], question: str) -> str:
    """Infer category from tags or question text"""
    if not tags:
        tags = []

    tags_lower = [t.lower() for t in tags]
    question_lower = question.lower()

    # Tag-based classification
    for tag in tags_lower:
        if tag in ("crypto", "bitcoin", "ethereum", "btc", "eth", "sol"):
            return "crypto"
        if tag in ("politics", "elections", "government", "president"):
            return "politics"
        if tag in ("sports", "nfl", "nba", "soccer", "football", "hockey", "olympics"):
            return "sports"
        if tag in ("entertainment", "movies", "oscars", "awards", "tv"):
            return "entertainment"
        if tag in ("economics", "fed", "interest-rates", "inflation"):
            return "economics"
        if tag in ("geopolitics", "war", "conflict", "diplomacy"):
            return "geopolitics"

    # Question-based fallback
    crypto_keywords = ["btc", "bitcoin", "eth", "ethereum", "sol", "solana", "crypto", "token"]
    if any(kw in question_lower for kw in crypto_keywords):
        return "crypto"

    politics_keywords = ["president", "election", "congress", "senate", "vote", "fed ", "federal reserve"]
    if any(kw in question_lower for kw in politics_keywords):
        return "politics"

    sports_keywords = ["win", "medal", "championship", "league", "hockey", "gold medal", "olympics", "world cup"]
    if any(kw in question_lower for kw in sports_keywords):
        return "sports"

    entertainment_keywords = ["oscar", "best picture", "movie", "emmy", "grammy"]
    if any(kw in question_lower for kw in entertainment_keywords):
        return "entertainment"

    economics_keywords = ["rate cut", "rate hold", "interest rate", "inflation", "gdp", "ceasefire"]
    if any(kw in question_lower for kw in economics_keywords):
        return "economics"

    return "other"


def find_correlated_positions(
    positions: List[Dict], market_data: Dict[str, Dict]
) -> List[Tuple[str, str, str]]:
    """Find potentially correlated positions (same event group or similar theme)"""
    correlations = []
    seen = set()

    for i, pos_a in enumerate(positions):
        mid_a = pos_a["market_id"]
        data_a = market_data.get(mid_a, {})
        slug_a = data_a.get("event_slug", "")

        for j, pos_b in enumerate(positions):
            if j <= i:
                continue
            mid_b = pos_b["market_id"]
            data_b = market_data.get(mid_b, {})
            slug_b = data_b.get("event_slug", "")

            pair_key = tuple(sorted([mid_a, mid_b]))
            if pair_key in seen:
                continue

            # Same event group
            if slug_a and slug_b and slug_a == slug_b:
                correlations.append((mid_a, mid_b, "same_event_group"))
                seen.add(pair_key)
                continue

            # Same category and similar end dates
            cat_a = _infer_category(data_a.get("tags", []), data_a.get("question", ""))
            cat_b = _infer_category(data_b.get("tags", []), data_b.get("question", ""))
            if cat_a == cat_b and cat_a != "other":
                dte_a = data_a.get("days_to_expiry")
                dte_b = data_b.get("days_to_expiry")
                if dte_a is not None and dte_b is not None and abs(dte_a - dte_b) < 3:
                    correlations.append((mid_a, mid_b, f"same_category_{cat_a}"))
                    seen.add(pair_key)

    return correlations


def calculate_herfindahl(positions: List[Dict], total_value: float) -> float:
    """Calculate Herfindahl-Hirschman Index (concentration measure)"""
    if total_value <= 0 or not positions:
        return 0
    hhi = sum(
        (pos.get("invested", pos["entry_price"] * pos["size"]) / total_value * 100) ** 2
        for pos in positions
    )
    return round(hhi, 1)


# === Edge estimation heuristic ===

def estimate_probability(market_price: float, edge_score: float, side: str) -> float:
    """
    Estimate true probability from market price adjusted by edge_score.

    Heuristic: edge_score > 0 means we believe the market underprices the outcome.
    Adjustment: estimated_prob = market_price + (edge_score/100 * 0.15) for YES positions.
    """
    adjustment = (edge_score / 100) * 0.15

    if side == "YES":
        estimated = market_price + adjustment
    else:
        # For NO positions, a positive edge_score means the NO outcome is underpriced
        # which means the YES outcome is overpriced
        estimated = market_price - adjustment

    # Clamp to valid range
    return max(0.01, min(0.99, estimated))


# === Rebalancing logic ===

def determine_action(
    pos: Dict,
    market_data: Dict,
    pct_of_portfolio: float,
    category_pct: float,
    edge_score: float,
    max_position_pct: float,
    max_category_pct: float,
) -> Tuple[str, str, int]:
    """
    Determine rebalancing action for a position.

    Returns: (action, reason, priority)
    Priority: 1=EXIT, 2=REDUCE, 3=HOLD, 4=ADD
    """
    side = pos["side"]
    size = pos["size"]
    entry_price = pos["entry_price"]
    invested = entry_price * size

    mdata = market_data
    current_price = mdata.get("yes_price", 0) if side == "YES" else mdata.get("no_price", 0)
    current_value = current_price * size
    unrealized_pnl = current_value - invested
    pnl_pct = (unrealized_pnl / invested * 100) if invested > 0 else 0
    days_to_expiry = mdata.get("days_to_expiry")
    is_closed = mdata.get("closed", False)
    is_active = mdata.get("active", True)

    # Market price from the YES side for Kelly calculations
    yes_price = mdata.get("yes_price", 0)

    # --- EXIT conditions ---

    # Closed/settled market
    if is_closed or not is_active:
        return ("EXIT", "Market is closed/settled", 1)

    # Near certainty — capital locked with minimal upside
    if side == "YES" and yes_price > 0.97:
        return ("EXIT", f"Price ${yes_price:.2f} near certain — low capital efficiency", 1)
    if side == "YES" and yes_price < 0.03:
        return ("EXIT", f"Price ${yes_price:.2f} near zero — likely loss", 1)
    if side == "NO" and mdata.get("no_price", 0) > 0.97:
        return ("EXIT", f"NO price ${mdata.get('no_price', 0):.2f} near certain — low capital efficiency", 1)
    if side == "NO" and mdata.get("no_price", 0) < 0.03:
        return ("EXIT", f"NO price ${mdata.get('no_price', 0):.2f} near zero — likely loss", 1)

    # Cut losses: P&L < -20% and enough time remaining
    if pnl_pct < -20 and days_to_expiry is not None and days_to_expiry > 7:
        return ("EXIT", f"Stop loss: P&L {pnl_pct:+.1f}% with {days_to_expiry:.0f} days left", 1)

    # About to expire while losing
    if days_to_expiry is not None and days_to_expiry < 1 and unrealized_pnl < 0:
        return ("EXIT", f"Expiring in <1 day with unrealized loss ${unrealized_pnl:+.2f}", 1)

    # --- REDUCE conditions ---

    # Single position concentration
    if pct_of_portfolio > max_position_pct:
        return ("REDUCE", f"Position {pct_of_portfolio:.1f}% > {max_position_pct:.0f}% limit", 2)

    # Category concentration
    if category_pct > max_category_pct:
        return ("REDUCE", f"Category at {category_pct:.1f}% > {max_category_pct:.0f}% limit", 2)

    # Negative edge
    if edge_score < -10:
        return ("REDUCE", f"Negative edge score ({edge_score:.1f})", 2)

    # --- ADD conditions ---

    if edge_score > 30 and pct_of_portfolio < 10:
        return ("ADD", f"Strong edge ({edge_score:.1f}) with low allocation ({pct_of_portfolio:.1f}%)", 4)

    # --- HOLD (default) ---
    return ("HOLD", f"Within parameters (edge={edge_score:.1f}, alloc={pct_of_portfolio:.1f}%)", 3)


def calculate_suggested_change(
    action: str,
    pos: Dict,
    market_data: Dict,
    kelly_result: Dict,
    bankroll: float,
    max_position_pct: float,
    total_portfolio: float,
) -> float:
    """
    Calculate suggested $ change for a position.
    Negative = reduce/exit, positive = add.
    """
    invested = pos.get("invested", pos["entry_price"] * pos["size"])

    if action == "EXIT":
        return -invested

    if action == "REDUCE":
        # Reduce to max_position_pct of portfolio
        target = total_portfolio * (max_position_pct / 100)
        if invested > target:
            return -(invested - target)
        # Reduce by 30% if category-based
        return -(invested * 0.3)

    if action == "ADD":
        # Use Kelly-optimal sizing
        kelly_optimal_usd = kelly_result.get("position_size_usd", 0)
        if kelly_optimal_usd > invested:
            addition = min(kelly_optimal_usd - invested, bankroll * 0.1)  # Cap at 10% of bankroll per add
            return max(addition, 0)
        return 0

    # HOLD
    return 0


# === Slippage estimation ===

def estimate_slippage(
    client, market_data: Dict, side: str, size_change: float
) -> Optional[Dict]:
    """Try to estimate slippage for a trade"""
    if abs(size_change) < 1:
        return None

    clob_token_ids = market_data.get("clob_token_ids", [])
    if not clob_token_ids:
        return None

    # YES = token 0, NO = token 1
    token_idx = 0 if side == "YES" else (1 if len(clob_token_ids) > 1 else 0)
    token_id = clob_token_ids[token_idx]

    trade_side = "SELL" if size_change < 0 else "BUY"

    try:
        slippage = client.calculate_slippage(token_id, trade_side, abs(size_change))
        time.sleep(0.3)
        return slippage
    except Exception as e:
        print(f"  [WARN] Slippage estimation failed: {e}", file=sys.stderr)
        return None


# === Main rebalancing engine ===

def run_rebalance(
    max_position_pct: float = 15.0,
    max_category_pct: float = 40.0,
    kelly_fraction: float = 0.5,
    bankroll_override: Optional[float] = None,
    user_id: str = "default",
    estimate_slippage_flag: bool = True,
    use_estimator: bool = False,
) -> Dict:
    """
    Run the full rebalancing analysis.

    Returns a dict with actions, summary, and session metadata.
    """
    session_id = str(uuid.uuid4())[:8]
    conn = db_utils.get_connection()
    ensure_rebalance_schema(conn)

    # 1. Load open positions
    positions = db_utils.get_positions(conn, user_id, "open")
    if not positions:
        conn.close()
        return {
            "session_id": session_id,
            "error": "No open positions found",
            "actions": [],
            "summary": {},
        }

    # 2. Create client and fetch live market data
    client = create_client()
    market_ids = list(set(p["market_id"] for p in positions))

    # Build slug lookup map from pm_markets table for reliable Gamma API queries
    slug_map = {}
    for mid in market_ids:
        row = conn.execute("SELECT slug FROM pm_markets WHERE id = ?", (mid,)).fetchone()
        if row and row["slug"]:
            slug_map[mid] = row["slug"]

    print(f"  Fetching data for {len(market_ids)} markets ({len(slug_map)} slugs)...", file=sys.stderr)
    market_data = fetch_live_market_data(client, market_ids, slug_map)

    # 2.5 Load estimator data if requested
    estimates_by_market = {}
    if use_estimator:
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

    # 3. Get bankroll (cash available)
    if bankroll_override is not None:
        bankroll = bankroll_override
    else:
        try:
            bankroll = client.get_balance_usdc()
        except Exception:
            bankroll = 0
    print(f"  Bankroll (cash): ${bankroll:.2f}", file=sys.stderr)

    # 4. Calculate portfolio totals
    total_invested = 0
    for pos in positions:
        pos["invested"] = pos["entry_price"] * pos["size"]
        total_invested += pos["invested"]

    total_portfolio = total_invested + bankroll

    # 5. Position concentration
    positions = calculate_concentration(positions, total_portfolio)

    # 6. Category concentration
    categories = calculate_category_concentration(positions, market_data)
    total_cat_invested = sum(c["invested"] for c in categories.values())
    for cat_name, cat_info in categories.items():
        cat_info["pct"] = (cat_info["invested"] / total_cat_invested * 100) if total_cat_invested > 0 else 0

    # 7. Build category lookup for each position
    pos_category_pct = {}
    for pos in positions:
        mid = pos["market_id"]
        mdata = market_data.get(mid, {})
        cat = _infer_category(mdata.get("tags", []), mdata.get("question", ""))
        pos_category_pct[mid] = categories.get(cat, {}).get("pct", 0)

    # 8. Correlated positions
    correlations = find_correlated_positions(positions, market_data)

    # 9. Determine actions for each position
    actions = []
    for pos in positions:
        mid = pos["market_id"]
        mdata = market_data.get(mid, {})
        if not mdata:
            continue

        side = pos["side"]
        entry_price = pos["entry_price"]
        size = pos["size"]
        invested = pos["invested"]
        current_price = mdata["yes_price"] if side == "YES" else mdata.get("no_price", 0)
        current_value = current_price * size
        unrealized_pnl = current_value - invested
        pnl_pct = (unrealized_pnl / invested * 100) if invested > 0 else 0

        # Edge score: use estimator if available, otherwise heuristic
        estimator_confidence = None
        estimator_edge_pct = None
        if use_estimator and mid in estimates_by_market:
            est = estimates_by_market[mid]
            estimator_edge_pct = est.get("edge_pct", 0)
            estimator_confidence = est.get("confidence", 0)
            edge_score = estimator_edge_pct * 10  # Map to heuristic scale (5% -> 50)
            estimated_prob_val = est.get("estimated_true_prob")
        else:
            # Simple heuristic: use pnl_pct as a proxy for edge when no analysis is available
            edge_score = pnl_pct * 0.5  # Scale down; positive P&L implies some edge
            estimated_prob_val = None

        # Kelly calculation
        yes_price = mdata["yes_price"]
        if yes_price > 0.01 and yes_price < 0.99:
            if estimated_prob_val is not None:
                estimated_prob = max(0.01, min(0.99, estimated_prob_val))
            else:
                estimated_prob = estimate_probability(yes_price, edge_score, side)
            kelly = kelly_criterion(estimated_prob, yes_price, kelly_fraction)
            sized_kelly = size_position(kelly, bankroll)
        else:
            kelly = {}
            sized_kelly = {"position_size_usd": 0}

        # Determine action
        action, reason, priority = determine_action(
            pos, mdata,
            pos["pct_of_portfolio"],
            pos_category_pct.get(mid, 0),
            edge_score,
            max_position_pct,
            max_category_pct,
        )

        # EV-based urgency adjustment when estimator is available
        if estimator_confidence is not None and estimator_edge_pct is not None:
            if estimator_edge_pct < -5 and estimator_confidence > 0.7:
                # High-confidence negative edge: escalate to EXIT
                if action in ("HOLD", "REVIEW", "REDUCE"):
                    action = "EXIT"
                    reason = f"Estimator: edge {estimator_edge_pct:+.1f}% with confidence {estimator_confidence:.1f} -> EXIT"
                    priority = 1
            elif estimator_edge_pct > 10 and estimator_confidence > 0.7:
                # High-confidence positive edge: escalate to ADD
                if action in ("HOLD", "REVIEW"):
                    action = "ADD"
                    reason = f"Estimator: edge {estimator_edge_pct:+.1f}% with confidence {estimator_confidence:.1f} -> ADD"
                    priority = 4
            elif estimator_confidence < 0.4:
                # Low confidence: demote action urgency
                if action == "EXIT" and priority == 1:
                    # Don't demote hard exits (closed market, extreme prices)
                    pass
                elif action in ("ADD", "REDUCE"):
                    action = "REVIEW"
                    reason = f"Low estimator confidence ({estimator_confidence:.1f}): {reason} -> REVIEW"
                    priority = 3

        # Calculate suggested change
        suggested_change = calculate_suggested_change(
            action, pos, mdata, sized_kelly,
            bankroll, max_position_pct, total_portfolio,
        )

        # Estimate slippage for non-HOLD actions
        slippage_info = None
        if action != "HOLD" and estimate_slippage_flag and abs(suggested_change) > 1:
            # Convert $ change to contracts
            contract_change = abs(suggested_change / current_price) if current_price > 0 else 0
            if contract_change > 0:
                slippage_info = estimate_slippage(client, mdata, side, -contract_change if suggested_change < 0 else contract_change)

        # Kelly-optimal allocation
        kelly_optimal_pct = sized_kelly.get("fractional_kelly_pct", 0) if sized_kelly else 0
        kelly_optimal_usd = sized_kelly.get("position_size_usd", 0) if sized_kelly else 0

        action_item = {
            "market_id": mid,
            "question": mdata.get("question", "")[:70],
            "side": side,
            "current_size": size,
            "current_invested": round(invested, 2),
            "current_value": round(current_value, 2),
            "current_price": round(current_price, 4),
            "entry_price": round(entry_price, 4),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "pnl_pct": round(pnl_pct, 1),
            "pct_of_portfolio": round(pos["pct_of_portfolio"], 1),
            "days_to_expiry": round(mdata.get("days_to_expiry", 0) or 0, 1),
            "action": action,
            "priority": priority,
            "reason": reason,
            "suggested_change_usd": round(suggested_change, 2),
            "edge_score": round(edge_score, 1),
            "kelly_optimal_pct": round(kelly_optimal_pct, 1),
            "kelly_optimal_usd": round(kelly_optimal_usd, 2),
            "estimated_slippage": slippage_info,
        }

        # Add estimator metadata when available
        if estimator_confidence is not None:
            action_item["estimator_edge_pct"] = round(estimator_edge_pct, 2)
            action_item["estimator_confidence"] = round(estimator_confidence, 2)
            if estimated_prob_val is not None:
                action_item["estimated_true_prob"] = round(estimated_prob_val, 4)

        actions.append(action_item)

    # Sort by priority (1=EXIT first), then by absolute suggested change
    actions.sort(key=lambda a: (a["priority"], -abs(a["suggested_change_usd"])))

    # 10. Summary statistics
    exit_count = sum(1 for a in actions if a["action"] == "EXIT")
    reduce_count = sum(1 for a in actions if a["action"] == "REDUCE")
    hold_count = sum(1 for a in actions if a["action"] == "HOLD")
    add_count = sum(1 for a in actions if a["action"] == "ADD")

    capital_to_free = abs(sum(
        a["suggested_change_usd"] for a in actions
        if a["action"] in ("EXIT", "REDUCE") and a["suggested_change_usd"] < 0
    ))
    capital_to_deploy = sum(
        a["suggested_change_usd"] for a in actions
        if a["action"] == "ADD" and a["suggested_change_usd"] > 0
    )
    net_change = sum(a["suggested_change_usd"] for a in actions)

    # Locked capital: positions with <5% potential profit
    locked_capital = 0
    for a in actions:
        if a["current_price"] > 0.95:
            max_profit_pct = ((1.0 - a["current_price"]) / a["current_price"] * 100)
            if max_profit_pct < 5:
                locked_capital += a["current_invested"]

    hhi_before = calculate_herfindahl(positions, total_portfolio)

    # Simulate after-rebalance HHI
    simulated_positions = []
    for a in actions:
        if a["action"] == "EXIT":
            continue  # removed
        new_invested = a["current_invested"] + a["suggested_change_usd"]
        if new_invested > 0:
            simulated_positions.append({"invested": new_invested, "entry_price": 1, "size": 1})
    new_total = sum(p["invested"] for p in simulated_positions) + bankroll + capital_to_free
    hhi_after = calculate_herfindahl(simulated_positions, new_total) if simulated_positions else 0

    summary = {
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_positions": len(positions),
        "actions_exit": exit_count,
        "actions_reduce": reduce_count,
        "actions_hold": hold_count,
        "actions_add": add_count,
        "capital_to_free": round(capital_to_free, 2),
        "capital_to_deploy": round(capital_to_deploy, 2),
        "net_change": round(net_change, 2),
        "locked_capital": round(locked_capital, 2),
        "bankroll": round(bankroll, 2),
        "total_invested": round(total_invested, 2),
        "total_portfolio": round(total_portfolio, 2),
        "hhi_before": hhi_before,
        "hhi_after": hhi_after,
        "max_position_pct": max_position_pct,
        "max_category_pct": max_category_pct,
        "kelly_fraction": kelly_fraction,
        "categories": {
            k: {"invested": round(v["invested"], 2), "pct": round(v["pct"], 1), "count": v["count"]}
            for k, v in categories.items()
        },
        "correlations": [
            {"market_a": a, "market_b": b, "type": t}
            for a, b, t in correlations
        ],
        "estimator_used": use_estimator and bool(estimates_by_market),
    }

    # Add estimator aggregate stats to summary
    if use_estimator and estimates_by_market:
        confidences = [
            a["estimator_confidence"] for a in actions
            if "estimator_confidence" in a
        ]
        summary["avg_confidence"] = round(sum(confidences) / len(confidences), 2) if confidences else 0
        # Collect unique data sources from estimator
        all_sources = set()
        for mid_key, est_data in estimates_by_market.items():
            for src in est_data.get("data_sources", []):
                all_sources.add(src)
        summary["data_sources"] = sorted(all_sources)

    # 11. Save actions to DB
    for a in actions:
        conn.execute("""
            INSERT INTO pm_rebalances (session_id, market_id, action, reason, current_size, suggested_change)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session_id, a["market_id"], a["action"], a["reason"], a["current_size"], a["suggested_change_usd"]))
    conn.commit()
    conn.close()

    return {
        "session_id": session_id,
        "actions": actions,
        "summary": summary,
    }


# === Output formatting ===

def format_report(result: Dict) -> str:
    """Format rebalancing result as human-readable report"""
    summary = result["summary"]
    actions = result["actions"]

    lines = []
    lines.append(f"\n{'='*70}")
    lines.append(f"  PORTFOLIO REBALANCING PLAN")
    lines.append(f"  Session: {result['session_id']}  |  {summary.get('timestamp', '')[:19]} UTC")
    lines.append(f"{'='*70}")

    # Portfolio overview
    lines.append(f"\n  PORTFOLIO OVERVIEW:")
    lines.append(f"  {'─'*50}")
    lines.append(f"  Total Positions:    {summary['total_positions']}")
    lines.append(f"  Total Invested:     ${summary['total_invested']:>10,.2f}")
    lines.append(f"  Cash Available:     ${summary['bankroll']:>10,.2f}")
    lines.append(f"  Total Portfolio:    ${summary['total_portfolio']:>10,.2f}")
    lines.append(f"  Locked Capital:     ${summary['locked_capital']:>10,.2f}")
    lines.append(f"  HHI (concentration): {summary['hhi_before']:.0f} -> {summary['hhi_after']:.0f}")
    if summary.get("estimator_used"):
        lines.append(f"  Estimator:          Active  |  Avg Confidence: {summary.get('avg_confidence', 0):.2f}")
        sources = summary.get("data_sources", [])
        if sources:
            lines.append(f"  Data Sources:       {', '.join(sources)}")

    # Category breakdown
    cats = summary.get("categories", {})
    if cats:
        lines.append(f"\n  CATEGORY CONCENTRATION:")
        lines.append(f"  {'─'*50}")
        for cat_name, cat_info in sorted(cats.items(), key=lambda x: -x[1]["pct"]):
            bar = "#" * int(cat_info["pct"] / 2)
            warn = " *** OVER LIMIT" if cat_info["pct"] > summary["max_category_pct"] else ""
            lines.append(f"  {cat_name:<15} ${cat_info['invested']:>8,.2f}  {cat_info['pct']:>5.1f}%  {bar}{warn}")

    # Correlations
    corrs = summary.get("correlations", [])
    if corrs:
        lines.append(f"\n  CORRELATED POSITIONS ({len(corrs)}):")
        lines.append(f"  {'─'*50}")
        for c in corrs:
            lines.append(f"  {c['type']}: {c['market_a'][:20]}.. <-> {c['market_b'][:20]}..")

    # Action summary
    lines.append(f"\n  ACTION SUMMARY:")
    lines.append(f"  {'─'*50}")
    lines.append(f"  EXIT:   {summary['actions_exit']:>3}  |  Capital to free:   ${summary['capital_to_free']:>10,.2f}")
    lines.append(f"  REDUCE: {summary['actions_reduce']:>3}  |  Capital to deploy: ${summary['capital_to_deploy']:>10,.2f}")
    lines.append(f"  HOLD:   {summary['actions_hold']:>3}  |  Net change:        ${summary['net_change']:>+10,.2f}")
    lines.append(f"  ADD:    {summary['actions_add']:>3}  |")

    # Detailed actions by priority
    for priority, label in [(1, "EXIT"), (2, "REDUCE"), (3, "HOLD"), (4, "ADD")]:
        priority_actions = [a for a in actions if a["priority"] == priority]
        if not priority_actions:
            continue

        lines.append(f"\n  {'='*70}")
        lines.append(f"  Priority {priority}: {label} ({len(priority_actions)} positions)")
        lines.append(f"  {'='*70}")

        for i, a in enumerate(priority_actions, 1):
            lines.append(f"\n  [{i}] {a['action']} — {a['question']}")
            lines.append(f"      Side: {a['side']}  |  Size: {a['current_size']:.0f}  |  Entry: ${a['entry_price']:.4f}  |  Now: ${a['current_price']:.4f}")
            lines.append(f"      Invested: ${a['current_invested']:.2f}  |  Value: ${a['current_value']:.2f}  |  P&L: ${a['unrealized_pnl']:+.2f} ({a['pnl_pct']:+.1f}%)")

            # Show estimator-enhanced edge or heuristic edge
            if "estimator_edge_pct" in a:
                est_prob_str = f"  est_prob:{a['estimated_true_prob']:.2f}" if "estimated_true_prob" in a else ""
                lines.append(f"      Portfolio %: {a['pct_of_portfolio']:.1f}%  |  Days: {a['days_to_expiry']:.0f}  |  "
                             f"Edge: {a['edge_score']:+.1f} (est:{a['estimator_edge_pct']:+.1f}%{est_prob_str} conf:{a['estimator_confidence']:.1f})")
            else:
                lines.append(f"      Portfolio %: {a['pct_of_portfolio']:.1f}%  |  Days: {a['days_to_expiry']:.0f}  |  Edge: {a['edge_score']:+.1f}")

            lines.append(f"      Reason: {a['reason']}")

            if a["suggested_change_usd"] != 0:
                change_str = f"${a['suggested_change_usd']:+,.2f}"
                lines.append(f"      Suggested Change: {change_str}")

            if a.get("kelly_optimal_usd") and a["action"] in ("ADD", "REDUCE"):
                lines.append(f"      Kelly Optimal: ${a['kelly_optimal_usd']:.2f} ({a['kelly_optimal_pct']:.1f}% of bankroll)")

            slip = a.get("estimated_slippage")
            if slip and slip.get("fillable") is not None:
                fillable = "Yes" if slip["fillable"] else "PARTIAL"
                lines.append(f"      Slippage: {slip.get('slippage_pct', 0):.2f}%  |  Avg Price: ${slip.get('avg_price', 0):.4f}  |  Fillable: {fillable}")

    lines.append(f"\n{'='*70}")
    lines.append(f"  DRY RUN — No trades executed. Use --execute to run.")
    lines.append(f"{'='*70}\n")

    return "\n".join(lines)


def format_telegram(result: Dict) -> str:
    """Format rebalancing result for Telegram (compact, mobile-friendly)"""
    summary = result["summary"]
    actions = result["actions"]

    lines = []
    lines.append(f"*REBALANCE PLAN* ({result['session_id']})")
    lines.append("")

    # Portfolio overview
    lines.append(f"*Portfolio*: ${summary['total_portfolio']:,.2f}")
    lines.append(f"Invested: ${summary['total_invested']:,.2f} | Cash: ${summary['bankroll']:,.2f}")
    lines.append(f"Locked: ${summary['locked_capital']:,.2f} | HHI: {summary['hhi_before']:.0f}")
    lines.append("")

    # Action counts
    non_hold = [a for a in actions if a["action"] != "HOLD"]
    if non_hold:
        lines.append(f"*Actions*: EXIT {summary['actions_exit']} | REDUCE {summary['actions_reduce']} | ADD {summary['actions_add']} | HOLD {summary['actions_hold']}")
        lines.append(f"Free: ${summary['capital_to_free']:,.2f} | Deploy: ${summary['capital_to_deploy']:,.2f}")
        lines.append("")

        # Non-HOLD details (max 8)
        for a in non_hold[:8]:
            emoji = {"EXIT": "X", "REDUCE": "-", "ADD": "+"}
            icon = emoji.get(a["action"], "?")
            lines.append(f"[{icon}] {a['question'][:45]}")
            lines.append(f"   {a['side']} ${a['current_invested']:.0f} P&L:{a['pnl_pct']:+.1f}% {a['reason'][:40]}")
    else:
        lines.append("All positions within parameters. No actions needed.")

    # Categories
    cats = summary.get("categories", {})
    if cats:
        cat_parts = [f"{k}:{v['pct']:.0f}%" for k, v in sorted(cats.items(), key=lambda x: -x[1]["pct"])]
        lines.append(f"\n*Categories*: {' | '.join(cat_parts)}")

    return "\n".join(lines)


# === CLI ===

def main():
    parser = argparse.ArgumentParser(description="Portfolio Rebalancing Engine")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--execute", action="store_true",
                        help="Execute rebalancing actions after analysis")
    parser.add_argument("--force", action="store_true",
                        help="Skip confirmation when executing (use with --execute)")
    parser.add_argument("--action", type=str, default=None,
                        help="Only execute specific action type: EXIT, REDUCE, ADD (use with --execute)")
    parser.add_argument("--telegram", action="store_true",
                        help="Telegram-formatted compact output")
    parser.add_argument("--max-position-pct", type=float, default=15.0,
                        help="Max single position %% of portfolio (default: 15)")
    parser.add_argument("--max-category-pct", type=float, default=40.0,
                        help="Max category %% of portfolio (default: 40)")
    parser.add_argument("--kelly-fraction", type=float, default=0.5,
                        help="Kelly fraction (default: 0.5 = Half Kelly)")
    parser.add_argument("--bankroll", type=float, default=None,
                        help="Override bankroll (default: auto-fetch from CLOB)")
    parser.add_argument("--user-id", default="default", help="User ID")
    parser.add_argument("--no-slippage", action="store_true",
                        help="Skip slippage estimation (faster)")
    parser.add_argument("--use-estimator", action="store_true",
                        help="Use multi-source true probability estimator for edge calculation")

    args = parser.parse_args()

    try:
        result = run_rebalance(
            max_position_pct=args.max_position_pct,
            max_category_pct=args.max_category_pct,
            kelly_fraction=args.kelly_fraction,
            bankroll_override=args.bankroll,
            user_id=args.user_id,
            estimate_slippage_flag=not args.no_slippage,
            use_estimator=args.use_estimator,
        )
    except Exception as e:
        error(f"Rebalancing failed: {e}", code="REBALANCE_ERROR")
        return

    if result.get("error"):
        error(result["error"], code="NO_POSITIONS")
        return

    # Output the analysis report
    if args.json:
        success(data=result, message="rebalancing_plan_generated")
    elif args.telegram:
        report(format_telegram(result), data={
            "session_id": result["session_id"],
            "summary": result["summary"],
        })
    else:
        report_text = format_report(result)
        report(report_text, data={
            "session_id": result["session_id"],
            "summary": result["summary"],
        })

    # Execute if requested
    if args.execute:
        session_id = result["session_id"]
        non_hold = [a for a in result["actions"] if a["action"] != "HOLD"]

        if not non_hold:
            print("\n  No actions to execute (all HOLD).", file=sys.stderr)
            return

        # Filter by action type if specified
        if args.action:
            filter_upper = args.action.upper()
            non_hold = [a for a in non_hold if a["action"] == filter_upper]
            if not non_hold:
                print(f"\n  No {filter_upper} actions to execute.", file=sys.stderr)
                return

        print(f"\n  Session {session_id}: {len(non_hold)} action(s) to execute", file=sys.stderr)
        for a in non_hold:
            print(f"    {a['action']}: {a['question']} (${a['suggested_change_usd']:+,.2f})", file=sys.stderr)

        # Chain to execute_rebalance_pm.py
        try:
            from execute_rebalance_pm import load_session, preflight_check, execute_action, execution_report, ensure_execution_log_schema
            conn = db_utils.get_connection()
            ensure_execution_log_schema(conn)
            client = create_client()

            if not client.has_trading:
                error("Trading credentials not configured", code="NO_CREDS")
                conn.close()
                return

            # Pre-flight
            market_cache: Dict[str, Dict] = {}
            print("  Running pre-flight checks...", file=sys.stderr)
            actions_to_exec = load_session(conn, session_id, action_filter=args.action)

            if not actions_to_exec:
                print("  No pending actions found in session.", file=sys.stderr)
                conn.close()
                return

            ok, messages, preflight_summary = preflight_check(conn, client, actions_to_exec, market_cache)
            for msg in messages:
                print(f"  {msg}", file=sys.stderr)

            if not ok:
                error("Pre-flight check failed", code="PREFLIGHT_FAILED")
                conn.close()
                return

            # Confirmation
            if not args.force:
                try:
                    answer = input(f"\n  Execute {len(actions_to_exec)} action(s)? [y/N]: ").strip().lower()
                    if answer not in ("y", "yes"):
                        print("  Cancelled.", file=sys.stderr)
                        conn.close()
                        return
                except (EOFError, KeyboardInterrupt):
                    print("\n  Cancelled.", file=sys.stderr)
                    conn.close()
                    return

            # Execute
            results = []
            for i, action in enumerate(actions_to_exec, 1):
                mdata = market_cache.get(action["market_id"], {})
                question = mdata.get("question", action["market_id"])[:50]
                print(f"\n  [{i}/{len(actions_to_exec)}] {action['action']} — {question}...", file=sys.stderr)

                exec_result = execute_action(conn, client, action, market_cache, session_id)
                results.append(exec_result)

                status_icon = {"filled": "OK", "failed": "FAIL", "skipped": "SKIP"}.get(exec_result["status"], "??")
                print(f"    -> [{status_icon}] {exec_result.get('error_message') or 'Done'}", file=sys.stderr)

                if i < len(actions_to_exec):
                    time.sleep(1.0)

            # Report
            report_text, report_data = execution_report(session_id, results, preflight_summary, market_cache, conn)
            conn.close()

            if args.json:
                success(data=report_data, message="rebalance_executed")
            elif args.telegram:
                filled = sum(1 for r in results if r["status"] == "filled")
                failed = sum(1 for r in results if r["status"] == "failed")
                print(f"\n*Execution*: {filled} filled, {failed} failed, portfolio ${report_data.get('final_portfolio', 0):,.2f}")
            else:
                report(report_text, data=report_data)

        except ImportError:
            error("execute_rebalance_pm.py not found — cannot execute", code="MISSING_MODULE")
        except Exception as e:
            error(f"Execution failed: {e}", code="EXEC_ERROR")


if __name__ == "__main__":
    main()
