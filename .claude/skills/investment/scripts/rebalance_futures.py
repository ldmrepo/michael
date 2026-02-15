"""
Futures Rebalancing Script
1. Cancel BTC orphan SELL STOP $64K
2. Set SOL SL $84.50 / TP $95.00
3. BTC LONG 0.015 market entry + SL $66,500 / TP $75,000
"""

import sys
import json
import time

sys.path.insert(0, ".")
from binance_client import BinanceClient
from config import BINANCE_FUTURES_BASE


def main():
    client = BinanceClient()
    results = {}

    # === Step 1: Cancel BTC orphan SELL STOP ===
    print("\n=== STEP 1: Cancel BTC orphan SELL STOP $64K ===")
    try:
        open_orders = client.get_futures_open_orders(symbol="BTCUSDT")
        print(f"BTC open orders: {len(open_orders)}")

        cancelled = 0
        for order in open_orders:
            otype = order.get("type", "")
            stop_price = float(order.get("stopPrice", 0))
            side = order.get("side", "")
            order_id = order.get("orderId")
            print(f"  Found: {side} {otype} stopPrice={stop_price} orderId={order_id}")

            # Cancel SELL STOP at $64K (orphan from closed BTC position)
            if side == "SELL" and "STOP" in otype and 63000 <= stop_price <= 65000:
                result = client.cancel_futures_order(symbol="BTCUSDT", order_id=order_id)
                print(f"  ✅ Cancelled orderId={order_id}: {result.get('status', 'OK')}")
                cancelled += 1

        if cancelled == 0:
            # Check algo orders too
            print("  No regular stop orders found, checking algo orders...")
            try:
                algo_resp = client._request("GET", f"{BINANCE_FUTURES_BASE}/fapi/v1/algoOrders",
                                           {"status": "WORKING"}, signed=True)
                algo_orders = algo_resp.get("orders", []) if isinstance(algo_resp, dict) else algo_resp
                for ao in algo_orders:
                    if ao.get("symbol") == "BTCUSDT" and ao.get("side") == "SELL":
                        trigger = float(ao.get("triggerPrice", 0))
                        algo_id = ao.get("algoId")
                        if 63000 <= trigger <= 65000:
                            result = client.cancel_futures_algo_order(symbol="BTCUSDT", algo_id=algo_id)
                            print(f"  ✅ Cancelled algo order algoId={algo_id}")
                            cancelled += 1
            except Exception as e:
                print(f"  ⚠️ Algo order check failed: {e}")

        results["step1"] = {"status": "ok", "cancelled": cancelled}
        if cancelled == 0:
            print("  ℹ️ No orphan BTC STOP orders found (may already be cancelled)")
            results["step1"]["note"] = "no orphan orders found"
    except Exception as e:
        print(f"  ❌ Step 1 failed: {e}")
        results["step1"] = {"status": "error", "error": str(e)}

    # === Step 2: SOL SL $84.50 / TP $95.00 ===
    print("\n=== STEP 2: Set SOL SL $84.50 / TP $95.00 ===")
    try:
        # Check position mode
        mode = client.get_position_mode()
        is_hedge = mode.get("dualSidePosition", False)
        position_side = "LONG" if is_hedge else "BOTH"
        print(f"  Position mode: {'Hedge' if is_hedge else 'One-Way'} → positionSide={position_side}")

        # Cancel existing SOL algo orders first
        try:
            algo_resp = client._request("GET", f"{BINANCE_FUTURES_BASE}/fapi/v1/algoOrders",
                                       {"status": "WORKING"}, signed=True)
            algo_orders = algo_resp.get("orders", []) if isinstance(algo_resp, dict) else algo_resp
            for ao in algo_orders:
                if ao.get("symbol") == "SOLUSDT":
                    algo_id = ao.get("algoId")
                    client.cancel_futures_algo_order(symbol="SOLUSDT", algo_id=algo_id)
                    print(f"  Cancelled existing SOL algo order: {algo_id}")
        except Exception as e:
            print(f"  ⚠️ Could not check/cancel existing SOL algo orders: {e}")

        # Also cancel regular SOL orders
        sol_orders = client.get_futures_open_orders(symbol="SOLUSDT")
        for order in sol_orders:
            otype = order.get("type", "")
            if "STOP" in otype or "PROFIT" in otype:
                client.cancel_futures_order(symbol="SOLUSDT", order_id=order.get("orderId"))
                print(f"  Cancelled existing SOL order: {order.get('orderId')}")

        # Set SL
        sl_result = client.create_stop_loss_order(
            symbol="SOLUSDT",
            side="SELL",
            stop_price=84.50,
            close_position=True,
            position_side=position_side
        )
        print(f"  ✅ SOL SL $84.50 set: algoId={sl_result.get('algoId', 'N/A')}")

        # Set TP
        tp_result = client.create_take_profit_order(
            symbol="SOLUSDT",
            side="SELL",
            stop_price=95.00,
            close_position=True,
            position_side=position_side
        )
        print(f"  ✅ SOL TP $95.00 set: algoId={tp_result.get('algoId', 'N/A')}")

        results["step2"] = {
            "status": "ok",
            "sl_algo_id": sl_result.get("algoId"),
            "tp_algo_id": tp_result.get("algoId")
        }
    except Exception as e:
        print(f"  ❌ Step 2 failed: {e}")
        results["step2"] = {"status": "error", "error": str(e)}

    # === Step 3: BTC LONG 0.015 @ Market + SL/TP ===
    print("\n=== STEP 3: BTC LONG 0.015 Market + SL $66,500 / TP $75,000 ===")
    try:
        # Set leverage 5x
        lev_result = client.set_leverage(symbol="BTCUSDT", leverage=5)
        print(f"  Leverage set to 5x: {lev_result.get('leverage', 'N/A')}")

        # Get current BTC price
        ticker = client.get_futures_ticker("BTCUSDT")
        btc_price = float(ticker["price"])
        print(f"  Current BTC price: ${btc_price:,.2f}")

        est_value = 0.015 * btc_price
        print(f"  Position size: 0.015 BTC = ${est_value:,.2f} / Margin ~${est_value/5:,.2f}")

        # Market buy
        order_result = client.create_futures_order(
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            quantity=0.015,
            position_side=position_side
        )
        fill_price = float(order_result.get("avgPrice", btc_price))
        fill_qty = float(order_result.get("executedQty", 0))
        print(f"  ✅ BTC LONG filled: {fill_qty} BTC @ ${fill_price:,.2f}")
        print(f"     OrderId: {order_result.get('orderId')}, Status: {order_result.get('status')}")

        time.sleep(1)  # Small delay before setting SL/TP

        # Set SL
        sl_result = client.create_stop_loss_order(
            symbol="BTCUSDT",
            side="SELL",
            stop_price=66500,
            close_position=True,
            position_side=position_side
        )
        print(f"  ✅ BTC SL $66,500 set: algoId={sl_result.get('algoId', 'N/A')}")

        # Set TP
        tp_result = client.create_take_profit_order(
            symbol="BTCUSDT",
            side="SELL",
            stop_price=75000,
            close_position=True,
            position_side=position_side
        )
        print(f"  ✅ BTC TP $75,000 set: algoId={tp_result.get('algoId', 'N/A')}")

        results["step3"] = {
            "status": "ok",
            "fill_price": fill_price,
            "fill_qty": fill_qty,
            "order_id": order_result.get("orderId"),
            "sl_algo_id": sl_result.get("algoId"),
            "tp_algo_id": tp_result.get("algoId")
        }
    except Exception as e:
        print(f"  ❌ Step 3 failed: {e}")
        results["step3"] = {"status": "error", "error": str(e)}

    # === Summary ===
    print("\n=== EXECUTION SUMMARY ===")
    for step, data in results.items():
        status = "✅" if data.get("status") == "ok" else "❌"
        print(f"  {status} {step}: {json.dumps(data, default=str)}")

    # Final account state
    print("\n=== FINAL ACCOUNT STATE ===")
    try:
        account = client.get_futures_account()
        print(f"  Wallet Balance: ${float(account.get('totalWalletBalance', 0)):,.2f}")
        print(f"  Unrealized PnL: ${float(account.get('totalUnrealizedProfit', 0)):,.2f}")
        print(f"  Available: ${float(account.get('availableBalance', 0)):,.2f}")

        positions = [p for p in account.get("positions", []) if float(p.get("positionAmt", 0)) != 0]
        for p in positions:
            sym = p["symbol"]
            amt = float(p["positionAmt"])
            entry = float(p["entryPrice"])
            pnl = float(p.get("unrealizedProfit", 0))
            margin = float(p.get("isolatedWallet", 0))
            lev = p.get("leverage", "?")
            print(f"  {sym}: {amt} @ ${entry:,.2f} | PnL ${pnl:,.2f} | Margin ${margin:,.2f} | {lev}x")
    except Exception as e:
        print(f"  ⚠️ Could not fetch final state: {e}")

    return results


if __name__ == "__main__":
    main()
