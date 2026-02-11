#!/usr/bin/env python3
"""
Polygon Wallet Utilities for Polymarket

On-chain operations for managing USDC deposits/withdrawals:
  balance          Check USDC and POL balances for EOA
  transfer-usdc    Transfer USDC from EOA to another address
  --to-proxy       Transfer all USDC from EOA to Proxy Wallet
  --dry-run        Simulate without sending transaction

Requires: POLYMARKET_PRIVATE_KEY in .env
Optional: POLYMARKET_PROXY_WALLET in .env (auto-derived if not set)
"""

import argparse
import sys
import time
from typing import Dict, Optional

from config import (
    POLYGON_CHAIN_ID,
    POLYGON_RPC_URL,
    POLYGON_RPC_FALLBACKS,
    USDC_CONTRACT_ADDRESS,
    USDC_E_ADDRESS,
    USDC_DECIMALS,
    ERC20_ABI,
    POLYMARKET_PRIVATE_KEY,
)
from output_format import success, error


def get_web3():
    """Initialize web3 with Polygon POS connection and POA middleware"""
    try:
        from web3 import Web3
        from web3.middleware import ExtraDataToPOAMiddleware
    except ImportError:
        error("web3 not installed. Run: pip install web3", code="MISSING_DEP")
        return None

    # Try primary RPC, then fallbacks
    rpcs = [POLYGON_RPC_URL] + POLYGON_RPC_FALLBACKS
    w3 = None
    for rpc_url in rpcs:
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if w3.is_connected():
            break

    if w3 is None or not w3.is_connected():
        error("Cannot connect to any Polygon RPC", code="RPC_ERROR")
        return None

    # Polygon is a POA chain — this middleware is REQUIRED
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    return w3


def get_eoa_address() -> str:
    """Derive EOA address from private key"""
    if not POLYMARKET_PRIVATE_KEY:
        error("POLYMARKET_PRIVATE_KEY not set in .env", code="NO_KEY")
        return ""

    from web3 import Web3
    account = Web3().eth.account.from_key(POLYMARKET_PRIVATE_KEY)
    return account.address


def check_balances(address: Optional[str] = None) -> Dict:
    """Check USDC and POL balances for an address"""
    w3 = get_web3()
    if not w3:
        return {}

    if not address:
        address = get_eoa_address()
    if not address:
        return {}

    address = w3.to_checksum_address(address)

    # POL (native) balance
    pol_balance_wei = w3.eth.get_balance(address)
    pol_balance = w3.from_wei(pol_balance_wei, "ether")

    # Native USDC balance
    usdc_contract = w3.eth.contract(
        address=w3.to_checksum_address(USDC_CONTRACT_ADDRESS),
        abi=ERC20_ABI,
    )
    usdc_balance_raw = usdc_contract.functions.balanceOf(address).call()
    usdc_balance = usdc_balance_raw / (10 ** USDC_DECIMALS)

    # USDC.e (bridged) balance — this is what Polymarket uses
    usdc_e_contract = w3.eth.contract(
        address=w3.to_checksum_address(USDC_E_ADDRESS),
        abi=ERC20_ABI,
    )
    usdc_e_balance_raw = usdc_e_contract.functions.balanceOf(address).call()
    usdc_e_balance = usdc_e_balance_raw / (10 ** USDC_DECIMALS)

    # Gas estimate for USDC transfer
    gas_price = w3.eth.gas_price
    estimated_gas = 65000  # typical for ERC20 transfer
    gas_cost_wei = gas_price * estimated_gas
    gas_cost_pol = float(w3.from_wei(gas_cost_wei, "ether"))

    return {
        "address": address,
        "pol_balance": round(float(pol_balance), 6),
        "usdc_native_balance": round(usdc_balance, 6),
        "usdc_native_balance_raw": usdc_balance_raw,
        "usdc_e_balance": round(usdc_e_balance, 6),
        "usdc_e_balance_raw": usdc_e_balance_raw,
        "gas_price_gwei": round(float(w3.from_wei(gas_price, "gwei")), 2),
        "estimated_transfer_gas_pol": round(gas_cost_pol, 6),
        "can_transfer": float(pol_balance) > gas_cost_pol,
    }


