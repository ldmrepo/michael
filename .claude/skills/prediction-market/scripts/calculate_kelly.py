#!/usr/bin/env python3
"""
Kelly Criterion Position Sizer

Calculates optimal position size based on estimated edge:
  --estimated-prob 0.75  Your estimated probability
  --market-price 0.60    Current market price
  --bankroll 1000        Available capital ($)
  --fraction 0.5         Kelly fraction (default: Half Kelly)
  --market-id <id>       Auto-fetch current market price
"""

import argparse
import json
import sys
from typing import Dict, Optional

from output_format import success, error


def kelly_criterion(
    estimated_prob: float,
    market_price: float,
    fraction: float = 0.5,
) -> Dict:
    """
    Calculate Kelly Criterion for binary prediction markets.

    In prediction markets:
      - Buying YES at price p: win (1-p) if YES, lose p if NO
      - Buying NO at price (1-p): win p if YES, lose (1-p) if NO

    Kelly formula for YES:
      f* = (p * (1-market_price) - (1-p) * market_price) / (1-market_price)
         = (p - market_price) / (1 - market_price)

    For NO (if estimated_prob < market_price):
      f* = (market_price - p) / market_price

    Args:
        estimated_prob: Your belief of YES probability (0-1)
        market_price: Current YES price on market (0-1)
        fraction: Kelly fraction (0.5 = Half Kelly, recommended)
    """
    if not (0 < estimated_prob < 1):
        return {"error": "estimated_prob must be between 0 and 1 (exclusive)"}
    if not (0 < market_price < 1):
        return {"error": "market_price must be between 0 and 1 (exclusive)"}

    edge = estimated_prob - market_price
    edge_pct = edge * 100

    if abs(edge) < 0.001:
        return {
            "direction": "NONE",
            "edge_pct": round(edge_pct, 2),
            "message": "No meaningful edge detected. Do not bet.",
            "kelly_fraction": 0,
            "position_size": 0,
            "contracts": 0,
            "expected_value": 0,
        }

    if edge > 0:
        # Buy YES
        direction = "YES"
        # Kelly: (p - market_price) / (1 - market_price)
        odds_b = (1 - market_price) / market_price  # decimal odds - 1
        full_kelly = (estimated_prob * odds_b - (1 - estimated_prob)) / odds_b
        contract_price = market_price
        win_payout = 1.0 - market_price
        loss_amount = market_price
    else:
        # Buy NO
        direction = "NO"
        no_price = 1.0 - market_price
        no_prob = 1.0 - estimated_prob
        odds_b = market_price / no_price  # decimal odds - 1
        full_kelly = (no_prob * odds_b - (1 - no_prob)) / odds_b
        contract_price = no_price
        win_payout = market_price
        loss_amount = no_price
        edge_pct = abs(edge_pct)

    # Clamp Kelly to [0, 1]
    full_kelly = max(0, min(1, full_kelly))
    fractional_kelly = full_kelly * fraction

    # Expected value per $1 bet
    if direction == "YES":
        ev = estimated_prob * win_payout - (1 - estimated_prob) * loss_amount
    else:
        ev = (1 - estimated_prob) * win_payout - estimated_prob * loss_amount

    return {
        "direction": direction,
        "edge_pct": round(edge_pct, 2),
        "estimated_prob": estimated_prob,
        "market_price": market_price,
        "contract_price": round(contract_price, 4),
        "full_kelly_pct": round(full_kelly * 100, 2),
        "fractional_kelly_pct": round(fractional_kelly * 100, 2),
        "kelly_fraction_used": fraction,
        "expected_value_per_dollar": round(ev, 4),
        "win_payout": round(win_payout, 4),
        "loss_amount": round(loss_amount, 4),
    }


