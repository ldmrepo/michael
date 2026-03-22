"""Position monitor — orphan detection and exchange sync."""

from __future__ import annotations

import threading

import structlog

from . import executor, state, notify

log = structlog.get_logger(__name__)

SYMBOL = "BTCUSDT"


def run(shutdown: threading.Event) -> None:
    """30s polling loop: check exchange position vs state.db."""
    log.info("monitor_started")
    import time as _time
    _last_alert: dict[str, float] = {}  # key -> last alert timestamp
    ALERT_COOLDOWN = 600  # 10 min between same alerts

    def _should_alert(key: str) -> bool:
        now = _time.time()
        if now - _last_alert.get(key, 0) > ALERT_COOLDOWN:
            _last_alert[key] = now
            return True
        return False

    while not shutdown.is_set():
        try:
            pos = state.get_open_position()

            # Check tracked side
            if pos:
                exchange_pos = executor.get_position(SYMBOL, position_side=pos["side"])
                if not exchange_pos:
                    entry = pos["entry_price"]
                    side = pos["side"]
                    exit_price = entry
                    pnl_pct = 0.0
                    try:
                        from . import feeds
                        closes = feeds.get_daily_closes(1)
                        if closes:
                            exit_price = closes[-1]
                            pnl_pct = ((exit_price / entry - 1) if side == "LONG" else (entry / exit_price - 1)) * 100 * pos["leverage"]
                    except Exception:
                        pass
                    log.warning("orphan_detected", pos_id=pos["id"], symbol=pos["symbol"], exit_price=exit_price, pnl=pnl_pct)
                    notify.send(f"ORPHAN: {SYMBOL} {side} closed on exchange. PnL ~{pnl_pct:+.1f}%")
                    state.close_position(pos["id"], exit_price, pnl_pct)
                else:
                    # Same side exists — detect DB qty vs exchange qty drift (>1%)
                    db_qty = float(pos.get("qty", 0))
                    exchange_qty = abs(float(exchange_pos.get("positionAmt", 0)))
                    if db_qty > 0:
                        drift_ratio = abs(exchange_qty - db_qty) / db_qty
                        if drift_ratio > 0.01:
                            drift_pct = drift_ratio * 100
                            log.warning(
                                "qty_drift",
                                symbol=SYMBOL,
                                side=pos["side"],
                                db_qty=db_qty,
                                exchange_qty=exchange_qty,
                                drift_pct=drift_pct,
                            )
                            if _should_alert("qty_drift"):
                                notify.send(
                                    f"QTY DRIFT: {SYMBOL} {pos['side']} "
                                    f"DB {db_qty:.6f} vs EXCH {exchange_qty:.6f} ({drift_pct:.2f}%)"
                                )

            # Check ALL exchange positions (both sides) for untracked
            try:
                tracked_side = pos["side"] if pos else ""
                for ep in executor.get_all_positions(SYMBOL):
                    ep_side = ep.get("positionSide", "")
                    amt = float(ep.get("positionAmt", 0))
                    if ep_side != tracked_side:
                        log.warning("untracked_position", symbol=SYMBOL, side=ep_side, amt=amt)
                        if _should_alert(f"untracked_{ep_side}"):
                            notify.send(f"UNTRACKED: {SYMBOL} {ep_side} {amt} on exchange")
            except Exception as e:
                log.warning("untracked_check_failed", error=str(e))
        except Exception as e:
            log.error("monitor_error", error=str(e))

        shutdown.wait(30)
