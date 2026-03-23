"""
Redeem resolved Polymarket CTF positions for USDC.e

Usage:
  python3 scripts/redeem_pm_positions.py --check     # Check redeemable positions
  python3 scripts/redeem_pm_positions.py --execute    # Execute redemptions
"""

import sys
import os
import json
import time
import argparse
from pathlib import Path

# Add skill scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / ".claude/skills/prediction-market/scripts"))

from config import (
    POLYMARKET_PRIVATE_KEY, POLYMARKET_PROXY_WALLET,
    POLYGON_RPC_URL, POLYGON_RPC_FALLBACKS,
    CONDITIONAL_TOKENS_ADDRESS, NEG_RISK_ADAPTER_ADDRESS,
    CTF_EXCHANGE_ADDRESS, NEG_RISK_CTF_EXCHANGE_ADDRESS,
    PROXY_FACTORY_ADDRESS, PROXY_FACTORY_ABI,
    USDC_E_ADDRESS, ERC20_ABI,
    GAMMA_API_BASE,
)

from web3 import Web3
from eth_account import Account
import requests


# ============================================================
# CTF Contract ABIs (minimal for redeem operations)
# ============================================================

CONDITIONAL_TOKENS_ABI = [
    # redeemPositions(collateralToken, parentCollectionId, conditionId, indexSets)
    {
        "inputs": [
            {"name": "collateralToken", "type": "address"},
            {"name": "parentCollectionId", "type": "bytes32"},
            {"name": "conditionId", "type": "bytes32"},
            {"name": "indexSets", "type": "uint256[]"}
        ],
        "name": "redeemPositions",
        "outputs": [],
        "type": "function"
    },
    # payoutNumerators(conditionId, index) -> uint256
    {
        "inputs": [
            {"name": "conditionId", "type": "bytes32"},
            {"name": "index", "type": "uint256"}
        ],
        "name": "payoutNumerators",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    # payoutDenominator(conditionId) -> uint256
    {
        "inputs": [{"name": "conditionId", "type": "bytes32"}],
        "name": "payoutDenominator",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    # balanceOf(owner, tokenId) -> uint256
    {
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "id", "type": "uint256"}
        ],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
]

NEG_RISK_ADAPTER_ABI = [
    # redeemPositions(conditionId, indexSets, amount)
    {
        "inputs": [
            {"name": "conditionId", "type": "bytes32"},
            {"name": "indexSets", "type": "uint256[]"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "redeemPositions",
        "outputs": [],
        "type": "function"
    },
]


def get_web3():
    """Get Web3 instance with fallback RPCs"""
    for rpc in [POLYGON_RPC_URL] + POLYGON_RPC_FALLBACKS:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 10}))
            if w3.is_connected():
                print(f"  Connected to: {rpc}")
                return w3
        except Exception:
            continue
    raise Exception("All RPC endpoints failed")


def get_market_by_slug(slug):
    """Fetch market data from Gamma API by slug"""
    url = f"{GAMMA_API_BASE}/markets?slug={slug}"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    markets = r.json()
    if markets:
        return markets[0]
    return None


def check_condition_resolved(w3, condition_id_hex):
    """Check if a condition has been resolved on CTF contract"""
    ctf = w3.eth.contract(
        address=Web3.to_checksum_address(CONDITIONAL_TOKENS_ADDRESS),
        abi=CONDITIONAL_TOKENS_ABI
    )

    condition_id = bytes.fromhex(condition_id_hex.replace("0x", ""))

    # Check payoutDenominator - if > 0, condition is resolved
    try:
        denominator = ctf.functions.payoutDenominator(condition_id).call()
        if denominator > 0:
            # Get payout numerators for each outcome
            numerators = []
            for i in range(10):  # Max 10 outcomes
                try:
                    num = ctf.functions.payoutNumerators(condition_id, i).call()
                    numerators.append(num)
                except Exception:
                    break
            return True, denominator, numerators
        return False, 0, []
    except Exception as e:
        print(f"  Error checking condition: {e}")
        return False, 0, []


def check_token_balance(w3, token_id, owner):
    """Check ERC1155 balance for a conditional token"""
    ctf = w3.eth.contract(
        address=Web3.to_checksum_address(CONDITIONAL_TOKENS_ADDRESS),
        abi=CONDITIONAL_TOKENS_ABI
    )

    try:
        balance = ctf.functions.balanceOf(
            Web3.to_checksum_address(owner),
            int(token_id)
        ).call()
        return balance
    except Exception as e:
        print(f"  Error checking token balance: {e}")
        return 0


