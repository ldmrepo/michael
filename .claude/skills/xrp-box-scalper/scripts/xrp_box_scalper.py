#!/usr/bin/env python3
"""
XRP Box-Range Scalping Bot (Binance Futures, Hedge Mode, Bidirectional)

Single-file bot that scalps XRP within a defined price box.
Supports simultaneous LONG and SHORT positions with independent state machines.
Uses urllib only (stdlib). Requires BINANCE_API_KEY and BINANCE_API_SECRET env vars.

Usage:
    python3 xrp_box_scalper.py
"""

import hashlib
import hmac
import json
import logging
import math
import os
import signal
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONFIG = {
    "SYMBOL": "XRPUSDT",
    "LEVERAGE": 12,

    # Box range
    "BOX_HIGH": 1.47,
    "BOX_LOW": 1.33,

    # LONG side
    "LONG_ENTRY": 1.36,
    "LONG_TP": 1.42,
    "LONG_SL": 1.33,

    # SHORT side
    "SHORT_ENTRY": 1.44,
    "SHORT_TP": 1.38,
    "SHORT_SL": 1.47,

    # Risk management
    "RISK_PER_TRADE_PCT": 2.0,
    "MAX_CONSECUTIVE_SL": 3,
    "COOLDOWN_3SL_SECS": 7200,      # 2hr
    "COOLDOWN_5SL_SECS": 43200,     # 12hr
    "DAILY_LOSS_LIMIT_PCT": 3.0,
    "BOX_BREAK_CANDLES": 2,
    "BOX_BREAK_MARGIN": 0.005,
    "MAX_FUNDING_RATE": 0.0003,     # 0.03%
    "MARGIN_PER_SIDE_PCT": 50.0,    # each side gets 50% of available margin

    # Polling
    "POLL_INTERVAL": 10,
    "KLINE_INTERVAL": 60,
    "ORDER_TIMEOUT": 900,           # 15min

    # Logging
    "LOG_FILE": "/tmp/xrp_scalper.log",
    "STATE_FILE": "/tmp/xrp_scalper_state.json",
}

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logger = logging.getLogger("xrp_scalper")
logger.setLevel(logging.DEBUG)

_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                         datefmt="%Y-%m-%d %H:%M:%S")

_sh = logging.StreamHandler(sys.stdout)
_sh.setLevel(logging.INFO)
_sh.setFormatter(_fmt)
logger.addHandler(_sh)

_fh = logging.FileHandler(CONFIG["LOG_FILE"])
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(_fmt)
logger.addHandler(_fh)

# ---------------------------------------------------------------------------
# BinanceClient
# ---------------------------------------------------------------------------

BASE_URL = "https://fapi.binance.com"


