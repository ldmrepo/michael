#!/usr/bin/env python3
"""
Polymarket Rebalancing Execution Pipeline

Takes a rebalancing session_id (from rebalance_engine.py) and executes
the approved actions: EXIT, REDUCE, ADD — in priority order.

Usage:
  python execute_rebalance_pm.py --session-id <id>            # Execute with confirmation
  python execute_rebalance_pm.py --session-id <id> --force    # Skip confirmation
  python execute_rebalance_pm.py --session-id <id> --action EXIT  # Only EXIT actions
  python execute_rebalance_pm.py --session-id <id> --dry-run  # Show plan only
  python execute_rebalance_pm.py --session-id <id> --json     # JSON output
  python execute_rebalance_pm.py --list-sessions              # Show recent sessions
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))

import db_utils
from config import DB_PATH, GAMMA_API_BASE, PROJECT_DATA_DIR
from output_format import error, report, success, table
from polymarket_client import create_client

# === Constants ===

ACTION_PRIORITY = {"EXIT": 1, "REDUCE": 2, "ADD": 3}
MAX_RETRIES = 3
ORDER_WAIT_SECONDS = 10
RATE_LIMIT_SLEEP = 1.0
PRICE_DRIFT_WARN_PCT = 5.0


# === Execution Log Schema ===

EXECUTION_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS pm_execution_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    market_id TEXT NOT NULL,
    action TEXT NOT NULL,
    planned_change_usd REAL,
    actual_change_usd REAL,
    order_id TEXT,
    fill_price REAL,
    fill_size REAL,
    slippage_pct REAL,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    created_at INTEGER DEFAULT (strftime('%s','now'))
);
CREATE INDEX IF NOT EXISTS idx_pm_execution_log_session
    ON pm_execution_log(session_id, created_at DESC);
"""


def ensure_execution_log_schema(conn):
    """Create pm_execution_log table if not exists"""
    conn.executescript(EXECUTION_LOG_SCHEMA)


# === Session Loading ===

def load_session(conn, session_id: str, action_filter: Optional[str] = None) -> List[Dict]:
    """
    Load non-executed rebalancing actions for a session.
    Sorted by priority: EXIT (1) first, then REDUCE (2), then ADD (3).
    HOLD actions are excluded since they require no execution.
    """
    rows = conn.execute(
        "SELECT * FROM pm_rebalances WHERE session_id = ? AND executed = 0 ORDER BY id ASC",
        (session_id,)
    ).fetchall()

    actions = [dict(r) for r in rows]

    # Filter out HOLD actions — nothing to execute
    actions = [a for a in actions if a["action"] != "HOLD"]

    # Apply optional action filter
    if action_filter:
        filter_upper = action_filter.upper()
        actions = [a for a in actions if a["action"] == filter_upper]

    # Sort by priority: EXIT first, then REDUCE, then ADD
    actions.sort(key=lambda a: ACTION_PRIORITY.get(a["action"], 99))

    return actions


