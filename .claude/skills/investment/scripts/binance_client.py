"""
Binance REST API Client
HMAC-SHA256 signed requests for spot and futures
"""

import time
import hmac
import hashlib
import urllib.parse
from typing import Optional, Dict, Any, List

import requests

from config import (
    BINANCE_API_KEY, BINANCE_API_SECRET,
    BINANCE_SPOT_BASE, BINANCE_FUTURES_BASE,
    API_TIMEOUT_SECONDS
)


class BinanceClient:
    """Binance REST API wrapper with HMAC-SHA256 signing"""

    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key or BINANCE_API_KEY
        self.api_secret = api_secret or BINANCE_API_SECRET
        self.session = requests.Session()
        self.session.headers.update({
            "X-MBX-APIKEY": self.api_key,
            "Content-Type": "application/x-www-form-urlencoded",
        })

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add timestamp and HMAC-SHA256 signature"""
        params["timestamp"] = int(time.time() * 1000)
        query = urllib.parse.urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return params

    def _request(self, method: str, url: str, params: Dict[str, Any] = None, signed: bool = False) -> Any:
        """Make an API request"""
        params = params or {}
        if signed:
            params = self._sign(params)

        try:
            if method == "GET":
                resp = self.session.get(url, params=params, timeout=API_TIMEOUT_SECONDS)
            elif method == "POST":
                resp = self.session.post(url, data=params, timeout=API_TIMEOUT_SECONDS)
            elif method == "DELETE":
                resp = self.session.delete(url, params=params, timeout=API_TIMEOUT_SECONDS)
            else:
                raise ValueError(f"Unsupported method: {method}")

            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            error_body = e.response.text if e.response else "No response body"
            raise RuntimeError(f"Binance API error {e.response.status_code}: {error_body}") from e

    # === Spot Account ===

    def get_spot_account(self) -> Dict[str, Any]:
        """GET /api/v3/account"""
        return self._request("GET", f"{BINANCE_SPOT_BASE}/api/v3/account", signed=True)

    def get_spot_balances(self) -> List[Dict[str, Any]]:
        """Get non-zero spot balances"""
        account = self.get_spot_account()
        return [
            b for b in account.get("balances", [])
            if float(b["free"]) > 0 or float(b["locked"]) > 0
        ]

    def get_spot_trades(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """GET /api/v3/myTrades"""
        return self._request("GET", f"{BINANCE_SPOT_BASE}/api/v3/myTrades", {
            "symbol": symbol, "limit": limit
        }, signed=True)

    def get_spot_price(self, symbol: str = None) -> Any:
        """GET /api/v3/ticker/price"""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", f"{BINANCE_SPOT_BASE}/api/v3/ticker/price", params)

    def get_spot_24hr(self, symbol: str = None) -> Any:
        """GET /api/v3/ticker/24hr"""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", f"{BINANCE_SPOT_BASE}/api/v3/ticker/24hr", params)

    # === Spot Order ===

    def create_spot_order(self, symbol: str, side: str, order_type: str,
                          quantity: float = None, quote_quantity: float = None,
                          price: float = None, time_in_force: str = None) -> Dict[str, Any]:
        """POST /api/v3/order"""
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
        }
        if quantity:
            params["quantity"] = f"{quantity}"
        if quote_quantity:
            params["quoteOrderQty"] = f"{quote_quantity}"
        if price:
            params["price"] = f"{price}"
        if time_in_force:
            params["timeInForce"] = time_in_force
        elif order_type == "LIMIT":
            params["timeInForce"] = "GTC"

        return self._request("POST", f"{BINANCE_SPOT_BASE}/api/v3/order", params, signed=True)

    # === Futures Account ===

    def get_futures_account(self) -> Dict[str, Any]:
        """GET /fapi/v2/account"""
        return self._request("GET", f"{BINANCE_FUTURES_BASE}/fapi/v2/account", signed=True)

    def get_futures_positions(self) -> List[Dict[str, Any]]:
        """Get non-zero futures positions"""
        account = self.get_futures_account()
        return [
            p for p in account.get("positions", [])
            if float(p.get("positionAmt", 0)) != 0
        ]

    def get_futures_balances(self) -> List[Dict[str, Any]]:
        """GET /fapi/v2/balance"""
        return self._request("GET", f"{BINANCE_FUTURES_BASE}/fapi/v2/balance", signed=True)

    def get_futures_income(self, income_type: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """GET /fapi/v1/income"""
        params: Dict[str, Any] = {"limit": limit}
        if income_type:
            params["incomeType"] = income_type
        return self._request("GET", f"{BINANCE_FUTURES_BASE}/fapi/v1/income", params, signed=True)

    # === Futures Order ===

    def create_futures_order(self, symbol: str, side: str, order_type: str,
                             quantity: float = None, price: float = None,
                             stop_price: float = None, time_in_force: str = None,
                             position_side: str = "BOTH") -> Dict[str, Any]:
        """POST /fapi/v1/order"""
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "positionSide": position_side,
        }
        if quantity:
            params["quantity"] = f"{quantity}"
        if price:
            params["price"] = f"{price}"
        if stop_price:
            params["stopPrice"] = f"{stop_price}"
        if time_in_force:
            params["timeInForce"] = time_in_force
        elif order_type == "LIMIT":
            params["timeInForce"] = "GTC"

        return self._request("POST", f"{BINANCE_FUTURES_BASE}/fapi/v1/order", params, signed=True)

    def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """POST /fapi/v1/leverage"""
        return self._request("POST", f"{BINANCE_FUTURES_BASE}/fapi/v1/leverage", {
            "symbol": symbol, "leverage": leverage
        }, signed=True)

    # === Market Data (Public) ===

    def get_funding_rate(self, symbol: str = None, limit: int = 10) -> Any:
        """GET /fapi/v1/fundingRate"""
        params: Dict[str, Any] = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", f"{BINANCE_FUTURES_BASE}/fapi/v1/fundingRate", params)

    def get_open_interest(self, symbol: str) -> Dict[str, Any]:
        """GET /fapi/v1/openInterest"""
        return self._request("GET", f"{BINANCE_FUTURES_BASE}/fapi/v1/openInterest", {"symbol": symbol})

    def get_long_short_ratio(self, symbol: str, period: str = "5m", limit: int = 10) -> List[Dict[str, Any]]:
        """GET /futures/data/globalLongShortAccountRatio"""
        return self._request("GET", f"{BINANCE_FUTURES_BASE}/futures/data/globalLongShortAccountRatio", {
            "symbol": symbol, "period": period, "limit": limit
        })

    def get_taker_volume(self, symbol: str, period: str = "5m", limit: int = 10) -> List[Dict[str, Any]]:
        """GET /futures/data/takerlongshortRatio"""
        return self._request("GET", f"{BINANCE_FUTURES_BASE}/futures/data/takerlongshortRatio", {
            "symbol": symbol, "period": period, "limit": limit
        })

    def get_futures_ticker(self, symbol: str = None) -> Any:
        """GET /fapi/v1/ticker/price"""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", f"{BINANCE_FUTURES_BASE}/fapi/v1/ticker/price", params)