class BinanceClient:
    """Binance Futures REST client using urllib only."""

    def __init__(self) -> None:
        self.api_key = os.environ["BINANCE_API_KEY"]
        self.api_secret = os.environ["BINANCE_API_SECRET"]

    # -- helpers ----------------------------------------------------------

    def _sign(self, params: dict) -> dict:
        params["timestamp"] = str(int(time.time() * 1000))
        query = urllib.parse.urlencode(params)
        sig = hmac.new(
            self.api_secret.encode(), query.encode(), hashlib.sha256
        ).hexdigest()
        params["signature"] = sig
        return params

    def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        signed: bool = False,
        max_retries: int = 3,
    ) -> Any:
        params = dict(params) if params else {}
        if signed:
            params = self._sign(params)

        url = BASE_URL + path
        headers = {"X-MBX-APIKEY": self.api_key}
        body = None

        if method == "GET" or method == "DELETE":
            if params:
                url += "?" + urllib.parse.urlencode(params)
        else:
            body = urllib.parse.urlencode(params).encode()

        for attempt in range(1, max_retries + 1):
            try:
                req = urllib.request.Request(url, data=body, headers=headers, method=method)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode())
                    return data
            except urllib.error.HTTPError as exc:
                err_body = exc.read().decode() if exc.fp else ""
                # Rate limit
                if exc.code == 429:
                    wait = min(2 ** attempt * 5, 60)
                    logger.warning("Rate limited (429). Waiting %ds ...", wait)
                    time.sleep(wait)
                    continue
                # Recvwindow / timestamp
                if exc.code == 400 and "-1021" in err_body:
                    logger.warning("Timestamp issue, retrying ...")
                    time.sleep(1)
                    continue
                logger.error("HTTP %d %s: %s", exc.code, path, err_body)
                if attempt == max_retries:
                    raise
                time.sleep(2 ** attempt)
            except (urllib.error.URLError, OSError) as exc:
                logger.warning("Network error on %s: %s (attempt %d)", path, exc, attempt)
                if attempt == max_retries:
                    raise
                time.sleep(2 ** attempt)
        return None  # unreachable

    # -- public API -------------------------------------------------------

    def get_price(self, symbol: str) -> float:
        data = self._request("GET", "/fapi/v1/ticker/price", {"symbol": symbol})
        return float(data["price"])

    def get_klines(self, symbol: str, interval: str = "1m", limit: int = 100) -> list:
        """Return list of kline arrays. interval e.g. '1m','5m','1h'."""
        data = self._request("GET", "/fapi/v1/klines", {
            "symbol": symbol, "interval": interval, "limit": limit,
        })
        return data

    def get_long_position(self, symbol: str) -> dict | None:
        """Return LONG position dict if positionAmt > 0, else None."""
        data = self._request("GET", "/fapi/v2/positionRisk", {"symbol": symbol}, signed=True)
        for p in data:
            if p.get("positionSide") == "LONG" and float(p.get("positionAmt", 0)) > 0:
                return p
        return None

    def get_short_position(self, symbol: str) -> dict | None:
        """Return SHORT position dict if positionAmt < 0, else None."""
        data = self._request("GET", "/fapi/v2/positionRisk", {"symbol": symbol}, signed=True)
        for p in data:
            if float(p.get("positionAmt", 0)) < 0 and p.get("positionSide") == "SHORT":
                return p
        return None

    def get_balance(self) -> float:
        """Return available USDT balance."""
        data = self._request("GET", "/fapi/v2/balance", {}, signed=True)
        for b in data:
            if b["asset"] == "USDT":
                return float(b["availableBalance"])
        return 0.0

    def get_open_orders(self, symbol: str) -> list:
        return self._request("GET", "/fapi/v1/openOrders", {"symbol": symbol}, signed=True)

    def get_funding_rate(self, symbol: str) -> float:
        data = self._request("GET", "/fapi/v1/premiumIndex", {"symbol": symbol})
        return float(data.get("lastFundingRate", 0))

    def place_order(self, **params: Any) -> dict:
        return self._request("POST", "/fapi/v1/order", params, signed=True)

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        return self._request("DELETE", "/fapi/v1/order", {
            "symbol": symbol, "orderId": order_id,
        }, signed=True)

    def cancel_all_orders(self, symbol: str) -> dict:
        return self._request("DELETE", "/fapi/v1/allOpenOrders", {
            "symbol": symbol,
        }, signed=True)

    def set_leverage(self, symbol: str, leverage: int) -> dict | None:
        try:
            return self._request("POST", "/fapi/v1/leverage", {
                "symbol": symbol, "leverage": leverage,
            }, signed=True)
        except Exception as exc:
            logger.warning("set_leverage: %s (may already be set)", exc)
            return None


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------

class Indicators:
    """Technical indicator calculations."""

    @staticmethod
    def is_bullish_candle(candle: list) -> bool:
        """close > open."""
        return float(candle[4]) > float(candle[1])

    @staticmethod
    def is_bearish_candle(candle: list) -> bool:
        """close < open."""
        return float(candle[4]) < float(candle[1])

    @staticmethod
    def detect_box_breakout(hourly_candles: list, config: dict) -> str | None:
        """Check if last N 1H candles closed outside the box.
        Returns 'UP', 'DOWN', or None.
        """
        n = config["BOX_BREAK_CANDLES"]
        margin = config["BOX_BREAK_MARGIN"]
        high = config["BOX_HIGH"]
        low = config["BOX_LOW"]

        if len(hourly_candles) < n:
            return None

        recent = hourly_candles[-n:]

        # All closes above box high + margin
        if all(float(c[4]) > high * (1 + margin) for c in recent):
            return "UP"

        # All closes below box low - margin
        if all(float(c[4]) < low * (1 - margin) for c in recent):
            return "DOWN"

        return None


