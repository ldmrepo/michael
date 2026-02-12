#!/usr/bin/env python3
"""
Cross-Asset Rebalancing Engine

Considers BOTH Polymarket positions AND Binance holdings to make
unified rebalancing decisions across platforms.

Reads Binance data from investment_holdings table (populated by investment skill).
Reads PM data from pm_positions table (populated by prediction-market skill).
Does NOT import from investment skill scripts directly — only reads shared DB.

Usage:
  python cross_asset_rebalancer.py                 # Full cross-asset report
  python cross_asset_rebalancer.py --json           # JSON output
  python cross_asset_rebalancer.py --pm-only        # PM positions only
  python cross_asset_rebalancer.py --binance-only   # Binance positions only
  python cross_asset_rebalancer.py --max-crypto-pct 60
  python cross_asset_rebalancer.py --dry-run        # Default, no execution
"""

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import db_utils
from config import DB_PATH, PROJECT_DATA_DIR
from output_format import error, report, success, table

# Try to import PM-specific modules (used for live PM data)
try:
    from polymarket_client import create_client
    HAS_PM_CLIENT = True
except ImportError:
    HAS_PM_CLIENT = False

try:
    from rebalance_engine import (
        _infer_category,
        calculate_concentration,
        calculate_herfindahl,
        fetch_live_market_data,
    )
    HAS_REBALANCE = True
except ImportError:
    HAS_REBALANCE = False

try:
    from calculate_kelly import kelly_criterion, size_position
    HAS_KELLY = True
except ImportError:
    HAS_KELLY = False


# === Schema for cross-asset rebalance sessions ===

CROSS_REBALANCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS pm_cross_rebalances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    asset_name TEXT,
    action TEXT NOT NULL,
    reason TEXT,
    current_size_usd REAL,
    suggested_change_usd REAL,
    target_size_usd REAL,
    category TEXT,
    edge_score REAL,
    created_at INTEGER DEFAULT (strftime('%s','now'))
);
CREATE INDEX IF NOT EXISTS idx_pm_cross_rebalances_session
    ON pm_cross_rebalances(session_id, created_at DESC);
