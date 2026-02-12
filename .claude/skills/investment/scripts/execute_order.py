#!/usr/bin/env python3
"""Execute Binance orders from approved proposals"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import MAX_ORDER_USD
from binance_client import BinanceClient
from db_utils import (
    get_connection, get_proposal, update_proposal_status,
    insert_transaction, upsert_holding
)
from output_format import success, error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposal-id", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        conn = get_connection()
        proposal = get_proposal(conn, args.proposal_id)

        if not proposal:
            error(f"Proposal {args.proposal_id} not found", "NOT_FOUND")
            return

        if proposal["status"] != "approved":
            error(f"Proposal status is '{proposal['status']}', expected 'approved'", "INVALID_STATUS")
            return

        client = BinanceClient()

        # Safety check: max order value
        # For MARKET orders, price may be NULL — fetch current price from Binance
        price = proposal.get("price")
        if not price and proposal["order_type"] == "MARKET":
            try:
                if proposal["account_type"] == "spot":
                    ticker = client.get_spot_price(proposal["symbol"])
                else:
                    ticker = client.get_futures_ticker(proposal["symbol"])
                price = float(ticker["price"]) if isinstance(ticker, dict) else 0
            except Exception as e:
                error(f"Failed to fetch current price for {proposal['symbol']}: {e}", "PRICE_FETCH_ERROR")
                return

        est_value = proposal["quantity"] * (price or 0)
        if est_value > MAX_ORDER_USD:
            update_proposal_status(conn, args.proposal_id, "failed",
                                   json.dumps({"error": f"Order value ${est_value:,.2f} exceeds limit ${MAX_ORDER_USD:,.2f}"}))
            error(f"Order value ${est_value:,.2f} exceeds limit ${MAX_ORDER_USD:,.2f}", "LIMIT_EXCEEDED")
            return

        if args.dry_run:
            success({
                "dry_run": True,
                "proposal_id": args.proposal_id,
                "symbol": proposal["symbol"],
                "side": proposal["side"],
                "quantity": proposal["quantity"],
                "est_value": est_value,
            }, "Dry run - order NOT placed")

        if proposal["account_type"] == "spot":
            result = client.create_spot_order(
                symbol=proposal["symbol"],
                side=proposal["side"],
                order_type=proposal["order_type"],
                quantity=proposal["quantity"],
                price=proposal.get("price"),
            )
        else:
            if proposal.get("leverage"):
                client.set_leverage(proposal["symbol"], proposal["leverage"])

            result = client.create_futures_order(
                symbol=proposal["symbol"],
                side=proposal["side"],
                order_type=proposal["order_type"],
                quantity=proposal["quantity"],
                price=proposal.get("price"),
            )

        # Create SL/TP orders for futures positions
        sl_tp_results = []
        if proposal["account_type"] == "futures":
            opposite_side = "SELL" if proposal["side"] == "BUY" else "BUY"
            fill_qty = float(result.get("executedQty", proposal["quantity"]))

            if proposal.get("stop_loss"):
                try:
                    sl_result = client.create_stop_loss_order(
                        symbol=proposal["symbol"],
                        side=opposite_side,
                        stop_price=proposal["stop_loss"],
                        close_position=True,
                    )
                    sl_tp_results.append({"type": "stop_loss", "order": sl_result})
                except Exception as e:
                    sl_tp_results.append({"type": "stop_loss", "error": str(e)})

            if proposal.get("take_profit"):
                try:
                    tp_result = client.create_take_profit_order(
                        symbol=proposal["symbol"],
                        side=opposite_side,
                        stop_price=proposal["take_profit"],
                        close_position=True,
                    )
                    sl_tp_results.append({"type": "take_profit", "order": tp_result})
                except Exception as e:
                    sl_tp_results.append({"type": "take_profit", "error": str(e)})

        result["sl_tp_orders"] = sl_tp_results

        # Update proposal status
        update_proposal_status(conn, args.proposal_id, "executed",
                               json.dumps(result, ensure_ascii=False, default=str))

        # Record transaction
        fill_price = float(result.get("avgPrice") or result.get("price", 0))
        fill_qty = float(result.get("executedQty", proposal["quantity"]))

        insert_transaction(
            conn, proposal["user_id"], "binance",
            proposal["account_type"], proposal["symbol"],
            proposal["side"], proposal["order_type"],
            fill_qty, fill_price,
            order_id=str(result.get("orderId", "")),
            source="semi-auto",
            executed_at=int(result.get("updateTime", 0) / 1000) or None,
        )

        conn.close()
        success({
            "proposal_id": args.proposal_id,
            "order_id": result.get("orderId"),
            "status": result.get("status"),
            "filled_qty": fill_qty,
            "fill_price": fill_price,
        }, f"Order executed: {proposal['side']} {fill_qty} {proposal['symbol']} @ ${fill_price:,.2f}")

    except Exception as e:
        try:
            conn = get_connection()
            update_proposal_status(conn, args.proposal_id, "failed",
                                   json.dumps({"error": str(e)}))
            conn.close()
        except Exception:
            pass
        error(str(e), "EXECUTE_ORDER_ERROR")


if __name__ == "__main__":
    main()