# ---------------------------------------------------------------------------
# RiskManager
# ---------------------------------------------------------------------------

class RiskManager:
    """Position sizing and risk checks."""

    @staticmethod
    def calculate_position_size(
        balance: float, entry: float, sl: float, leverage: int,
        margin_pct: float = 100.0,
    ) -> float:
        """Return quantity (XRP) sized so loss at SL = RISK_PER_TRADE_PCT of balance.
        margin_pct: percentage of available balance allocated to this side.
        """
        effective_balance = balance * (margin_pct / 100.0)
        risk_amount = effective_balance * (CONFIG["RISK_PER_TRADE_PCT"] / 100.0)
        price_risk = abs(entry - sl)
        if price_risk == 0:
            return 0.0
        # qty such that qty * price_risk = risk_amount
        qty = risk_amount / price_risk
        # Round down to 1 decimal (XRP lot step = 0.1)
        qty = math.floor(qty * 10) / 10
        # Sanity: notional = qty * entry must be <= effective_balance * leverage
        max_notional = effective_balance * leverage
        max_qty = math.floor((max_notional / entry) * 10) / 10
        qty = min(qty, max_qty)
        return qty

    @staticmethod
    def check_cooldown(trade_log: list) -> int:
        """Return cooldown seconds remaining, or 0."""
        if not trade_log:
            return 0

        # Count consecutive SL from most recent
        consecutive_sl = 0
        for t in reversed(trade_log):
            if t.get("result") == "SL":
                consecutive_sl += 1
            else:
                break

        now = time.time()

        if consecutive_sl >= 5:
            last_sl_time = trade_log[-1].get("time", 0)
            remaining = int((last_sl_time + CONFIG["COOLDOWN_5SL_SECS"]) - now)
            if remaining > 0:
                return remaining

        if consecutive_sl >= CONFIG["MAX_CONSECUTIVE_SL"]:
            last_sl_time = trade_log[-1].get("time", 0)
            remaining = int((last_sl_time + CONFIG["COOLDOWN_3SL_SECS"]) - now)
            if remaining > 0:
                return remaining

        return 0

    @staticmethod
    def check_daily_limit(start_balance: float, current_balance: float) -> bool:
        """Return True if daily loss limit exceeded (should stop)."""
        if start_balance <= 0:
            return False
        loss_pct = ((start_balance - current_balance) / start_balance) * 100
        return loss_pct >= CONFIG["DAILY_LOSS_LIMIT_PCT"]

    @staticmethod
    def check_funding_rate(client: BinanceClient, side: str) -> bool:
        """Return True if funding rate is acceptable for the given side.
        For LONG: high positive funding is bad (paying shorts).
        For SHORT: high negative funding is bad (paying longs).
        We use abs() to keep it simple — skip if funding is extreme either way.
        """
        try:
            rate = client.get_funding_rate(CONFIG["SYMBOL"])
            if abs(rate) > CONFIG["MAX_FUNDING_RATE"]:
                logger.warning("[%s] Funding rate %.5f exceeds max %.5f — skipping",
                               side, rate, CONFIG["MAX_FUNDING_RATE"])
                return False
            return True
        except Exception as exc:
            logger.warning("[%s] Could not fetch funding rate: %s — allowing trade", side, exc)
            return True


# ---------------------------------------------------------------------------
# SideState — independent state for each trading side
# ---------------------------------------------------------------------------

class SideStateEnum(Enum):
    IDLE = "IDLE"
    ENTRY_SIGNAL = "ENTRY_SIGNAL"
    IN_POSITION = "IN_POSITION"
    EXIT_EVAL = "EXIT_EVAL"
    COOLDOWN = "COOLDOWN"


