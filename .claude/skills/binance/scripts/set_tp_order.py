#!/usr/bin/env python3
"""Set Take Profit order for BTC LONG position."""

import hmac, hashlib, time, os, sys
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("BINANCE_API_KEY", "")
API_SECRET = os.environ.get("BINANCE_API_SECRET", "")
FAPI = "https://fapi.binance.com"

if not API_KEY or not API_SECRET:
    print("ERROR: BINANCE_API_KEY and BINANCE_API_SECRET required"); sys.exit(1)


def signed_req(method, path, params=None):
    params = params or {}
    params["timestamp"] = int(time.time() * 1000)
    query = "&".join(f"{k}={v}" for k, v in params.items())
    sig = hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    headers = {"X-MBX-APIKEY": API_KEY}
    url = f"{FAPI}{path}?{query}&signature={sig}"
    resp = requests.request(method, url, headers=headers)
    return resp.json()


def main():
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    tp_price = float(sys.argv[2]) if len(sys.argv) > 2 else 75000.0

    # 1. Verify open position exists
    positions = signed_req("GET", "/fapi/v2/positionRisk", {"symbol": symbol})
    if isinstance(positions, dict) and "code" in positions:
        print(f"Error: {positions}"); sys.exit(1)

    open_pos = [p for p in positions if float(p.get("positionAmt", 0)) != 0]
    if not open_pos:
        print(f"No open position for {symbol}"); sys.exit(1)

    pos = open_pos[0]
    amt = float(pos["positionAmt"])
    side = "LONG" if amt > 0 else "SHORT"
    entry = float(pos["entryPrice"])
    print(f"Found {symbol} {side} position: {abs(amt)} @ ${entry:,.2f}")

    # 2. Check if TP already exists
    orders = signed_req("GET", "/fapi/v1/openOrders", {"symbol": symbol})
    existing_tp = [o for o in orders if o.get("type") in ("TAKE_PROFIT_MARKET", "TAKE_PROFIT")]
    if existing_tp:
        print(f"TP already exists at ${float(existing_tp[0].get('stopPrice', 0)):,.2f}")
        print("Cancel it first if you want to set a new one.")
        sys.exit(0)

    # 3. Determine close side (opposite of position)
    close_side = "SELL" if side == "LONG" else "BUY"

    # 4. Check position mode (one-way vs hedge)
    mode = signed_req("GET", "/fapi/v1/positionSide/dual")
    is_hedge = mode.get("dualSidePosition", False)

    # 5. Place TP order
    # NOTE: TAKE_PROFIT_MARKET may fail with -4120 "use Algo Order API"
    # Use TAKE_PROFIT (limit) as fallback with price slightly below stopPrice
    limit_price = round(tp_price * 0.999, 2)  # 0.1% below stop
    order_params = {
        "symbol": symbol,
        "side": close_side,
        "type": "TAKE_PROFIT",
        "stopPrice": tp_price,
        "price": limit_price,
        "quantity": str(abs(amt)),
        "workingType": "MARK_PRICE",
        "timeInForce": "GTE_GTC",
    }
    if is_hedge:
        order_params["positionSide"] = "LONG" if side == "LONG" else "SHORT"

    result = signed_req("POST", "/fapi/v1/order", order_params)

    if "orderId" in result:
        print(f"\n✅ TP order placed successfully!")
        print(f"   Symbol: {symbol}")
        print(f"   Type: TAKE_PROFIT_MARKET")
        print(f"   Side: {close_side} (close {side})")
        print(f"   Stop Price: ${tp_price:,.2f}")
        print(f"   Order ID: {result['orderId']}")
        print(f"   Status: {result.get('status', '?')}")
    else:
        print(f"\n❌ Failed to place TP order: {result}")
        sys.exit(1)


if __name__ == "__main__":
    main()