def transfer_usdc(
    to_address: str,
    amount_raw: Optional[int] = None,
    dry_run: bool = False,
) -> Dict:
    """
    Transfer USDC from EOA to target address.

    Args:
        to_address: Destination address (proxy wallet or other)
        amount_raw: Amount in raw units (6 decimals). None = full balance.
        dry_run: If True, build tx but don't send
    """
    w3 = get_web3()
    if not w3:
        return {}

    if not POLYMARKET_PRIVATE_KEY:
        error("POLYMARKET_PRIVATE_KEY not set", code="NO_KEY")
        return {}

    account = w3.eth.account.from_key(POLYMARKET_PRIVATE_KEY)
    eoa = account.address
    to_address = w3.to_checksum_address(to_address)

    usdc_contract = w3.eth.contract(
        address=w3.to_checksum_address(USDC_CONTRACT_ADDRESS),
        abi=ERC20_ABI,
    )

    # Get balance if amount not specified
    if amount_raw is None:
        amount_raw = usdc_contract.functions.balanceOf(eoa).call()

    amount_usdc = amount_raw / (10 ** USDC_DECIMALS)

    if amount_raw == 0:
        error("No USDC to transfer", code="ZERO_BALANCE")
        return {}

    # Check POL for gas
    pol_balance = w3.eth.get_balance(eoa)
    gas_price = w3.eth.gas_price
    estimated_gas = 65000
    gas_cost = gas_price * estimated_gas

    if pol_balance < gas_cost:
        pol_needed = float(w3.from_wei(gas_cost - pol_balance, "ether"))
        error(
            f"Insufficient POL for gas. Need ~{pol_needed:.4f} more POL",
            code="INSUFFICIENT_GAS",
            data={
                "pol_balance": float(w3.from_wei(pol_balance, "ether")),
                "gas_cost_pol": float(w3.from_wei(gas_cost, "ether")),
            },
        )
        return {}

    # Build transaction
    nonce = w3.eth.get_transaction_count(eoa)

    # Use EIP-1559 if supported
    try:
        base_fee = w3.eth.get_block("latest").get("baseFeePerGas", 0)
        max_priority = w3.to_wei(30, "gwei")
        max_fee = base_fee * 2 + max_priority

        tx = usdc_contract.functions.transfer(to_address, amount_raw).build_transaction({
            "from": eoa,
            "nonce": nonce,
            "gas": estimated_gas,
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": max_priority,
            "chainId": POLYGON_CHAIN_ID,
        })
    except Exception:
        # Fallback to legacy gas pricing
        tx = usdc_contract.functions.transfer(to_address, amount_raw).build_transaction({
            "from": eoa,
            "nonce": nonce,
            "gas": estimated_gas,
            "gasPrice": gas_price,
            "chainId": POLYGON_CHAIN_ID,
        })

    result = {
        "from": eoa,
        "to": to_address,
        "amount_usdc": round(amount_usdc, 6),
        "amount_raw": amount_raw,
        "gas_estimate": estimated_gas,
        "gas_price_gwei": round(float(w3.from_wei(gas_price, "gwei")), 2),
    }

    if dry_run:
        result["status"] = "dry_run"
        result["message"] = "Transaction built but NOT sent (dry-run mode)"
        return result

    # Sign and send (with retry for rate limits)
    signed_tx = w3.eth.account.sign_transaction(tx, POLYMARKET_PRIVATE_KEY)
    tx_hash = None
    for attempt in range(3):
        try:
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            break
        except Exception as e:
            if "rate limit" in str(e).lower() and attempt < 2:
                time.sleep(15)
                continue
            raise
    if tx_hash is None:
        error("Failed to send transaction after retries", code="SEND_FAILED")
        return {}

    result["tx_hash"] = tx_hash.hex()
    result["status"] = "sent"
    result["explorer_url"] = f"https://polygonscan.com/tx/0x{tx_hash.hex()}"

    # Wait for receipt (timeout 120s)
    try:
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        result["confirmed"] = receipt["status"] == 1
        result["block_number"] = receipt["blockNumber"]
        result["gas_used"] = receipt["gasUsed"]
        result["actual_gas_cost_pol"] = round(
            float(w3.from_wei(receipt["gasUsed"] * receipt["effectiveGasPrice"], "ether")), 6
        )
    except Exception as e:
        result["confirmed"] = None
        result["receipt_error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser(description="Polygon Wallet Utilities for Polymarket")
    sub = parser.add_subparsers(dest="command", required=True)

    # balance command
    bal = sub.add_parser("balance", help="Check USDC and POL balances")
    bal.add_argument("--address", type=str, help="Address to check (default: EOA from private key)")
    bal.add_argument("--json", action="store_true", help="JSON output")

    # transfer-usdc command
    tx = sub.add_parser("transfer-usdc", help="Transfer USDC from EOA")
    tx.add_argument("--to", type=str, help="Destination address")
    tx.add_argument("--to-proxy", action="store_true", help="Transfer to Polymarket Proxy Wallet")
    tx.add_argument("--proxy-address", type=str, help="Proxy wallet address (if known)")
    tx.add_argument("--amount", type=float, help="USDC amount (default: full balance)")
    tx.add_argument("--dry-run", action="store_true", help="Simulate without sending")
    tx.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()

    if args.command == "balance":
        balances = check_balances(args.address)
        if not balances:
            return

        if getattr(args, "json", False):
            success(data=balances)
        else:
            print(f"\n{'=' * 50}")
            print(f"  Polygon Wallet Balances")
            print(f"{'=' * 50}")
            print(f"  Address:      {balances['address']}")
            print(f"  USDC.e:       ${balances['usdc_e_balance']:,.6f}  (Polymarket)")
            print(f"  Native USDC:  ${balances['usdc_native_balance']:,.6f}  (needs swap)")
            print(f"  POL:          {balances['pol_balance']:.6f}")
            print(f"  Gas Price:    {balances['gas_price_gwei']:.2f} gwei")
            print(f"  Transfer Cost: ~{balances['estimated_transfer_gas_pol']:.6f} POL")
            can = "YES" if balances["can_transfer"] else "NO (need more POL)"
            print(f"  Can Transfer: {can}")
            print(f"{'=' * 50}\n")

    elif args.command == "transfer-usdc":
        import os

        # Determine destination
        to_address = args.to
        if args.to_proxy:
            to_address = args.proxy_address or os.getenv("POLYMARKET_PROXY_WALLET", "")
            if not to_address:
                error(
                    "Proxy wallet address not set. Use --proxy-address or set POLYMARKET_PROXY_WALLET in .env",
                    code="NO_PROXY",
                )
                return

        if not to_address:
            error("Specify --to <address> or --to-proxy", code="NO_DEST")
            return

        # Convert amount to raw
        amount_raw = None
        if args.amount:
            amount_raw = int(args.amount * (10 ** USDC_DECIMALS))

        result = transfer_usdc(to_address, amount_raw, dry_run=args.dry_run)
        if not result:
            return

        if getattr(args, "json", False):
            success(data=result)
        else:
            print(f"\n{'=' * 50}")
            print(f"  USDC Transfer {'(DRY RUN)' if args.dry_run else ''}")
            print(f"{'=' * 50}")
            print(f"  From:    {result['from']}")
            print(f"  To:      {result['to']}")
            print(f"  Amount:  ${result['amount_usdc']:,.6f} USDC")
            print(f"  Status:  {result['status']}")
            if result.get("tx_hash"):
                print(f"  TX Hash: {result['tx_hash']}")
                print(f"  Explorer: {result['explorer_url']}")
            if result.get("confirmed") is True:
                print(f"  Confirmed: YES (block {result['block_number']})")
                print(f"  Gas Used:  {result['gas_used']} ({result['actual_gas_cost_pol']} POL)")
            elif result.get("confirmed") is False:
                print(f"  Confirmed: FAILED")
            print(f"{'=' * 50}\n")


if __name__ == "__main__":
    main()
