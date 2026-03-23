"""BTC Trend Follower — EMA crossover + RSI momentum strategy.

Consensus parameters (3-team verified: Alpha/Beta/Gamma):
Entry LONG:  EMA(10) > EMA(26) + RSI(21) > 45
Entry SHORT: EMA(10) < EMA(26) + RSI(21) < 55
Exit: SL -70% leveraged PnL OR (TP 20%+ then EMA(7) vs EMA(14) cross 2 consecutive days)
BB regime switch: When BB width > 1.8x avg → SL tightens to -40%
Leverage: 2x, Allocation: 100% of wallet
"""

from __future__ import annotations

import time
import threading
import json
from datetime import datetime, timezone
from pathlib import Path

import structlog

from . import executor, feeds, state, notify
from .indicators import compute_ema, compute_rsi, bb_width_ratio

log = structlog.get_logger(__name__)

SYMBOL = "BTCUSDT"
LEVERAGE = 2
ALLOCATION = 1.0  # 100% of wallet (BB regime switch protects capital)
COOLDOWN_SECONDS = 86400  # 24h between signals
SL_NORMAL = -70.0   # default SL
SL_TIGHT = -40.0    # SL when BB width regime shift detected
BB_THRESHOLD = 1.8  # BB width / avg > this → tighten SL


DATA_DIR = Path("data")


def _log_trade(event_type: str, side: str, price: float, qty: float, reason: str, pnl: float = 0.0) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "symbol": SYMBOL,
        "side": side,
        "price": price,
        "qty": qty,
        "reason": reason,
        "pnl": pnl,
    }
    path = DATA_DIR / f"trades-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")