@dataclass
class SideState:
    """Independent state for one trading side (LONG or SHORT)."""
    side: str  # "LONG" or "SHORT"
    state: SideStateEnum = SideStateEnum.IDLE
    entry_order_id: int | None = None
    entry_order_time: float = 0.0
    tp_order_id: int | None = None
    sl_order_id: int | None = None
    entry_qty: float = 0.0
    cooldown_until: float = 0.0
    trade_log: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "entry_order_id": self.entry_order_id,
            "entry_order_time": self.entry_order_time,
            "tp_order_id": self.tp_order_id,
            "sl_order_id": self.sl_order_id,
            "entry_qty": self.entry_qty,
            "cooldown_until": self.cooldown_until,
            "trade_log": self.trade_log,
        }

    @classmethod
    def from_dict(cls, side: str, data: dict) -> "SideState":
        return cls(
            side=side,
            state=SideStateEnum(data.get("state", "IDLE")),
            entry_order_id=data.get("entry_order_id"),
            entry_order_time=data.get("entry_order_time", 0.0),
            tp_order_id=data.get("tp_order_id"),
            sl_order_id=data.get("sl_order_id"),
            entry_qty=data.get("entry_qty", 0.0),
            cooldown_until=data.get("cooldown_until", 0.0),
            trade_log=data.get("trade_log", []),
        )

    def transition(self, new_state: SideStateEnum) -> None:
        old = self.state
        self.state = new_state
        logger.info("[%s] State: %s -> %s", self.side, old.value, new_state.value)

    def log_trade(self, result: dict) -> None:
        result["time"] = time.time()
        result["side"] = self.side
        self.trade_log.append(result)
        logger.info("[%s] Trade logged: %s", self.side, result)

    def reset_orders(self) -> None:
        self.entry_order_id = None
        self.tp_order_id = None
        self.sl_order_id = None
        self.entry_qty = 0.0


# ---------------------------------------------------------------------------
# StateManager
# ---------------------------------------------------------------------------

class StateManager:
    """Persists bot state for both sides and global state to JSON."""

    def __init__(self, state_file: str) -> None:
        self.state_file = state_file
        self.long = SideState(side="LONG")
        self.short = SideState(side="SHORT")
        self.daily_start_balance: float = 0.0
        self.daily_start_date: str = ""
        self.stopped: bool = False
        self._load()

    def _load(self) -> None:
        try:
            with open(self.state_file, "r") as f:
                data = json.load(f)

            # Handle migration from old single-side state format
            if "long" in data:
                self.long = SideState.from_dict("LONG", data["long"])
            if "short" in data:
                self.short = SideState.from_dict("SHORT", data["short"])
            self.daily_start_balance = data.get("daily_start_balance", 0.0)
            self.daily_start_date = data.get("daily_start_date", "")
            self.stopped = data.get("stopped", False)
            logger.info("Loaded state: LONG=%s SHORT=%s stopped=%s",
                        self.long.state.value, self.short.state.value, self.stopped)
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            logger.info("No saved state found — starting fresh")

    def save(self) -> None:
        data = {
            "long": self.long.to_dict(),
            "short": self.short.to_dict(),
            "daily_start_balance": self.daily_start_balance,
            "daily_start_date": self.daily_start_date,
            "stopped": self.stopped,
        }
        tmp = self.state_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.state_file)

    def reset_daily(self, balance: float) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self.daily_start_date != today:
            self.daily_start_balance = balance
            self.daily_start_date = today
            self.long.trade_log = []
            self.short.trade_log = []
            self.stopped = False
            self.save()
            logger.info("Daily reset: balance=%.2f date=%s", balance, today)


# ---------------------------------------------------------------------------
# Main bot loop
# ---------------------------------------------------------------------------

_shutdown = False


def _handle_signal(signum: int, _frame: Any) -> None:
    global _shutdown
    logger.info("Signal %d received — shutting down gracefully ...", signum)
    _shutdown = True


def _round_price(price: float, tick: float = 0.0001) -> float:
    """Round price to tick size."""
    return round(round(price / tick) * tick, 4)


