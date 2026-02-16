"""
Polymarket Portfolio Status & PnL Report

Fetches:
1. Proxy wallet USDC.e balance (on-chain via Polygon RPC)
2. Trade history from CLOB API to reconstruct positions
3. Current market prices from Gamma API (clob_token_ids lookup) and CLOB
4. Calculates unrealized PnL for each position
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


# ─── RPC Connection ────────────────────────────────────
def get_web3():
    """Try each RPC endpoint until one works."""
    for rpc in RPC_ENDPOINTS:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 10}))
            if w3.is_connected():
                print(f"  Connected to RPC: {rpc}")
                return w3
        except Exception as e:
            print(f"  RPC failed ({rpc}): {e}")
    raise RuntimeError("All Polygon RPC endpoints failed")


def get_usdc_balance(w3: Web3) -> float:
    """Get USDC.e balance of proxy wallet."""
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_E_ADDRESS),
        abi=ERC20_BALANCE_ABI,
    )
    raw = contract.functions.balanceOf(Web3.to_checksum_address(PROXY_WALLET)).call()
    return raw / (10 ** USDC_DECIMALS)


# ─── CLOB Client ───────────────────────────────────────
def get_clob_client():
    """Initialize py-clob-client with POLY_PROXY signature."""
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


# ─── Gamma API ─────────────────────────────────────────
_gamma_cache = {}  # token_id -> market_info


def gamma_lookup_by_token(token_id: str) -> dict:
    """Look up market by CLOB token ID (most reliable method)."""
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
            # Also cache for all tokens in this market
            for tid in market.get("clobTokenIds", []):
                if tid not in _gamma_cache:
                    _gamma_cache[tid] = market
            return market
    except Exception as e:
        print(f"    Gamma token lookup failed: {e}")
    return {}


def gamma_get_market_by_slug(slug: str) -> dict:
    """Get market via slug."""
    cache_key = f"slug:{slug}"
    if cache_key in _gamma_cache:
        return _gamma_cache[cache_key]
    try:
        resp = requests.get(
            f"{GAMMA_API_BASE}/markets",
            params={"slug": slug},
            timeout=15,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and len(data) > 0:
            _gamma_cache[cache_key] = data[0]
            return data[0]
    except Exception as e:
        print(f"    Gamma slug lookup failed for '{slug}': {e}")
    return {}


def parse_outcome_prices(market: dict) -> list:
    """Parse outcomePrices from Gamma market data."""
    prices = market.get("outcomePrices", "")
    if isinstance(prices, str):
        try:
            prices = json.loads(prices)
        except (json.JSONDecodeError, TypeError):
            prices = []
    return [float(p) for p in prices] if prices else []


def parse_outcomes(market: dict) -> list:
    """Parse outcome names."""
    outcomes = market.get("outcomes", "")
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except (json.JSONDecodeError, TypeError):
            outcomes = ["Yes", "No"]
    return outcomes


def format_end_date(end_date) -> str:
    """Format end date string."""
    if not end_date or end_date == "N/A":
        return "N/A"
    if isinstance(end_date, str) and len(end_date) > 10:
        try:
            dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return end_date[:10]
    return str(end_date)[:10]


# ─── Main ──────────────────────────────────────────────
def main():
    print("=" * 80)
    print("  POLYMARKET PORTFOLIO STATUS & PnL REPORT")
    print(f"  Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 80)
    print()

    # ── 1. On-chain USDC.e Balance ──
    print("[1] Proxy Wallet USDC.e Balance")
    print(f"  Wallet: {PROXY_WALLET}")
    try:
        w3 = get_web3()
        usdc_balance = get_usdc_balance(w3)
        print(f"  USDC.e Balance: ${usdc_balance:,.6f}")
    except Exception as e:
        usdc_balance = 0
        print(f"  Error reading balance: {e}")
    print()

    # ── 2. CLOB Client Init ──
    print("[2] Initializing CLOB Client...")
    if not PRIVATE_KEY:
        print("  ERROR: POLYMARKET_PRIVATE_KEY not set in .env")
        sys.exit(1)
    client = get_clob_client()
    print("  CLOB client ready (signature_type=POLY_PROXY)")
    print()

    # ── 3. Fetch Open Orders ──
    print("[3] Open Orders")
    try:
        open_orders = client.get_orders()
        if isinstance(open_orders, list) and open_orders:
            print(f"  Found {len(open_orders)} open orders:")
            for i, order in enumerate(open_orders):
                side = order.get("side", "?")
                price = order.get("price", "?")
                size = order.get("original_size", order.get("size", "?"))
                status = order.get("status", "?")
                print(f"    [{i+1}] {side} {size} @ ${price} | status={status}")
        else:
            print("  No open orders found.")
    except Exception as e:
        print(f"  Warning: get_orders failed: {e}")
    print()

    # ── 4. Reconstruct Positions from Trade History ──
    print("[4] Fetching Trade History...")
    try:
        trades = client.get_trades()
    except Exception as e:
        print(f"  ERROR: {e}")
        sys.exit(1)

    if not isinstance(trades, list) or not trades:
        print("  No trades found.")
        print()
        print("=" * 80)
        print(f"  Cash (USDC.e): ${usdc_balance:,.2f}")
        print(f"  No positions.")
        print("=" * 80)
        return

    print(f"  Found {len(trades)} trades. Reconstructing positions...")

    # Group trades by market (condition_id) and token
    market_positions = {}  # condition_id -> {tokens: {token_id -> data}}

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

    # Filter to markets with at least one non-zero position
    active_markets = {}
    closed_count = 0
    for cid, mdata in market_positions.items():
        has_active = False
        for tid, tdata in mdata["tokens"].items():
            if abs(tdata["net_size"]) > 0.01:
                has_active = True
                break
        if has_active:
            active_markets[cid] = mdata
        else:
            closed_count += 1

    print(f"  Active markets: {len(active_markets)} | Closed/settled: {closed_count}")
    print()

    # ── 5. Look up market details and get current prices ──
    print("[5] Position Details & PnL")
    print("-" * 80)

    total_invested = 0.0
    total_current_value = 0.0
    total_pnl = 0.0
    total_realized_pnl = 0.0
    pos_num = 0

    for condition_id, mdata in active_markets.items():
        # Look up market info using the first token ID (most reliable method)
        first_token = list(mdata["tokens"].keys())[0]
        market_info = gamma_lookup_by_token(first_token)
        time.sleep(0.3)  # rate limit

        question = market_info.get("question", f"Unknown Market ({condition_id[:30]}...)")
        slug = market_info.get("slug", "")
        end_date = market_info.get("endDate", market_info.get("endDateIso", "N/A"))
        end_date_str = format_end_date(end_date)
        active = market_info.get("active", True)
        closed = market_info.get("closed", False)
        gamma_outcome_prices = parse_outcome_prices(market_info)
        gamma_outcomes = parse_outcomes(market_info)
        clob_token_ids = market_info.get("clobTokenIds", [])

        # Process each token in this market that has an active position
        for token_id, tdata in mdata["tokens"].items():
            net_size = tdata["net_size"]
            if abs(net_size) < 0.01:
                continue  # skip closed sub-positions

            pos_num += 1
            outcome = tdata["outcome"]

            # Average entry price (for BUY positions)
            if tdata["total_buy_size"] > 0:
                avg_buy_price = tdata["total_buy_cost"] / tdata["total_buy_size"]
            else:
                avg_buy_price = 0

            # Determine position direction
            is_long = net_size > 0
            display_size = abs(net_size)

            if is_long:
                # Long position: cost basis = avg_buy * remaining
                invested = display_size * avg_buy_price
                # Realized PnL from partial sells
                if tdata["total_sell_size"] > 0:
                    avg_sell_price = tdata["total_sell_revenue"] / tdata["total_sell_size"]
                    realized = tdata["total_sell_size"] * (avg_sell_price - avg_buy_price)
                    total_realized_pnl += realized
            else:
                # Net short: shares sold without buying on this token.
                # In Polymarket this typically means the user minted a complete set
                # and sold one side. The revenue from selling = basis of the other side.
                # For display: show the sell revenue as "received"
                avg_sell_price = tdata["total_sell_revenue"] / tdata["total_sell_size"] if tdata["total_sell_size"] > 0 else 0
                invested = display_size * avg_sell_price  # what was received from selling
                # Note: short positions profit if the price drops to 0 (position resolves NO)
                # and lose if price goes to 1 (position resolves YES)

            # Get current price from CLOB
            current_price = 0.0
            try:
                resp = client.get_price(token_id, "BUY")
                if isinstance(resp, dict):
                    current_price = float(resp.get("price", 0))
                else:
                    current_price = float(resp)
            except Exception:
                # Fallback: use Gamma prices
                if gamma_outcome_prices and clob_token_ids:
                    if token_id in clob_token_ids:
                        idx = clob_token_ids.index(token_id)
                        if idx < len(gamma_outcome_prices):
                            current_price = gamma_outcome_prices[idx]
            time.sleep(0.15)

            # Calculate values
            if is_long:
                current_value = display_size * current_price
                unrealized_pnl = current_value - invested
            else:
                # Short: profit = sell_revenue - cost_to_buy_back
                cost_to_close = display_size * current_price
                unrealized_pnl = invested - cost_to_close  # sold high, buy low = profit
                current_value = invested - unrealized_pnl  # what it would cost to close

            pnl_pct = (unrealized_pnl / invested * 100) if invested > 0 else 0

            total_invested += invested
            total_current_value += current_value if is_long else invested  # for shorts, count received
            total_pnl += unrealized_pnl

            pnl_sign = "+" if unrealized_pnl >= 0 else ""

            # Market status indicator
            status_str = ""
            if closed:
                status_str = " [CLOSED/SETTLED]"
            elif not active:
                status_str = " [INACTIVE]"

            direction = "LONG" if is_long else "SHORT"

            print(f"  [{pos_num}] {question}{status_str}")
            print(f"      Slug: {slug or 'N/A'}")
            print(f"      Position: {direction} {outcome} | Size: {display_size:,.2f} contracts")
            print(f"      Avg Entry:      ${avg_buy_price:.4f}" if is_long else f"      Avg Sell Price: ${avg_sell_price:.4f}")
            print(f"      Current Price:  ${current_price:.4f}")
            print(f"      Cost Basis:     ${invested:,.2f}" if is_long else f"      Sell Revenue:   ${invested:,.2f}")
            print(f"      Current Value:  ${current_value:,.2f}" if is_long else f"      Close Cost:     ${cost_to_close:,.2f}")
            print(f"      Unrealized PnL: {pnl_sign}${unrealized_pnl:,.2f} ({pnl_sign}{pnl_pct:.1f}%)")
            print(f"      Settlement:     {end_date_str}")

            if gamma_outcome_prices and gamma_outcomes:
                price_strs = [
                    f"{gamma_outcomes[j]}={gamma_outcome_prices[j]:.3f}"
                    for j in range(min(len(gamma_outcomes), len(gamma_outcome_prices)))
                ]
                print(f"      Gamma Prices:   {' | '.join(price_strs)}")
            print()

    # ── 6. Summary ──
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
    pnl_sign = "+" if total_pnl >= 0 else ""
    real_sign = "+" if total_realized_pnl >= 0 else ""

    print("=" * 80)
    print("  PORTFOLIO SUMMARY")
    print(f"  Cash (USDC.e):       ${usdc_balance:,.2f}")
    print(f"  Positions Value:     ${total_current_value:,.2f}")
    print(f"  Total Cost Basis:    ${total_invested:,.2f}")
    print(f"  Unrealized PnL:      {pnl_sign}${total_pnl:,.2f} ({pnl_sign}{total_pnl_pct:.1f}%)")
    print(f"  Realized PnL (est):  {real_sign}${total_realized_pnl:,.2f}")
    print(f"  ─────────────────────────────────────")
    print(f"  Total Portfolio:     ${usdc_balance + total_current_value:,.2f}")
    print("=" * 80)


if __name__ == "__main__":
    main()