def list_sessions(conn, limit: int = 10) -> List[Dict]:
    """List recent rebalancing sessions with summary info"""
    rows = conn.execute("""
        SELECT
            session_id,
            COUNT(*) as total_actions,
            SUM(CASE WHEN action = 'EXIT' THEN 1 ELSE 0 END) as exits,
            SUM(CASE WHEN action = 'REDUCE' THEN 1 ELSE 0 END) as reduces,
            SUM(CASE WHEN action = 'ADD' THEN 1 ELSE 0 END) as adds,
            SUM(CASE WHEN action = 'HOLD' THEN 1 ELSE 0 END) as holds,
            SUM(CASE WHEN executed = 1 THEN 1 ELSE 0 END) as executed_count,
            MIN(created_at) as created_at
        FROM pm_rebalances
        GROUP BY session_id
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,)).fetchall()

    sessions = []
    for r in rows:
        row_dict = dict(r)
        ts = row_dict.get("created_at", 0)
        row_dict["created_at_iso"] = (
            datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else ""
        )
        pending = row_dict["total_actions"] - row_dict["executed_count"] - row_dict["holds"]
        row_dict["pending_actions"] = max(pending, 0)
        sessions.append(row_dict)

    return sessions


# === Market Data Fetching ===

def fetch_market_info(client, market_id: str, slug: str = None) -> Optional[Dict]:
    """Fetch current market info from Gamma API.

    Args:
        slug: if provided, used for slug-based lookup (most reliable).
    """
    try:
        if slug:
            result = client._gamma_get("/markets", {"slug": slug})
        else:
            result = client._gamma_get("/markets", {"condition_id": market_id})
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

            return {
                "question": market.get("question", ""),
                "yes_price": yes_price,
                "no_price": no_price,
                "active": market.get("active", False),
                "closed": market.get("closed", False),
                "clob_token_ids": market.get("clobTokenIds", []),
                "end_date": market.get("endDate", ""),
                "volume": float(market.get("volume", 0) or 0),
                "liquidity": float(market.get("liquidity", 0) or 0),
            }
    except Exception as e:
        print(f"  [WARN] Failed to fetch market {market_id}: {e}", file=sys.stderr)
    return None


def get_position_for_market(conn, market_id: str, user_id: str = "default") -> Optional[Dict]:
    """Get the open position for a specific market"""
    row = conn.execute(
        "SELECT * FROM pm_positions WHERE market_id = ? AND user_id = ? AND status = 'open' "
        "ORDER BY opened_at DESC LIMIT 1",
        (market_id, user_id)
    ).fetchone()
    return dict(row) if row else None


# === Pre-flight Checks ===

def preflight_check(
    conn,
    client,
    actions: List[Dict],
    market_cache: Dict[str, Dict],
) -> Tuple[bool, List[str], Dict]:
    """
    Pre-flight validation before executing any trades.

    Returns: (ok, warnings, summary_dict)
    """
    warnings = []
    errors_found = []

    # Fetch market info for all actions (prefer slug-based lookup)
    market_ids = list(set(a["market_id"] for a in actions))
    for mid in market_ids:
        if mid not in market_cache:
            slug = None
            row = conn.execute("SELECT slug FROM pm_markets WHERE id = ?", (mid,)).fetchone()
            if row:
                slug = row["slug"]
            info = fetch_market_info(client, mid, slug=slug)
            if info:
                market_cache[mid] = info
            else:
                errors_found.append(f"Cannot fetch market data for {mid}")
            time.sleep(0.3)

    # Check each action
    total_add_cost = 0.0
    total_exit_proceeds = 0.0
    total_reduce_proceeds = 0.0

    for action in actions:
        mid = action["market_id"]
        mdata = market_cache.get(mid)

        if not mdata:
            errors_found.append(f"[{mid[:8]}] Market data unavailable")
            continue

        # Check market is still active
        if mdata.get("closed", False) or not mdata.get("active", True):
            if action["action"] == "EXIT":
                warnings.append(f"[{mid[:8]}] Market closed — EXIT may need manual settlement")
            else:
                errors_found.append(
                    f"[{mid[:8]}] Market is closed/inactive — cannot {action['action']}"
                )
                continue

        # Check clob_token_ids are available
        if not mdata.get("clob_token_ids"):
            errors_found.append(f"[{mid[:8]}] No CLOB token IDs — cannot trade")
            continue

        # Check position exists for EXIT/REDUCE
        if action["action"] in ("EXIT", "REDUCE"):
            pos = get_position_for_market(conn, mid)
            if not pos:
                errors_found.append(
                    f"[{mid[:8]}] No open position found — cannot {action['action']}"
                )
                continue

        # Price drift check
        pos = get_position_for_market(conn, mid)
        if pos and action.get("current_size"):
            side = pos["side"]
            current_price = mdata["yes_price"] if side == "YES" else mdata["no_price"]
            entry_price = pos["entry_price"]
            invested = entry_price * pos["size"]
            # Compare current invested value vs what rebalance engine saw
            rebalance_invested = action.get("current_size", 0) * entry_price
            if rebalance_invested > 0 and invested > 0:
                drift = abs(current_price - entry_price) / entry_price * 100
                if drift > PRICE_DRIFT_WARN_PCT:
                    warnings.append(
                        f"[{mid[:8]}] Price moved {drift:.1f}% since analysis "
                        f"(entry ${entry_price:.4f} -> now ${current_price:.4f})"
                    )

        # Tally costs
        suggested = action.get("suggested_change", 0)
        if action["action"] == "ADD" and suggested > 0:
            total_add_cost += suggested
        elif action["action"] == "EXIT":
            total_exit_proceeds += abs(suggested)
        elif action["action"] == "REDUCE":
            total_reduce_proceeds += abs(suggested)

    # Check USDC.e balance for ADD actions
    usdc_balance = 0.0
    if total_add_cost > 0:
        try:
            usdc_balance = client.get_balance_usdc()
        except Exception as e:
            warnings.append(f"Cannot fetch USDC.e balance: {e}")

        if usdc_balance < total_add_cost:
            # If we are also doing EXITs/REDUCEs, those proceeds can fund ADDs
            expected_after_exits = usdc_balance + total_exit_proceeds + total_reduce_proceeds
            if expected_after_exits < total_add_cost:
                errors_found.append(
                    f"Insufficient USDC.e: have ${usdc_balance:.2f}, "
                    f"need ${total_add_cost:.2f} for ADDs "
                    f"(even after ${total_exit_proceeds + total_reduce_proceeds:.2f} from exits/reduces)"
                )
            else:
                warnings.append(
                    f"USDC.e balance ${usdc_balance:.2f} < ADD cost ${total_add_cost:.2f}, "
                    f"but ${total_exit_proceeds + total_reduce_proceeds:.2f} expected from exits/reduces"
                )
    else:
        try:
            usdc_balance = client.get_balance_usdc()
        except Exception:
            pass

    summary = {
        "total_actions": len(actions),
        "exit_count": sum(1 for a in actions if a["action"] == "EXIT"),
        "reduce_count": sum(1 for a in actions if a["action"] == "REDUCE"),
        "add_count": sum(1 for a in actions if a["action"] == "ADD"),
        "total_exit_proceeds": round(total_exit_proceeds, 2),
        "total_reduce_proceeds": round(total_reduce_proceeds, 2),
        "total_add_cost": round(total_add_cost, 2),
        "net_change": round(-total_exit_proceeds - total_reduce_proceeds + total_add_cost, 2),
        "usdc_balance": round(usdc_balance, 2),
        "warnings": warnings,
        "errors": errors_found,
    }

    ok = len(errors_found) == 0
    return ok, warnings + errors_found, summary


# === Order Execution ===

def resolve_token_id(mdata: Dict, side: str) -> Optional[str]:
    """
    Resolve the CLOB token ID for a given side.
    YES token = clobTokenIds[0], NO token = clobTokenIds[1].
    """
    token_ids = mdata.get("clob_token_ids", [])
    if not token_ids:
        return None
    if side == "YES":
        return token_ids[0]
    elif side == "NO" and len(token_ids) > 1:
        return token_ids[1]
    return token_ids[0]


def execute_sell_order(
    client,
    token_id: str,
    size: float,
    max_retries: int = MAX_RETRIES,
) -> Dict:
    """
    Execute a sell order with retry logic.

    Strategy:
    1. Get order book, place limit sell at best_bid for immediate fill.
    2. If not filled in ORDER_WAIT_SECONDS, cancel and retry at best_bid - $0.01.
    3. Max MAX_RETRIES retries.
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            # Get current order book
            book_summary = client.get_order_book_summary(token_id)
            best_bid = book_summary["best_bid"]

            if best_bid <= 0:
                return {
                    "status": "failed",
                    "error": "No bids available in order book",
                    "attempts": attempt + 1,
                }

            # Adjust price down on retries
            price = round(best_bid - (attempt * 0.01), 2)
            price = max(price, 0.01)

            print(
                f"    Attempt {attempt + 1}/{max_retries}: SELL {size:.1f} @ ${price:.2f} "
                f"(best_bid=${best_bid:.2f})",
                file=sys.stderr,
            )

            # Place limit sell order
            result = client.create_limit_order(
                token_id=token_id,
                side="SELL",
                price=price,
                size=size,
            )

            order_id = result.get("orderID") or result.get("order_id") or result.get("id", "")
            status = (result.get("status") or result.get("orderStatus") or "").upper()

            # If matched immediately
            if status in ("MATCHED", "FILLED"):
                return {
                    "status": "filled",
                    "order_id": order_id,
                    "fill_price": price,
                    "fill_size": size,
                    "attempts": attempt + 1,
                    "raw_response": result,
                }

            # Wait for fill
            if order_id:
                time.sleep(ORDER_WAIT_SECONDS)

                # Check if filled — try to cancel; if cancel fails, it was already filled
                try:
                    cancelled = client.cancel_order(order_id)
                    if not cancelled:
                        # Cancel failed — order was likely filled
                        return {
                            "status": "filled",
                            "order_id": order_id,
                            "fill_price": price,
                            "fill_size": size,
                            "attempts": attempt + 1,
                            "raw_response": result,
                        }
                    # Successfully cancelled — order was not filled, retry
                    print(
                        f"    Order {order_id[:12]}.. not filled, cancelled. Retrying...",
                        file=sys.stderr,
                    )
                except Exception:
                    # If cancel throws, assume the order was filled
                    return {
                        "status": "filled",
                        "order_id": order_id,
                        "fill_price": price,
                        "fill_size": size,
                        "attempts": attempt + 1,
                        "raw_response": result,
                    }
            else:
                # No order_id means immediate response — check status
                if status == "LIVE":
                    # Order placed but not filled immediately, wait and check
                    time.sleep(ORDER_WAIT_SECONDS)
                else:
                    return {
                        "status": "filled" if status in ("MATCHED", "FILLED") else "unknown",
                        "order_id": order_id,
                        "fill_price": price,
                        "fill_size": size,
                        "attempts": attempt + 1,
                        "raw_response": result,
                    }

            time.sleep(RATE_LIMIT_SLEEP)

        except Exception as e:
            last_error = str(e)
            print(f"    Attempt {attempt + 1} failed: {e}", file=sys.stderr)
            time.sleep(RATE_LIMIT_SLEEP * 2)

    return {
        "status": "failed",
        "error": last_error or "Max retries exceeded",
        "attempts": max_retries,
    }


def execute_buy_order(
    client,
    token_id: str,
    size: float,
    max_retries: int = MAX_RETRIES,
) -> Dict:
    """
    Execute a buy order with retry logic.

    Strategy:
    1. Get order book, place limit buy at best_ask for immediate fill.
    2. If not filled in ORDER_WAIT_SECONDS, cancel and retry at best_ask + $0.01.
    3. Max MAX_RETRIES retries.
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            # Get current order book
            book_summary = client.get_order_book_summary(token_id)
            best_ask = book_summary["best_ask"]

            if best_ask <= 0 or best_ask >= 1:
                return {
                    "status": "failed",
                    "error": f"Invalid ask price: ${best_ask}",
                    "attempts": attempt + 1,
                }

            # Adjust price up on retries
            price = round(best_ask + (attempt * 0.01), 2)
            price = min(price, 0.99)

            print(
                f"    Attempt {attempt + 1}/{max_retries}: BUY {size:.1f} @ ${price:.2f} "
                f"(best_ask=${best_ask:.2f})",
                file=sys.stderr,
            )

            # Place limit buy order
            result = client.create_limit_order(
                token_id=token_id,
                side="BUY",
                price=price,
                size=size,
            )

            order_id = result.get("orderID") or result.get("order_id") or result.get("id", "")
            status = (result.get("status") or result.get("orderStatus") or "").upper()

            # If matched immediately
            if status in ("MATCHED", "FILLED"):
                return {
                    "status": "filled",
                    "order_id": order_id,
                    "fill_price": price,
                    "fill_size": size,
                    "attempts": attempt + 1,
                    "raw_response": result,
                }

            # Wait for fill
            if order_id:
                time.sleep(ORDER_WAIT_SECONDS)

                try:
                    cancelled = client.cancel_order(order_id)
                    if not cancelled:
                        return {
                            "status": "filled",
                            "order_id": order_id,
                            "fill_price": price,
                            "fill_size": size,
                            "attempts": attempt + 1,
                            "raw_response": result,
                        }
                    print(
                        f"    Order {order_id[:12]}.. not filled, cancelled. Retrying...",
                        file=sys.stderr,
                    )
                except Exception:
                    return {
                        "status": "filled",
                        "order_id": order_id,
                        "fill_price": price,
                        "fill_size": size,
                        "attempts": attempt + 1,
                        "raw_response": result,
                    }
            else:
                if status == "LIVE":
                    time.sleep(ORDER_WAIT_SECONDS)
                else:
                    return {
                        "status": "filled" if status in ("MATCHED", "FILLED") else "unknown",
                        "order_id": order_id,
                        "fill_price": price,
                        "fill_size": size,
                        "attempts": attempt + 1,
                        "raw_response": result,
                    }

            time.sleep(RATE_LIMIT_SLEEP)

        except Exception as e:
            last_error = str(e)
            print(f"    Attempt {attempt + 1} failed: {e}", file=sys.stderr)
            time.sleep(RATE_LIMIT_SLEEP * 2)

    return {
        "status": "failed",
        "error": last_error or "Max retries exceeded",
        "attempts": max_retries,
    }


def execute_action(
    conn,
    client,
    action: Dict,
    market_cache: Dict[str, Dict],
    session_id: str,
    dry_run: bool = False,
) -> Dict:
    """
    Execute a single rebalancing action.

    For EXIT: sell entire position at market.
    For REDUCE: sell partial position to reach target.
    For ADD: buy additional contracts.
    """
    mid = action["market_id"]
    action_type = action["action"]
    suggested_change = action.get("suggested_change", 0)
    mdata = market_cache.get(mid)

    if not mdata:
        return _log_execution(
            conn, session_id, mid, action_type, suggested_change,
            status="failed", error_message="Market data unavailable",
        )

    # Get position info
    pos = get_position_for_market(conn, mid)
    side = pos["side"] if pos else "YES"
    token_id = resolve_token_id(mdata, side)

    if not token_id:
        return _log_execution(
            conn, session_id, mid, action_type, suggested_change,
            status="failed", error_message="Cannot resolve CLOB token ID",
        )

    # Get current price for calculations
    current_price = mdata["yes_price"] if side == "YES" else mdata["no_price"]

    if action_type == "EXIT":
        if not pos:
            return _log_execution(
                conn, session_id, mid, action_type, suggested_change,
                status="failed", error_message="No open position to EXIT",
            )

        sell_size = pos["size"]
        planned_usd = -(current_price * sell_size)

        if dry_run:
            return _log_execution(
                conn, session_id, mid, action_type, planned_usd,
                status="dry_run",
                fill_price=current_price,
                fill_size=sell_size,
            )

        print(f"  EXIT: Selling {sell_size:.1f} {side} contracts of {mid[:20]}...", file=sys.stderr)
        result = execute_sell_order(client, token_id, sell_size)

        if result["status"] in ("filled", "unknown"):
            fill_price = result.get("fill_price", current_price)
            fill_size = result.get("fill_size", sell_size)
            actual_usd = -(fill_price * fill_size)
            slippage = _calc_slippage(current_price, fill_price, "SELL")

            # Close position in DB
            db_utils.close_position(conn, pos["id"], fill_price)

            # Record trade
            db_utils.record_trade(
                conn, mid, side="SELL",
                price=fill_price, size=fill_size,
                order_type="limit", order_id=result.get("order_id", ""),
            )

            # Mark rebalance as executed
            _mark_executed(conn, action["id"])

            return _log_execution(
                conn, session_id, mid, action_type, planned_usd,
                actual_change_usd=actual_usd,
                order_id=result.get("order_id", ""),
                fill_price=fill_price,
                fill_size=fill_size,
                slippage_pct=slippage,
                status="filled",
            )
        else:
            return _log_execution(
                conn, session_id, mid, action_type, planned_usd,
                status="failed",
                error_message=result.get("error", "Sell order failed"),
            )

    elif action_type == "REDUCE":
        if not pos:
            return _log_execution(
                conn, session_id, mid, action_type, suggested_change,
                status="failed", error_message="No open position to REDUCE",
            )

        # Calculate shares to sell: suggested_change is negative $ amount
        reduce_usd = abs(suggested_change)
        sell_size = reduce_usd / current_price if current_price > 0 else 0
        sell_size = min(sell_size, pos["size"])  # Cannot sell more than we hold
        sell_size = round(sell_size, 1)

        if sell_size < 1:
            return _log_execution(
                conn, session_id, mid, action_type, suggested_change,
                status="skipped",
                error_message=f"Sell size too small ({sell_size:.1f} contracts)",
            )

        planned_usd = -(current_price * sell_size)

        if dry_run:
            return _log_execution(
                conn, session_id, mid, action_type, planned_usd,
                status="dry_run",
                fill_price=current_price,
                fill_size=sell_size,
            )

        print(
            f"  REDUCE: Selling {sell_size:.1f}/{pos['size']:.1f} {side} contracts of {mid[:20]}...",
            file=sys.stderr,
        )
        result = execute_sell_order(client, token_id, sell_size)

        if result["status"] in ("filled", "unknown"):
            fill_price = result.get("fill_price", current_price)
            fill_size = result.get("fill_size", sell_size)
            actual_usd = -(fill_price * fill_size)
            slippage = _calc_slippage(current_price, fill_price, "SELL")

            # Update position: reduce size (create a new partial close record)
            remaining_size = pos["size"] - fill_size
            if remaining_size <= 0.5:
                # Close fully if nearly empty
                db_utils.close_position(conn, pos["id"], fill_price)
            else:
                # Reduce position size manually
                conn.execute(
                    "UPDATE pm_positions SET size = ?, current_price = ? WHERE id = ?",
                    (round(remaining_size, 1), fill_price, pos["id"]),
                )
                conn.commit()

            db_utils.record_trade(
                conn, mid, side="SELL",
                price=fill_price, size=fill_size,
                order_type="limit", order_id=result.get("order_id", ""),
            )

            _mark_executed(conn, action["id"])

            return _log_execution(
                conn, session_id, mid, action_type, planned_usd,
                actual_change_usd=actual_usd,
                order_id=result.get("order_id", ""),
                fill_price=fill_price,
                fill_size=fill_size,
                slippage_pct=slippage,
                status="filled",
            )
        else:
            return _log_execution(
                conn, session_id, mid, action_type, planned_usd,
                status="failed",
                error_message=result.get("error", "Sell order failed"),
            )

    elif action_type == "ADD":
        # Calculate shares to buy: suggested_change is positive $ amount
        add_usd = abs(suggested_change)
        buy_size = add_usd / current_price if current_price > 0 else 0
        buy_size = round(buy_size, 1)

        if buy_size < 1:
            return _log_execution(
                conn, session_id, mid, action_type, suggested_change,
                status="skipped",
                error_message=f"Buy size too small ({buy_size:.1f} contracts)",
            )

        planned_usd = current_price * buy_size

        if dry_run:
            return _log_execution(
                conn, session_id, mid, action_type, planned_usd,
                status="dry_run",
                fill_price=current_price,
                fill_size=buy_size,
            )

        print(
            f"  ADD: Buying {buy_size:.1f} {side} contracts of {mid[:20]}...",
            file=sys.stderr,
        )
        result = execute_buy_order(client, token_id, buy_size)

        if result["status"] in ("filled", "unknown"):
            fill_price = result.get("fill_price", current_price)
            fill_size = result.get("fill_size", buy_size)
            actual_usd = fill_price * fill_size
            slippage = _calc_slippage(current_price, fill_price, "BUY")

            # Update or create position
            db_utils.upsert_position(
                conn, mid,
                side=side,
                size=fill_size,
                entry_price=fill_price,
                current_price=fill_price,
            )

            db_utils.record_trade(
                conn, mid, side="BUY",
                price=fill_price, size=fill_size,
                order_type="limit", order_id=result.get("order_id", ""),
            )

            _mark_executed(conn, action["id"])

            return _log_execution(
                conn, session_id, mid, action_type, planned_usd,
                actual_change_usd=actual_usd,
                order_id=result.get("order_id", ""),
                fill_price=fill_price,
                fill_size=fill_size,
                slippage_pct=slippage,
                status="filled",
            )
        else:
            return _log_execution(
                conn, session_id, mid, action_type, planned_usd,
                status="failed",
                error_message=result.get("error", "Buy order failed"),
            )

    else:
        return _log_execution(
            conn, session_id, mid, action_type, suggested_change,
            status="skipped",
            error_message=f"Unknown action type: {action_type}",
        )


def _calc_slippage(expected_price: float, actual_price: float, trade_side: str) -> float:
    """Calculate slippage percentage. Positive = worse than expected."""
    if expected_price <= 0:
        return 0.0
    if trade_side == "SELL":
        # Selling: slippage is how much lower we sold vs expected
        return round((expected_price - actual_price) / expected_price * 100, 4)
    else:
        # Buying: slippage is how much higher we paid vs expected
        return round((actual_price - expected_price) / expected_price * 100, 4)


def _mark_executed(conn, rebalance_id: int):
    """Mark a rebalance action as executed"""
    now = int(time.time())
    conn.execute(
        "UPDATE pm_rebalances SET executed = 1, executed_at = ? WHERE id = ?",
        (now, rebalance_id),
    )
    conn.commit()


def _log_execution(
    conn,
    session_id: str,
    market_id: str,
    action: str,
    planned_change_usd: float,
    actual_change_usd: Optional[float] = None,
    order_id: str = "",
    fill_price: Optional[float] = None,
    fill_size: Optional[float] = None,
    slippage_pct: Optional[float] = None,
    status: str = "pending",
    error_message: str = "",
) -> Dict:
    """Record execution result in pm_execution_log and return summary dict"""
    conn.execute("""
        INSERT INTO pm_execution_log
            (session_id, market_id, action, planned_change_usd, actual_change_usd,
             order_id, fill_price, fill_size, slippage_pct, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id, market_id, action,
        round(planned_change_usd, 2) if planned_change_usd else None,
        round(actual_change_usd, 2) if actual_change_usd is not None else None,
        order_id or None,
        round(fill_price, 4) if fill_price is not None else None,
        round(fill_size, 1) if fill_size is not None else None,
        round(slippage_pct, 4) if slippage_pct is not None else None,
        status,
        error_message or None,
    ))
    conn.commit()

    return {
        "market_id": market_id,
        "action": action,
        "planned_change_usd": round(planned_change_usd, 2) if planned_change_usd else 0,
        "actual_change_usd": round(actual_change_usd, 2) if actual_change_usd is not None else None,
        "order_id": order_id,
        "fill_price": fill_price,
        "fill_size": fill_size,
        "slippage_pct": slippage_pct,
        "status": status,
        "error_message": error_message,
    }