def run() -> None:
    global _shutdown

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    logger.info("=" * 60)
    logger.info("XRP Box-Range Scalper starting (BIDIRECTIONAL)")
    logger.info("Symbol: %s  Leverage: %dx", CONFIG["SYMBOL"], CONFIG["LEVERAGE"])
    logger.info("Box: %.4f - %.4f", CONFIG["BOX_LOW"], CONFIG["BOX_HIGH"])
    logger.info("LONG  Entry: %.4f  TP: %.4f  SL: %.4f",
                CONFIG["LONG_ENTRY"], CONFIG["LONG_TP"], CONFIG["LONG_SL"])
    logger.info("SHORT Entry: %.4f  TP: %.4f  SL: %.4f",
                CONFIG["SHORT_ENTRY"], CONFIG["SHORT_TP"], CONFIG["SHORT_SL"])
    logger.info("=" * 60)

    client = BinanceClient()
    state = StateManager(CONFIG["STATE_FILE"])
    indicators = Indicators()
    risk = RiskManager()

    # Set leverage once
    client.set_leverage(CONFIG["SYMBOL"], CONFIG["LEVERAGE"])

    # Daily reset
    balance = client.get_balance()
    state.reset_daily(balance)
    logger.info("USDT balance: %.2f", balance)

    while not _shutdown:
        try:
            _tick(client, state, indicators, risk)
        except KeyboardInterrupt:
            break
        except Exception as exc:
            logger.exception("Unhandled error in tick: %s", exc)
            time.sleep(30)
            continue

        time.sleep(CONFIG["POLL_INTERVAL"])

    # Graceful shutdown
    logger.info("Shutting down. LONG=%s SHORT=%s stopped=%s",
                state.long.state.value, state.short.state.value, state.stopped)
    state.save()


def _tick(
    client: BinanceClient,
    state: StateManager,
    indicators: Indicators,
    risk: RiskManager,
) -> None:
    """One iteration of the main loop."""

    sym = CONFIG["SYMBOL"]

    # Daily reset check
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if state.daily_start_date != today:
        balance = client.get_balance()
        state.reset_daily(balance)

    # ---- STOPPED (global) ----
    if state.stopped:
        return  # do nothing, manual restart needed

    # ---- Global checks (apply to both sides) ----

    # Daily loss check (combined PnL)
    current_balance = client.get_balance()
    if risk.check_daily_limit(state.daily_start_balance, current_balance):
        logger.warning("Daily loss limit (%.1f%%) reached — STOPPED (both sides)",
                       CONFIG["DAILY_LOSS_LIMIT_PCT"])
        state.stopped = True
        state.save()
        return

    # Box breakout check (1H candles) — stops both sides
    try:
        hourly = client.get_klines(sym, "1h", limit=5)
        breakout = indicators.detect_box_breakout(hourly, CONFIG)
        if breakout:
            logger.warning("Box breakout detected: %s — STOPPED (both sides)", breakout)
            # Market close any open positions
            _market_close_side(client, state.long, "LONG")
            _market_close_side(client, state.short, "SHORT")
            state.stopped = True
            state.save()
            return
    except Exception as exc:
        logger.warning("Hourly kline fetch failed: %s", exc)

    # Fetch shared data once
    price = client.get_price(sym)
    klines_5m = None
    try:
        klines_5m = client.get_klines(sym, "5m", limit=20)
    except Exception as exc:
        logger.warning("5m kline fetch failed: %s", exc)

    # Process each side independently
    _process_side(client, state, state.long, indicators, risk, price, klines_5m)
    _process_side(client, state, state.short, indicators, risk, price, klines_5m)

    # Save state after processing both sides
    state.save()


# ---------------------------------------------------------------------------
# Per-side processing
# ---------------------------------------------------------------------------

def _process_side(
    client: BinanceClient,
    state_mgr: StateManager,
    side: SideState,
    indicators: Indicators,
    risk: RiskManager,
    price: float,
    klines_5m: list | None,
) -> None:
    """Process one trading side (LONG or SHORT)."""

    if side.state == SideStateEnum.COOLDOWN:
        _handle_cooldown(side)
        return

    if side.state == SideStateEnum.EXIT_EVAL:
        _handle_exit_eval(client, state_mgr, side, risk)
        return

    if side.state == SideStateEnum.IN_POSITION:
        _handle_in_position(client, state_mgr, side, risk, price)
        return

    if side.state == SideStateEnum.ENTRY_SIGNAL:
        _handle_entry_signal(client, side)
        return

    if side.state == SideStateEnum.IDLE:
        _handle_idle(client, state_mgr, side, indicators, risk, price, klines_5m)
        return


# -- State handlers -------------------------------------------------------

def _handle_cooldown(side: SideState) -> None:
    if time.time() >= side.cooldown_until:
        logger.info("[%s] Cooldown expired — resuming", side.side)
        side.transition(SideStateEnum.IDLE)
    else:
        remaining = int(side.cooldown_until - time.time())
        if remaining % 60 == 0:  # log every ~minute
            logger.info("[%s] Cooldown: %ds remaining", side.side, remaining)