class BTCTrendWorker:
    def __init__(self) -> None:
        self._last_signal_time: float = 0.0
        self._exit_cross_days: int = 0
        self._tp_activated: bool = False  # latch: once True, stays True until exit
        self._last_candle_time: int = 0   # open_time of last processed candle
        self._dry_run: bool = True
        # Restore TP latch from SQLite (survives process restart)
        if state.get_config("tp_activated") == "true":
            self._tp_activated = True
            log.info("tp_latch_restored")

    def _reset_tp_state(self) -> None:
        """Reset all TP-related state. Call on any position exit."""
        self._exit_cross_days = 0
        self._tp_activated = False
        self._last_candle_time = 0
        state.set_config("tp_activated", "false")

    def detect(self) -> dict | None:
        closes = feeds.get_daily_closes(250)
        pos = state.get_open_position()

        # If data insufficient but position is open, fall through to SL check via mark price
        if len(closes) < 30:
            if pos:
                log.warning("insufficient_candles_with_position", candles=len(closes))
                # Direct mark-price SL check without indicators
                try:
                    ep = executor.get_position(SYMBOL, position_side=pos["side"])
                    if ep:
                        mark = float(ep["markPrice"])
                        entry = pos["entry_price"]
                        pnl = ((mark / entry - 1) if pos["side"] == "LONG" else (entry / mark - 1)) * 100 * LEVERAGE
                        if pnl <= -70.0:
                            self._reset_tp_state()
                            return {"action": "close", "pos_id": pos["id"], "price": mark, "pnl_pct": pnl, "side": pos["side"],
                                    "reason": f"SL hit {pnl:+.1f}% (emergency, {len(closes)} candles)"}
                except Exception as e:
                    log.error("emergency_sl_check_failed", error=str(e))
                    notify.send(f"EMERGENCY SL CHECK FAILED: {e}")
            return None

        # Staleness check: warn if latest candle open_time is >72h old (~48h after close)
        last_time = feeds.get_last_candle_time()
        if last_time > 0:
            import time as _time
            age_hours = (_time.time() * 1000 - last_time) / 3600000
            if age_hours > 72:  # open_time based, so 72h ≈ 48h after candle close
                log.warning("stale_data", age_hours=f"{age_hours:.0f}", last_candle_time=last_time)
                if not hasattr(self, '_last_stale_alert') or _time.time() - self._last_stale_alert > 3600:
                    notify.send(f"STALE DATA: last candle {age_hours:.0f}h old")
                    self._last_stale_alert = _time.time()
                if not pos:
                    return None  # block new entries on stale data
                # Position open + stale: SL only via mark price, skip TP/entry
                try:
                    ep = executor.get_position(SYMBOL, position_side=pos["side"])
                    if ep:
                        mark = float(ep["markPrice"])
                        entry = pos["entry_price"]
                        pnl = ((mark / entry - 1) if pos["side"] == "LONG" else (entry / mark - 1)) * 100 * LEVERAGE
                        if pnl <= -70.0:
                            self._reset_tp_state()
                            return {"action": "close", "pos_id": pos["id"], "price": mark, "pnl_pct": pnl, "side": pos["side"],
                                    "reason": f"SL hit {pnl:+.1f}% (stale data)"}
                except Exception as e:
                    log.error("stale_sl_check_failed", error=str(e))
                    notify.send(f"STALE SL CHECK FAILED: {e}")
                return None  # stale: SL only, no TP/entry

        ema7 = compute_ema(closes, 7)
        ema10 = compute_ema(closes, 10)
        ema14 = compute_ema(closes, 14)
        ema26 = compute_ema(closes, 26)
        rsi21 = compute_rsi(closes, 21)
        bb_ratio = bb_width_ratio(closes, 20)

        i = len(closes) - 1
        price = closes[i]

        if any(v is None for v in [ema7[i], ema10[i], ema14[i], ema26[i], rsi21[i]]):
            return None

        # Dynamic SL: tighten when BB width signals volatility regime shift
        sl_level = SL_NORMAL
        if bb_ratio[i] is not None and bb_ratio[i] > BB_THRESHOLD:
            sl_level = SL_TIGHT
            log.info("bb_regime_shift", bb_ratio=f"{bb_ratio[i]:.2f}", sl=sl_level)

        # If no position but TP state is dirty, reset (handles /close, orphan, etc.)
        if not pos and (self._tp_activated or self._exit_cross_days > 0):
            self._reset_tp_state()

        # ── Exit check ──
        if pos:
            entry = pos["entry_price"]
            side = pos["side"]
            pnl_pct = ((price / entry - 1) if side == "LONG" else (entry / price - 1)) * 100 * LEVERAGE

            # SL check: use exchange mark price for real-time accuracy
            try:
                exchange_pos = executor.get_position(SYMBOL, position_side=side)
                if exchange_pos:
                    mark = float(exchange_pos["markPrice"])
                    if mark > 0:
                        mark_pnl = ((mark / entry - 1) if side == "LONG" else (entry / mark - 1)) * 100 * LEVERAGE
                        pnl_pct = mark_pnl  # use real-time mark price
            except Exception as e:
                log.warning("mark_price_fallback", error=str(e), using="candle_close")
                notify.send(f"SL CHECK: mark price unavailable, using candle close ${price:,.0f}")

            if pnl_pct <= sl_level:
                self._reset_tp_state()
                reason_tag = f"SL hit {pnl_pct:+.1f}%"
                if sl_level == SL_TIGHT:
                    reason_tag += f" (BB regime, tightened to {sl_level:.0f}%)"
                return {"action": "close", "pos_id": pos["id"], "price": price, "pnl_pct": pnl_pct, "side": side,
                        "reason": reason_tag}

            # TP activation: latch using CLOSE price (matches backtest)
            close_pnl = ((price / entry - 1) if side == "LONG" else (entry / price - 1)) * 100 * LEVERAGE
            if close_pnl >= 20.0 and not self._tp_activated:
                self._tp_activated = True
                state.set_config("tp_activated", "true")

            # TP exit: EMA(7) vs EMA(14) cross 2 consecutive days (only when activated)
            # Use candle open_time to detect new daily candle (not len which caps at 250)
            if self._tp_activated:
                last_time = feeds.get_last_candle_time()
                if last_time != self._last_candle_time:
                    self._last_candle_time = last_time
                    if side == "LONG" and ema7[i] < ema14[i]:
                        self._exit_cross_days += 1
                    elif side == "SHORT" and ema7[i] > ema14[i]:
                        self._exit_cross_days += 1
                    else:
                        self._exit_cross_days = 0

                if self._exit_cross_days >= 2:
                    self._reset_tp_state()
                    return {"action": "close", "pos_id": pos["id"], "price": price, "pnl_pct": pnl_pct, "side": side,
                            "reason": f"TP EMA cross {pnl_pct:+.1f}%"}
            return None  # Hold position

        # ── Cooldown ──
        if time.monotonic() - self._last_signal_time < COOLDOWN_SECONDS:
            return None

        wallet = executor.get_available_balance()

        # ── Entry check ──
        if state.get_config("killed") == "true":
            return None

        # Block entry if exchange already has any position (fail-close: API error = block)
        try:
            exchange_pos = executor.get_position(SYMBOL)
            if exchange_pos and float(exchange_pos.get("positionAmt", 0)) != 0:
                log.warning("entry_blocked_untracked", symbol=SYMBOL, amt=exchange_pos["positionAmt"])
                return None
        except Exception as e:
            log.warning("entry_blocked_api_fail", error=str(e))
            return None

        # Use mark price for qty calculation (avoids margin insufficient on price gap)
        try:
            order_price = executor.get_mark_price(SYMBOL)
        except Exception:
            order_price = price
        if order_price <= 0:
            order_price = price

        # LONG: EMA(10) > EMA(26) + RSI(21) > 45
        if ema10[i] > ema26[i] and rsi21[i] > 45:
            qty = int(wallet * ALLOCATION * LEVERAGE * 0.95 / order_price * 1000) / 1000
            self._last_signal_time = time.monotonic()
            return {"action": "open", "side": "LONG", "price": price, "qty": qty,
                    "reason": f"LONG: EMA10>{ema26[i]:.0f}(26), RSI={rsi21[i]:.0f}>45"}

        # SHORT: EMA(10) < EMA(26) + RSI(21) < 55
        if ema10[i] < ema26[i] and rsi21[i] < 55:
            qty = int(wallet * ALLOCATION * LEVERAGE * 0.95 / order_price * 1000) / 1000
            self._last_signal_time = time.monotonic()
            return {"action": "open", "side": "SHORT", "price": price, "qty": qty,
                    "reason": f"SHORT: EMA10<{ema26[i]:.0f}(26), RSI={rsi21[i]:.0f}<55"}

        return None

    def execute(self, signal: dict) -> None:
        if signal["action"] == "close":
            pos = state.get_open_position()
            if not pos:
                return
            close_side = "SELL" if signal["side"] == "LONG" else "BUY"
            pos_side = signal["side"]

            # Get mark price before closing for accurate logging
            # Get actual exchange position for accurate qty and price
            exit_price = signal["price"]
            close_qty = pos["qty"]
            try:
                ep = executor.get_position(SYMBOL, position_side=signal["side"])
                if ep:
                    exit_price = float(ep["markPrice"])
                    exchange_qty = abs(float(ep.get("positionAmt", 0)))
                    if exchange_qty > 0:
                        close_qty = exchange_qty  # use exchange actual qty
            except Exception as e:
                log.warning("close_position_query_failed", error=str(e), using="db_qty")

            if not self._dry_run:
                try:
                    executor.place_market_order(SYMBOL, close_side, pos_side, close_qty)
                except Exception as e:
                    log.error("close_failed", error=str(e))
                    return
            # Recalculate PnL with actual exit price
            actual_pnl = ((exit_price / pos["entry_price"] - 1) if signal["side"] == "LONG" else (pos["entry_price"] / exit_price - 1)) * 100 * LEVERAGE
            state.close_position(pos["id"], exit_price, actual_pnl)
            reason = signal.get("reason", f"exit {actual_pnl:+.1f}%")
            _log_trade("exit", signal["side"], exit_price, close_qty, reason, actual_pnl)
            notify.send(f"CLOSED {SYMBOL} {signal['side']} {close_qty} @ ${exit_price:,.2f} PnL {actual_pnl:+.1f}%")
            log.info("position_closed", side=signal["side"], qty=close_qty, pnl=actual_pnl, exit_price=exit_price)

        elif signal["action"] == "open":
            open_side = "BUY" if signal["side"] == "LONG" else "SELL"

            if not self._dry_run:
                try:
                    executor.place_market_order(SYMBOL, open_side, signal["side"], signal["qty"])
                except Exception as e:
                    log.error("open_failed", error=str(e))
                    return
            # Use exchange mark price as entry for accurate PnL tracking
            entry_price = signal["price"]
            try:
                ep = executor.get_position(SYMBOL, position_side=signal["side"])
                if ep:
                    actual_entry = float(ep["entryPrice"])
                    if actual_entry > 0:
                        entry_price = actual_entry
            except Exception as e:
                log.warning("entry_price_query_failed", error=str(e), using="signal_price")
            state.save_position(SYMBOL, signal["side"], entry_price, signal["qty"], LEVERAGE)
            _log_trade("entry", signal["side"], entry_price, signal["qty"], signal["reason"])
            notify.send(f"OPENED {SYMBOL} {signal['side']} {LEVERAGE}x @ ${entry_price:,.2f} qty={signal['qty']}")
            log.info("position_opened", side=signal["side"], price=entry_price, qty=signal["qty"])


def run_loop(shutdown: threading.Event, interval: float = 3600.0, dry_run: bool = True) -> None:
    worker = BTCTrendWorker()
    worker._dry_run = dry_run
    log.info("strategy_loop_started", interval=interval, dry_run=dry_run)

    while not shutdown.is_set():
        try:
            signal = worker.detect()
            if signal:
                log.info("signal_detected", signal=signal)
                worker.execute(signal)
        except Exception as e:
            log.error("detect_error", error=str(e))
        shutdown.wait(interval)