# === Execution Report ===

def execution_report(
    session_id: str,
    results: List[Dict],
    preflight_summary: Dict,
    market_cache: Dict[str, Dict],
    conn,
) -> Tuple[str, Dict]:
    """Generate execution report as text and data dict"""

    filled = [r for r in results if r["status"] == "filled"]
    failed = [r for r in results if r["status"] == "failed"]
    skipped = [r for r in results if r["status"] == "skipped"]
    dry_runs = [r for r in results if r["status"] == "dry_run"]

    total_planned = sum(abs(r.get("planned_change_usd", 0)) for r in results)
    total_actual = sum(abs(r.get("actual_change_usd", 0)) for r in filled if r.get("actual_change_usd") is not None)
    total_slippage_cost = 0.0
    for r in filled:
        if r.get("slippage_pct") and r.get("actual_change_usd"):
            total_slippage_cost += abs(r["actual_change_usd"]) * abs(r["slippage_pct"]) / 100

    # Fetch updated USDC balance
    final_balance = preflight_summary.get("usdc_balance", 0)
    try:
        client = create_client()
        final_balance = client.get_balance_usdc()
    except Exception:
        pass

    # Get updated portfolio
    positions = db_utils.get_positions(conn, "default", "open")
    total_invested = sum(p["entry_price"] * p["size"] for p in positions)

    lines = []
    lines.append(f"\n{'='*70}")
    lines.append(f"  REBALANCING EXECUTION REPORT")
    lines.append(f"  Session: {session_id}  |  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    lines.append(f"{'='*70}")

    # Execution summary
    is_dry = len(dry_runs) > 0 and len(filled) == 0
    mode_label = "DRY RUN" if is_dry else "LIVE"
    lines.append(f"\n  MODE: {mode_label}")
    lines.append(f"  {'─'*50}")
    lines.append(f"  Total Actions:   {len(results)}")
    lines.append(f"  Filled:          {len(filled)}")
    lines.append(f"  Failed:          {len(failed)}")
    lines.append(f"  Skipped:         {len(skipped)}")
    if dry_runs:
        lines.append(f"  Dry Run:         {len(dry_runs)}")

    # Fills detail
    if filled or dry_runs:
        detail_set = filled if filled else dry_runs
        label = "EXECUTED TRADES" if filled else "DRY RUN PREVIEW"
        lines.append(f"\n  {label}:")
        lines.append(f"  {'─'*50}")

        for r in detail_set:
            mid = r["market_id"]
            mdata = market_cache.get(mid, {})
            question = mdata.get("question", mid)[:55]
            action_str = r["action"]
            price_str = f"${r['fill_price']:.4f}" if r.get("fill_price") else "N/A"
            size_str = f"{r['fill_size']:.1f}" if r.get("fill_size") else "N/A"
            usd_str = f"${abs(r.get('actual_change_usd', 0) or r.get('planned_change_usd', 0)):,.2f}"
            slip_str = f"{r.get('slippage_pct', 0):.2f}%" if r.get("slippage_pct") is not None else "N/A"

            lines.append(f"\n  [{action_str}] {question}")
            lines.append(f"    Price: {price_str}  |  Size: {size_str}  |  USD: {usd_str}  |  Slippage: {slip_str}")
            if r.get("order_id"):
                lines.append(f"    Order ID: {r['order_id'][:40]}")

    # Failed trades
    if failed:
        lines.append(f"\n  FAILED TRADES:")
        lines.append(f"  {'─'*50}")
        for r in failed:
            mid = r["market_id"]
            mdata = market_cache.get(mid, {})
            question = mdata.get("question", mid)[:55]
            lines.append(f"  [{r['action']}] {question}")
            lines.append(f"    Error: {r.get('error_message', 'Unknown')}")

    # Skipped trades
    if skipped:
        lines.append(f"\n  SKIPPED:")
        lines.append(f"  {'─'*50}")
        for r in skipped:
            mid = r["market_id"]
            mdata = market_cache.get(mid, {})
            question = mdata.get("question", mid)[:55]
            lines.append(f"  [{r['action']}] {question}: {r.get('error_message', '')}")

    # Slippage summary
    if filled:
        lines.append(f"\n  SLIPPAGE SUMMARY:")
        lines.append(f"  {'─'*50}")
        lines.append(f"  Total Planned Volume: ${total_planned:>10,.2f}")
        lines.append(f"  Total Actual Volume:  ${total_actual:>10,.2f}")
        lines.append(f"  Est. Slippage Cost:   ${total_slippage_cost:>10,.2f}")
        avg_slippage = (
            sum(r.get("slippage_pct", 0) for r in filled if r.get("slippage_pct") is not None)
            / len(filled) if filled else 0
        )
        lines.append(f"  Avg Slippage:         {avg_slippage:>10.2f}%")

    # Updated portfolio state
    lines.append(f"\n  UPDATED PORTFOLIO STATE:")
    lines.append(f"  {'─'*50}")
    lines.append(f"  Open Positions:     {len(positions)}")
    lines.append(f"  Total Invested:     ${total_invested:>10,.2f}")
    lines.append(f"  USDC.e Balance:     ${final_balance:>10,.2f}")
    lines.append(f"  Total Portfolio:    ${total_invested + final_balance:>10,.2f}")

    lines.append(f"\n{'='*70}\n")

    data = {
        "session_id": session_id,
        "mode": mode_label.lower().replace(" ", "_"),
        "total_actions": len(results),
        "filled": len(filled),
        "failed": len(failed),
        "skipped": len(skipped),
        "dry_run": len(dry_runs),
        "total_planned_volume": round(total_planned, 2),
        "total_actual_volume": round(total_actual, 2),
        "slippage_cost": round(total_slippage_cost, 2),
        "final_usdc_balance": round(final_balance, 2),
        "final_invested": round(total_invested, 2),
        "final_portfolio": round(total_invested + final_balance, 2),
        "results": results,
    }

    return "\n".join(lines), data


# === CLI ===

def main():
    parser = argparse.ArgumentParser(description="Execute PM Rebalancing Actions")
    parser.add_argument("--session-id", type=str, help="Rebalancing session ID to execute")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--action", type=str, help="Only execute specific action type (EXIT, REDUCE, ADD)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without executing")
    parser.add_argument("--json", action="store_true", help="JSON output format")
    parser.add_argument("--list-sessions", action="store_true", help="List recent rebalancing sessions")
    parser.add_argument("--user-id", default="default", help="User ID (default: default)")

    args = parser.parse_args()

    try:
        conn = db_utils.get_connection()
        ensure_execution_log_schema(conn)

        # Also ensure rebalance schema exists
        from rebalance_engine import ensure_rebalance_schema
        ensure_rebalance_schema(conn)

    except Exception as e:
        error(f"Database connection failed: {e}", code="DB_ERROR")
        return

    # --- List sessions mode ---
    if args.list_sessions:
        sessions = list_sessions(conn)
        conn.close()

        if not sessions:
            if args.json:
                success(data=[], message="No rebalancing sessions found")
            else:
                error("No rebalancing sessions found", code="NO_SESSIONS")
            return

        if args.json:
            success(data=sessions, message=f"Found {len(sessions)} sessions")
        else:
            headers = ["Session ID", "Created", "Total", "EXIT", "REDUCE", "ADD", "HOLD", "Executed", "Pending"]
            rows = []
            for s in sessions:
                rows.append([
                    s["session_id"],
                    s["created_at_iso"][:19],
                    s["total_actions"],
                    s["exits"],
                    s["reduces"],
                    s["adds"],
                    s["holds"],
                    s["executed_count"],
                    s["pending_actions"],
                ])
            report_text = table(headers, rows, title="Recent Rebalancing Sessions")
            report(report_text, data=sessions)
        return

    # --- Execute session mode ---
    if not args.session_id:
        error("--session-id is required (use --list-sessions to find one)", code="MISSING_SESSION")
        conn.close()
        return

    session_id = args.session_id

    # 1. Load session actions
    actions = load_session(conn, session_id, action_filter=args.action)
    if not actions:
        conn.close()
        error(
            f"No pending actions found for session '{session_id}'"
            + (f" with filter '{args.action}'" if args.action else ""),
            code="NO_ACTIONS",
        )
        return

    print(
        f"\n  Loaded {len(actions)} pending action(s) for session {session_id}",
        file=sys.stderr,
    )

    # 2. Create trading client
    try:
        client = create_client()
        if not client.has_trading:
            error("Trading credentials not configured (POLYMARKET_PRIVATE_KEY required)", code="NO_CREDS")
            conn.close()
            return
    except Exception as e:
        error(f"Failed to create trading client: {e}", code="CLIENT_ERROR")
        conn.close()
        return

    # 3. Pre-flight checks
    market_cache: Dict[str, Dict] = {}
    print("  Running pre-flight checks...", file=sys.stderr)
    ok, messages, preflight_summary = preflight_check(conn, client, actions, market_cache)

    # Print warnings/errors
    for msg in messages:
        prefix = "  [WARN]" if "WARN" not in msg else "  "
        print(f"{prefix} {msg}", file=sys.stderr)

    if not ok:
        conn.close()
        if args.json:
            error(
                f"Pre-flight check failed with {len(preflight_summary['errors'])} error(s)",
                code="PREFLIGHT_FAILED",
                data=preflight_summary,
            )
        else:
            error(
                f"Pre-flight check failed:\n" + "\n".join(f"  - {e}" for e in preflight_summary["errors"]),
                code="PREFLIGHT_FAILED",
            )
        return

    # 4. Show summary and confirm
    print(f"\n  Pre-flight OK:", file=sys.stderr)
    print(f"    EXITs:  {preflight_summary['exit_count']}  (proceeds ~${preflight_summary['total_exit_proceeds']:.2f})", file=sys.stderr)
    print(f"    REDUCEs: {preflight_summary['reduce_count']}  (proceeds ~${preflight_summary['total_reduce_proceeds']:.2f})", file=sys.stderr)
    print(f"    ADDs:   {preflight_summary['add_count']}  (cost ~${preflight_summary['total_add_cost']:.2f})", file=sys.stderr)
    print(f"    USDC.e: ${preflight_summary['usdc_balance']:.2f}", file=sys.stderr)

    if args.dry_run:
        print(f"\n  DRY RUN MODE — no real orders will be placed.", file=sys.stderr)

    if not args.force and not args.dry_run:
        try:
            answer = input(f"\n  Proceed with execution? [y/N]: ").strip().lower()
            if answer not in ("y", "yes"):
                conn.close()
                print("  Execution cancelled by user.", file=sys.stderr)
                if args.json:
                    success(data={"cancelled": True}, message="Execution cancelled by user")
                else:
                    report("Execution cancelled by user.")
                return
        except (EOFError, KeyboardInterrupt):
            conn.close()
            print("\n  Execution cancelled.", file=sys.stderr)
            if args.json:
                success(data={"cancelled": True}, message="Execution cancelled")
            else:
                report("Execution cancelled.")
            return

    # 5. Execute actions in order
    results = []
    for i, action in enumerate(actions, 1):
        mdata = market_cache.get(action["market_id"], {})
        question = mdata.get("question", action["market_id"])[:50]
        print(
            f"\n  [{i}/{len(actions)}] {action['action']} — {question}...",
            file=sys.stderr,
        )

        result = execute_action(
            conn, client, action, market_cache,
            session_id=session_id,
            dry_run=args.dry_run,
        )
        results.append(result)

        status_icon = {
            "filled": "OK",
            "failed": "FAIL",
            "skipped": "SKIP",
            "dry_run": "DRY",
        }.get(result["status"], "??")
        print(f"    -> [{status_icon}] {result.get('error_message') or 'Done'}", file=sys.stderr)

        # Rate limit between orders
        if i < len(actions) and not args.dry_run:
            time.sleep(RATE_LIMIT_SLEEP)

    # 6. Generate execution report
    report_text, report_data = execution_report(
        session_id, results, preflight_summary, market_cache, conn,
    )

    conn.close()

    if args.json:
        success(data=report_data, message="Rebalancing execution complete")
    else:
        report(report_text, data={
            "session_id": session_id,
            "filled": report_data["filled"],
            "failed": report_data["failed"],
            "skipped": report_data["skipped"],
        })


if __name__ == "__main__":
    main()