def build_redeem_tx(w3, condition_id_hex, index_sets, is_neg_risk=False):
    """Build redeem transaction data for CTF or NegRisk"""
    condition_id = bytes.fromhex(condition_id_hex.replace("0x", ""))

    if is_neg_risk:
        adapter = w3.eth.contract(
            address=Web3.to_checksum_address(NEG_RISK_ADAPTER_ADDRESS),
            abi=NEG_RISK_ADAPTER_ABI
        )
        # NegRisk uses different redeem signature
        # For now, use CTF directly as it's more universal
        pass

    # Standard CTF redeemPositions
    ctf = w3.eth.contract(
        address=Web3.to_checksum_address(CONDITIONAL_TOKENS_ADDRESS),
        abi=CONDITIONAL_TOKENS_ABI
    )

    parent_collection_id = b'\x00' * 32  # bytes32(0) for top-level

    data = ctf.functions.redeemPositions(
        Web3.to_checksum_address(USDC_E_ADDRESS),
        parent_collection_id,
        condition_id,
        index_sets
    ).build_transaction({
        "from": Web3.to_checksum_address(POLYMARKET_PROXY_WALLET),
        "gas": 0,
        "gasPrice": 0,
    })["data"]

    return CONDITIONAL_TOKENS_ADDRESS, data


def execute_via_proxy(w3, account, calls):
    """Execute calls through Proxy Factory"""
    factory = w3.eth.contract(
        address=Web3.to_checksum_address(PROXY_FACTORY_ADDRESS),
        abi=PROXY_FACTORY_ABI
    )

    # Build proxy call tuples: (typeCode=1, to, value=0, data)
    proxy_calls = [(1, Web3.to_checksum_address(to), 0, bytes.fromhex(data.replace("0x", ""))) for to, data in calls]

    # Get gas price with EIP-1559 style (base × 3 for safety)
    base_fee = w3.eth.get_block("latest")["baseFeePerGas"]
    max_priority = w3.to_wei(30, "gwei")
    max_fee = base_fee * 3 + max_priority

    nonce = w3.eth.get_transaction_count(account.address)

    tx = factory.functions.proxy(proxy_calls).build_transaction({
        "from": account.address,
        "nonce": nonce,
        "gas": 500000,
        "maxFeePerGas": max_fee,
        "maxPriorityFeePerGas": max_priority,
        "chainId": 137,
    })

    # Estimate gas
    try:
        estimated = w3.eth.estimate_gas(tx)
        tx["gas"] = int(estimated * 1.3)
        print(f"  Gas estimate: {estimated} (using {tx['gas']})")
    except Exception as e:
        print(f"  Gas estimation failed: {e}")
        print(f"  Using default 500,000")

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"  TX sent: {tx_hash.hex()}")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    print(f"  Status: {'SUCCESS' if receipt.status == 1 else 'FAILED'}")
    print(f"  Gas used: {receipt.gasUsed}")

    return receipt


