#!/usr/bin/env python3
"""
Polymarket Portfolio Full Status Check (2026-02-16)

Checks ALL positions for proxy wallet (from POLYMARKET_PROXY_WALLET env var):
- Reconstructs positions from CLOB trade history
- Looks up each market via Gamma API (clob_token_ids method)
- Specifically checks Canada Hockey + ETH $2K settlement status
- Shows current value, P&L, and settlement status for each position

Uses environment variables from .env
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
import requests
from web3 import Web3

# ─── Load environment ───────────────────────────────────
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY", "")
PROXY_WALLET = os.getenv("POLYMARKET_PROXY_WALLET", "")
API_KEY = os.getenv("POLYMARKET_API_KEY", "")
API_SECRET = os.getenv("POLYMARKET_API_SECRET", "")
PASSPHRASE = os.getenv("POLYMARKET_PASSPHRASE", "")

USDC_E_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
USDC_DECIMALS = 6
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"

RPC_ENDPOINTS = [
    "https://polygon-rpc.com",
    "https://1rpc.io/matic",
    "https://polygon-bor-rpc.publicnode.com",
]

ERC20_BALANCE_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    }
]


# ─── Utility: RPC Connection ────────────────────────────
def get_web3():
    for rpc in RPC_ENDPOINTS:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 10}))
            if w3.is_connected():
                return w3
        except Exception:
            pass
    raise RuntimeError("All Polygon RPC endpoints failed")


def get_usdc_balance(w3: Web3) -> float:
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_E_ADDRESS),
        abi=ERC20_BALANCE_ABI,
    )
    raw = contract.functions.balanceOf(Web3.to_checksum_address(PROXY_WALLET)).call()
    return raw / (10 ** USDC_DECIMALS)


# ─── CLOB Client ─────────────────────────────────────────
def get_clob_client():
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import ApiCreds

    creds = ApiCreds(
        api_key=API_KEY,
        api_secret=API_SECRET,
        api_passphrase=PASSPHRASE,
    )
    return ClobClient(
        CLOB_API_BASE,
        key=PRIVATE_KEY,
        chain_id=137,
        creds=creds,
        signature_type=1,  # POLY_PROXY
        funder=PROXY_WALLET,
    )


# ─── Gamma API ────────────────────────────────────────────
_gamma_cache = {}


def gamma_lookup_by_token(token_id: str) -> dict:
    """Look up market by CLOB token ID (reliable method)."""
    if token_id in _gamma_cache:
        return _gamma_cache[token_id]
    try:
        resp = requests.get(
            f"{GAMMA_API_BASE}/markets",
            params={"clob_token_ids": token_id},
            timeout=15,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and len(data) > 0:
            market = data[0]
            _gamma_cache[token_id] = market
            for tid in market.get("clobTokenIds", []):
                _gamma_cache[tid] = market
            return market
    except Exception as e:
        print(f"    [WARN] Gamma token lookup failed for {token_id[:20]}...: {e}")
    return {}


def gamma_search(query: str) -> list:
    """Search Gamma API for markets matching a query."""
    try:
        resp = requests.get(
            f"{GAMMA_API_BASE}/markets",
            params={"_q": query, "limit": 5},
            timeout=15,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"    [WARN] Gamma search failed for '{query}': {e}")
    return []


def parse_outcome_prices(market: dict) -> list:
    prices = market.get("outcomePrices", "")
    if isinstance(prices, str):
        try:
            prices = json.loads(prices)
        except (json.JSONDecodeError, TypeError):
            prices = []
    return [float(p) for p in prices] if prices else []


def parse_outcomes(market: dict) -> list:
    outcomes = market.get("outcomes", "")
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except (json.JSONDecodeError, TypeError):
            outcomes = ["Yes", "No"]
    return outcomes


def format_end_date(end_date) -> str:
    if not end_date or end_date == "N/A":
        return "N/A"
    if isinstance(end_date, str) and len(end_date) > 10:
        try:
            dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            return end_date[:10]
    return str(end_date)[:10]


def get_settlement_status(market: dict) -> str:
    """Determine detailed settlement status."""
    active = market.get("active", True)
    closed = market.get("closed", False)
    resolved = market.get("resolved", False)
    accepting_orders = market.get("acceptingOrders", True)

    # Check winning outcome
    outcome_prices = parse_outcome_prices(market)
    outcomes = parse_outcomes(market)
    winner = None
    if outcome_prices:
        for i, p in enumerate(outcome_prices):
            if p >= 0.99:
                winner = outcomes[i] if i < len(outcomes) else f"Outcome {i}"
                break
            elif p <= 0.01:
                pass  # loser

    if resolved and closed:
        if winner:
            return f"SETTLED -> Winner: {winner}"
        return "SETTLED (resolved & closed)"
    elif closed and not active:
        if winner:
            return f"CLOSED -> Winner: {winner}"
        return "CLOSED (awaiting resolution)"
    elif not active:
        return "INACTIVE"
    elif not accepting_orders:
        return "TRADING HALTED (pending settlement)"
    else:
        return "ACTIVE (trading)"


# ─── Main ─────────────────────────────────────────────────
def main():
    now_utc = datetime.now(timezone.utc)

    print("=" * 85)
    print("  POLYMARKET PORTFOLIO — FULL STATUS CHECK")
    print(f"  Date: {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')} (Today is Feb 16, 2026)")
    print(f"  Proxy Wallet: {PROXY_WALLET}")
    print("=" * 85)
    print()

    # ── 1. On-chain USDC.e Balance ──
    print("[1] WALLET BALANCE")
    try:
        w3 = get_web3()
        usdc_balance = get_usdc_balance(w3)
        print(f"    USDC.e (on-chain): ${usdc_balance:,.6f}")
    except Exception as e:
        usdc_balance = 0
        print(f"    Error reading on-chain balance: {e}")

    # CLOB balance
    try:
        client = get_clob_client()
        from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
        bal_resp = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
        if isinstance(bal_resp, dict):
            clob_balance = int(bal_resp.get("balance", 0)) / 1e6
        else:
            clob_balance = 0
        print(f"    USDC.e (CLOB):     ${clob_balance:,.6f}")
    except Exception as e:
        clob_balance = 0
        print(f"    CLOB balance error: {e}")
        client = get_clob_client()
    print()

    # ── 2. Fetch all trades ──
    print("[2] FETCHING TRADE HISTORY...")
    try:
        trades = client.get_trades()
    except Exception as e:
        print(f"    ERROR fetching trades: {e}")
        sys.exit(1)

    if not isinstance(trades, list) or not trades:
        print("    No trades found.")
        print(f"\n    Total Cash: ${usdc_balance + clob_balance:,.2f}")
        return

    print(f"    Found {len(trades)} trades total.")
    print()

    # ── 3. Reconstruct positions from trades ──
    print("[3] RECONSTRUCTING POSITIONS FROM TRADES...")
    market_positions = {}

    for t in trades:
        if t.get("status") not in ("MATCHED", "CONFIRMED"):
            continue

        condition_id = t.get("market", "")
        asset_id = t.get("asset_id", "")
        side = t.get("side", "")
        size = float(t.get("size", 0))
        price = float(t.get("price", 0))
        outcome = t.get("outcome", "")

        if condition_id not in market_positions:
            market_positions[condition_id] = {"tokens": {}}

        if asset_id not in market_positions[condition_id]["tokens"]:
            market_positions[condition_id]["tokens"][asset_id] = {
                "token_id": asset_id,
                "outcome": outcome,
                "net_size": 0,
                "total_buy_cost": 0,
                "total_buy_size": 0,
                "total_sell_revenue": 0,
                "total_sell_size": 0,
            }

        tok = market_positions[condition_id]["tokens"][asset_id]
        if side == "BUY":
            tok["net_size"] += size
            tok["total_buy_cost"] += size * price
            tok["total_buy_size"] += size
        elif side == "SELL":
            tok["net_size"] -= size
            tok["total_sell_revenue"] += size * price
            tok["total_sell_size"] += size

    # Separate active vs closed
    active_markets = {}
    closed_markets = {}
    for cid, mdata in market_positions.items():
        has_active = any(abs(td["net_size"]) > 0.01 for td in mdata["tokens"].values())
        if has_active:
            active_markets[cid] = mdata
        else:
            closed_markets[cid] = mdata

    print(f"    Active positions: {len(active_markets)} markets")
    print(f"    Closed/settled:   {len(closed_markets)} markets")
    print()

    # ── 4. SPECIFIC CHECKS: Canada Hockey & ETH $2K ──
    print("[4] SPECIFIC MARKET CHECKS")
    print("-" * 85)

    # Search for Canada Hockey
    print("  >> Searching: Canada Hockey (Winter Olympics)")
    canada_results = gamma_search("Canada hockey gold 2026 Winter Olympics")
    time.sleep(0.3)
    if canada_results:
        for m in canada_results[:3]:
            q = m.get("question", "")
            slug = m.get("slug", "")
            closed = m.get("closed", False)
            active = m.get("active", True)
            resolved = m.get("resolved", False)
            prices = parse_outcome_prices(m)
            outcomes = parse_outcomes(m)
            status = get_settlement_status(m)
            end_date = format_end_date(m.get("endDate", ""))

            price_str = " | ".join(
                f"{outcomes[i]}={prices[i]:.3f}"
                for i in range(min(len(outcomes), len(prices)))
            ) if prices else "N/A"

            print(f"     Market: {q}")
            print(f"     Slug: {slug}")
            print(f"     Status: {status}")
            print(f"     Prices: {price_str}")
            print(f"     End Date: {end_date}")
            print()
    else:
        print("     No results found for Canada Hockey\n")

    # Search for ETH $2K
    print("  >> Searching: ETH $2,000 / ETH $2K")
    eth_results = gamma_search("ETH $2,000 February")
    time.sleep(0.3)
    if not eth_results:
        eth_results = gamma_search("Ethereum 2000")
        time.sleep(0.3)
    if eth_results:
        for m in eth_results[:3]:
            q = m.get("question", "")
            slug = m.get("slug", "")
            closed = m.get("closed", False)
            active = m.get("active", True)
            prices = parse_outcome_prices(m)
            outcomes = parse_outcomes(m)
            status = get_settlement_status(m)
            end_date = format_end_date(m.get("endDate", ""))

            price_str = " | ".join(
                f"{outcomes[i]}={prices[i]:.3f}"
                for i in range(min(len(outcomes), len(prices)))
            ) if prices else "N/A"

            if "2,000" in q or "2000" in q or "2k" in q.lower() or "2K" in q:
                print(f"     Market: {q}")
                print(f"     Slug: {slug}")
                print(f"     Status: {status}")
                print(f"     Prices: {price_str}")
                print(f"     End Date: {end_date}")
                print()

    # Also search ETH $2,800 (known position)
    print("  >> Searching: ETH $2,800 (known position)")
    eth2800_results = gamma_search("ETH $2,800")
    time.sleep(0.3)
    if eth2800_results:
        for m in eth2800_results[:2]:
            q = m.get("question", "")
            slug = m.get("slug", "")
            status = get_settlement_status(m)
            prices = parse_outcome_prices(m)
            outcomes = parse_outcomes(m)
            end_date = format_end_date(m.get("endDate", ""))

            price_str = " | ".join(
                f"{outcomes[i]}={prices[i]:.3f}"
                for i in range(min(len(outcomes), len(prices)))
            ) if prices else "N/A"

            if "2,800" in q or "2800" in q:
                print(f"     Market: {q}")
                print(f"     Slug: {slug}")
                print(f"     Status: {status}")
                print(f"     Prices: {price_str}")
                print(f"     End Date: {end_date}")
                print()

    print("-" * 85)
    print()

    # ── 5. ALL ACTIVE POSITIONS ──
    print("[5] ALL ACTIVE POSITIONS — DETAILED")
    print("=" * 85)

    total_invested = 0.0
    total_current_value = 0.0
    total_unrealized_pnl = 0.0
    pos_num = 0
    position_rows = []  # For summary table

    for condition_id, mdata in active_markets.items():
        first_token = list(mdata["tokens"].keys())[0]
        market_info = gamma_lookup_by_token(first_token)
        time.sleep(0.3)

        question = market_info.get("question", f"Unknown ({condition_id[:40]}...)")
        slug = market_info.get("slug", "")
        end_date = market_info.get("endDate", market_info.get("endDateIso", "N/A"))
        end_date_str = format_end_date(end_date)
        gamma_outcome_prices = parse_outcome_prices(market_info)
        gamma_outcomes = parse_outcomes(market_info)
        clob_token_ids = market_info.get("clobTokenIds", [])
        status_str = get_settlement_status(market_info)

        # Days to expiry
        days_to_expiry = "?"
        if end_date and end_date != "N/A" and isinstance(end_date, str):
            try:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                delta = (end_dt - now_utc).days
                days_to_expiry = str(max(delta, 0))
                if delta <= 0:
                    days_to_expiry = "TODAY" if delta == 0 else "EXPIRED"
            except Exception:
                pass

        for token_id, tdata in mdata["tokens"].items():
            net_size = tdata["net_size"]
            if abs(net_size) < 0.01:
                continue

            pos_num += 1
            outcome = tdata["outcome"]
            is_long = net_size > 0
            display_size = abs(net_size)

            if tdata["total_buy_size"] > 0:
                avg_buy_price = tdata["total_buy_cost"] / tdata["total_buy_size"]
            else:
                avg_buy_price = 0

            if is_long:
                invested = display_size * avg_buy_price
            else:
                avg_sell_price = tdata["total_sell_revenue"] / tdata["total_sell_size"] if tdata["total_sell_size"] > 0 else 0
                invested = display_size * avg_sell_price

            # Get current price
            current_price = 0.0
            try:
                resp = client.get_price(token_id, "BUY")
                if isinstance(resp, dict):
                    current_price = float(resp.get("price", 0))
                else:
                    current_price = float(resp)
            except Exception:
                if gamma_outcome_prices and clob_token_ids:
                    if token_id in clob_token_ids:
                        idx = clob_token_ids.index(token_id)
                        if idx < len(gamma_outcome_prices):
                            current_price = gamma_outcome_prices[idx]
            time.sleep(0.15)

            # Calculate P&L
            if is_long:
                current_value = display_size * current_price
                unrealized_pnl = current_value - invested
            else:
                cost_to_close = display_size * current_price
                unrealized_pnl = invested - cost_to_close
                current_value = cost_to_close

            pnl_pct = (unrealized_pnl / invested * 100) if invested > 0 else 0
            max_profit = display_size * (1.0 - avg_buy_price) if is_long else display_size * avg_sell_price if not is_long else 0
            max_roi = ((1.0 - avg_buy_price) / avg_buy_price * 100) if is_long and avg_buy_price > 0 else 0

            total_invested += invested
            total_current_value += current_value
            total_unrealized_pnl += unrealized_pnl

            direction = "LONG" if is_long else "SHORT"
            pnl_sign = "+" if unrealized_pnl >= 0 else ""

            # Check if this is a "special interest" market
            special = ""
            q_lower = question.lower()
            if "canada" in q_lower and "hockey" in q_lower:
                special = " *** CANADA HOCKEY ***"
            elif "eth" in q_lower and ("2,000" in question or "2000" in question or "2k" in q_lower):
                special = " *** ETH $2K ***"
            elif "eth" in q_lower and ("2,800" in question or "2800" in question):
                special = " *** ETH $2,800 ***"

            print(f"  [{pos_num}] {question}{special}")
            print(f"      Status:         {status_str}")
            print(f"      Slug:           {slug or 'N/A'}")
            print(f"      Position:       {direction} {outcome} | {display_size:,.1f} contracts")
            if is_long:
                print(f"      Avg Entry:      ${avg_buy_price:.4f}")
            else:
                print(f"      Avg Sell Price: ${avg_sell_price:.4f}")
            print(f"      Current Price:  ${current_price:.4f}")
            print(f"      Cost Basis:     ${invested:,.2f}")
            print(f"      Current Value:  ${current_value:,.2f}")
            print(f"      Unrealized PnL: {pnl_sign}${unrealized_pnl:,.2f} ({pnl_sign}{pnl_pct:.1f}%)")
            if is_long:
                print(f"      Max Profit:     ${max_profit:,.2f} (if wins, ROI: {max_roi:.1f}%)")
            print(f"      Settlement:     {end_date_str} ({days_to_expiry} days)")

            if gamma_outcome_prices and gamma_outcomes:
                price_strs = [
                    f"{gamma_outcomes[j]}={gamma_outcome_prices[j]:.3f}"
                    for j in range(min(len(gamma_outcomes), len(gamma_outcome_prices)))
                ]
                print(f"      Gamma Prices:   {' | '.join(price_strs)}")
            print()

            position_rows.append({
                "num": pos_num,
                "question": question[:55],
                "direction": direction,
                "outcome": outcome,
                "size": display_size,
                "entry": avg_buy_price if is_long else (avg_sell_price if not is_long else 0),
                "current": current_price,
                "invested": invested,
                "value": current_value,
                "pnl": unrealized_pnl,
                "pnl_pct": pnl_pct,
                "days": days_to_expiry,
                "status": status_str,
                "special": special,
            })

    # ── 6. Closed/Settled Positions Summary ──
    print()
    print("[6] CLOSED / SETTLED POSITIONS")
    print("-" * 85)

    total_realized = 0.0
    for condition_id, mdata in closed_markets.items():
        first_token = list(mdata["tokens"].keys())[0]
        market_info = gamma_lookup_by_token(first_token)
        time.sleep(0.3)

        question = market_info.get("question", f"Unknown ({condition_id[:40]}...)")
        status_str = get_settlement_status(market_info)

        for token_id, tdata in mdata["tokens"].items():
            if tdata["total_buy_size"] > 0 and tdata["total_sell_size"] > 0:
                avg_buy = tdata["total_buy_cost"] / tdata["total_buy_size"]
                avg_sell = tdata["total_sell_revenue"] / tdata["total_sell_size"]
                realized = tdata["total_sell_revenue"] - tdata["total_buy_cost"]
                total_realized += realized
                sign = "+" if realized >= 0 else ""
                print(f"  {question[:60]}")
                print(f"    {tdata['outcome']} | Bought {tdata['total_buy_size']:.0f}@${avg_buy:.4f} | Sold {tdata['total_sell_size']:.0f}@${avg_sell:.4f} | P&L: {sign}${realized:,.2f}")
                print(f"    Status: {status_str}")
                print()
            elif tdata["total_buy_size"] > 0:
                # Bought but not sold — may have been settled/redeemed
                avg_buy = tdata["total_buy_cost"] / tdata["total_buy_size"]
                cost = tdata["total_buy_cost"]

                # Check if market resolved in our favor
                gamma_prices = parse_outcome_prices(market_info)
                clob_ids = market_info.get("clobTokenIds", [])
                if gamma_prices and token_id in clob_ids:
                    idx = clob_ids.index(token_id)
                    if idx < len(gamma_prices) and gamma_prices[idx] >= 0.99:
                        # Won! Value = size * 1.0
                        won_value = tdata["total_buy_size"] * 1.0
                        realized = won_value - cost
                        total_realized += realized
                        sign = "+" if realized >= 0 else ""
                        print(f"  {question[:60]}")
                        print(f"    {tdata['outcome']} | Bought {tdata['total_buy_size']:.0f}@${avg_buy:.4f} | SETTLED WIN | P&L: {sign}${realized:,.2f}")
                        print(f"    Status: {status_str}")
                        print()
                    elif idx < len(gamma_prices) and gamma_prices[idx] <= 0.01:
                        realized = -cost
                        total_realized += realized
                        print(f"  {question[:60]}")
                        print(f"    {tdata['outcome']} | Bought {tdata['total_buy_size']:.0f}@${avg_buy:.4f} | SETTLED LOSS | P&L: -${cost:,.2f}")
                        print(f"    Status: {status_str}")
                        print()
                    else:
                        print(f"  {question[:60]}")
                        print(f"    {tdata['outcome']} | Bought {tdata['total_buy_size']:.0f}@${avg_buy:.4f} | Net size=0 (sold/redeemed)")
                        print(f"    Status: {status_str}")
                        print()
                else:
                    print(f"  {question[:60]}")
                    print(f"    {tdata['outcome']} | Bought {tdata['total_buy_size']:.0f}@${avg_buy:.4f} | Net size=0")
                    print(f"    Status: {status_str}")
                    print()

    if not closed_markets:
        print("  (No closed positions found)")
    print()

    # ── 7. Summary Table ──
    print("=" * 85)
    print("  PORTFOLIO SUMMARY TABLE")
    print("=" * 85)
    print(f"  {'#':>2} {'Dir':<5} {'Side':<4} {'Size':>6} {'Entry':>7} {'Now':>7} {'Invested':>9} {'Value':>9} {'P&L':>9} {'P&L%':>7} {'Days':>6} {'Status':<15}")
    print("  " + "-" * 83)

    for r in sorted(position_rows, key=lambda x: x["invested"], reverse=True):
        pnl_sign = "+" if r["pnl"] >= 0 else ""
        print(f"  {r['num']:>2} {r['direction']:<5} {r['outcome']:<4} {r['size']:>6.0f} ${r['entry']:.4f} ${r['current']:.4f} ${r['invested']:>8,.2f} ${r['value']:>8,.2f} {pnl_sign}${r['pnl']:>7,.2f} {r['pnl_pct']:>+6.1f}% {str(r['days']):>6} {r['status'][:15]}")
        q = r["question"][:60] + r.get("special", "")
        print(f"     {q}")

    print("  " + "-" * 83)
    total_pnl_pct = (total_unrealized_pnl / total_invested * 100) if total_invested > 0 else 0
    pnl_sign = "+" if total_unrealized_pnl >= 0 else ""
    real_sign = "+" if total_realized >= 0 else ""

    print(f"\n  TOTALS:")
    print(f"  {'─' * 50}")
    print(f"  Cash (USDC.e on-chain):  ${usdc_balance:>10,.2f}")
    print(f"  Cash (CLOB balance):     ${clob_balance:>10,.2f}")
    print(f"  Positions Cost Basis:    ${total_invested:>10,.2f}")
    print(f"  Positions Current Value: ${total_current_value:>10,.2f}")
    print(f"  Unrealized P&L:          {pnl_sign}${total_unrealized_pnl:>9,.2f} ({pnl_sign}{total_pnl_pct:.1f}%)")
    print(f"  Realized P&L (est):      {real_sign}${total_realized:>9,.2f}")
    print(f"  {'─' * 50}")
    total_portfolio = usdc_balance + clob_balance + total_current_value
    print(f"  TOTAL PORTFOLIO VALUE:   ${total_portfolio:>10,.2f}")
    print("=" * 85)


if __name__ == "__main__":
    main()