def _handle_idle(
    client: BinanceClient,
    state_mgr: StateManager,
    side: SideState,
    indicators: Indicators,
    risk: RiskManager,
    price: float,
    klines_5m: list | None,
) -> None:
    sym = CONFIG["SYMBOL"]

    # 1. Check if already in a position (recovery after restart)
    pos = _get_position_for_side(client, sym, side.side)
    if pos:
        amt = abs(float(pos.get("positionAmt", 0)))
        if amt > 0:
            side.entry_qty = amt
            logger.info("[%s] Existing position found: %.1f XRP — resuming IN_POSITION",
                        side.side, side.entry_qty)
            side.transition(SideStateEnum.IN_POSITION)
            return

    # 2. Per-side cooldown check
    cooldown = risk.check_cooldown(side.trade_log)
    if cooldown > 0:
        side.cooldown_until = time.time() + cooldown
        logger.info("[%s] Cooldown triggered: %ds", side.side, cooldown)
        side.transition(SideStateEnum.COOLDOWN)
        return

    # 3. Box range check — only trade when price is within the box
    if not (CONFIG["BOX_LOW"] <= price <= CONFIG["BOX_HIGH"]):
        logger.debug("[%s] Price %.4f outside box [%.4f-%.4f] — skipping",
                     side.side, price, CONFIG["BOX_LOW"], CONFIG["BOX_HIGH"])
        return

    # 4. Price check
    if side.side == "LONG":
        entry_price = CONFIG["LONG_ENTRY"]
        if price > entry_price:
            logger.debug("[LONG] Price %.4f > entry %.4f — waiting", price, entry_price)
            return
    else:  # SHORT
        entry_price = CONFIG["SHORT_ENTRY"]
        if price < entry_price:
            logger.debug("[SHORT] Price %.4f < entry %.4f — waiting", price, entry_price)
            return

    # 5. Candle confirmation (latest closed 5m candle)
    if klines_5m and len(klines_5m) >= 2:
        last_closed = klines_5m[-2]  # -1 is current (incomplete)
        if side.side == "LONG":
            if not indicators.is_bullish_candle(last_closed):
                logger.debug("[LONG] Last closed 5m candle not bullish — waiting")
                return
        else:  # SHORT
            if not indicators.is_bearish_candle(last_closed):
                logger.debug("[SHORT] Last closed 5m candle not bearish — waiting")
                return

    # 6. Funding rate check
    if not risk.check_funding_rate(client, side.side):
        return

    # 7. All conditions met — place entry order
    balance = client.get_balance()
    sl_price = CONFIG[f"{side.side}_SL"]
    qty = risk.calculate_position_size(
        balance, entry_price, sl_price, CONFIG["LEVERAGE"],
        margin_pct=CONFIG["MARGIN_PER_SIDE_PCT"],
    )
    if qty <= 0:
        logger.warning("[%s] Position size is 0 — insufficient balance?", side.side)
        return

    logger.info("[%s] Entry signal! Price=%.4f Qty=%.1f", side.side, price, qty)

    try:
        if side.side == "LONG":
            order = client.place_order(
                symbol=sym,
                side="BUY",
                positionSide="LONG",
                type="LIMIT",
                timeInForce="GTC",
                quantity=str(qty),
                price=str(_round_price(entry_price)),
            )
        else:  # SHORT
            order = client.place_order(
                symbol=sym,
                side="SELL",
                positionSide="SHORT",
                type="LIMIT",
                timeInForce="GTC",
                quantity=str(qty),
                price=str(_round_price(entry_price)),
            )
        side.entry_order_id = int(order["orderId"])
        side.entry_order_time = time.time()
        side.entry_qty = qty
        side.transition(SideStateEnum.ENTRY_SIGNAL)
        logger.info("[%s] Entry LIMIT order placed: id=%d qty=%.1f @ %.4f",
                     side.side, side.entry_order_id, qty, entry_price)
    except Exception as exc:
        logger.error("[%s] Failed to place entry order: %s", side.side, exc)


