#!/usr/bin/env python3
"""
Quick Polymarket Market Status Check (2026-02-16)

Checks:
1. "Canada wins gold in ice hockey" market status (Gamma API slug search)
2. "ETH above $2,000 on February 16" market status (Gamma API slug search)
3. USDC.e balance on Proxy Wallet (on-chain via Polygon RPC)
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
import requests
from web3 import Web3

# ─── Load environment ────────────────────────────────────
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

PROXY_WALLET = os.getenv("POLYMARKET_PROXY_WALLET", "")
USDC_E_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
USDC_DECIMALS = 6
GAMMA_API_BASE = "https://gamma-api.polymarket.com"

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


# ─── Gamma API helpers ────────────────────────────────────
def gamma_get_by_slug(slug: str) -> dict:
    """Get market via Gamma API ?slug= parameter (most reliable method)."""
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
            return data[0]
    except Exception as e:
        print(f"    [WARN] Gamma slug lookup failed for '{slug}': {e}")
    return {}


def gamma_search(query: str, limit: int = 5) -> list:
    """Search Gamma API with keyword query."""
    try:
        resp = requests.get(
            f"{GAMMA_API_BASE}/markets",
            params={"_q": query, "limit": limit},
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

    outcome_prices = parse_outcome_prices(market)
    outcomes = parse_outcomes(market)
    winner = None
    if outcome_prices:
        for i, p in enumerate(outcome_prices):
            if p >= 0.99:
                winner = outcomes[i] if i < len(outcomes) else f"Outcome {i}"
                break

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


def print_market_info(market: dict, label: str = ""):
    """Print formatted market details."""
    if not market:
        print(f"    No market data found.")
        return

    question = market.get("question", "Unknown")
    slug = market.get("slug", "N/A")
    end_date = market.get("endDate", market.get("endDateIso", "N/A"))
    prices = parse_outcome_prices(market)
    outcomes = parse_outcomes(market)
    status = get_settlement_status(market)
    description = market.get("description", "")

    # Days to expiry
    now_utc = datetime.now(timezone.utc)
    days_to_expiry = "?"
    if end_date and end_date != "N/A" and isinstance(end_date, str):
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            delta = (end_dt - now_utc).days
            if delta < 0:
                days_to_expiry = "EXPIRED"
            elif delta == 0:
                days_to_expiry = "TODAY"
            else:
                days_to_expiry = str(delta)
        except Exception:
            pass

    price_str = " | ".join(
        f"{outcomes[i]}={prices[i]:.4f}"
        for i in range(min(len(outcomes), len(prices)))
    ) if prices else "N/A"

    if label:
        print(f"    {label}")
    print(f"    Question:    {question}")
    print(f"    Slug:        {slug}")
    print(f"    Status:      {status}")
    print(f"    Prices:      {price_str}")
    print(f"    End Date:    {format_end_date(end_date)} ({days_to_expiry} days)")
    print(f"    Active:      {market.get('active', '?')}")
    print(f"    Closed:      {market.get('closed', '?')}")
    print(f"    Resolved:    {market.get('resolved', '?')}")
    if description:
        print(f"    Description: {description[:200]}")


# ─── RPC / On-chain ──────────────────────────────────────
def get_web3():
    for rpc in RPC_ENDPOINTS:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 10}))
            if w3.is_connected():
                print(f"    Connected to RPC: {rpc}")
                return w3
        except Exception as e:
            print(f"    RPC failed ({rpc}): {e}")
    raise RuntimeError("All Polygon RPC endpoints failed")


def get_usdc_balance(w3: Web3, wallet: str) -> float:
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_E_ADDRESS),
        abi=ERC20_BALANCE_ABI,
    )
    raw = contract.functions.balanceOf(Web3.to_checksum_address(wallet)).call()
    return raw / (10 ** USDC_DECIMALS)


# ─── Main ─────────────────────────────────────────────────
def main():
    now_utc = datetime.now(timezone.utc)
    print("=" * 80)
    print("  POLYMARKET QUICK MARKET STATUS CHECK")
    print(f"  Date: {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 80)
    print()

    # ── 1. Canada Hockey Gold Market ──
    print("[1] CANADA WINS GOLD IN ICE HOCKEY (Men's, 2026 Winter Olympics)")
    print("-" * 80)

    # Try several slug variants (verified via Gamma API events scan)
    canada_slugs = [
        "will-canada-win-the-mens-ice-hockey-gold-medal-at-the-2026-winter-olympics",
        "canada-wins-gold-in-ice-hockey-mens-at-the-2026-winter-olympics",
        "canada-wins-gold-in-mens-ice-hockey-at-the-2026-winter-olympics",
        "will-canada-win-gold-in-ice-hockey-at-the-2026-winter-olympics",
    ]

    canada_market = {}
    for slug in canada_slugs:
        canada_market = gamma_get_by_slug(slug)
        if canada_market:
            print(f"    Found via slug: {slug}")
            break
        time.sleep(0.3)

    # Fallback: keyword search
    if not canada_market:
        print("    Slug lookup failed, trying keyword search...")
        results = gamma_search("Canada hockey gold 2026 Winter Olympics")
        time.sleep(0.3)
        if results:
            # Find the most relevant match
            for r in results:
                q = r.get("question", "").lower()
                if "canada" in q and ("hockey" in q or "ice hockey" in q) and "gold" in q:
                    canada_market = r
                    print(f"    Found via search: {r.get('slug', '')}")
                    break

        if not canada_market and results:
            # Show top results for manual review
            print("    No exact match. Top search results:")
            for r in results[:3]:
                print(f"      - {r.get('question', '?')} [slug: {r.get('slug', '?')}]")
            # Use first result if somewhat relevant
            canada_market = results[0]

    print()
    print_market_info(canada_market)
    print()

    # ── 2. ETH above $2,000 on February 16 ──
    print("[2] ETH ABOVE $2,000 ON FEBRUARY 16")
    print("-" * 80)

    # Verified slug via direct Gamma API lookup
    eth_slugs = [
        "ethereum-above-2000-on-february-16",
        "will-the-price-of-ethereum-be-above-2000-on-february-16",
        "will-ethereum-be-above-2000-on-february-16",
        "eth-above-2000-on-february-16",
    ]

    eth_market = {}
    for slug in eth_slugs:
        eth_market = gamma_get_by_slug(slug)
        if eth_market:
            print(f"    Found via slug: {slug}")
            break
        time.sleep(0.3)

    # Fallback: keyword search
    if not eth_market:
        print("    Slug lookup failed, trying keyword search...")
        search_queries = [
            "ETH $2,000 February 16",
            "Ethereum 2000 February 16",
            "ETH above 2000",
            "Ethereum 2000 February",
        ]
        for query in search_queries:
            results = gamma_search(query)
            time.sleep(0.3)
            if results:
                for r in results:
                    q = r.get("question", "").lower()
                    if ("eth" in q or "ethereum" in q) and ("2,000" in q or "2000" in q):
                        eth_market = r
                        print(f"    Found via search '{query}': {r.get('slug', '')}")
                        break
            if eth_market:
                break

        if not eth_market and results:
            print("    No exact match. Top search results:")
            for r in results[:3]:
                print(f"      - {r.get('question', '?')} [slug: {r.get('slug', '?')}]")
            eth_market = results[0] if results else {}

    print()
    print_market_info(eth_market)
    print()

    # ── 3. USDC.e Balance on Proxy Wallet ──
    print("[3] PROXY WALLET USDC.e BALANCE")
    print("-" * 80)
    print(f"    Wallet: {PROXY_WALLET}")
    print(f"    Token:  USDC.e ({USDC_E_ADDRESS})")

    try:
        w3 = get_web3()
        balance = get_usdc_balance(w3, PROXY_WALLET)
        print(f"    Balance: ${balance:,.6f} USDC.e")
    except Exception as e:
        print(f"    ERROR: {e}")

    print()
    print("=" * 80)
    print("  CHECK COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