def main():
    parser = argparse.ArgumentParser(description="Redeem resolved Polymarket positions")
    parser.add_argument("--check", action="store_true", help="Check redeemable positions")
    parser.add_argument("--execute", action="store_true", help="Execute redemptions")
    args = parser.parse_args()

    if not args.check and not args.execute:
        args.check = True  # Default to check mode

    print("=" * 70)
    print("  POLYMARKET CTF POSITION REDEMPTION")
    print("=" * 70)

    if not POLYMARKET_PRIVATE_KEY:
        print("ERROR: POLYMARKET_PRIVATE_KEY not set")
        sys.exit(1)

    account = Account.from_key(POLYMARKET_PRIVATE_KEY)
    proxy_wallet = POLYMARKET_PROXY_WALLET or "unknown"
    print(f"  EOA: {account.address}")
    print(f"  Proxy: {proxy_wallet}")

    # Connect to Polygon
    w3 = get_web3()

    # Known resolved/expired markets to check
    markets_to_check = [
        {
            "name": "Canada vs Switzerland Hockey",
            "slug": "mwoh-can-swi-2026-02-13",
            "position": "LONG Canada",
            "contracts": 44,
            "cost": 39.60,
        },
        {
            "name": "US strikes Iran by Feb 20",
            "slug": "us-strikes-iran-by-february-20-2026-151-468-624-297-614-778-872-127-349-448-499-337-826-553",
            "position": "LONG No",
            "contracts": 52,
            "cost": 49.13,
        },
    ]

    redeemable = []

    for mkt in markets_to_check:
        print(f"\n--- {mkt['name']} ---")
        print(f"  Position: {mkt['position']} × {mkt['contracts']}")

        # Get market data from Gamma
        gamma_data = get_market_by_slug(mkt["slug"])
        if not gamma_data:
            print(f"  WARNING: Market not found on Gamma API")
            continue

        condition_id = gamma_data.get("conditionId", "")
        question = gamma_data.get("question", "")
        resolved = gamma_data.get("resolved", False)
        closed = gamma_data.get("closed", False)
        active = gamma_data.get("active", True)
        outcome_prices = gamma_data.get("outcomePrices", "")

        print(f"  Question: {question}")
        print(f"  Condition ID: {condition_id[:20]}...")
        print(f"  Gamma resolved: {resolved}")
        print(f"  Gamma closed: {closed}")
        print(f"  Gamma active: {active}")
        print(f"  Outcome prices: {outcome_prices}")

        # Check on-chain resolution
        if condition_id:
            is_resolved, denom, numerators = check_condition_resolved(w3, condition_id)
            print(f"  On-chain resolved: {is_resolved}")
            if is_resolved:
                print(f"  Payout denominator: {denom}")
                print(f"  Payout numerators: {numerators}")

        # Check token balances
        tokens = gamma_data.get("tokens", [])
        if tokens:
            for tok in tokens:
                token_id = tok.get("token_id", "")
                outcome = tok.get("outcome", "")
                if token_id:
                    balance = check_token_balance(w3, token_id, proxy_wallet)
                    balance_human = balance / 1e6 if balance > 0 else 0
                    print(f"  Token [{outcome}] balance: {balance} ({balance_human:.2f} USDC.e)")

                    if balance > 0 and is_resolved:
                        redeemable.append({
                            "name": mkt["name"],
                            "condition_id": condition_id,
                            "token_id": token_id,
                            "outcome": outcome,
                            "balance": balance,
                            "balance_human": balance_human,
                            "denom": denom,
                            "numerators": numerators,
                            "is_neg_risk": gamma_data.get("neg_risk", "false") == "true",
                        })
        else:
            # Gamma tokens array might be empty — try conditionId-based token lookup
            print(f"  Gamma tokens array empty — checking CLOB for token IDs...")
            # For neg_risk markets, tokens are wrapped differently
            neg_risk = gamma_data.get("neg_risk", "false")
            print(f"  Neg risk: {neg_risk}")

        time.sleep(0.3)

    # Also check USDC.e balance
    usdc_e = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_E_ADDRESS),
        abi=ERC20_ABI
    )
    proxy_balance = usdc_e.functions.balanceOf(Web3.to_checksum_address(proxy_wallet)).call()
    print(f"\n  Proxy USDC.e balance: ${proxy_balance / 1e6:.2f}")

    eoa_balance = usdc_e.functions.balanceOf(account.address).call()
    print(f"  EOA USDC.e balance: ${eoa_balance / 1e6:.2f}")

    eoa_pol = w3.eth.get_balance(account.address)
    print(f"  EOA POL balance: {w3.from_wei(eoa_pol, 'ether'):.4f} POL")

    print(f"\n{'=' * 70}")
    print(f"  REDEEMABLE POSITIONS: {len(redeemable)}")
    print(f"{'=' * 70}")

    total_redeemable = 0
    for r in redeemable:
        payout_per_token = r["numerators"][0] / r["denom"] if r["denom"] > 0 and len(r["numerators"]) > 0 else 0
        expected_usdc = r["balance_human"] * payout_per_token if payout_per_token > 0 else r["balance_human"]
        total_redeemable += expected_usdc
        print(f"  {r['name']} [{r['outcome']}]:")
        print(f"    Balance: {r['balance_human']:.2f} tokens")
        print(f"    Expected payout: ~${expected_usdc:.2f} USDC.e")

    if total_redeemable > 0:
        print(f"\n  TOTAL REDEEMABLE: ~${total_redeemable:.2f} USDC.e")

    if args.execute and redeemable:
        print(f"\n{'=' * 70}")
        print(f"  EXECUTING REDEMPTIONS...")
        print(f"{'=' * 70}")

        calls = []
        for r in redeemable:
            # Build redeem call
            # indexSets: [1] for outcome 0, [2] for outcome 1, [1,2] for both
            # We redeem all outcomes that have balance
            to_addr, data = build_redeem_tx(w3, r["condition_id"], [1, 2], r["is_neg_risk"])
            calls.append((to_addr, data))

        if calls:
            print(f"  Executing {len(calls)} redeem calls via proxy...")
            receipt = execute_via_proxy(w3, account, calls)

            if receipt.status == 1:
                # Check new balance
                new_balance = usdc_e.functions.balanceOf(Web3.to_checksum_address(proxy_wallet)).call()
                print(f"\n  NEW Proxy USDC.e balance: ${new_balance / 1e6:.2f}")
                print(f"  Redeemed: ~${(new_balance - proxy_balance) / 1e6:.2f}")
                print(f"\n  SUCCESS!")
            else:
                print(f"\n  FAILED — check TX on polygonscan")
    elif args.execute:
        print("\n  Nothing to redeem.")
    else:
        if redeemable:
            print(f"\n  Run with --execute to redeem these positions")


if __name__ == "__main__":
    main()
