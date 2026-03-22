"""Binance Futures REST API — order execution and account queries."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Any

import requests
import structlog

log = structlog.get_logger(__name__)

FAPI = "https://fapi.binance.com"


_time_offset: int = 0  # ms offset between local and Binance server time


def _sync_time() -> None:
    """Sync local clock with Binance server time."""
    global _time_offset
    try:
        r = requests.get(f"{FAPI}/fapi/v1/time", timeout=5)
        server_time = r.json()["serverTime"]
        _time_offset = server_time - int(time.time() * 1000)
    except Exception:
        pass


def _sign(params: dict[str, Any]) -> str:
    params["timestamp"] = int(time.time() * 1000) + _time_offset
    params["recvWindow"] = 10000
    query = "&".join(f"{k}={v}" for k, v in params.items())
    secret = os.environ.get("BINANCE_API_SECRET", "")
    sig = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    return f"{query}&signature={sig}"


def _headers() -> dict[str, str]:
    return {"X-MBX-APIKEY": os.environ.get("BINANCE_API_KEY", "")}


def _post(path: str, params: dict[str, Any]) -> dict[str, Any]:
    url = f"{FAPI}{path}?{_sign(params)}"
    r = requests.post(url, headers=_headers(), timeout=10)
    data = r.json()
    if r.status_code != 200:
        if data.get("code") == -1021:
            _sync_time()
            params.pop("timestamp", None)
            params.pop("signature", None)
            params.pop("recvWindow", None)
            url = f"{FAPI}{path}?{_sign(params)}"
            r = requests.post(url, headers=_headers(), timeout=10)
            data = r.json()
            if r.status_code == 200:
                return data
        log.error("api_error", path=path, code=data.get("code"), msg=data.get("msg"))
        raise RuntimeError(f"Binance API error: {data.get('msg', 'unknown')}")
    return data


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    params = params or {}
    url = f"{FAPI}{path}?{_sign(params)}"
    r = requests.get(url, headers=_headers(), timeout=10)
    data = r.json()
    if r.status_code != 200:
        # Auto-sync time on timestamp error and retry once
        if data.get("code") == -1021:
            _sync_time()
            params.pop("timestamp", None)
            params.pop("signature", None)
            params.pop("recvWindow", None)
            url = f"{FAPI}{path}?{_sign(params)}"
            r = requests.get(url, headers=_headers(), timeout=10)
            data = r.json()
            if r.status_code == 200:
                return data
        log.error("api_error", path=path, code=data.get("code"), msg=data.get("msg"))
        raise RuntimeError(f"Binance API error: {data.get('msg', 'unknown')}")
    return data


def fetch_klines(symbol: str, interval: str, limit: int = 100) -> list[list]:
    """Fetch klines (no auth needed)."""
    r = requests.get(
        f"{FAPI}/fapi/v1/klines",
        params={"symbol": symbol, "interval": interval, "limit": limit},
        timeout=10,
    )
    return r.json()


def check_hedge_mode() -> bool:
    """Verify account is in Hedge mode (dualSidePosition=true). Raises if not."""
    result = _get("/fapi/v1/positionSide/dual", {})
    dual = result.get("dualSidePosition", False)
    if not dual:
        raise RuntimeError("Account is NOT in Hedge mode. Set dualSidePosition=true on Binance.")
    return True


def set_leverage(symbol: str, leverage: int) -> None:
    """Set symbol leverage. Always succeeds — Binance returns current leverage even if unchanged."""
    result = _post("/fapi/v1/leverage", {"symbol": symbol, "leverage": leverage})
    log.info("leverage_set", symbol=symbol, leverage=result.get("leverage"))


def get_all_positions(symbol: str) -> list[dict]:
    """Get all positions for symbol (both sides). Public API for monitor."""
    result = _get("/fapi/v2/positionRisk", {"symbol": symbol})
    if isinstance(result, list):
        return [p for p in result if float(p.get("positionAmt", 0)) != 0]
    return []


def place_market_order(symbol: str, side: str, position_side: str, qty: float) -> dict:
    return _post("/fapi/v1/order", {
        "symbol": symbol,
        "side": side,
        "positionSide": position_side,
        "type": "MARKET",
        "quantity": qty,
    })


def get_position(symbol: str, position_side: str = "") -> dict | None:
    """Get position. If position_side given, filter by LONG/SHORT (Hedge mode)."""
    result = _get("/fapi/v2/positionRisk", {"symbol": symbol})
    if isinstance(result, list):
        for p in result:
            if float(p.get("positionAmt", 0)) != 0:
                if position_side and p.get("positionSide", "") != position_side:
                    continue
                return p
    return None


def get_wallet_balance() -> float:
    acct = _get("/fapi/v2/account")
    return float(acct.get("totalWalletBalance", 0))


def get_available_balance() -> float:
    acct = _get("/fapi/v2/account")
    return float(acct.get("availableBalance", 0))