def size_position(kelly_result: Dict, bankroll: float) -> Dict:
    """Apply Kelly result to a specific bankroll"""
    if kelly_result.get("direction") == "NONE" or kelly_result.get("error"):
        return {
            **kelly_result,
            "bankroll": bankroll,
            "position_size_usd": 0,
            "contracts": 0,
        }

    frac = kelly_result["fractional_kelly_pct"] / 100
    position_usd = bankroll * frac
    contract_price = kelly_result["contract_price"]
    contracts = position_usd / contract_price if contract_price > 0 else 0

    # Expected profit
    ev_per_dollar = kelly_result["expected_value_per_dollar"]
    expected_profit = position_usd * ev_per_dollar

    # Max win / max loss
    max_win = contracts * kelly_result["win_payout"]
    max_loss = position_usd  # lose entire position

    return {
        **kelly_result,
        "bankroll": bankroll,
        "position_size_usd": round(position_usd, 2),
        "contracts": round(contracts, 1),
        "expected_profit": round(expected_profit, 2),
        "max_win": round(max_win, 2),
        "max_loss": round(max_loss, 2),
    }


def main():
    parser = argparse.ArgumentParser(description="Kelly Criterion Position Sizer")
    parser.add_argument("--estimated-prob", type=float, required=True,
                        help="Your estimated probability (0-1)")
    parser.add_argument("--market-price", type=float, default=0,
                        help="Current market YES price (0-1)")
    parser.add_argument("--market-id", type=str, default="",
                        help="Auto-fetch market price by ID")
    parser.add_argument("--bankroll", type=float, default=1000,
                        help="Available capital in USD")
    parser.add_argument("--fraction", type=float, default=0.5,
                        help="Kelly fraction (0.5 = Half Kelly)")
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()

    market_price = args.market_price
    market_question = ""

    # Auto-fetch from API if market-id provided
    if args.market_id and market_price == 0:
        try:
            from polymarket_client import create_client
            client = create_client()
            market = client.get_market(args.market_id)
            prices_raw = market.get("outcomePrices", "")
            if isinstance(prices_raw, str):
                prices = json.loads(prices_raw)
            else:
                prices = prices_raw or []
            if prices:
                market_price = float(prices[0])
                market_question = market.get("question", "")[:80]
        except Exception as e:
            error(f"Failed to fetch market price: {e}", code="FETCH_ERROR")
            return

    if market_price <= 0 or market_price >= 1:
        error("market-price must be between 0 and 1. Provide --market-price or --market-id.", code="INVALID_PRICE")
        return

    # Calculate
    kelly_result = kelly_criterion(args.estimated_prob, market_price, args.fraction)
    sized = size_position(kelly_result, args.bankroll)

    if args.json:
        if market_question:
            sized["market_question"] = market_question
        success(data=sized)
    else:
        # Pretty print
        print("\n" + "=" * 60)
        print("  Kelly Criterion Position Sizer")
        print("=" * 60)

        if market_question:
            print(f"\n  Market: {market_question}")

        print(f"\n  Your Estimate:  {args.estimated_prob*100:.1f}% probability")
        print(f"  Market Price:   ${market_price:.4f} (implied {market_price*100:.1f}%)")
        print(f"  Edge:           {sized.get('edge_pct', 0):+.2f}%")
        print(f"  Direction:      {sized.get('direction', 'NONE')}")

        if sized.get("direction") == "NONE":
            print(f"\n  No meaningful edge. Do not bet.")
        else:
            print(f"\n  --- Position Sizing ---")
            frac_name = {0.25: "Quarter", 0.5: "Half", 0.75: "Three-Quarter", 1.0: "Full"}
            kelly_name = frac_name.get(args.fraction, f"{args.fraction:.0%}")
            print(f"  Kelly ({kelly_name}):  {sized['fractional_kelly_pct']:.1f}% of bankroll")
            print(f"  Full Kelly:     {sized['full_kelly_pct']:.1f}% of bankroll")
            print(f"  Bankroll:       ${args.bankroll:,.2f}")
            print(f"  Position Size:  ${sized['position_size_usd']:,.2f}")
            print(f"  Contracts:      {sized['contracts']:,.1f}")
            print(f"\n  --- Expected Outcomes ---")
            print(f"  EV per $1 bet:  ${sized['expected_value_per_dollar']:+.4f}")
            print(f"  Expected Profit: ${sized['expected_profit']:+,.2f}")
            print(f"  Max Win:         ${sized['max_win']:+,.2f}")
            print(f"  Max Loss:        -${sized['max_loss']:,.2f}")

        print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