"""


def ensure_cross_rebalance_schema(conn):
    """Create pm_cross_rebalances table if not exists"""
    conn.executescript(CROSS_REBALANCE_SCHEMA)


# ============================================================
#  Helpers: Binance DB access (reads from investment tables)
# ============================================================

def _binance_tables_exist(conn) -> bool:
    """Check if investment_holdings table exists in the shared DB"""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='investment_holdings'"
    ).fetchone()
    return row is not None


def _research_table_exists(conn) -> bool:
    """Check if investment_research table exists"""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='investment_research'"
    ).fetchone()
    return row is not None


def _snapshots_table_exists(conn) -> bool:
    """Check if investment_snapshots table exists"""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='investment_snapshots'"
    ).fetchone()
    return row is not None


def load_binance_holdings(conn, user_id: str = "default") -> List[Dict]:
    """Load Binance holdings from investment_holdings table"""
    if not _binance_tables_exist(conn):
        return []
    rows = conn.execute(
        "SELECT * FROM investment_holdings WHERE user_id = ? ORDER BY (current_price * quantity) DESC",
        (user_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def load_latest_crypto_prices(conn) -> Dict[str, float]:
    """
    Load latest crypto prices from investment_research table.
    Returns mapping like {"BTC": 68000.0, "ETH": 2500.0, ...}
    """
    if not _research_table_exists(conn):
        return {}

    prices = {}
    rows = conn.execute(
        "SELECT symbol, data_json FROM investment_research "
        "WHERE category = 'market' AND symbol IS NOT NULL "
        "ORDER BY collected_at DESC"
    ).fetchall()

    seen_symbols = set()
    for row in rows:
        row_d = dict(row)
        symbol = row_d.get("symbol", "")
        if not symbol or symbol in seen_symbols:
            continue
        seen_symbols.add(symbol)
        try:
            data = json.loads(row_d["data_json"])
            price = data.get("price") or data.get("current_price") or data.get("mark_price")
            if price is not None:
                # Normalize symbol: "BTCUSDT" -> "BTC"
                clean = symbol.replace("USDT", "").replace("USDC", "").replace("BUSD", "")
                prices[clean] = float(price)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

    return prices


def load_latest_binance_nav(conn, user_id: str = "default") -> Optional[Dict]:
    """Load most recent Binance NAV snapshot"""
    if not _snapshots_table_exists(conn):
        return None
    row = conn.execute(
        "SELECT * FROM investment_snapshots WHERE user_id = ? ORDER BY date DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    return dict(row) if row else None


# ============================================================
#  Crypto keyword detection (shared between PM + Binance)
# ============================================================

CRYPTO_SYMBOLS = {"BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "MATIC", "DOT", "LINK"}
CRYPTO_KEYWORDS = [
    "btc", "bitcoin", "eth", "ethereum", "sol", "solana", "crypto",
    "token", "blockchain", "defi", "nft", "web3", "altcoin",
]


def _is_crypto_related(question: str, tags: List[str]) -> bool:
    """Check if a PM market question or Binance symbol is crypto-related"""
    q_lower = question.lower()
    if any(kw in q_lower for kw in CRYPTO_KEYWORDS):
        return True
    tags_lower = [t.lower() for t in tags]
    if any(t in ("crypto", "bitcoin", "ethereum", "btc", "eth", "sol") for t in tags_lower):
        return True
    return False


def _extract_crypto_symbol(question: str) -> Optional[str]:
    """Try to extract a crypto symbol from a PM market question"""
    q_upper = question.upper()
    for sym in CRYPTO_SYMBOLS:
        if sym in q_upper:
            return sym
    # Extended check for full names
    name_map = {
        "BITCOIN": "BTC", "ETHEREUM": "ETH", "SOLANA": "SOL",
        "DOGECOIN": "DOGE", "CARDANO": "ADA", "AVALANCHE": "AVAX",
    }
    for name, sym in name_map.items():
        if name in q_upper:
            return sym
    return None


def _infer_pm_direction(side: str, question: str) -> Optional[str]:
    """
    Infer the directional stance of a PM crypto bet.
    Returns "BULLISH", "BEARISH", or None.

    For example:
      - BTC > $50K YES -> BULLISH
      - BTC > $50K NO  -> BEARISH
      - BTC < $45K YES -> BEARISH
    """
    q_lower = question.lower()
    above_keywords = ["above", "over", ">", "reach", "hit", "exceed", "surpass", "higher"]
    below_keywords = ["below", "under", "<", "fall", "drop", "crash", "lower"]

    is_above = any(kw in q_lower for kw in above_keywords)
    is_below = any(kw in q_lower for kw in below_keywords)

    if is_above:
        return "BULLISH" if side == "YES" else "BEARISH"
    elif is_below:
        return "BEARISH" if side == "YES" else "BULLISH"
    return None


# ============================================================
#  1. Unified Portfolio View
# ============================================================

def build_unified_portfolio(
    conn,
    user_id: str = "default",
    pm_only: bool = False,
    binance_only: bool = False,
) -> Dict:
    """
    Load PM positions + Binance holdings, normalize to common format,
    and compute total NAV across both platforms.
    """
    unified_positions = []
    pm_cash = 0.0
    binance_cash_equiv = 0.0

    # --- PM Positions ---
    if not binance_only:
        pm_positions = db_utils.get_positions(conn, user_id, "open")
        pm_market_data = {}

        # Fetch live PM market data if client available
        if HAS_PM_CLIENT and HAS_REBALANCE and pm_positions:
            try:
                client = create_client()
                market_ids = list(set(p["market_id"] for p in pm_positions))
                print(f"  Fetching live data for {len(market_ids)} PM markets...", file=sys.stderr)
                # Build slug_map from DB for reliable Gamma API lookups
                slug_map = {}
                for mid in market_ids:
                    mkt = db_utils.get_market(conn, mid)
                    if mkt and mkt.get("slug"):
                        slug_map[mid] = mkt["slug"]
                pm_market_data = fetch_live_market_data(client, market_ids, slug_map=slug_map)
                try:
                    pm_cash = client.get_balance_usdc()
                except Exception:
                    pm_cash = 0.0
            except Exception as e:
                print(f"  [WARN] PM client unavailable: {e}", file=sys.stderr)

        for pos in pm_positions:
            mid = pos["market_id"]
            side = pos["side"]
            entry_price = pos["entry_price"]
            size = pos["size"]
            invested = entry_price * size

            mdata = pm_market_data.get(mid, {})
            question = mdata.get("question", mid[:50])
            tags = mdata.get("tags", [])
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except (json.JSONDecodeError, TypeError):
                    tags = []

            if side == "YES":
                current_price = mdata.get("yes_price", entry_price)
            else:
                current_price = mdata.get("no_price", 1.0 - entry_price if entry_price < 1 else entry_price)

            current_value = current_price * size
            pnl = current_value - invested
            pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

            # Category via rebalance_engine if available
            if HAS_REBALANCE:
                category = _infer_category(tags, question)
            else:
                category = "crypto" if _is_crypto_related(question, tags) else "other"

            is_crypto = category == "crypto" or _is_crypto_related(question, tags)
            crypto_symbol = _extract_crypto_symbol(question) if is_crypto else None
            direction = _infer_pm_direction(side, question) if is_crypto else None

            unified_positions.append({
                "platform": "polymarket",
                "asset_class": "prediction",
                "asset_id": mid,
                "symbol": crypto_symbol or f"PM:{mid[:12]}",
                "name": question[:70] if question else mid[:40],
                "side": side,
                "size_usd": round(invested, 2),
                "current_value_usd": round(current_value, 2),
                "entry_price": round(entry_price, 4),
                "current_price": round(current_price, 4),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 1),
                "category": category,
                "is_crypto": is_crypto,
                "crypto_symbol": crypto_symbol,
                "crypto_direction": direction,
                "days_to_expiry": mdata.get("days_to_expiry"),
                "tags": tags,
                "raw_position": pos,
            })

    # --- Binance Holdings ---
    if not pm_only:
        binance_holdings = load_binance_holdings(conn, user_id)

        for h in binance_holdings:
            symbol = h.get("symbol", "")
            quantity = h.get("quantity", 0)
            current_price = h.get("current_price", 0) or 0
            avg_entry = h.get("avg_entry_price", 0) or 0
            unrealized_pnl = h.get("unrealized_pnl", 0) or 0
            leverage = h.get("leverage", 1) or 1
            account_type = h.get("account_type", "spot")

            # Skip stablecoins (they are cash equivalents)
            clean_sym = symbol.replace("USDT", "").replace("USDC", "").replace("BUSD", "")
            if clean_sym in ("USDT", "USDC", "BUSD", "DAI", "TUSD", "FDUSD", ""):
                # Track as cash
                binance_cash_equiv += quantity * (current_price if current_price > 0 else 1.0)
                continue

            size_usd = abs(quantity) * current_price if current_price > 0 else 0
            if size_usd < 1.0:
                continue  # Skip dust

            # Calculate PnL
            if avg_entry and avg_entry > 0 and current_price > 0:
                cost_basis = abs(quantity) * avg_entry
                pnl = unrealized_pnl if unrealized_pnl else (size_usd - cost_basis)
                pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0
            else:
                pnl = unrealized_pnl or 0
                pnl_pct = 0

            # Determine side for futures
            if account_type == "futures":
                position_side = h.get("position_side", "BOTH")
                if quantity > 0:
                    side = "LONG"
                elif quantity < 0:
                    side = "SHORT"
                else:
                    side = position_side
                direction = "BULLISH" if side == "LONG" else "BEARISH"
            else:
                side = "LONG"  # Spot is always long
                direction = "BULLISH"

            unified_positions.append({
                "platform": "binance",
                "asset_class": "crypto_" + account_type,
                "asset_id": symbol,
                "symbol": clean_sym,
                "name": f"{clean_sym} ({account_type.capitalize()}{f' {leverage}x' if leverage > 1 else ''})",
                "side": side,
                "size_usd": round(size_usd, 2),
                "current_value_usd": round(size_usd, 2),
                "entry_price": round(avg_entry, 2) if avg_entry else None,
                "current_price": round(current_price, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 1),
                "category": "crypto",
                "is_crypto": True,
                "crypto_symbol": clean_sym,
                "crypto_direction": direction,
                "leverage": leverage,
                "account_type": account_type,
                "liquidation_price": h.get("liquidation_price"),
                "days_to_expiry": None,
                "tags": [],
                "raw_position": h,
            })

    # Calculate totals
    total_pm_invested = sum(p["size_usd"] for p in unified_positions if p["platform"] == "polymarket")
    total_pm_value = sum(p["current_value_usd"] for p in unified_positions if p["platform"] == "polymarket")
    total_binance_value = sum(p["current_value_usd"] for p in unified_positions if p["platform"] == "binance")

    total_nav = total_pm_value + pm_cash + total_binance_value + binance_cash_equiv

    return {
        "positions": unified_positions,
        "pm_cash": round(pm_cash, 2),
        "binance_cash": round(binance_cash_equiv, 2),
        "total_pm_invested": round(total_pm_invested, 2),
        "total_pm_value": round(total_pm_value, 2),
        "total_binance_value": round(total_binance_value, 2),
        "total_nav": round(total_nav, 2),
        "total_cash": round(pm_cash + binance_cash_equiv, 2),
    }


# ============================================================
#  2. Cross-Asset Risk Analysis
# ============================================================

def analyze_cross_asset_risk(portfolio: Dict) -> Dict:
    """
    Analyze risk across both platforms:
    - Crypto exposure from PM + Binance
    - Category concentration
    - Contradictory positions
    - Leverage exposure
    - Hedging opportunities
    """
    positions = portfolio["positions"]
    total_nav = portfolio["total_nav"]

    if total_nav <= 0 or not positions:
        return {
            "total_crypto_exposure_usd": 0,
            "total_crypto_exposure_pct": 0,
            "category_concentration": {},
            "contradictions": [],
            "hedging_pairs": [],
            "leverage_analysis": {},
            "platform_concentration": {},
        }

    # --- Crypto exposure ---
    crypto_positions = [p for p in positions if p["is_crypto"]]
    total_crypto_usd = sum(p["current_value_usd"] for p in crypto_positions)
    total_crypto_pct = (total_crypto_usd / total_nav * 100) if total_nav > 0 else 0

    # Per-symbol crypto exposure
    crypto_by_symbol: Dict[str, Dict] = {}
    for p in crypto_positions:
        sym = p.get("crypto_symbol") or "UNKNOWN"
        if sym not in crypto_by_symbol:
            crypto_by_symbol[sym] = {
                "total_usd": 0,
                "pm_usd": 0,
                "binance_usd": 0,
                "pm_direction": None,
                "binance_direction": None,
                "positions": [],
            }
        crypto_by_symbol[sym]["total_usd"] += p["current_value_usd"]
        if p["platform"] == "polymarket":
            crypto_by_symbol[sym]["pm_usd"] += p["current_value_usd"]
            crypto_by_symbol[sym]["pm_direction"] = p.get("crypto_direction")
        else:
            crypto_by_symbol[sym]["binance_usd"] += p["current_value_usd"]
            crypto_by_symbol[sym]["binance_direction"] = p.get("crypto_direction")
        crypto_by_symbol[sym]["positions"].append(p)

    # --- Category concentration (all positions) ---
    category_totals: Dict[str, Dict] = {}
    for p in positions:
        cat = p["category"]
        if cat not in category_totals:
            category_totals[cat] = {"usd": 0, "count": 0, "pm_usd": 0, "binance_usd": 0}
        category_totals[cat]["usd"] += p["current_value_usd"]
        category_totals[cat]["count"] += 1
        if p["platform"] == "polymarket":
            category_totals[cat]["pm_usd"] += p["current_value_usd"]
        else:
            category_totals[cat]["binance_usd"] += p["current_value_usd"]

    for cat in category_totals:
        category_totals[cat]["pct"] = round(
            category_totals[cat]["usd"] / total_nav * 100, 1
        ) if total_nav > 0 else 0

    # --- Contradictory positions ---
    contradictions = []
    for sym, info in crypto_by_symbol.items():
        pm_dir = info.get("pm_direction")
        bin_dir = info.get("binance_direction")
        if pm_dir and bin_dir and pm_dir != bin_dir:
            contradictions.append({
                "symbol": sym,
                "pm_direction": pm_dir,
                "pm_usd": round(info["pm_usd"], 2),
                "binance_direction": bin_dir,
                "binance_usd": round(info["binance_usd"], 2),
                "severity": "high" if min(info["pm_usd"], info["binance_usd"]) > 50 else "low",
                "suggestion": (
                    f"Contradictory stance on {sym}: PM={pm_dir} vs Binance={bin_dir}. "
                    f"Consider aligning or explicitly hedging."
                ),
            })

    # --- Hedging pairs (same symbol, complementary directions) ---
    hedging_pairs = []
    for sym, info in crypto_by_symbol.items():
        pm_dir = info.get("pm_direction")
        bin_dir = info.get("binance_direction")
        # If PM is BEARISH and Binance is BULLISH, the PM bet hedges the Binance holding
        if pm_dir == "BEARISH" and bin_dir == "BULLISH":
            hedge_ratio = info["pm_usd"] / info["binance_usd"] if info["binance_usd"] > 0 else 0
            hedging_pairs.append({
                "symbol": sym,
                "hedge_type": "PM_NO_hedges_Binance_LONG",
                "pm_usd": round(info["pm_usd"], 2),
                "binance_usd": round(info["binance_usd"], 2),
                "hedge_ratio": round(hedge_ratio, 2),
                "assessment": (
                    "Good hedge" if 0.1 <= hedge_ratio <= 0.5
                    else "Over-hedged" if hedge_ratio > 0.5
                    else "Under-hedged"
                ),
            })

    # --- Leverage analysis ---
    leveraged_positions = [p for p in positions if p.get("leverage", 1) > 1]
    total_leveraged_notional = sum(
        p["current_value_usd"] * p.get("leverage", 1) for p in leveraged_positions
    )
    total_position_value = sum(p["current_value_usd"] for p in positions)
    weighted_leverage = (
        total_leveraged_notional / total_position_value
        if total_position_value > 0 else 1.0
    )

    leverage_analysis = {
        "leveraged_position_count": len(leveraged_positions),
        "total_leveraged_notional_usd": round(total_leveraged_notional, 2),
        "weighted_avg_leverage": round(weighted_leverage, 2),
        "max_leverage": max((p.get("leverage", 1) for p in positions), default=1),
        "at_risk_liquidation": [
            {
                "symbol": p["symbol"],
                "leverage": p.get("leverage"),
                "liquidation_price": p.get("liquidation_price"),
                "current_price": p["current_price"],
            }
            for p in leveraged_positions
            if p.get("liquidation_price") and p["current_price"]
            and abs(p["current_price"] - p["liquidation_price"]) / p["current_price"] < 0.15
        ],
    }

    # --- Platform concentration ---
    pm_value = portfolio["total_pm_value"] + portfolio["pm_cash"]
    binance_value = portfolio["total_binance_value"] + portfolio["binance_cash"]
    platform_concentration = {
        "polymarket": {
            "value_usd": round(pm_value, 2),
            "pct": round(pm_value / total_nav * 100, 1) if total_nav > 0 else 0,
        },
        "binance": {
            "value_usd": round(binance_value, 2),
            "pct": round(binance_value / total_nav * 100, 1) if total_nav > 0 else 0,
        },
    }

    return {
        "total_crypto_exposure_usd": round(total_crypto_usd, 2),
        "total_crypto_exposure_pct": round(total_crypto_pct, 1),
        "crypto_by_symbol": {
            sym: {
                "total_usd": round(info["total_usd"], 2),
                "pm_usd": round(info["pm_usd"], 2),
                "binance_usd": round(info["binance_usd"], 2),
                "pct_of_nav": round(info["total_usd"] / total_nav * 100, 1) if total_nav > 0 else 0,
            }
            for sym, info in crypto_by_symbol.items()
        },
        "category_concentration": {
            cat: {"usd": round(v["usd"], 2), "pct": v["pct"], "count": v["count"]}
            for cat, v in category_totals.items()
        },
        "contradictions": contradictions,
        "hedging_pairs": hedging_pairs,
        "leverage_analysis": leverage_analysis,
        "platform_concentration": platform_concentration,
    }


# ============================================================
#  3. Unified Rebalancing Plan
# ============================================================

def _pm_edge_score(pos: Dict, market_data: Dict) -> float:
    """
    Compute heuristic edge score for a PM position.
    Positive = market appears favorable, negative = unfavorable.
    """
    side = pos.get("side", "YES")
    entry_price = pos.get("entry_price", 0)
    current_price = pos.get("current_price", 0)

    if entry_price <= 0:
        return 0.0

    # PnL-based proxy
    pnl_pct = ((current_price - entry_price) / entry_price * 100) if side == "YES" else (
        ((1 - current_price) - entry_price) / entry_price * 100 if entry_price > 0 else 0
    )

    # Time premium: positions near 0 or 1 have little upside
    if current_price > 0.95 or current_price < 0.05:
        time_penalty = -20
    elif pos.get("days_to_expiry") is not None and pos["days_to_expiry"] < 2:
        time_penalty = -15
    else:
        time_penalty = 0

    edge = pnl_pct * 0.5 + time_penalty
    return round(edge, 1)


def _binance_edge_score(pos: Dict) -> float:
    """
    Compute heuristic edge score for a Binance position.
    Based on PnL momentum and leverage risk.
    """
    pnl_pct = pos.get("pnl_pct", 0)
    leverage = pos.get("leverage", 1) or 1

    # Momentum score from PnL
    momentum = pnl_pct * 0.3

    # Leverage penalty: high leverage = more risk
    leverage_penalty = 0
    if leverage > 5:
        leverage_penalty = -15
    elif leverage > 3:
        leverage_penalty = -8
    elif leverage > 1:
        leverage_penalty = -3

    # Liquidation proximity penalty
    liq_price = pos.get("liquidation_price")
    current_price = pos.get("current_price", 0)
    liq_penalty = 0
    if liq_price and current_price and current_price > 0:
        distance_pct = abs(current_price - liq_price) / current_price * 100
        if distance_pct < 5:
            liq_penalty = -30
        elif distance_pct < 10:
            liq_penalty = -15
        elif distance_pct < 20:
            liq_penalty = -5

    return round(momentum + leverage_penalty + liq_penalty, 1)


def _determine_unified_action(
    pos: Dict,
    edge_score: float,
    allocation_pct: float,
    crypto_pct: float,
    max_crypto_pct: float,
    max_single_pct: float,
    has_contradiction: bool,
) -> Tuple[str, str, int]:
    """
    Determine action for a unified position.
    Returns (action, reason, priority).
    Priority: 1=EXIT, 2=REDUCE, 3=HOLD, 4=ADD, 5=TRANSFER
    """
    platform = pos["platform"]

    # --- EXIT conditions ---

    # Market closed / near certainty (PM only)
    if platform == "polymarket":
        cp = pos.get("current_price", 0)
        if cp > 0.97 or cp < 0.03:
            return ("EXIT", f"Price ${cp:.2f} near boundary — low capital efficiency", 1)
        dte = pos.get("days_to_expiry")
        if dte is not None and dte < 1 and pos["pnl"] < 0:
            return ("EXIT", f"Expiring in <1 day with loss ${pos['pnl']:+.2f}", 1)

    # Contradictory position
    if has_contradiction:
        return ("REDUCE", f"Contradicts position on other platform — resolve directional conflict", 2)

    # Liquidation risk (Binance futures)
    if pos.get("liquidation_price") and pos.get("current_price"):
        distance = abs(pos["current_price"] - pos["liquidation_price"]) / pos["current_price"] * 100
        if distance < 5:
            return ("EXIT", f"Liquidation at ${pos['liquidation_price']:.2f} — only {distance:.1f}% away", 1)
        elif distance < 10:
            return ("REDUCE", f"Liquidation proximity warning: {distance:.1f}% buffer", 2)

    # Stop loss: significant loss
    if pos["pnl_pct"] < -25 and platform == "polymarket":
        return ("EXIT", f"Stop loss: P&L {pos['pnl_pct']:+.1f}%", 1)
    if pos["pnl_pct"] < -15 and platform == "binance" and pos.get("leverage", 1) > 1:
        return ("REDUCE", f"Leveraged loss {pos['pnl_pct']:+.1f}% at {pos.get('leverage', 1)}x", 2)

    # --- REDUCE conditions ---

    # Single position too large
    if allocation_pct > max_single_pct:
        return ("REDUCE", f"Position {allocation_pct:.1f}% > {max_single_pct:.0f}% limit", 2)

    # Crypto overweight
    if pos["is_crypto"] and crypto_pct > max_crypto_pct:
        return ("REDUCE", f"Crypto at {crypto_pct:.1f}% > {max_crypto_pct:.0f}% limit", 2)

    # Negative edge
    if edge_score < -15:
        return ("REDUCE", f"Negative edge ({edge_score:.1f})", 2)

    # --- ADD conditions ---
    if edge_score > 25 and allocation_pct < 10:
        return ("ADD", f"Strong edge ({edge_score:.1f}) with low allocation ({allocation_pct:.1f}%)", 4)

    # --- HOLD (default) ---
    return ("HOLD", f"Within parameters (edge={edge_score:.1f}, alloc={allocation_pct:.1f}%)", 3)


def generate_rebalance_plan(
    portfolio: Dict,
    risk_analysis: Dict,
    max_crypto_pct: float = 60.0,
    max_single_pct: float = 15.0,
    max_leverage: float = 3.0,
) -> Dict:
    """
    Generate unified rebalancing plan for both platforms.
    """
    positions = portfolio["positions"]
    total_nav = portfolio["total_nav"]

    if total_nav <= 0 or not positions:
        return {"actions": [], "summary": {}}

    # Build set of contradicted symbols
    contradicted_symbols = set()
    for c in risk_analysis.get("contradictions", []):
        contradicted_symbols.add(c["symbol"])

    crypto_pct = risk_analysis.get("total_crypto_exposure_pct", 0)

    actions = []
    for pos in positions:
        alloc_pct = (pos["current_value_usd"] / total_nav * 100) if total_nav > 0 else 0
        has_contradiction = pos.get("crypto_symbol") in contradicted_symbols

        # Calculate edge score
        if pos["platform"] == "polymarket":
            edge = _pm_edge_score(pos, {})
        else:
            edge = _binance_edge_score(pos)

        action, reason, priority = _determine_unified_action(
            pos, edge, alloc_pct, crypto_pct,
            max_crypto_pct, max_single_pct, has_contradiction,
        )

        # Calculate suggested change
        current_usd = pos["current_value_usd"]
        if action == "EXIT":
            suggested_change = -current_usd
            target_usd = 0
        elif action == "REDUCE":
            target_alloc = min(alloc_pct, max_single_pct) * 0.7
            target_usd = total_nav * (target_alloc / 100)
            suggested_change = target_usd - current_usd
            if suggested_change > -5:
                suggested_change = -(current_usd * 0.3)
                target_usd = current_usd + suggested_change
        elif action == "ADD":
            # Add up to 5% of NAV
            add_amount = min(total_nav * 0.05, portfolio["total_cash"] * 0.2)
            suggested_change = max(add_amount, 0)
            target_usd = current_usd + suggested_change
        else:
            suggested_change = 0
            target_usd = current_usd

        actions.append({
            "platform": pos["platform"],
            "asset_id": pos["asset_id"],
            "asset_name": pos["name"],
            "symbol": pos["symbol"],
            "side": pos["side"],
            "category": pos["category"],
            "is_crypto": pos["is_crypto"],
            "action": action,
            "reason": reason,
            "priority": priority,
            "edge_score": edge,
            "current_size_usd": round(current_usd, 2),
            "suggested_change_usd": round(suggested_change, 2),
            "target_size_usd": round(max(target_usd, 0), 2),
            "current_allocation_pct": round(alloc_pct, 1),
            "target_allocation_pct": round(max(target_usd, 0) / total_nav * 100, 1) if total_nav > 0 else 0,
            "pnl": pos["pnl"],
            "pnl_pct": pos["pnl_pct"],
            "leverage": pos.get("leverage", 1),
        })

    # Sort: EXIT first, then REDUCE, then HOLD, then ADD
    actions.sort(key=lambda a: (a["priority"], -abs(a["suggested_change_usd"])))

    # Summary
    exit_count = sum(1 for a in actions if a["action"] == "EXIT")
    reduce_count = sum(1 for a in actions if a["action"] == "REDUCE")
    hold_count = sum(1 for a in actions if a["action"] == "HOLD")
    add_count = sum(1 for a in actions if a["action"] == "ADD")

    capital_freed = abs(sum(
        a["suggested_change_usd"] for a in actions
        if a["action"] in ("EXIT", "REDUCE") and a["suggested_change_usd"] < 0
    ))
    capital_deployed = sum(
        a["suggested_change_usd"] for a in actions
        if a["action"] == "ADD" and a["suggested_change_usd"] > 0
    )

    pm_actions = [a for a in actions if a["platform"] == "polymarket" and a["action"] != "HOLD"]
    binance_actions = [a for a in actions if a["platform"] == "binance" and a["action"] != "HOLD"]

    summary = {
        "total_actions": len(actions),
        "exit": exit_count,
        "reduce": reduce_count,
        "hold": hold_count,
        "add": add_count,
        "capital_to_free_usd": round(capital_freed, 2),
        "capital_to_deploy_usd": round(capital_deployed, 2),
        "pm_action_count": len(pm_actions),
        "binance_action_count": len(binance_actions),
        "max_crypto_pct": max_crypto_pct,
        "max_single_pct": max_single_pct,
        "max_leverage": max_leverage,
    }

    return {"actions": actions, "summary": summary}


# ============================================================
#  4. Capital Flow Optimizer
# ============================================================

# Transaction cost estimates (in USD per $100 moved)
PM_DEPOSIT_COST_PCT = 1.0    # DEX swap fee + gas (~1% for Paraswap + Polygon gas)
PM_WITHDRAW_COST_PCT = 0.5   # Bridge/swap back (estimated)
BINANCE_WITHDRAW_COST_PCT = 0.3  # Withdrawal fee (network dependent)
BINANCE_DEPOSIT_COST_PCT = 0.0   # Free to deposit


def optimize_capital_flow(
    portfolio: Dict,
    rebalance_plan: Dict,
    risk_analysis: Dict,
) -> Dict:
    """
    Determine optimal capital distribution between platforms.
    Consider transaction costs and platform-specific opportunities.
    """
    pm_cash = portfolio["pm_cash"]
    binance_cash = portfolio["binance_cash"]
    total_nav = portfolio["total_nav"]
    total_cash = portfolio["total_cash"]
    actions = rebalance_plan.get("actions", [])
    summary = rebalance_plan.get("summary", {})

    # Capital freed by EXIT/REDUCE per platform
    pm_freed = abs(sum(
        a["suggested_change_usd"] for a in actions
        if a["platform"] == "polymarket" and a["action"] in ("EXIT", "REDUCE")
        and a["suggested_change_usd"] < 0
    ))
    binance_freed = abs(sum(
        a["suggested_change_usd"] for a in actions
        if a["platform"] == "binance" and a["action"] in ("EXIT", "REDUCE")
        and a["suggested_change_usd"] < 0
    ))

    # Capital needed for ADD per platform
    pm_needed = sum(
        a["suggested_change_usd"] for a in actions
        if a["platform"] == "polymarket" and a["action"] == "ADD"
        and a["suggested_change_usd"] > 0
    )
    binance_needed = sum(
        a["suggested_change_usd"] for a in actions
        if a["platform"] == "binance" and a["action"] == "ADD"
        and a["suggested_change_usd"] > 0
    )

    # Available after rebalance per platform
    pm_available = pm_cash + pm_freed
    binance_available = binance_cash + binance_freed

    # Net surplus/deficit per platform
    pm_surplus = pm_available - pm_needed
    binance_surplus = binance_available - binance_needed

    # Determine flow direction
    flows = []

    # PM has excess, Binance needs capital
    if pm_surplus > 50 and binance_surplus < -50:
        transfer_amount = min(pm_surplus * 0.5, abs(binance_surplus))
        cost = transfer_amount * (PM_WITHDRAW_COST_PCT + BINANCE_DEPOSIT_COST_PCT) / 100
        net_transfer = transfer_amount - cost
        if net_transfer > 20:
            flows.append({
                "direction": "PM -> Binance",
                "gross_amount": round(transfer_amount, 2),
                "estimated_cost": round(cost, 2),
                "net_amount": round(net_transfer, 2),
                "reason": f"PM surplus ${pm_surplus:.0f}, Binance deficit ${abs(binance_surplus):.0f}",
                "steps": [
                    "Sell/exit PM positions to free USDC.e",
                    "Swap USDC.e -> Native USDC via Paraswap on Polygon",
                    "Bridge/withdraw to Binance (Polygon network)",
                    "Deploy into Binance opportunities",
                ],
            })

    # Binance has excess, PM needs capital
    if binance_surplus > 50 and pm_surplus < -50:
        transfer_amount = min(binance_surplus * 0.5, abs(pm_surplus))
        cost = transfer_amount * (BINANCE_WITHDRAW_COST_PCT + PM_DEPOSIT_COST_PCT) / 100
        net_transfer = transfer_amount - cost
        if net_transfer > 20:
            flows.append({
                "direction": "Binance -> PM",
                "gross_amount": round(transfer_amount, 2),
                "estimated_cost": round(cost, 2),
                "net_amount": round(net_transfer, 2),
                "reason": f"Binance surplus ${binance_surplus:.0f}, PM deficit ${abs(pm_surplus):.0f}",
                "steps": [
                    "Withdraw USDC from Binance via Polygon",
                    "Swap Native USDC -> USDC.e via Paraswap ($50 chunks)",
                    "Transfer USDC.e to Proxy Wallet",
                    "Deploy into PM high-EV markets",
                ],
            })

    # Both have surplus — suggest rebalancing toward optimal allocation
    if pm_surplus > 100 and binance_surplus > 100:
        pm_pct = risk_analysis.get("platform_concentration", {}).get("polymarket", {}).get("pct", 50)
        binance_pct = risk_analysis.get("platform_concentration", {}).get("binance", {}).get("pct", 50)

        if abs(pm_pct - binance_pct) > 20:
            # Significantly unbalanced
            if pm_pct > binance_pct + 20:
                transfer = min(pm_surplus * 0.3, total_nav * 0.05)
                cost = transfer * (PM_WITHDRAW_COST_PCT + BINANCE_DEPOSIT_COST_PCT) / 100
                if transfer - cost > 20:
                    flows.append({
                        "direction": "PM -> Binance (rebalance)",
                        "gross_amount": round(transfer, 2),
                        "estimated_cost": round(cost, 2),
                        "net_amount": round(transfer - cost, 2),
                        "reason": f"Platform imbalance: PM {pm_pct:.0f}% vs Binance {binance_pct:.0f}%",
                        "steps": ["Gradually shift allocation toward 50/50 split"],
                    })
            elif binance_pct > pm_pct + 20:
                transfer = min(binance_surplus * 0.3, total_nav * 0.05)
                cost = transfer * (BINANCE_WITHDRAW_COST_PCT + PM_DEPOSIT_COST_PCT) / 100
                if transfer - cost > 20:
                    flows.append({
                        "direction": "Binance -> PM (rebalance)",
                        "gross_amount": round(transfer, 2),
                        "estimated_cost": round(cost, 2),
                        "net_amount": round(transfer - cost, 2),
                        "reason": f"Platform imbalance: Binance {binance_pct:.0f}% vs PM {pm_pct:.0f}%",
                        "steps": ["Gradually shift allocation toward 50/50 split"],
                    })

    # Optimal distribution recommendation
    pm_total = portfolio["total_pm_value"] + pm_cash
    binance_total = portfolio["total_binance_value"] + binance_cash

    optimal = {
        "current_pm_pct": round(pm_total / total_nav * 100, 1) if total_nav > 0 else 0,
        "current_binance_pct": round(binance_total / total_nav * 100, 1) if total_nav > 0 else 0,
        "pm_available_after_rebalance": round(pm_available, 2),
        "binance_available_after_rebalance": round(binance_available, 2),
        "suggested_flows": flows,
        "total_estimated_transfer_cost": round(sum(f["estimated_cost"] for f in flows), 2),
    }

    return optimal


# ============================================================
#  5. Full report formatting
# ============================================================

def format_cross_asset_report(
    portfolio: Dict,
    risk_analysis: Dict,
    rebalance_plan: Dict,
    capital_flow: Dict,
    session_id: str,
) -> str:
    """Format the complete cross-asset report as human-readable text"""
    lines = []
    lines.append(f"\n{'='*72}")
    lines.append(f"  CROSS-ASSET REBALANCING REPORT")
    lines.append(f"  Session: {session_id}  |  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"{'='*72}")

    # --- Portfolio Overview ---
    lines.append(f"\n  UNIFIED PORTFOLIO OVERVIEW:")
    lines.append(f"  {'─'*60}")
    lines.append(f"  Total NAV:              ${portfolio['total_nav']:>12,.2f}")
    lines.append(f"  PM Positions:           ${portfolio['total_pm_value']:>12,.2f}")
    lines.append(f"  PM Cash (USDC.e):       ${portfolio['pm_cash']:>12,.2f}")
    lines.append(f"  Binance Positions:      ${portfolio['total_binance_value']:>12,.2f}")
    lines.append(f"  Binance Cash:           ${portfolio['binance_cash']:>12,.2f}")

    pm_pct = risk_analysis.get("platform_concentration", {}).get("polymarket", {}).get("pct", 0)
    bin_pct = risk_analysis.get("platform_concentration", {}).get("binance", {}).get("pct", 0)
    lines.append(f"  Platform Split:         PM {pm_pct:.0f}%  |  Binance {bin_pct:.0f}%")

    # --- Crypto Exposure ---
    lines.append(f"\n  CRYPTO EXPOSURE:")
    lines.append(f"  {'─'*60}")
    lines.append(f"  Total Crypto:           ${risk_analysis['total_crypto_exposure_usd']:>12,.2f}  ({risk_analysis['total_crypto_exposure_pct']:.1f}%)")

    crypto_by_sym = risk_analysis.get("crypto_by_symbol", {})
    if crypto_by_sym:
        for sym, info in sorted(crypto_by_sym.items(), key=lambda x: -x[1]["total_usd"]):
            pm_part = f"PM ${info['pm_usd']:,.0f}" if info["pm_usd"] > 0 else ""
            bin_part = f"Binance ${info['binance_usd']:,.0f}" if info["binance_usd"] > 0 else ""
            parts = " + ".join(filter(None, [pm_part, bin_part]))
            lines.append(f"    {sym:<6} ${info['total_usd']:>10,.2f}  ({info['pct_of_nav']:.1f}%)  [{parts}]")

    # --- Category Concentration ---
    cats = risk_analysis.get("category_concentration", {})
    if cats:
        lines.append(f"\n  CATEGORY CONCENTRATION:")
        lines.append(f"  {'─'*60}")
        for cat, info in sorted(cats.items(), key=lambda x: -x[1]["pct"]):
            bar = "#" * int(info["pct"] / 2)
            lines.append(f"    {cat:<15} ${info['usd']:>10,.2f}  {info['pct']:>5.1f}%  {bar}")

    # --- Contradictions ---
    contradictions = risk_analysis.get("contradictions", [])
    if contradictions:
        lines.append(f"\n  !!! CONTRADICTORY POSITIONS ({len(contradictions)}):")
        lines.append(f"  {'─'*60}")
        for c in contradictions:
            lines.append(f"    {c['symbol']}: PM={c['pm_direction']} (${c['pm_usd']:.0f}) vs "
                         f"Binance={c['binance_direction']} (${c['binance_usd']:.0f})  "
                         f"[{c['severity'].upper()}]")
            lines.append(f"      -> {c['suggestion']}")

    # --- Hedging Pairs ---
    hedges = risk_analysis.get("hedging_pairs", [])
    if hedges:
        lines.append(f"\n  HEDGING PAIRS ({len(hedges)}):")
        lines.append(f"  {'─'*60}")
        for h in hedges:
            lines.append(f"    {h['symbol']}: PM hedge ${h['pm_usd']:.0f} vs "
                         f"Binance exposure ${h['binance_usd']:.0f}  "
                         f"(ratio: {h['hedge_ratio']:.2f} — {h['assessment']})")

    # --- Leverage Analysis ---
    lev = risk_analysis.get("leverage_analysis", {})
    if lev.get("leveraged_position_count", 0) > 0:
        lines.append(f"\n  LEVERAGE ANALYSIS:")
        lines.append(f"  {'─'*60}")
        lines.append(f"    Leveraged Positions:   {lev['leveraged_position_count']}")
        lines.append(f"    Total Notional:        ${lev['total_leveraged_notional_usd']:>12,.2f}")
        lines.append(f"    Weighted Avg Leverage:  {lev['weighted_avg_leverage']:.1f}x")
        lines.append(f"    Max Leverage:           {lev['max_leverage']}x")
        if lev.get("at_risk_liquidation"):
            lines.append(f"    ** LIQUIDATION WARNINGS:")
            for lr in lev["at_risk_liquidation"]:
                lines.append(f"       {lr['symbol']} @ {lr['leverage']}x: "
                             f"current ${lr['current_price']:.2f}, liq ${lr['liquidation_price']:.2f}")

    # --- Rebalancing Actions ---
    actions = rebalance_plan.get("actions", [])
    plan_summary = rebalance_plan.get("summary", {})

    lines.append(f"\n  REBALANCING ACTIONS:")
    lines.append(f"  {'─'*60}")
    lines.append(f"    EXIT: {plan_summary.get('exit', 0):>3}  |  Capital to free:   ${plan_summary.get('capital_to_free_usd', 0):>10,.2f}")
    lines.append(f"    REDUCE: {plan_summary.get('reduce', 0):>1}  |  Capital to deploy: ${plan_summary.get('capital_to_deploy_usd', 0):>10,.2f}")
    lines.append(f"    HOLD: {plan_summary.get('hold', 0):>3}  |  PM actions: {plan_summary.get('pm_action_count', 0)}  Binance: {plan_summary.get('binance_action_count', 0)}")
    lines.append(f"    ADD:  {plan_summary.get('add', 0):>3}  |")

    for priority, label in [(1, "EXIT"), (2, "REDUCE"), (3, "HOLD"), (4, "ADD")]:
        priority_actions = [a for a in actions if a["priority"] == priority]
        if not priority_actions:
            continue

        lines.append(f"\n  {'='*72}")
        lines.append(f"  Priority {priority}: {label} ({len(priority_actions)} positions)")
        lines.append(f"  {'='*72}")

        for i, a in enumerate(priority_actions, 1):
            platform_tag = "PM" if a["platform"] == "polymarket" else "BIN"
            lines.append(f"\n  [{i}] {a['action']} [{platform_tag}] — {a['asset_name']}")
            lines.append(f"      Side: {a['side']}  |  Size: ${a['current_size_usd']:.2f}  |  "
                         f"P&L: ${a['pnl']:+.2f} ({a['pnl_pct']:+.1f}%)")
            lines.append(f"      Alloc: {a['current_allocation_pct']:.1f}%  |  "
                         f"Edge: {a['edge_score']:+.1f}  |  "
                         f"Category: {a['category']}")
            lines.append(f"      Reason: {a['reason']}")
            if a["suggested_change_usd"] != 0:
                lines.append(f"      Suggested: ${a['suggested_change_usd']:+,.2f}  ->  "
                             f"Target: ${a['target_size_usd']:,.2f} ({a['target_allocation_pct']:.1f}%)")

    # --- Capital Flow ---
    flows = capital_flow.get("suggested_flows", [])
    if flows:
        lines.append(f"\n  CAPITAL FLOW SUGGESTIONS:")
        lines.append(f"  {'─'*60}")
        for j, f in enumerate(flows, 1):
            lines.append(f"  [{j}] {f['direction']}")
            lines.append(f"      Amount: ${f['gross_amount']:,.2f}  (cost: ${f['estimated_cost']:,.2f}, "
                         f"net: ${f['net_amount']:,.2f})")
            lines.append(f"      Reason: {f['reason']}")
            for step in f.get("steps", []):
                lines.append(f"        - {step}")

        total_cost = capital_flow.get("total_estimated_transfer_cost", 0)
        if total_cost > 0:
            lines.append(f"\n      Total estimated transfer costs: ${total_cost:,.2f}")
    else:
        lines.append(f"\n  CAPITAL FLOW: No cross-platform transfers recommended.")

    lines.append(f"\n  Current split: PM {capital_flow.get('current_pm_pct', 0):.0f}%  |  "
                 f"Binance {capital_flow.get('current_binance_pct', 0):.0f}%")

    lines.append(f"\n{'='*72}")
    lines.append(f"  DRY RUN — No trades executed.")
    lines.append(f"{'='*72}\n")

    return "\n".join(lines)


# ============================================================
#  Main engine
# ============================================================

def run_cross_asset_rebalance(
    max_crypto_pct: float = 60.0,
    max_single_pct: float = 15.0,
    max_leverage: float = 3.0,
    user_id: str = "default",
    pm_only: bool = False,
    binance_only: bool = False,
) -> Dict:
    """
    Run the full cross-asset rebalancing analysis.
    Returns structured data with portfolio, risk, actions, and capital flow.
    """
    session_id = str(uuid.uuid4())[:8]
    conn = db_utils.get_connection()
    ensure_cross_rebalance_schema(conn)

    # 1. Build unified portfolio
    print("  Building unified portfolio...", file=sys.stderr)
    portfolio = build_unified_portfolio(conn, user_id, pm_only=pm_only, binance_only=binance_only)

    if not portfolio["positions"]:
        conn.close()
        return {
            "session_id": session_id,
            "error": "No positions found on either platform",
            "portfolio": portfolio,
            "risk_analysis": {},
            "rebalance_plan": {"actions": [], "summary": {}},
            "capital_flow": {},
        }

    # 2. Cross-asset risk analysis
    print("  Analyzing cross-asset risk...", file=sys.stderr)
    risk_analysis = analyze_cross_asset_risk(portfolio)

    # 3. Generate rebalancing plan
    print("  Generating rebalance plan...", file=sys.stderr)
    rebalance_plan = generate_rebalance_plan(
        portfolio, risk_analysis,
        max_crypto_pct=max_crypto_pct,
        max_single_pct=max_single_pct,
        max_leverage=max_leverage,
    )

    # 4. Optimize capital flow
    print("  Optimizing capital flow...", file=sys.stderr)
    capital_flow = optimize_capital_flow(portfolio, rebalance_plan, risk_analysis)

    # 5. Save actions to DB
    for a in rebalance_plan.get("actions", []):
        conn.execute("""
            INSERT INTO pm_cross_rebalances
                (session_id, platform, asset_id, asset_name, action, reason,
                 current_size_usd, suggested_change_usd, target_size_usd, category, edge_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            a["platform"],
            a["asset_id"],
            a["asset_name"],
            a["action"],
            a["reason"],
            a["current_size_usd"],
            a["suggested_change_usd"],
            a["target_size_usd"],
            a["category"],
            a["edge_score"],
        ))
    conn.commit()
    conn.close()

    return {
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "portfolio": portfolio,
        "risk_analysis": risk_analysis,
        "rebalance_plan": rebalance_plan,
        "capital_flow": capital_flow,
    }


