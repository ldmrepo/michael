"""
Polymarket Integrated API Client

Wraps three API layers:
  - Gamma API: Public market discovery (no auth required)
  - CLOB API: Trading execution (via py-clob-client, requires private key)
  - Data API: Historical analytics (public/auth)

Authentication strategy:
  - No private_key → Gamma API only (read-only)
  - private_key → CLOB auth + trading
  - api_key/secret/passphrase → L2 auth (faster, skip on-chain derivation)
"""

import time
import logging
from typing import Any, Dict, List, Optional

import requests

from config import (
    GAMMA_API_BASE,
    CLOB_API_BASE,
    DATA_API_BASE,
    POLYGON_CHAIN_ID,
    API_TIMEOUT_SECONDS,
    DEFAULT_MARKET_LIMIT,
    POLYMARKET_PRIVATE_KEY,
    POLYMARKET_API_KEY,
    POLYMARKET_API_SECRET,
    POLYMARKET_PASSPHRASE,
    POLYMARKET_PROXY_WALLET,
)

logger = logging.getLogger(__name__)


class PolymarketClient:
    """
    Polymarket integrated API client.

    - Gamma API: Market discovery (public, no auth)
    - CLOB API: Trading execution (py-clob-client delegation)
    - Data API: Historical analysis (public/auth)
    """

    def __init__(
        self,
        private_key: str = "",
        api_key: str = "",
        api_secret: str = "",
        passphrase: str = "",
        proxy_wallet: str = "",
    ):
        self.private_key = private_key or POLYMARKET_PRIVATE_KEY
        self.api_key = api_key or POLYMARKET_API_KEY
        self.api_secret = api_secret or POLYMARKET_API_SECRET
        self.passphrase = passphrase or POLYMARKET_PASSPHRASE
        self.proxy_wallet = proxy_wallet or POLYMARKET_PROXY_WALLET

        # HTTP session for Gamma/Data API
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "michael-polymarket-client/1.0",
        })

        # Lazy-initialized py-clob-client
        self._clob = None

    # ─────────────────────────────────────────────
    #  CLOB Client (Lazy Init)
    # ─────────────────────────────────────────────

    @property
    def clob(self):
        """Lazy-init py-clob-client ClobClient. Raises if no private key."""
        if self._clob is not None:
            return self._clob

        if not self.private_key:
            raise RuntimeError(
                "CLOB trading requires POLYMARKET_PRIVATE_KEY. "
                "Set it in .env or pass to constructor."
            )

        try:
            from py_clob_client.client import ClobClient
            from py_clob_client.clob_types import ApiCreds
            from py_order_utils.model.signatures import POLY_PROXY
        except ImportError:
            raise RuntimeError(
                "py-clob-client not installed. Run: pip install py-clob-client"
            )

        host = CLOB_API_BASE
        key = self.private_key

        # Determine proxy wallet address (funder) if not provided
        funder = self.proxy_wallet or None
        # Use POLY_PROXY signature type when funder is set (proxy wallet holds funds)
        sig_type = POLY_PROXY if funder else None

        # Initialize with L2 creds if available, otherwise derive
        if self.api_key and self.api_secret and self.passphrase:
            creds = ApiCreds(
                api_key=self.api_key,
                api_secret=self.api_secret,
                api_passphrase=self.passphrase,
            )
            self._clob = ClobClient(
                host, key=key, chain_id=POLYGON_CHAIN_ID, creds=creds,
                signature_type=sig_type, funder=funder,
            )
        else:
            self._clob = ClobClient(
                host, key=key, chain_id=POLYGON_CHAIN_ID,
                signature_type=sig_type, funder=funder,
            )
            # Derive L2 credentials from L1 signature
            try:
                self._clob.set_api_creds(self._clob.create_or_derive_api_creds())
                logger.info("L2 API credentials derived from private key")
            except Exception as e:
                logger.warning(f"Failed to derive L2 creds: {e}")

        return self._clob

    @property
    def has_trading(self) -> bool:
        """Check if trading is available"""
        return bool(self.private_key)

    # ─────────────────────────────────────────────
    #  Gamma API (Public Market Data)
    # ─────────────────────────────────────────────

    def _gamma_get(self, path: str, params: Optional[Dict] = None) -> Any:
        """Make GET request to Gamma API"""
        url = f"{GAMMA_API_BASE}{path}"
        resp = self.session.get(url, params=params, timeout=API_TIMEOUT_SECONDS)
        resp.raise_for_status()
        return resp.json()

    def get_markets(
        self,
        tag: Optional[str] = None,
        active: bool = True,
        closed: bool = False,
        limit: int = DEFAULT_MARKET_LIMIT,
        offset: int = 0,
        order: str = "volume24hr",
        ascending: bool = False,
    ) -> List[Dict]:
        """
        Fetch markets from Gamma API.

        Args:
            tag: Filter by tag (e.g. "crypto", "politics", "sports")
            active: Only active markets
            closed: Include closed markets
            limit: Max results (default 100)
            offset: Pagination offset
            order: Sort field (volume24hr, liquidity, endDate, startDate)
            ascending: Sort direction
        """
        params = {
            "limit": limit,
            "offset": offset,
            "order": order,
            "ascending": str(ascending).lower(),
            "active": str(active).lower(),
            "closed": str(closed).lower(),
        }
        if tag:
            params["tag"] = tag

        return self._gamma_get("/markets", params)

    def get_market(self, market_id: str) -> Dict:
        """Get detailed info for a single market by condition_id or slug"""
        # Try by condition_id first
        result = self._gamma_get("/markets", {"id": market_id})
        if result and isinstance(result, list) and len(result) > 0:
            return result[0]

        # Try by slug
        result = self._gamma_get("/markets", {"slug": market_id})
        if result and isinstance(result, list) and len(result) > 0:
            return result[0]

        raise ValueError(f"Market not found: {market_id}")

    def get_events(self, limit: int = 50, active: bool = True) -> List[Dict]:
        """Get events (groups of related markets)"""
        params = {
            "limit": limit,
            "active": str(active).lower(),
        }
        return self._gamma_get("/events", params)

    def search_markets(self, query: str, limit: int = 20) -> List[Dict]:
        """Search markets by text query"""
        params = {"_q": query, "limit": limit, "active": "true"}
        return self._gamma_get("/markets", params)

    # ─────────────────────────────────────────────
    #  CLOB API — Order Book & Pricing
    # ─────────────────────────────────────────────

    def get_order_book(self, token_id: str) -> Dict:
        """Get full order book for a token"""
        return self.clob.get_order_book(token_id)

    def get_order_book_summary(self, token_id: str) -> Dict:
        """Get order book summary with depth"""
        book = self.get_order_book(token_id)
        # py-clob-client returns OrderBookSummary object, not dict
        if hasattr(book, "bids"):
            bids = book.bids or []
            asks = book.asks or []
        else:
            bids = book.get("bids", [])
            asks = book.get("asks", [])

        def _price(entry):
            return float(entry.price if hasattr(entry, "price") else entry["price"])

        def _size(entry):
            return float(entry.size if hasattr(entry, "size") else entry["size"])

        best_bid = _price(bids[0]) if bids else 0
        best_ask = _price(asks[0]) if asks else 1
        spread = best_ask - best_bid

        # Calculate depth (sum of sizes at top 5 levels)
        bid_depth = sum(_size(b) for b in bids[:5])
        ask_depth = sum(_size(a) for a in asks[:5])

        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "spread_pct": (spread / best_ask * 100) if best_ask > 0 else 0,
            "bid_depth_5": bid_depth,
            "ask_depth_5": ask_depth,
            "bid_levels": len(bids),
            "ask_levels": len(asks),
        }

    def get_midpoint(self, token_id: str) -> float:
        """Get midpoint price for a token"""
        resp = self.clob.get_midpoint(token_id)
        return float(resp.get("mid", 0))

    def get_price(self, token_id: str, side: str = "buy") -> float:
        """Get best price for a side (buy/sell)"""
        resp = self.clob.get_price(token_id, side)
        return float(resp.get("price", 0))

    def get_spread(self, token_id: str) -> Dict:
        """Get bid-ask spread for a token"""
        resp = self.clob.get_spread(token_id)
        return {
            "bid": float(resp.get("bid", 0)),
            "ask": float(resp.get("ask", 0)),
            "spread": float(resp.get("spread", 0)),
        }

    # ─────────────────────────────────────────────
    #  CLOB API — Trading
    # ─────────────────────────────────────────────

    def create_limit_order(
        self,
        token_id: str,
        side: str,
        price: float,
        size: float,
    ) -> Dict:
        """
        Create a limit order.

        Args:
            token_id: The token to trade (YES or NO token)
            side: "BUY" or "SELL"
            price: Limit price (0-1)
            size: Number of contracts
        """
        from py_clob_client.order_builder.constants import BUY, SELL
        from py_clob_client.clob_types import OrderArgs

        order_side = BUY if side.upper() == "BUY" else SELL
        order_args = OrderArgs(
            token_id=token_id,
            price=price,
            size=size,
            side=order_side,
        )
        signed_order = self.clob.create_order(order_args)
        return self.clob.post_order(signed_order)

    def create_market_order(
        self,
        token_id: str,
        side: str,
        amount: float,
    ) -> Dict:
        """
        Create a market order.

        Args:
            token_id: The token to trade
            side: "BUY" or "SELL"
            amount: Amount in USDC for BUY, contracts for SELL
        """
        from py_clob_client.order_builder.constants import BUY, SELL
        from py_clob_client.clob_types import MarketOrderArgs

        order_side = BUY if side.upper() == "BUY" else SELL
        order_args = MarketOrderArgs(
            token_id=token_id,
            amount=amount,
            side=order_side,
        )
        signed_order = self.clob.create_market_order(order_args)
        return self.clob.post_order(signed_order)

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a specific order"""
        resp = self.clob.cancel(order_id)
        return resp.get("canceled", False) if isinstance(resp, dict) else bool(resp)

    def cancel_all_orders(self) -> bool:
        """Cancel all open orders"""
        resp = self.clob.cancel_all()
        return bool(resp)

    # ─────────────────────────────────────────────
    #  CLOB API — Account
    # ─────────────────────────────────────────────

    def get_positions(self) -> List[Dict]:
        """Get all current positions"""
        # CLOB doesn't have a direct positions endpoint;
        # use the balance/trades to reconstruct
        try:
            return self.clob.get_positions()
        except Exception:
            # Fallback: derive from trades
            return []

    def get_open_orders(self) -> List[Dict]:
        """Get all open orders"""
        return self.clob.get_orders()

    def get_trades(self, limit: int = 100) -> List[Dict]:
        """Get trade history"""
        return self.clob.get_trades()

    def get_balances(self) -> Dict:
        """Get USDC.e collateral balance and allowance from Proxy Wallet"""
        try:
            from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
            params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
            resp = self.clob.get_balance_allowance(params)
            if isinstance(resp, dict):
                balance_raw = int(resp.get("balance", 0))
                return {
                    "balance_raw": balance_raw,
                    "balance_usdc": balance_raw / 1e6,
                    "allowance": resp.get("allowance", "0"),
                }
            if hasattr(resp, "__dict__"):
                return vars(resp)
            return {"raw": str(resp)}
        except Exception as e:
            return {"error": str(e), "note": "Deposit USDC.e to start trading"}

    def get_balance_usdc(self) -> float:
        """Get Proxy Wallet USDC.e balance as float (convenience method)"""
        bal = self.get_balances()
        return bal.get("balance_usdc", 0.0)

    # ─────────────────────────────────────────────
    #  Data API (Historical)
    # ─────────────────────────────────────────────

    def _data_get(self, path: str, params: Optional[Dict] = None) -> Any:
        """Make GET request to Data API"""
        url = f"{DATA_API_BASE}{path}"
        resp = self.session.get(url, params=params, timeout=API_TIMEOUT_SECONDS)
        resp.raise_for_status()
        return resp.json()

    def get_price_history(
        self,
        token_id: str,
        interval: str = "1h",
        fidelity: int = 60,
    ) -> List[Dict]:
        """
        Get price history for a token.

        Args:
            token_id: CLOB token ID
            interval: Time interval
            fidelity: Data point granularity in minutes
        """
        params = {"market": token_id, "interval": interval, "fidelity": fidelity}
        try:
            return self._data_get("/prices-history", params)
        except Exception as e:
            logger.warning(f"Price history unavailable: {e}")
            return []

    def get_timeseries(
        self,
        token_id: str,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
    ) -> List[Dict]:
        """Get price timeseries data"""
        params = {"market": token_id}
        if start_ts:
            params["startTs"] = start_ts
        if end_ts:
            params["endTs"] = end_ts
        try:
            return self._data_get("/timeseries", params)
        except Exception as e:
            logger.warning(f"Timeseries unavailable: {e}")
            return []

    # ─────────────────────────────────────────────
    #  High-Level Utilities
    # ─────────────────────────────────────────────

    def get_market_summary(self, market_id: str) -> Dict:
        """
        Comprehensive market summary:
        metadata + current prices + order book depth + volume
        """
        market = self.get_market(market_id)

        # Extract token IDs from market data
        outcomes = []
        clob_token_ids = market.get("clobTokenIds", [])
        outcome_names = market.get("outcomes", "")

        # Parse outcomes (can be JSON string or list)
        if isinstance(outcome_names, str):
            try:
                import json
                outcome_names = json.loads(outcome_names)
            except (json.JSONDecodeError, TypeError):
                outcome_names = ["Yes", "No"]

        # Get prices for each outcome
        for i, token_id in enumerate(clob_token_ids):
            name = outcome_names[i] if i < len(outcome_names) else f"Outcome {i}"
            outcome_data = {"name": name, "token_id": token_id}

            try:
                if self.has_trading:
                    summary = self.get_order_book_summary(token_id)
                    outcome_data.update(summary)
                else:
                    # Use Gamma prices if no CLOB access
                    price_key = f"outcomePrices"
                    prices = market.get(price_key, "")
                    if isinstance(prices, str):
                        try:
                            import json
                            prices = json.loads(prices)
                        except Exception:
                            prices = []
                    if i < len(prices):
                        outcome_data["price"] = float(prices[i])
            except Exception as e:
                logger.warning(f"Failed to get price for {name}: {e}")

            outcomes.append(outcome_data)

        return {
            "id": market.get("id", market_id),
            "question": market.get("question", ""),
            "slug": market.get("slug", ""),
            "description": market.get("description", "")[:200],
            "end_date": market.get("endDate", ""),
            "active": market.get("active", False),
            "closed": market.get("closed", False),
            "volume": float(market.get("volume", 0) or 0),
            "volume_24h": float(market.get("volume24hr", 0) or 0),
            "liquidity": float(market.get("liquidity", 0) or 0),
            "tags": market.get("tags", []),
            "outcomes": outcomes,
        }

    def calculate_slippage(
        self, token_id: str, side: str, size: float
    ) -> Dict:
        """
        Calculate expected slippage for a given order size.

        Args:
            token_id: Token to analyze
            side: "BUY" or "SELL"
            size: Number of contracts

        Returns:
            Dict with avg_price, slippage_pct, levels_consumed
        """
        book = self.get_order_book(token_id)

        # py-clob-client returns OrderBookSummary object, not dict
        if hasattr(book, "asks"):
            all_asks = book.asks or []
            all_bids = book.bids or []
        else:
            all_asks = book.get("asks", [])
            all_bids = book.get("bids", [])

        if side.upper() == "BUY":
            levels = all_asks
        else:
            levels = all_bids

        if not levels:
            return {"avg_price": 0, "slippage_pct": 0, "levels_consumed": 0, "fillable": False}

        def _float(entry, key):
            return float(entry.price if key == "price" and hasattr(entry, "price") else
                         entry.size if key == "size" and hasattr(entry, "size") else
                         entry[key])

        best_price = _float(levels[0], "price")
        remaining = size
        total_cost = 0.0
        levels_consumed = 0

        for level in levels:
            level_price = _float(level, "price")
            level_size = _float(level, "size")
            fill = min(remaining, level_size)
            total_cost += fill * level_price
            remaining -= fill
            levels_consumed += 1
            if remaining <= 0:
                break

        filled = size - remaining
        if filled == 0:
            return {"avg_price": 0, "slippage_pct": 0, "levels_consumed": 0, "fillable": False}

        avg_price = total_cost / filled
        slippage = abs(avg_price - best_price) / best_price * 100 if best_price > 0 else 0

        return {
            "avg_price": round(avg_price, 4),
            "best_price": round(best_price, 4),
            "slippage_pct": round(slippage, 2),
            "levels_consumed": levels_consumed,
            "filled": round(filled, 2),
            "total_cost": round(total_cost, 2),
            "fillable": remaining <= 0,
        }


def create_client(
    private_key: str = "",
    api_key: str = "",
    api_secret: str = "",
    passphrase: str = "",
    proxy_wallet: str = "",
) -> PolymarketClient:
    """Factory: create client with optional credentials"""
    return PolymarketClient(
        private_key=private_key,
        api_key=api_key,
        api_secret=api_secret,
        passphrase=passphrase,
        proxy_wallet=proxy_wallet,
    )
