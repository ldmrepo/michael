"""WebSocket feed — BTCUSDT 1d candle real-time collection + SQLite storage."""

from __future__ import annotations

import json
import threading
import time

import structlog
import websocket

from . import executor, state

log = structlog.get_logger(__name__)

SYMBOL = "BTCUSDT"
INTERVAL = "1d"
WS_URL = f"wss://fstream.binance.com/ws/{SYMBOL.lower()}@kline_{INTERVAL}"


def backfill(limit: int = 250) -> None:
    """Fetch historical candles via REST and store in SQLite."""
    import time as _time
    klines = executor.fetch_klines(SYMBOL, INTERVAL, limit)
    now_ms = int(_time.time() * 1000)
    for k in klines:
        close_time = int(k[6])  # kline close time in ms
        is_closed = close_time < now_ms  # only mark closed if close_time is in the past
        state.upsert_candle(
            SYMBOL, INTERVAL,
            open_time=int(k[0]),
            o=float(k[1]), h=float(k[2]), l=float(k[3]), c_=float(k[4]),
            vol=float(k[5]),
            closed=is_closed,
        )
    log.info("backfill_complete", symbol=SYMBOL, candles=len(klines))


def get_daily_closes(limit: int = 100) -> list[float]:
    """Get CLOSED daily close prices from SQLite (excludes in-progress candle)."""
    candles = state.get_candles(SYMBOL, INTERVAL, limit, closed_only=True)
    return [c["close"] for c in candles]


def get_daily_highs(limit: int = 100) -> list[float]:
    """Get CLOSED daily high prices (excludes in-progress candle)."""
    candles = state.get_candles(SYMBOL, INTERVAL, limit, closed_only=True)
    return [c["high"] for c in candles]


def get_daily_lows(limit: int = 100) -> list[float]:
    """Get CLOSED daily low prices (excludes in-progress candle)."""
    candles = state.get_candles(SYMBOL, INTERVAL, limit, closed_only=True)
    return [c["low"] for c in candles]


def get_last_candle_time() -> int:
    """Get open_time of the most recent closed candle."""
    candles = state.get_candles(SYMBOL, INTERVAL, 1, closed_only=True)
    return candles[-1]["open_time"] if candles else 0


def _on_message(ws: websocket.WebSocketApp, message: str) -> None:
    try:
        data = json.loads(message)
    except Exception:
        return
    k = data.get("k", {})
    if not k:
        return
    is_closed = k.get("x", False)
    state.upsert_candle(
        SYMBOL, INTERVAL,
        open_time=int(k["t"]),
        o=float(k["o"]), h=float(k["h"]), l=float(k["l"]), c_=float(k["c"]),
        vol=float(k["v"]),
        closed=is_closed,
    )
    if is_closed:
        log.info("candle_closed", symbol=SYMBOL, close=k["c"])


def _on_error(ws: websocket.WebSocketApp, error: Exception) -> None:
    log.error("ws_error", error=str(error))


def _on_close(ws: websocket.WebSocketApp, code: int | None, msg: str | None) -> None:
    log.warning("ws_closed", code=code, msg=msg)


def run(shutdown_event: threading.Event) -> None:
    """Run WebSocket feed with auto-reconnect. Blocks until shutdown."""
    backfill()
    while not shutdown_event.is_set():
        try:
            ws = websocket.WebSocketApp(
                WS_URL,
                on_message=_on_message,
                on_error=_on_error,
                on_close=_on_close,
            )
            ws_thread = threading.Thread(target=ws.run_forever, kwargs={"ping_interval": 30}, daemon=True)
            ws_thread.start()
            log.info("ws_connected", url=WS_URL)
            while not shutdown_event.is_set() and ws_thread.is_alive():
                shutdown_event.wait(5)
            ws.close()
        except Exception as e:
            log.error("ws_reconnect", error=str(e))
            shutdown_event.wait(5)