# ============================================================
#  CLI Interface
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Cross-Asset Rebalancing Engine")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Show plan without executing (default)")
    parser.add_argument("--pm-only", action="store_true",
                        help="Show Polymarket positions only")
    parser.add_argument("--binance-only", action="store_true",
                        help="Show Binance positions only")
    parser.add_argument("--max-crypto-pct", type=float, default=60.0,
                        help="Max total crypto exposure %% of NAV (default: 60)")
    parser.add_argument("--max-single-pct", type=float, default=15.0,
                        help="Max single position %% of NAV (default: 15)")
    parser.add_argument("--max-leverage", type=float, default=3.0,
                        help="Max weighted average leverage (default: 3.0)")
    parser.add_argument("--user-id", default="default", help="User ID")

    args = parser.parse_args()

    if args.pm_only and args.binance_only:
        error("Cannot use --pm-only and --binance-only together", code="INVALID_ARGS")
        return

    try:
        result = run_cross_asset_rebalance(
            max_crypto_pct=args.max_crypto_pct,
            max_single_pct=args.max_single_pct,
            max_leverage=args.max_leverage,
            user_id=args.user_id,
            pm_only=args.pm_only,
            binance_only=args.binance_only,
        )
    except Exception as e:
        error(f"Cross-asset rebalancing failed: {e}", code="CROSS_REBALANCE_ERROR")
        return

    if result.get("error"):
        error(result["error"], code="NO_POSITIONS")
        return

    if args.json:
        # Strip raw_position from JSON output (not serializable cleanly)
        for pos in result.get("portfolio", {}).get("positions", []):
            pos.pop("raw_position", None)
        success(data=result, message="cross_asset_rebalance_complete")
    else:
        report_text = format_cross_asset_report(
            result["portfolio"],
            result["risk_analysis"],
            result["rebalance_plan"],
            result["capital_flow"],
            result["session_id"],
        )
        # Strip raw_position before passing to data
        for pos in result.get("portfolio", {}).get("positions", []):
            pos.pop("raw_position", None)
        report(report_text, data={
            "session_id": result["session_id"],
            "portfolio_summary": {
                "total_nav": result["portfolio"]["total_nav"],
                "pm_value": result["portfolio"]["total_pm_value"],
                "binance_value": result["portfolio"]["total_binance_value"],
                "total_cash": result["portfolio"]["total_cash"],
            },
            "risk_summary": {
                "crypto_exposure_pct": result["risk_analysis"].get("total_crypto_exposure_pct", 0),
                "contradictions": len(result["risk_analysis"].get("contradictions", [])),
                "hedging_pairs": len(result["risk_analysis"].get("hedging_pairs", [])),
            },
            "plan_summary": result["rebalance_plan"].get("summary", {}),
            "capital_flow": result["capital_flow"],
        })


if __name__ == "__main__":
    main()