def _handle_entry_signal(client: BinanceClient, side: SideState) -> None:
    sym = CONFIG["SYMBOL"]

    # Check if order filled
    pos = _get_position_for_side(client, sym, side.side)
    if pos:
        amt = abs(float(pos.get("positionAmt", 0)))
        if amt > 0:
            side.entry_qty = amt
            logger.info("[%s] Entry order FILLED: %.1f XRP", side.side, side.entry_qty)
            _place_tp_sl(client, side)
            side.transition(SideStateEnum.IN_POSITION)
            return

    # Check timeout
    elapsed = time.time() - side.entry_order_time
    if elapsed > CONFIG["ORDER_TIMEOUT"]:
        logger.info("[%s] Entry order timed out after %ds — cancelling", side.side, int(elapsed))
        try:
            if side.entry_order_id:
                client.cancel_order(sym, side.entry_order_id)
        except Exception as exc:
            logger.warning("[%s] Cancel failed (may already be done): %s", side.side, exc)
        side.entry_order_id = None
        side.transition(SideStateEnum.IDLE)
        return

    logger.debug("[%s] Entry order pending ... (%.0fs elapsed)", side.side, elapsed)


def _place_tp_sl(client: BinanceClient, side: SideState) -> None:
    """Place server-side TP and SL orders for the given side."""
    sym = CONFIG["SYMBOL"]
    qty = side.entry_qty

    if side.side == "LONG":
        tp_price = CONFIG["LONG_TP"]
        sl_price = CONFIG["LONG_SL"]
        close_side = "SELL"
        position_side = "LONG"
        # TP limit slightly below stop for LONG (to ensure fill)
        tp_limit = _round_price(tp_price * 0.999)
    else:  # SHORT
        tp_price = CONFIG["SHORT_TP"]
        sl_price = CONFIG["SHORT_SL"]
        close_side = "BUY"
        position_side = "SHORT"
        # TP limit slightly above stop for SHORT (to ensure fill)
        tp_limit = _round_price(tp_price * 1.001)

    # TP: TAKE_PROFIT (limit), NOT TAKE_PROFIT_MARKET
    try:
        tp_order = client.place_order(
            symbol=sym,
            side=close_side,
            positionSide=position_side,
            type="TAKE_PROFIT",
            stopPrice=str(_round_price(tp_price)),
            price=str(tp_limit),
            quantity=str(qty),
            timeInForce="GTE_GTC",
        )
        side.tp_order_id = int(tp_order["orderId"])
        logger.info("[%s] TP order placed: id=%d @ %.4f", side.side, side.tp_order_id, tp_price)
    except Exception as exc:
        logger.error("[%s] Failed to place TP order: %s", side.side, exc)
        side.tp_order_id = None

    # SL: STOP_MARKET
    try:
        sl_order = client.place_order(
            symbol=sym,
            side=close_side,
            positionSide=position_side,
            type="STOP_MARKET",
            stopPrice=str(_round_price(sl_price)),
            quantity=str(qty),
            closePosition="false",
            workingType="MARK_PRICE",
        )
        side.sl_order_id = int(sl_order["orderId"])
        logger.info("[%s] SL order placed: id=%d @ %.4f", side.side, side.sl_order_id, sl_price)
    except Exception as exc:
        logger.error("[%s] Failed to place SL order: %s", side.side, exc)
        side.sl_order_id = None


def _handle_in_position(
    client: BinanceClient,
    state_mgr: StateManager,
    side: SideState,
    risk: RiskManager,
    price: float,
) -> None:
    sym = CONFIG["SYMBOL"]

    pos = _get_position_for_side(client, sym, side.side)
    if not pos or abs(float(pos.get("positionAmt", 0))) == 0:
        # Position closed — figure out how
        logger.info("[%s] Position closed — evaluating exit", side.side)
        side.transition(SideStateEnum.EXIT_EVAL)
        return

    # Check if TP/SL orders are still active
    open_orders = client.get_open_orders(sym)
    open_ids = {int(o["orderId"]) for o in open_orders}

    tp_active = side.tp_order_id in open_ids if side.tp_order_id else False
    sl_active = side.sl_order_id in open_ids if side.sl_order_id else False

    # If TP gone but SL still there => TP filled
    if not tp_active and sl_active:
        logger.info("[%s] TP order appears filled — position should close soon", side.side)

    # If SL gone but TP still there => SL filled
    if not sl_active and tp_active:
        logger.info("[%s] SL order appears filled — position should close soon", side.side)

    unrealized_pnl = float(pos.get("unRealizedProfit", 0))
    logger.debug("[%s] Position: %.1f XRP @ %.4f  PnL: %.2f  Price: %.4f",
                 side.side, abs(float(pos["positionAmt"])), float(pos["entryPrice"]),
                 unrealized_pnl, price)


def _market_close_side(client: BinanceClient, side: SideState, side_name: str) -> None:
    """Emergency market close for one side."""
    sym = CONFIG["SYMBOL"]
    if side.entry_qty <= 0:
        return

    pos = _get_position_for_side(client, sym, side_name)
    if not pos or abs(float(pos.get("positionAmt", 0))) == 0:
        return

    # Cancel orders for this side (we cancel all — both sides' orders)
    # This is safe because box breakout stops everything
    try:
        client.cancel_all_orders(sym)
    except Exception:
        pass

    close_side = "SELL" if side_name == "LONG" else "BUY"
    try:
        client.place_order(
            symbol=sym,
            side=close_side,
            positionSide=side_name,
            type="MARKET",
            quantity=str(side.entry_qty),
        )
        logger.info("[%s] Market close executed: %.1f XRP", side_name, side.entry_qty)
    except Exception as exc:
        logger.error("[%s] Market close FAILED: %s", side_name, exc)
    side.transition(SideStateEnum.EXIT_EVAL)


def _handle_exit_eval(
    client: BinanceClient,
    state_mgr: StateManager,
    side: SideState,
    risk: RiskManager,
) -> None:
    """Evaluate the closed trade and decide next action."""
    sym = CONFIG["SYMBOL"]

    # Cancel any remaining orders for this side
    # Note: cancel_all_orders cancels ALL orders for the symbol.
    # This is acceptable since exit_eval should clean up.
    try:
        # Only cancel specific orders if we have their IDs
        if side.tp_order_id:
            try:
                client.cancel_order(sym, side.tp_order_id)
            except Exception:
                pass
        if side.sl_order_id:
            try:
                client.cancel_order(sym, side.sl_order_id)
            except Exception:
                pass
    except Exception:
        pass

    # Determine result from current price vs entry
    current_price = client.get_price(sym)
    entry = CONFIG[f"{side.side}_ENTRY"]
    tp = CONFIG[f"{side.side}_TP"]
    sl = CONFIG[f"{side.side}_SL"]

    # Heuristic: if price near TP => TP hit, near SL => SL hit
    dist_tp = abs(current_price - tp)
    dist_sl = abs(current_price - sl)

    if dist_tp < dist_sl:
        result = "TP"
        exit_price = tp
    else:
        result = "SL"
        exit_price = sl

    # Calculate PnL based on side direction
    if side.side == "LONG":
        pnl = (exit_price - entry) * side.entry_qty
    else:  # SHORT
        pnl = (entry - exit_price) * side.entry_qty

    side.log_trade({
        "entry": entry,
        "exit": exit_price,
        "qty": side.entry_qty,
        "pnl": round(pnl, 2),
        "result": result,
    })

    logger.info("[%s] Trade result: %s  PnL: $%.2f  (entry=%.4f exit=%.4f qty=%.1f)",
                side.side, result, pnl, entry, exit_price, side.entry_qty)

    # Reset order tracking
    side.reset_orders()

    # Check if we need per-side cooldown
    cooldown = risk.check_cooldown(side.trade_log)
    if cooldown > 0:
        side.cooldown_until = time.time() + cooldown
        logger.info("[%s] Entering cooldown for %ds after consecutive SLs", side.side, cooldown)
        side.transition(SideStateEnum.COOLDOWN)
        return

    side.transition(SideStateEnum.IDLE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_position_for_side(client: BinanceClient, symbol: str, side: str) -> dict | None:
    """Get position for a specific side."""
    if side == "LONG":
        return client.get_long_position(symbol)
    else:
        return client.get_short_position(symbol)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Validate env vars early
    for var in ("BINANCE_API_KEY", "BINANCE_API_SECRET"):
        if var not in os.environ:
            print(f"ERROR: {var} environment variable not set", file=sys.stderr)
            sys.exit(1)

    run()
